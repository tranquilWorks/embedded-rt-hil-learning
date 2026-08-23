from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_FOLDER = ROOT / "modules/14-prevent-ring-buffer-overrun"
QUESTION = (
    "What inputs, observable effects, and failure modes matter when you prevent "
    "Ring-Buffer Overrun?"
)
CORE_ARTIFACTS = {
    "README.md",
    "checks.md",
    "experiment.m",
    "interactive.m",
    "lesson.m",
    "lesson.md",
    "model.m",
    "p14_scenario.m",
    "run_checks.m",
    "walkthrough.md",
}
BASELINE_SOURCE = [(37 * index + 11) % 4096 for index in range(32)]


def read(name: str) -> str:
    return (MODULE_FOLDER / name).read_text(encoding="utf-8")


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


def matlab_code_without_comments(text: str) -> str:
    """Remove MATLAB comments without treating percent signs in strings as comments."""
    code_lines: list[str] = []
    for line in text.splitlines():
        fragments = re.split(r"('(?:''|[^'])*')", line)
        retained: list[str] = []
        for index, fragment in enumerate(fragments):
            if index % 2 == 1:
                retained.append(fragment)
                continue
            before_comment, separator, _comment = fragment.partition("%")
            retained.append(before_comment)
            if separator:
                break
        code_lines.append("".join(retained))
    return "\n".join(code_lines)


def finite_required_capacity(
    count: int,
    producer_period: float,
    consumer_period: float,
    quota: int,
    consumer_start: float,
) -> int:
    producer_index = 0
    producer_time = 0.0
    consumer_time = consumer_start
    occupancy = 0
    required = 0
    while producer_index < count:
        if occupancy == 0 and consumer_time < producer_time:
            skipped = math.ceil((producer_time - consumer_time) / consumer_period)
            consumer_time += skipped * consumer_period
        elif consumer_time <= producer_time:
            occupancy = max(0, occupancy - quota)
            consumer_time += consumer_period
        else:
            occupancy += 1
            required = max(required, occupancy)
            producer_index += 1
            producer_time = producer_index * producer_period
    return required


def _simulate_ring(
    source: list[float] | None = None,
    *,
    producer_period: float = 50,
    consumer_period: float = 200,
    quota: int = 4,
    consumer_start: float = 200,
    capacity: int = 8,
    policy: str = "drop-newest",
    drain_timeout: float = math.inf,
    timeout_action: str = "continue-waiting",
) -> dict[str, object]:
    values = list(BASELINE_SOURCE if source is None else source)
    ring: list[tuple[int, float, float]] = []
    source_index = 0
    record_ready = 0.0
    next_producer = 0.0
    next_consumer = consumer_start
    producer_blocked = False
    cumulative_producer_stall = 0.0
    consumer_tick = 0
    consumed_ids: list[int] = []
    consumed_values: list[float] = []
    ages: list[float] = []
    dropped: list[int] = []
    overwritten: list[int] = []
    full_ids: set[int] = set()
    stalls: list[float] = []
    occupancy_after_write: list[int | None] = [None] * len(values)
    peak = 0
    last_decision: float | None = None
    last_consumed: float | None = None
    timed_out = False
    cancelled = False
    pending_at_timeout = 0
    deadline: float | None = None

    while True:
        producer_done = source_index >= len(values)
        if producer_done and not ring:
            break
        if producer_done and deadline is None and math.isfinite(drain_timeout):
            assert last_decision is not None
            deadline = last_decision + drain_timeout
        producer_event = (
            next_producer
            if not producer_done and not producer_blocked
            else math.inf
        )
        if not ring and not producer_blocked and next_consumer < producer_event:
            skipped = math.ceil((producer_event - next_consumer) / consumer_period)
            consumer_tick += skipped
            next_consumer = consumer_start + consumer_tick * consumer_period
            continue
        if deadline is not None and deadline < next_consumer:
            pending_at_timeout = len(ring)
            timed_out = bool(ring)
            if timed_out and timeout_action == "cancel-consumer":
                cancelled = True
                break
            deadline = math.inf
            continue
        if next_consumer <= producer_event:
            drain_count = min(quota, len(ring))
            for source_id, value, written_at in ring[:drain_count]:
                consumed_ids.append(source_id)
                consumed_values.append(value)
                ages.append(next_consumer - written_at)
            if drain_count:
                last_consumed = next_consumer
            del ring[:drain_count]
            current_time = next_consumer
            consumer_tick += 1
            next_consumer = consumer_start + consumer_tick * consumer_period
            if producer_blocked and len(ring) < capacity:
                next_producer = current_time
                producer_blocked = False
            continue

        current_time = next_producer
        source_id = source_index + 1
        if len(ring) < capacity:
            producer_stall = current_time - record_ready
            stalls.append(producer_stall)
            cumulative_producer_stall += producer_stall
            ring.append((source_id, values[source_index], current_time))
            occupancy_after_write[source_index] = len(ring)
            source_index += 1
            last_decision = current_time
            if source_index < len(values):
                record_ready = (
                    source_index * producer_period + cumulative_producer_stall
                )
                next_producer = record_ready
        else:
            full_ids.add(source_id)
            if policy == "drop-newest":
                dropped.append(source_id)
                occupancy_after_write[source_index] = len(ring)
                source_index += 1
                last_decision = current_time
                if source_index < len(values):
                    record_ready = (
                        source_index * producer_period + cumulative_producer_stall
                    )
                    next_producer = record_ready
            elif policy == "overwrite-oldest":
                old_id, _old_value, _old_time = ring.pop(0)
                overwritten.append(old_id)
                stalls.append(current_time - record_ready)
                ring.append((source_id, values[source_index], current_time))
                occupancy_after_write[source_index] = len(ring)
                source_index += 1
                last_decision = current_time
                if source_index < len(values):
                    record_ready = (
                        source_index * producer_period + cumulative_producer_stall
                    )
                    next_producer = record_ready
            elif policy == "backpressure":
                producer_blocked = True
                next_producer = math.inf
            else:
                raise AssertionError(f"unsupported policy in oracle: {policy}")
        peak = max(peak, len(ring))

    pending_ids = [entry[0] for entry in ring]
    complete = source_index == len(values) and not pending_ids
    completion = (
        max(last_decision or 0, last_consumed or 0) if complete else None
    )
    classifications = set(consumed_ids) | set(pending_ids) | set(dropped) | set(overwritten)
    return {
        "source": values,
        "consumed_ids": consumed_ids,
        "consumed_values": consumed_values,
        "ages": ages,
        "dropped": dropped,
        "overwritten": overwritten,
        "pending": pending_ids,
        "peak": peak,
        "required_capacity": finite_required_capacity(
            len(values), producer_period, consumer_period, quota, consumer_start
        ),
        "offered_load": consumer_period / (quota * producer_period),
        "occupancy_after_write": occupancy_after_write,
        "full_count": len(full_ids),
        "stall_count": sum(delay > 0 for delay in stalls),
        "stall_total": sum(stalls),
        "last_decision": last_decision,
        "completion": completion,
        "timed_out": timed_out,
        "cancelled": cancelled,
        "pending_at_timeout": pending_at_timeout,
        "conservation_error": len(values) - len(classifications),
    }


def ring_reference(**kwargs: object) -> dict[str, object]:
    action = str(kwargs.get("timeout_action", "continue-waiting"))
    reference_kwargs = dict(kwargs)
    reference_kwargs["timeout_action"] = "continue-waiting"
    reference = _simulate_ring(**reference_kwargs)
    if action == "cancel-consumer" and reference["timed_out"]:
        observed = _simulate_ring(**kwargs)
    else:
        observed = reference
    observed = dict(observed)
    observed["reference_completion"] = reference["completion"]
    return observed


class P14IdentityAndArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        manifest = json.loads(
            (ROOT / "curriculum/modules.json").read_text(encoding="utf-8")
        )
        cls.modules = manifest["modules"]
        cls.module = next(module for module in cls.modules if module["id"] == "P14")

    def test_permanent_manifest_identity_prerequisite_status_and_evidence(self) -> None:
        self.assertEqual(self.module["number"], 14)
        self.assertEqual(self.module["title"], "Prevent Ring-Buffer Overrun")
        self.assertEqual(self.module["guiding_question"], QUESTION)
        self.assertEqual(self.module["phase"], 4)
        self.assertEqual(self.module["phase_title"], "Data movement and timing")
        self.assertEqual(self.module["slug"], "prevent-ring-buffer-overrun")
        self.assertEqual(
            self.module["folder"], "modules/14-prevent-ring-buffer-overrun"
        )
        self.assertEqual(self.module["implementation_batch"], "P14")
        self.assertEqual(self.module["prerequisites"], ["P13"])
        self.assertEqual(self.module["status"], "implemented")
        self.assertEqual(self.module["evidence_level"], "simulated")
        p13 = next(module for module in self.modules if module["id"] == "P13")
        p15 = next(module for module in self.modules if module["id"] == "P15")
        self.assertEqual(p13["status"], "implemented")
        self.assertEqual(p15["prerequisites"], ["P14"])

    def test_complete_artifact_set_has_clean_terminal_newlines_and_bounds(self) -> None:
        names = {path.name for path in MODULE_FOLDER.iterdir() if path.is_file()}
        self.assertTrue(CORE_ARTIFACTS <= names)
        for path in MODULE_FOLDER.iterdir():
            if path.is_file():
                payload = path.read_bytes()
                with self.subTest(path=path.name):
                    self.assertTrue(payload.endswith(b"\n"))
                    self.assertFalse(payload.endswith(b"\n\n"))
                    self.assertLess(len(payload), 130_000)

    def test_guiding_question_p13_connection_p15_boundary_and_claims_are_explicit(self) -> None:
        combined = "\n".join(read(name) for name in CORE_ARTIFACTS).lower()
        self.assertIn(QUESTION.lower(), combined)
        for concept in (
            "p13",
            "p15",
            "finite",
            "occupancy",
            "consumer",
            "drop-newest",
            "overwrite-oldest",
            "backpressure",
            "matlab-runtime",
            "bench",
            "hil",
            "field",
            "production",
        ):
            self.assertIn(concept, combined)

    def test_no_scaffold_placeholder_or_opaque_residue(self) -> None:
        combined = "\n".join(read(name) for name in CORE_ARTIFACTS).lower()
        for residue in (
            "scaffolded",
            "activate its governed",
            "not implemented yet",
            "todo",
            "tbd",
            "placeholder",
            "black-box queue",
        ):
            self.assertNotIn(residue, combined)


class P14ModelContractTests(unittest.TestCase):
    def test_model_is_transparent_counted_deterministic_and_resource_bounded(self) -> None:
        source = read("model.m")
        code = matlab_code_without_comments(source)
        normalized = compact(code)
        self.assertIn("functionout=model(", normalized)
        for token in (
            "occupancy==0",
            "occupancy<capacitysamples",
            "occupancy==capacitysamples",
            "advanceslot(readslot,capacitysamples)",
            "advanceslot(writeslot,capacitysamples)",
            "source_conservation_error_samples",
            "finiteTraceRequiredCapacity".lower(),
            "drop-newest",
            "overwrite-oldest",
            "backpressure",
            "consumer,producer,thentimeout",
        ):
            with self.subTest(token=token):
                self.assertIn(token, normalized)
        self.assertRegex(
            normalized,
            r"offeredloadratio=consumerperiodus\./\.\.\.\(consumerquotasamples\.\*producerperiodus\)",
        )
        self.assertRegex(source, r"maxSamples\s*=\s*10000")
        self.assertRegex(source, r"maxCapacitySamples\s*=\s*100000")
        self.assertRegex(source, r"maxTimelineUs\s*=\s*1e12")
        self.assertLess(source.index("simulateCampaign("), source.index("ringSamples = nan"))
        self.assertIn("values(:) > uint64(flintmax)", source)
        self.assertIn("values(:) > int64(flintmax)", source)
        self.assertIn("values(:) < -int64(flintmax)", source)
        self.assertLess(source.index("uint64(flintmax)"), source.index("values = double"))
        self.assertIn("function nextUs = addBoundedTime", source)
        self.assertGreaterEqual(source.count("anchoredProducerTime("), 4)
        self.assertGreaterEqual(
            source.count("addBoundedTime(lastProducerDecisionUs"), 2
        )
        self.assertIn("Derived rate or load diagnostics", source)
        self.assertIn("offeredLoadPct", source)

    def test_model_has_no_presentation_hardware_state_or_opaque_calls(self) -> None:
        code = matlab_code_without_comments(read("model.m")).lower()
        for forbidden in (
            "figure",
            "plot",
            "uifigure",
            "uiaxes",
            "uispinner",
            "uidropdown",
            "persistent",
            "global",
            "rng",
            "rand",
            "randn",
            "pause",
            "timer",
            "eval",
            "system",
            "parfor",
            "table",
            "timetable",
            "timeseries",
            "daq",
            "arduino",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotRegex(code, rf"\b{forbidden}\s*\(")
        self.assertNotIn("simulink", code)
        self.assertNotIn("data acquisition toolbox", code)

    def test_model_rejects_malformed_policy_timing_precision_and_resources(self) -> None:
        source = read("model.m")
        for identifier in (
            "P14:model:Arity",
            "P14:model:SourceSamples",
            "P14:model:SourcePrecision",
            "P14:model:SampleResourceBound",
            "P14:model:Policy",
            "P14:model:DrainTimeout",
            "P14:model:TimeoutAction",
            "P14:model:TimelineResourceBound",
            "P14:model:TimingPrecision",
            "P14:model:EventResourceBound",
            "P14:model:RingInvariant",
            "P14:model:FifoInvariant",
        ):
            self.assertIn(identifier, source)
        for dynamic_label in (
            "'ProducerPeriod'",
            "'ConsumerPeriod'",
            "'ConsumerQuota'",
            "'ConsumerStart'",
            "'Capacity'",
            "['P14:model:' label]",
            "['P14:model:' label 'ResourceBound']",
        ):
            self.assertIn(dynamic_label, source)
        self.assertLess(source.index("validateSourceSamples"), source.index("simulateCampaign"))
        self.assertLess(source.index("conservativeEndUs"), source.index("simulateCampaign"))
        self.assertIn("addBoundedTime(lastProducerDecisionUs", source)

    def test_scenario_is_seedless_bounded_and_model_compatible(self) -> None:
        scenario = read("p14_scenario.m")
        for name in (
            "baseline",
            "undersized-buffer",
            "slow-consumer",
            "overwrite-oldest",
            "backpressure",
            "timeout-continue",
            "timeout-cancel",
        ):
            self.assertIn(name, scenario)
        for field in (
            "source_samples",
            "producer_period_us",
            "consumer_period_us",
            "consumer_quota_samples",
            "consumer_start_us",
            "capacity_samples",
            "overrun_policy",
            "drain_timeout_us",
            "timeout_action",
        ):
            self.assertIn(field, scenario)
        self.assertRegex(scenario, r"mod\s*\(\s*37\s*\.\*")
        self.assertIn("4096", scenario)
        self.assertIn("if ~strcmp(name, 'baseline')", scenario)
        self.assertIn("value >= 1 && value <= 1e9", scenario)
        scenario_code = matlab_code_without_comments(scenario).lower()
        self.assertNotRegex(scenario_code, r"\b(?:rng|rand|randn|while|timer|pause)\b")

    def test_independent_baseline_event_order_fifo_and_conservation(self) -> None:
        result = ring_reference()
        self.assertEqual(result["source"], BASELINE_SOURCE)
        self.assertEqual(result["occupancy_after_write"], [1, 2, 3, 4] * 8)
        self.assertEqual(result["peak"], 4)
        self.assertEqual(result["required_capacity"], 4)
        self.assertEqual(result["offered_load"], 1)
        self.assertEqual(result["consumed_ids"], list(range(1, 33)))
        self.assertEqual(result["consumed_values"], BASELINE_SOURCE)
        self.assertEqual(result["ages"], [200, 150, 100, 50] * 8)
        self.assertEqual(result["completion"], 1600)
        self.assertEqual(result["dropped"], [])
        self.assertEqual(result["overwritten"], [])
        self.assertEqual(result["pending"], [])
        self.assertEqual(result["conservation_error"], 0)

    def test_independent_capacity_sweep_isolates_finite_headroom(self) -> None:
        results = [ring_reference(capacity=value) for value in [1, 2, 3, 4, 6, 8]]
        self.assertEqual([len(result["dropped"]) for result in results], [24, 16, 8, 0, 0, 0])
        self.assertEqual([result["peak"] for result in results], [1, 2, 3, 4, 4, 4])
        self.assertEqual([len(result["consumed_ids"]) for result in results], [8, 16, 24, 32, 32, 32])
        self.assertTrue(all(result["offered_load"] == 1 for result in results))
        self.assertTrue(all(result["conservation_error"] == 0 for result in results))

    def test_independent_consumer_quota_sweep_exposes_load_and_required_capacity(self) -> None:
        results = [ring_reference(quota=value) for value in [1, 2, 3, 4, 5, 8]]
        self.assertEqual([len(result["dropped"]) for result in results], [17, 10, 3, 0, 0, 0])
        self.assertEqual([result["peak"] for result in results], [8, 8, 8, 4, 4, 4])
        self.assertEqual([result["required_capacity"] for result in results], [25, 18, 11, 4, 4, 4])
        self.assertEqual([result["completion"] for result in results], [3000, 2200, 2000, 1600, 1600, 1600])
        for actual, expected in zip(
            [result["offered_load"] for result in results],
            [4, 2, 4 / 3, 1, 0.8, 0.5],
        ):
            self.assertAlmostEqual(actual, expected)

    def test_independent_broken_policy_backpressure_and_recovery(self) -> None:
        broken = ring_reference(capacity=4, quota=1, policy="overwrite-oldest")
        self.assertEqual(broken["consumed_ids"], [1, 5, 9, 13, 17, 21, 25, 29, 30, 31, 32])
        self.assertEqual(
            broken["overwritten"],
            [2, 3, 4, 6, 7, 8, 10, 11, 12, 14, 15, 16, 18, 19, 20, 22, 23, 24, 26, 27, 28],
        )
        self.assertEqual(broken["peak"], 4)
        self.assertEqual(broken["full_count"], 21)
        self.assertEqual(broken["completion"], 2200)
        self.assertEqual(broken["conservation_error"], 0)

        dropped = ring_reference(capacity=4, quota=1, policy="drop-newest")
        self.assertEqual(dropped["consumed_ids"], [1, 2, 3, 4, 5, 9, 13, 17, 21, 25, 29])
        self.assertEqual(len(dropped["dropped"]), 21)
        backpressure = ring_reference(capacity=4, quota=1, policy="backpressure")
        self.assertEqual(backpressure["consumed_ids"], list(range(1, 33)))
        self.assertEqual(backpressure["stall_count"], 27)
        self.assertEqual(backpressure["stall_total"], 4050)
        self.assertEqual(backpressure["last_decision"], 5600)
        self.assertEqual(backpressure["completion"], 6400)
        self.assertEqual(backpressure["conservation_error"], 0)
        self.assertEqual(ring_reference(), ring_reference())

    def test_independent_timeout_cancellation_limits_and_duplicate_identity(self) -> None:
        equality = ring_reference(drain_timeout=50, timeout_action="cancel-consumer")
        self.assertFalse(equality["timed_out"])
        self.assertFalse(equality["cancelled"])
        self.assertEqual(equality["completion"], 1600)
        continued = ring_reference(drain_timeout=49)
        self.assertTrue(continued["timed_out"])
        self.assertFalse(continued["cancelled"])
        self.assertEqual(continued["consumed_ids"], list(range(1, 33)))
        cancelled = ring_reference(drain_timeout=49, timeout_action="cancel-consumer")
        self.assertTrue(cancelled["timed_out"])
        self.assertTrue(cancelled["cancelled"])
        self.assertEqual(cancelled["consumed_ids"], list(range(1, 29)))
        self.assertEqual(cancelled["pending"], [29, 30, 31, 32])
        self.assertEqual(cancelled["reference_completion"], 1600)
        self.assertEqual(cancelled["conservation_error"], 0)

        capacity_one = ring_reference(
            source=[1, 2, 3, 4],
            producer_period=50,
            consumer_period=50,
            quota=1,
            consumer_start=50,
            capacity=1,
        )
        self.assertEqual(capacity_one["consumed_ids"], [1, 2, 3, 4])
        self.assertEqual(capacity_one["dropped"], [])
        duplicate = ring_reference(
            source=[7, 7, 7, 7],
            producer_period=50,
            consumer_period=50,
            quota=1,
            consumer_start=50,
            capacity=1,
        )
        self.assertEqual(duplicate["consumed_ids"], [1, 2, 3, 4])
        self.assertEqual(duplicate["consumed_values"], [7, 7, 7, 7])

    def test_fractional_equal_rate_ties_do_not_create_spurious_overrun(self) -> None:
        result = ring_reference(
            source=list(range(1, 8)),
            producer_period=0.1,
            consumer_period=0.1,
            quota=1,
            consumer_start=0.2,
            capacity=2,
        )
        self.assertEqual(result["occupancy_after_write"], [1, 2, 2, 2, 2, 2, 2])
        self.assertEqual(result["peak"], 2)
        self.assertEqual(result["required_capacity"], 2)
        self.assertEqual(result["consumed_ids"], list(range(1, 8)))
        self.assertEqual(result["dropped"], [])
        self.assertEqual(result["full_count"], 0)
        self.assertAlmostEqual(result["completion"], 0.8)

        model = compact(read("model.m"))
        self.assertIn("functionreadyus=anchoredproducertime(", model)
        self.assertIn(
            "nominalreadyus=(sourceid-1).*producerperiodus;",
            model,
        )
        self.assertNotIn(
            "addboundedtime(currentus,producerperiodus,'producerperiod'",
            model,
        )
        checks = compact(read("run_checks.m"))
        self.assertIn("fractionaltie=modelfcn(", checks)


class P14LearningAndRegressionTests(unittest.TestCase):
    def test_experiment_has_baseline_two_isolated_sweeps_and_broken_case(self) -> None:
        experiment = read("experiment.m").lower()
        normalized = compact(experiment)
        self.assertIn("%% baseline", experiment)
        self.assertIn("isequaln(baseline,baselinerepeat)", normalized)
        self.assertGreaterEqual(experiment.count("%% sweep"), 2)
        self.assertRegex(experiment, r"capacity\w*sweep\w*\s*=\s*\[1 2 3 4 6 8\]")
        self.assertRegex(experiment, r"quota\w*sweep\w*\s*=\s*\[1 2 3 4 5 8\]")
        for vector in (
            "[24 16 8 0 0 0]",
            "[1 2 3 4 4 4]",
            "[17 10 3 0 0 0]",
            "[25 18 11 4 4 4]",
            "[3000 2200 2000 1600 1600 1600]",
        ):
            self.assertIn(vector.replace(" ", ""), normalized)
        self.assertIn("%% broken case", experiment)
        self.assertIn("expectedoverwritten", normalized)
        self.assertIn("mechanism for sweep 1", experiment)
        self.assertIn("mechanism for sweep 2", experiment)
        self.assertIn("must isolate", experiment)
        self.assertIn("isequaln(recovered,baseline)", normalized)
        self.assertIn("rollback", experiment)
        self.assertGreaterEqual(experiment.count("figure("), 6)
        self.assertIn("xlabel(", experiment)
        self.assertIn("ylabel(", experiment)
        self.assertIn("(us)", experiment)
        self.assertIn("(sample)", experiment)

    def test_interactive_exposes_controls_scenarios_two_views_and_bound_callbacks(self) -> None:
        interactive = read("interactive.m").lower()
        normalized = compact(interactive)
        self.assertIn("modelfcn=@model;", normalized)
        self.assertIn("scenariofcn=@p14_scenario;", normalized)
        self.assertIn("uifigure(", interactive)
        self.assertGreaterEqual(interactive.count("uispinner("), 1)
        self.assertGreaterEqual(interactive.count("numericspinner("), 6)
        self.assertGreaterEqual(interactive.count("uidropdown("), 3)
        self.assertGreaterEqual(interactive.count("uiaxes("), 2)
        self.assertIn("valuechangedfcn", interactive)
        for label in (
            "capacity",
            "producer period",
            "consumer period",
            "quota",
            "drop newest",
            "overwrite oldest",
            "backpressure",
            "timeout",
            "scenario",
            "not matlab-runtime",
            "hardware",
        ):
            self.assertIn(label, interactive)
        callback_region = normalized[normalized.index("functionupdateviews"):]
        self.assertIn("scenariofcn(", callback_region)
        self.assertIn("modelfcn(", callback_region)
        self.assertNotRegex(callback_region, r"(?<!model)\bmodel\(")

    def test_fixed_diagnostics_reset_controls_before_rendering(self) -> None:
        interactive = compact(read("interactive.m"))
        selector = interactive[
            interactive.index("functionscenariochanged") : interactive.index("functionupdateviews")
        ]
        self.assertIn("fixedinput=scenariofcn(", selector)
        self.assertGreaterEqual(selector.count(".value="), 7)
        self.assertIn("controls{controlindex}.enable=onoff(~fixedscenario);", selector)
        self.assertIn("elsefixedinput=scenariofcn('baseline');", selector)
        self.assertLess(selector.rindex(".value="), selector.index("updateviews();"))

    def test_executable_checks_cover_complete_failure_and_recovery_contract(self) -> None:
        checks = read("run_checks.m")
        lower = checks.lower()
        self.assertGreaterEqual(len(re.findall(r"\bassert\s*\(", checks)), 30)
        for marker in (
            "deterministic",
            "occupancy recurrence",
            "source identities",
            "capacity sweep",
            "consumer-quota sweep",
            "overwrite-oldest",
            "drop-newest",
            "backpressure",
            "consumer-before-producer",
            "drain deadline",
            "pending records",
            "rollback",
            "recovery",
            "callback-bound",
            "path cleanup",
            "duplicate values",
            "flintmax",
            "realmin",
            "resource boundary",
            "malformed",
            "not matlab-runtime",
            "p14 checks passed",
        ):
            self.assertIn(marker, lower)
        for identifier in (
            "p14:model:arity",
            "p14:model:sourcesamples",
            "p14:model:sourceprecision",
            "p14:model:producerperiod",
            "p14:model:consumerperiod",
            "p14:model:consumerquota",
            "p14:model:consumerstart",
            "p14:model:capacity",
            "p14:model:policy",
            "p14:model:draintimeout",
            "p14:model:timeoutaction",
            "p14:model:sampleresourcebound",
            "p14:model:capacityresourcebound",
            "p14:model:timelineresourcebound",
            "p14:model:timingprecision",
        ):
            self.assertIn(identifier, lower)

    def test_tutor_text_is_mechanism_first_one_prediction_and_teach_back(self) -> None:
        lesson = read("lesson.md").lower()
        walkthrough = read("walkthrough.md").lower()
        checks = read("checks.md").lower()
        self.assertEqual(lesson.count("## prediction before the baseline"), 1)
        for equation in (
            "q_after_consumer",
            "q_after_event",
            "rho = (1/t_p) / (b/t_c)",
            "1 + mod",
        ):
            self.assertIn(equation, lesson)
        self.assertLess(lesson.index("## read:"), lesson.index("## prediction"))
        self.assertLess(lesson.index("## prediction"), lesson.index("## baseline"))
        self.assertLess(lesson.index("## baseline"), lesson.index("## lever 1"))
        self.assertIn("reset", lesson)
        self.assertIn("p13", lesson)
        self.assertIn("p15", lesson)
        self.assertIn("reset", walkthrough)
        self.assertIn("interpretation questions", checks)
        self.assertIn("teach-back", checks)

    def test_claim_language_separates_simulated_runtime_concurrency_and_physical_evidence(self) -> None:
        combined = "\n".join(
            read(name)
            for name in (
                "README.md",
                "experiment.m",
                "interactive.m",
                "lesson.md",
                "walkthrough.md",
                "checks.md",
            )
        ).lower()
        for marker in (
            "deterministic simulated",
            "not matlab-runtime",
            "rendered-ui",
            "atomic",
            "cache",
            "dma",
            "bench",
            "hil",
            "field",
            "production",
            "rt1/rt2",
            "unreal",
            "signing",
            "deployment",
        ):
            self.assertIn(marker, combined)
        self.assertNotIn("hardware-validated", combined)
        self.assertNotIn("matlab-validated", combined)

    def test_cli_start_routes_p14_and_persists_only_isolated_progress(self) -> None:
        root_state_path = ROOT / ".learning/progress.json"
        original_root_state = (
            root_state_path.read_bytes() if root_state_path.exists() else None
        )
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary) / "repo"
            shutil.copytree(ROOT / "bin", fixture / "bin")
            shutil.copytree(ROOT / "curriculum", fixture / "curriculum")
            target = fixture / "modules/14-prevent-ring-buffer-overrun"
            target.mkdir(parents=True)
            for name in ("README.md", "lesson.md", "walkthrough.md", "checks.md"):
                shutil.copy2(MODULE_FOLDER / name, target / name)
            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            result = subprocess.run(
                [str(fixture / "bin/learn"), "start", "P14"],
                cwd=fixture,
                text=True,
                capture_output=True,
                timeout=10,
                env=environment,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(QUESTION, result.stdout)
            state = json.loads(
                (fixture / ".learning/progress.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["current"], "P14")
        final_root_state = root_state_path.read_bytes() if root_state_path.exists() else None
        self.assertEqual(final_root_state, original_root_state)

    def test_cli_check_resolves_p14_public_matlab_entry_point(self) -> None:
        result = subprocess.run(
            [str(ROOT / "bin/learn"), "check", "P14"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=10,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "Run in MATLAB: run_module_checks('P14')\n")

    @unittest.skipUnless(shutil.which("matlab"), "MATLAB executable unavailable")
    def test_matlab_executes_module_checks_and_callback_lifetime(self) -> None:
        command = (
            "addpath('" + str(MODULE_FOLDER).replace("'", "''") + "'); "
            "run_checks;"
        )
        result = subprocess.run(
            ["matlab", "-batch", command],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("P14 checks passed", result.stdout)


class P14RetainedEvidenceTests(unittest.TestCase):
    def test_date_agnostic_retained_evidence_is_complete_and_honest(self) -> None:
        evidence_files = sorted((ROOT / "docs/evidence").glob("P14-*.md"))
        self.assertTrue(evidence_files, "P14 requires a retained evidence record")
        for path in evidence_files:
            payload = path.read_bytes()
            self.assertTrue(payload.endswith(b"\n"))
            self.assertFalse(payload.endswith(b"\n\n"))
            text = payload.decode("utf-8").lower()
            for heading in (
                "acceptance mapping",
                "exact commands and results",
                "changed invariants",
                "preserved invariants",
                "residual risks",
                "rollback",
                "unperformed validation",
                "figure, control, metric, and unit inventory",
                "runtime inventory",
            ):
                self.assertIn(heading, text)
            self.assertGreaterEqual(text.count("| pass"), 8)
            self.assertGreaterEqual(text.count("exit `0`"), 8)
            for marker in (
                "intended-final-state",
                "post-transition",
                "verify pass: 24 modules",
                "matlab runtime",
                "ui",
                "bench",
                "hil",
                "field",
                "production",
                "portfolio control validation",
                "target quality workflow",
            ):
                self.assertIn(marker, text)
            for exact_command_marker in (
                "tests.test_p14_module.p14modelcontracttests",
                "def flatten(suite):",
                "sha256sum contracts/active-batch.yaml",
                "./scripts/agent-verify.sh",
            ):
                self.assertIn(exact_command_marker, text)
            self.assertNotIn("| unverified", text)

    def test_structured_evidence_matches_retained_acceptance(self) -> None:
        path = MODULE_FOLDER / "evidence.json"
        payload = path.read_bytes()
        self.assertTrue(payload.endswith(b"\n"))
        self.assertFalse(payload.endswith(b"\n\n"))
        evidence = json.loads(payload.decode("utf-8"))
        required = {
            "schema_version",
            "batch_id",
            "status",
            "commands",
            "acceptance",
            "residual_risks",
            "unperformed_validation",
        }
        self.assertEqual(set(evidence), required | {"changed_invariants"})
        self.assertEqual(evidence["schema_version"], 1)
        self.assertEqual(evidence["batch_id"], "P14")
        self.assertEqual(evidence["status"], "pass")
        self.assertGreaterEqual(len(evidence["commands"]), 8)
        commands = "\n".join(item["command"] for item in evidence["commands"])
        for placeholder in (
            "[19 P14 source selectors]",
            "[21 P14 intended-state selectors]",
            "repository-wide source suite",
            "protected SHA-256 and runtime discovery",
        ):
            self.assertNotIn(placeholder, commands)
        self.assertEqual(len(evidence["acceptance"]), 8)
        self.assertTrue(all(item.get("status") == "pass" for item in evidence["acceptance"]))
        self.assertTrue(evidence["changed_invariants"])
        self.assertTrue(evidence["residual_risks"])
        self.assertTrue(evidence["unperformed_validation"])


if __name__ == "__main__":
    unittest.main()
