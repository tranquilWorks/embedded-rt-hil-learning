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
MODULE_FOLDER = ROOT / "modules/16-execute-a-multi-rate-processing-graph"
QUESTION = (
    "What inputs, observable effects, and failure modes matter when you execute "
    "a Multi-Rate Processing Graph?"
)
CORE_ARTIFACTS = {
    "README.md",
    "checks.md",
    "evidence.json",
    "experiment.m",
    "interactive.m",
    "lesson.m",
    "lesson.md",
    "model.m",
    "p16_scenario.m",
    "run_checks.m",
    "walkthrough.md",
}
INSTRUCTIONAL_ARTIFACTS = CORE_ARTIFACTS - {"evidence.json"}


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


def graph_reference(
    *,
    samples: list[float] | None = None,
    times_us: list[int] | None = None,
    decimation: int = 4,
    fast_cost_us: int = 100,
    slow_cost_us: int = 1200,
    timeout_us: float = 2000,
    timeout_action: str = "continue-processing",
    execution_order: str = "producer-first",
) -> dict[str, object]:
    """Independent small oracle for P16's documented discrete-event rules."""
    values = list(range(32)) if samples is None else list(samples)
    times = [1000 * index for index in range(32)] if times_us is None else list(times_us)
    period = times[1] - times[0]

    filtered = [values[0]]
    for previous, current in zip(values, values[1:]):
        filtered.append((previous + current) / 2)

    fast_start: list[int] = []
    fast_finish: list[int] = []
    fast_available = times[0]
    for release in times:
        start = max(release, fast_available)
        finish = start + fast_cost_us
        fast_start.append(start)
        fast_finish.append(finish)
        fast_available = finish

    frames: list[dict[str, object]] = []
    previous_stops: list[int] = []
    slow_available = times[0]
    for frame_index in range(len(values) // decimation):
        first = frame_index * decimation
        last = (frame_index + 1) * decimation - 1
        release = times[last]
        expected_timestamp = sum(times[first : last + 1]) / decimation
        if execution_order == "producer-first":
            consumed_first = first
            consumed_last = last
            consumed_timestamp = expected_timestamp
            computed = sum(filtered[first : last + 1]) / decimation
            ready = max(release, fast_finish[last])
            data_valid = True
            visible_fast_count = last + 1
        elif execution_order == "consumer-first":
            visible_fast_count = sum(finish < release for finish in fast_finish)
            consumed_first = visible_fast_count - decimation
            consumed_last = visible_fast_count - 1
            consumed_timestamp = (
                times[0] + ((consumed_first + consumed_last) / 2) * period
            )
            data_valid = visible_fast_count >= decimation
            computed = (
                sum(filtered[visible_fast_count - decimation : visible_fast_count])
                / decimation
                if data_valid
                else math.nan
            )
            ready = release if data_valid else math.nan
        else:
            raise AssertionError(f"unknown execution order: {execution_order}")

        deadline = release + timeout_us if math.isfinite(timeout_us) else math.inf
        if data_valid:
            outstanding_depth = 1 + sum(stop > ready for stop in previous_stops)
            start = max(ready, slow_available)
            scheduled_finish = start + slow_cost_us
            slack = deadline - scheduled_finish
            timed_out = scheduled_finish > deadline
            cancelled = timed_out and timeout_action == "cancel-frame"
            stop = max(start, deadline) if cancelled else scheduled_finish
            completion = math.nan if cancelled else scheduled_finish
            emitted = not cancelled
            output = computed if emitted else math.nan
            latency = completion - release if emitted else math.nan
            previous_stops.append(int(stop))
            slow_available = int(stop)
        else:
            # A firing without a complete D-value input window is rejected
            # before slow-worker admission and consumes no service time.
            outstanding_depth = 0
            start = math.nan
            scheduled_finish = math.nan
            slack = math.nan
            timed_out = False
            cancelled = False
            stop = math.nan
            completion = math.nan
            emitted = False
            output = math.nan
            latency = math.nan
        frames.append(
            {
                "expected_first": first,
                "expected_last": last,
                "consumed_first": consumed_first,
                "consumed_last": consumed_last,
                "release": release,
                "ready": ready,
                "expected_timestamp": expected_timestamp,
                "consumed_timestamp": consumed_timestamp,
                "timestamp_error": consumed_timestamp - expected_timestamp,
                "computed": computed,
                "data_valid": data_valid,
                "visible_fast_count": visible_fast_count,
                "visibility_lag": last + 1 - visible_fast_count,
                "outstanding_depth": outstanding_depth,
                "start": start,
                "scheduled_finish": scheduled_finish,
                "deadline": deadline,
                "slack": slack,
                "timed_out": timed_out,
                "cancelled": cancelled,
                "stop": stop,
                "completion": completion,
                "emitted": emitted,
                "output": output,
                "latency": latency,
            }
        )

    scheduled_latencies = [
        frame["scheduled_finish"] - frame["release"]
        for frame in frames
        if not math.isnan(frame["scheduled_finish"])
    ]
    finite_latencies = [
        frame["latency"] for frame in frames if not math.isnan(frame["latency"])
    ]
    finite_slacks = [
        frame["slack"] for frame in frames if not math.isnan(frame["slack"])
    ]
    return {
        "samples": values,
        "times": times,
        "period": period,
        "filtered": filtered,
        "fast_start": fast_start,
        "fast_finish": fast_finish,
        "frames": frames,
        "frame_count": len(frames),
        "emitted_count": sum(frame["emitted"] for frame in frames),
        "timeout_count": sum(frame["timed_out"] for frame in frames),
        "cancelled_count": sum(frame["cancelled"] for frame in frames),
        "underflow_count": sum(not frame["data_valid"] for frame in frames),
        "output_rate_hz": 1_000_000 / (decimation * period),
        "slow_utilization": slow_cost_us / (decimation * period),
        "max_outstanding": max(frame["outstanding_depth"] for frame in frames),
        "max_scheduled_latency": (
            max(scheduled_latencies) if scheduled_latencies else math.nan
        ),
        "max_output_latency": max(finite_latencies) if finite_latencies else math.nan,
        "minimum_slack": min(finite_slacks) if finite_slacks else math.nan,
    }


class P16IdentityAndArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        manifest = json.loads(
            (ROOT / "curriculum/modules.json").read_text(encoding="utf-8")
        )
        cls.modules = manifest["modules"]
        cls.module = next(module for module in cls.modules if module["id"] == "P16")

    def test_permanent_manifest_identity_prerequisite_status_and_evidence(self) -> None:
        self.assertEqual(self.module["number"], 16)
        self.assertEqual(self.module["title"], "Execute a Multi-Rate Processing Graph")
        self.assertEqual(self.module["guiding_question"], QUESTION)
        self.assertEqual(self.module["phase"], 4)
        self.assertEqual(self.module["phase_title"], "Data movement and timing")
        self.assertEqual(self.module["slug"], "execute-a-multi-rate-processing-graph")
        self.assertEqual(
            self.module["folder"], "modules/16-execute-a-multi-rate-processing-graph"
        )
        self.assertEqual(self.module["implementation_batch"], "P16")
        self.assertEqual(self.module["prerequisites"], ["P15"])
        self.assertEqual(self.module["status"], "implemented")
        self.assertEqual(self.module["evidence_level"], "simulated")
        p15 = next(module for module in self.modules if module["id"] == "P15")
        p17 = next(module for module in self.modules if module["id"] == "P17")
        self.assertEqual(p15["status"], "implemented")
        self.assertEqual(p17["prerequisites"], ["P16"])

    def test_complete_artifact_set_has_clean_terminal_newlines_and_bounds(self) -> None:
        names = {path.name for path in MODULE_FOLDER.iterdir() if path.is_file()}
        self.assertTrue(CORE_ARTIFACTS <= names)
        for path in MODULE_FOLDER.iterdir():
            if path.is_file():
                payload = path.read_bytes()
                with self.subTest(path=path.name):
                    self.assertTrue(payload.endswith(b"\n"))
                    self.assertFalse(payload.endswith(b"\n\n"))
                    self.assertLess(len(payload), 150_000)

    def test_guiding_question_p15_connection_p17_boundary_and_claims_are_explicit(self) -> None:
        combined = "\n".join(read(name) for name in INSTRUCTIONAL_ARTIFACTS).lower()
        self.assertIn(QUESTION.lower(), combined)
        for concept in (
            "p15",
            "p17",
            "decimation",
            "producer-first",
            "consumer-first",
            "timeout",
            "matlab-runtime",
            "bench",
            "hil",
            "field",
            "production",
        ):
            self.assertIn(concept, combined)

    def test_no_scaffold_placeholder_or_opaque_residue(self) -> None:
        combined = "\n".join(read(name) for name in INSTRUCTIONAL_ARTIFACTS).lower()
        for residue in (
            "scaffolded",
            "activate its governed",
            "not implemented yet",
            "todo",
            "tbd",
            "placeholder",
        ):
            self.assertNotIn(residue, combined)


class P16ModelContractTests(unittest.TestCase):
    def test_model_is_transparent_deterministic_indexed_and_resource_bounded(self) -> None:
        source = read("model.m")
        normalized = compact(matlab_code_without_comments(source))
        self.assertIn("functionout=model(", normalized)
        for token in (
            "sampleperiodus=sampletimeus(2)-sampletimeus(1)",
            "any(diff(sampletimeus)~=sampleperiodus)",
            "(samplevalue(sampleindex-1)+samplevalue(sampleindex))./2",
            "firstindex=(frameindex-1).*decimationfactor+1",
            "lastindex=frameindex.*decimationfactor",
            "fastfinishus<framereleaseus(frameindex)",
            "latestvisibleindex<decimationfactor",
            "slowstartus(frameindex)=max(framereadyus(frameindex),...slowavailableus)",
            "scheduledfinishus(frameindex)>deadlineus(frameindex)",
            "producer-first",
            "consumer-first",
            "continue-processing",
            "cancel-frame",
        ):
            with self.subTest(token=token):
                self.assertIn(token, normalized)
        self.assertRegex(source, r"maxSampleCount\s*=\s*4096")
        self.assertRegex(source, r"maxDecimationFactor\s*=\s*1024")
        self.assertRegex(source, r"maxInputTimestampUs\s*=\s*1e12")
        self.assertRegex(source, r"maxTimelineUs\s*=\s*2e12")
        self.assertIn("uint64(flintmax)", source)
        self.assertLess(source.index("validateSampleVector"), source.index("fastStartUs = zeros"))
        self.assertLess(source.index("slowPeriodUs ="), source.index("frameCount ="))

    def test_model_has_no_presentation_state_waiting_or_opaque_calls(self) -> None:
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
            "filter",
            "resample",
            "decimate",
            "rateTransition",
            "table",
            "timetable",
            "timeseries",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotRegex(code, rf"\b{forbidden.lower()}\s*\(")
        self.assertNotIn("simulink", code)

    def test_model_and_checks_cover_malformed_precision_and_resource_rejection(self) -> None:
        source = read("model.m")
        checks = read("run_checks.m")
        for identifier in (
            "P16:model:Arity",
            "P16:model:SampleValue",
            "P16:model:SampleCount",
            "P16:model:SampleResourceBound",
            "P16:model:SampleValueResourceBound",
            "P16:model:SampleTime",
            "P16:model:SampleTimeOrder",
            "P16:model:SampleTimeUniform",
            "P16:model:SampleTimePrecision",
            "P16:model:SampleLength",
            "P16:model:DecimationFactor",
            "P16:model:DecimationResourceBound",
            "P16:model:FramePartition",
            "P16:model:OutputTimeout",
            "P16:model:OutputTimeoutResourceBound",
            "P16:model:TimeoutAction",
            "P16:model:ExecutionOrder",
            "P16:model:TimelineResourceBound",
        ):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, source + checks)
                self.assertIn(identifier, checks)
        self.assertGreaterEqual(checks.count("assertReject("), 30)
        self.assertIn("zeros(1, 4096)", checks)
        self.assertIn("zeros(1, 4097)", checks)
        self.assertIn("zeros(1, 1000000)", checks)

    def test_scenario_is_seedless_bounded_and_model_compatible(self) -> None:
        scenario = read("p16_scenario.m")
        for name in (
            "baseline",
            "unity-rate",
            "zero-cost",
            "broken-consumer-first",
            "timeout-continue",
            "timeout-cancel",
        ):
            self.assertIn(name, scenario)
        for field in (
            "sample_value",
            "sample_time_us",
            "decimation_factor",
            "fast_cost_us",
            "slow_cost_us",
            "output_timeout_us",
            "timeout_action",
            "execution_order",
        ):
            self.assertIn(field, scenario)
        self.assertIn("if strcmp(name, 'baseline')", scenario)
        code = matlab_code_without_comments(scenario).lower()
        self.assertNotRegex(code, r"\b(?:rng|rand|randn|while|timer|pause)\b")

    def test_independent_baseline_values_timing_rates_and_bounds(self) -> None:
        result = graph_reference()
        self.assertEqual(result["filtered"], [0, 0.5] + [index + 0.5 for index in range(1, 31)])
        frames = result["frames"]
        self.assertEqual(
            [frame["output"] for frame in frames],
            [1.125, 5, 9, 13, 17, 21, 25, 29],
        )
        self.assertEqual([frame["release"] for frame in frames], list(range(3000, 31001, 4000)))
        self.assertEqual([frame["ready"] for frame in frames], list(range(3100, 31101, 4000)))
        self.assertEqual([frame["completion"] for frame in frames], list(range(4300, 32301, 4000)))
        self.assertEqual([frame["latency"] for frame in frames], [1300] * 8)
        self.assertEqual([frame["slack"] for frame in frames], [700] * 8)
        self.assertEqual(result["output_rate_hz"], 250)
        self.assertEqual(result["slow_utilization"], 0.3)
        self.assertEqual(result["max_outstanding"], 1)
        self.assertEqual(result["emitted_count"], 8)
        self.assertEqual(result["timeout_count"], 0)

    def test_independent_decimation_and_cost_sweeps_isolate_two_parameters(self) -> None:
        factors = [1, 2, 4, 8]
        by_factor = [graph_reference(decimation=value) for value in factors]
        self.assertEqual([result["frame_count"] for result in by_factor], [32, 16, 8, 4])
        self.assertEqual([result["output_rate_hz"] for result in by_factor], [1000, 500, 250, 125])
        self.assertEqual([result["slow_utilization"] for result in by_factor], [1.2, 0.6, 0.3, 0.15])
        self.assertEqual([result["timeout_count"] for result in by_factor], [28, 0, 0, 0])
        self.assertEqual([result["max_output_latency"] for result in by_factor], [7500, 1300, 1300, 1300])
        self.assertEqual([result["max_outstanding"] for result in by_factor], [7, 1, 1, 1])

        costs = [200, 800, 1200, 1800, 4200]
        by_cost = [graph_reference(slow_cost_us=value) for value in costs]
        self.assertEqual([result["slow_utilization"] for result in by_cost], [0.05, 0.2, 0.3, 0.45, 1.05])
        self.assertEqual([result["max_output_latency"] for result in by_cost], [300, 900, 1300, 1900, 5700])
        self.assertEqual([result["minimum_slack"] for result in by_cost], [1700, 1100, 700, 100, -3700])
        self.assertEqual([result["timeout_count"] for result in by_cost], [0, 0, 0, 0, 8])
        self.assertEqual([result["max_outstanding"] for result in by_cost], [1, 1, 1, 1, 2])

    def test_independent_broken_order_underflow_and_stale_timestamp(self) -> None:
        correct = graph_reference()
        broken = graph_reference(execution_order="consumer-first")
        self.assertEqual(broken["underflow_count"], 1)
        frames = broken["frames"]
        self.assertTrue(math.isnan(frames[0]["output"]))
        self.assertEqual([frame["output"] for frame in frames[1:]], [4, 8, 12, 16, 20, 24, 28])
        self.assertEqual([frame["timestamp_error"] for frame in frames], [-1000] * 8)
        self.assertEqual([frame["consumed_last"] for frame in frames], [2, 6, 10, 14, 18, 22, 26, 30])
        self.assertEqual([frame["expected_last"] for frame in correct["frames"]], [3, 7, 11, 15, 19, 23, 27, 31])

    def test_independent_consumer_first_tracks_fast_stage_overload(self) -> None:
        broken = graph_reference(
            execution_order="consumer-first", fast_cost_us=2000
        )
        frames = broken["frames"]
        self.assertEqual(
            [frame["visible_fast_count"] for frame in frames],
            [1, 3, 5, 7, 9, 11, 13, 15],
        )
        self.assertEqual(broken["underflow_count"], 2)
        self.assertTrue(math.isnan(frames[0]["output"]))
        self.assertTrue(math.isnan(frames[1]["output"]))
        self.assertEqual(
            [frame["output"] for frame in frames[2:]], [2, 4, 6, 8, 10, 12]
        )
        self.assertEqual(
            [frame["timestamp_error"] for frame in frames],
            [-3000, -5000, -7000, -9000, -11000, -13000, -15000, -17000],
        )

    def test_underflow_is_rejected_before_slow_worker_admission(self) -> None:
        source = compact(matlab_code_without_comments(read("model.m")))
        rejection = source.index("if~datavalid(frameindex)")
        admission = source.index("slowstartus(frameindex)=max(")
        self.assertLess(rejection, admission)
        self.assertIn("continue;", source[rejection:admission])
        checks = compact(matlab_code_without_comments(read("run_checks.m")))
        for retained in (
            "isnan(underflowisolation.frame.ready_us(1))",
            "underflowisolation.frame.slow_start_us(2)==1000",
            "underflowisolation.metrics.timeout_count==26",
            "underflowisolation.metrics.maximum_output_latency_us==7200",
            "underflowisolation.metrics.maximum_outstanding_depth==6",
        ):
            with self.subTest(retained=retained):
                self.assertIn(retained, checks)

        broken = graph_reference(decimation=1, execution_order="consumer-first")
        first, first_valid = broken["frames"][:2]
        self.assertFalse(first["data_valid"])
        self.assertEqual(first["outstanding_depth"], 0)
        for field in ("ready", "start", "scheduled_finish", "stop", "completion"):
            with self.subTest(field=field):
                self.assertTrue(math.isnan(first[field]))
        self.assertFalse(first["timed_out"])
        self.assertFalse(first["cancelled"])
        self.assertEqual(first_valid["start"], 1000)
        self.assertEqual(first_valid["completion"], 2200)
        self.assertEqual(broken["timeout_count"], 26)
        self.assertEqual(broken["max_output_latency"], 7200)
        self.assertEqual(broken["max_outstanding"], 6)

    def test_independent_timeout_cancellation_rollback_and_recovery(self) -> None:
        equality = graph_reference(slow_cost_us=1900, timeout_action="cancel-frame")
        one_late = graph_reference(slow_cost_us=1901, timeout_action="cancel-frame")
        self.assertEqual(equality["timeout_count"], 0)
        self.assertEqual(equality["emitted_count"], 8)
        self.assertEqual([frame["latency"] for frame in equality["frames"]], [2000] * 8)
        self.assertEqual(one_late["timeout_count"], 8)
        self.assertEqual(one_late["cancelled_count"], 8)
        self.assertEqual(one_late["emitted_count"], 0)

        continued = graph_reference(decimation=1)
        cancelled = graph_reference(decimation=1, timeout_action="cancel-frame")
        self.assertEqual((continued["timeout_count"], continued["emitted_count"], continued["max_outstanding"]), (28, 32, 7))
        self.assertEqual((cancelled["timeout_count"], cancelled["cancelled_count"], cancelled["emitted_count"], cancelled["max_outstanding"]), (28, 28, 4, 2))
        self.assertEqual(
            [frame["computed"] for frame in continued["frames"]],
            [frame["computed"] for frame in cancelled["frames"]],
        )
        self.assertEqual(graph_reference(), graph_reference())

    def test_independent_zero_cost_and_unity_rate_limits(self) -> None:
        zero = graph_reference(fast_cost_us=0, slow_cost_us=0, timeout_us=0)
        self.assertEqual(zero["timeout_count"], 0)
        self.assertEqual(zero["emitted_count"], 8)
        self.assertTrue(all(frame["latency"] == 0 for frame in zero["frames"]))
        unity = graph_reference(decimation=1, slow_cost_us=800)
        self.assertEqual(unity["frame_count"], 32)
        self.assertEqual(unity["slow_utilization"], 0.8)
        self.assertEqual(unity["max_output_latency"], 900)
        self.assertEqual(
            [frame["output"] for frame in unity["frames"]], unity["filtered"]
        )


class P16LearningAndRegressionTests(unittest.TestCase):
    def test_experiment_has_baseline_two_isolated_sweeps_broken_and_recovery(self) -> None:
        experiment = read("experiment.m").lower()
        normalized = compact(experiment)
        self.assertIn("%% baseline", experiment)
        self.assertIn("isequaln(baseline,baselinerepeat)", normalized)
        self.assertGreaterEqual(experiment.count("%% sweep"), 2)
        self.assertRegex(experiment, r"decimation\w*sweep\w*\s*=\s*\[1 2 4 8\]")
        self.assertRegex(experiment, r"slowcost\w*sweep\w*\s*=\s*\[200 800 1200 1800 4200\]")
        for vector in (
            "[1.125 5 9 13 17 21 25 29]",
            "[32 16 8 4]",
            "[1000 500 250 125]",
            "[7500 1300 1300 1300]",
            "[300 900 1300 1900 5700]",
            "[nan 4 8 12 16 20 24 28]",
        ):
            self.assertIn(vector.replace(" ", ""), normalized)
        self.assertIn("%% broken case", experiment)
        self.assertIn("mechanism for sweep 1", experiment)
        self.assertIn("mechanism for sweep 2", experiment)
        self.assertIn("must isolate", experiment)
        self.assertIn("isequaln(recovered,baseline)", normalized)
        self.assertIn("rollback", experiment)
        self.assertGreaterEqual(experiment.count("figure("), 6)
        self.assertIn("xlabel(", experiment)
        self.assertIn("ylabel(", experiment)
        self.assertIn("(us)", experiment)
        self.assertIn("(hz)", experiment)

    def test_public_lesson_launches_one_interactive_session(self) -> None:
        lesson_code = matlab_code_without_comments(read("lesson.m"))
        experiment_code = matlab_code_without_comments(read("experiment.m"))
        interactive_call = re.compile(r"^\s*interactive\s*;\s*$", re.MULTILINE)
        self.assertEqual(len(interactive_call.findall(lesson_code)), 1)
        self.assertFalse(interactive_call.search(experiment_code))
        composed = lesson_code + "\n" + experiment_code
        live_predictions = re.findall(r"disp\s*\(\s*'Prediction:", composed)
        self.assertEqual(len(live_predictions), 1)

    def test_interactive_exposes_controls_scenarios_two_views_and_bound_callbacks(self) -> None:
        interactive = read("interactive.m").lower()
        normalized = compact(interactive)
        self.assertIn("modelfcn=@model;", normalized)
        self.assertIn("scenariofcn=@p16_scenario;", normalized)
        self.assertIn("uifigure(", interactive)
        self.assertGreaterEqual(interactive.count("numericspinner("), 3)
        self.assertGreaterEqual(interactive.count("uidropdown("), 4)
        self.assertGreaterEqual(interactive.count("uiaxes("), 2)
        self.assertIn("valuechangedfcn", interactive)
        self.assertIn("uibutton(", interactive)
        self.assertIn("buttonpushedfcn", interactive)
        self.assertIn("reset editable", interactive)
        self.assertIn("roundfractionalvalues", interactive)
        for label in (
            "samples/frame",
            "fast cost",
            "slow cost",
            "output timeout",
            "producer first",
            "consumer first",
            "cancel frame",
            "not matlab-runtime",
            "hardware",
        ):
            self.assertIn(label, interactive)
        callback_region = normalized[normalized.index("functionupdateviews") :]
        self.assertIn("scenariofcn(", callback_region)
        self.assertIn("modelfcn(", callback_region)
        self.assertNotRegex(callback_region, r"(?<!model)\bmodel\(")

    def test_fixed_diagnostics_reset_every_control_before_rendering(self) -> None:
        interactive = compact(read("interactive.m"))
        selector = interactive[
            interactive.index("functionscenariochanged") : interactive.index("functionupdateviews")
        ]
        self.assertIn("fixedinput=scenariofcn(", selector)
        self.assertGreaterEqual(selector.count(".value="), 6)
        self.assertIn("controls{controlindex}.enable=onoff(~fixedscenario);", selector)
        self.assertLess(selector.rindex(".value="), selector.index("updateviews();"))

    def test_executable_checks_cover_failure_recovery_isolation_and_compatibility(self) -> None:
        checks = read("run_checks.m")
        lower = checks.lower()
        self.assertGreaterEqual(len(re.findall(r"\bassert\s*\(", checks)), 30)
        for marker in (
            "deterministic baseline",
            "independent graph equations",
            "decimation factor",
            "slow-node execution cost",
            "limiting cases",
            "consumer-first",
            "timeout equality",
            "strict lateness",
            "continue-processing",
            "cancellation",
            "rollback",
            "recovery",
            "compatibility",
            "callback lifetime",
            "module isolation",
            "path cleanup",
            "flintmax",
            "resource-bound",
            "malformed",
            "not matlab-runtime",
            "p16 checks passed",
        ):
            self.assertIn(marker, lower)

    def test_tutor_text_is_mechanism_first_one_prediction_and_teach_back(self) -> None:
        lesson = read("lesson.md").lower()
        walkthrough = read("walkthrough.md").lower()
        checks = read("checks.md").lower()
        self.assertEqual(lesson.count("## prediction before the baseline"), 1)
        for equation in (
            "t_slow = d t_s",
            "f_slow = f_s / d",
            "u_slow = c_slow / (d t_s)",
            "start[k]  = max(input_ready[k], previous_stop[k])",
            "late[k]   = finish[k] > release[k] + timeout",
        ):
            self.assertIn(equation, lesson)
        self.assertLess(lesson.index("## read:"), lesson.index("## prediction"))
        self.assertLess(lesson.index("## prediction"), lesson.index("## baseline"))
        self.assertLess(lesson.index("## baseline"), lesson.index("## lever 1"))
        self.assertIn("reset", lesson)
        self.assertIn("p15", lesson)
        self.assertIn("p17", lesson)
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
            "real concurrency",
            "processor",
            "dma",
            "bench",
            "hil",
            "field",
            "production",
            "rt1/rt2",
            "unreal",
            "signing",
            "deployment",
            "staging",
        ):
            self.assertIn(marker, combined)
        self.assertNotIn("hardware-validated", combined)
        self.assertNotIn("matlab-validated", combined)

    def test_cli_start_routes_p16_and_persists_only_isolated_progress(self) -> None:
        root_state_path = ROOT / ".learning/progress.json"
        original_root_state = root_state_path.read_bytes() if root_state_path.exists() else None
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary) / "repo"
            shutil.copytree(ROOT / "bin", fixture / "bin")
            shutil.copytree(ROOT / "curriculum", fixture / "curriculum")
            target = fixture / "modules/16-execute-a-multi-rate-processing-graph"
            target.mkdir(parents=True)
            for name in ("README.md", "lesson.md", "walkthrough.md", "checks.md"):
                shutil.copy2(MODULE_FOLDER / name, target / name)
            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            result = subprocess.run(
                [str(fixture / "bin/learn"), "start", "P16"],
                cwd=fixture,
                text=True,
                capture_output=True,
                timeout=10,
                env=environment,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(QUESTION, result.stdout)
            state = json.loads((fixture / ".learning/progress.json").read_text(encoding="utf-8"))
            self.assertEqual(state["current"], "P16")
        final_root_state = root_state_path.read_bytes() if root_state_path.exists() else None
        self.assertEqual(final_root_state, original_root_state)

    def test_cli_check_resolves_p16_public_matlab_entry_point(self) -> None:
        result = subprocess.run(
            [str(ROOT / "bin/learn"), "check", "P16"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=10,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "Run in MATLAB: run_module_checks('P16')\n")

    @unittest.skipUnless(shutil.which("matlab"), "MATLAB executable unavailable")
    def test_matlab_executes_module_checks_and_callback_lifetime(self) -> None:
        command = "addpath('" + str(MODULE_FOLDER).replace("'", "''") + "'); run_checks;"
        result = subprocess.run(
            ["matlab", "-batch", command],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("P16 checks passed", result.stdout)


class P16RetainedEvidenceTests(unittest.TestCase):
    def test_date_agnostic_retained_evidence_is_complete_and_honest(self) -> None:
        evidence_files = sorted((ROOT / "docs/evidence").glob("P16-*.md"))
        self.assertTrue(evidence_files, "P16 requires a retained evidence record")
        payloads = [path.read_bytes() for path in evidence_files]
        for path, payload in zip(evidence_files, payloads):
            with self.subTest(path=path.name):
                self.assertTrue(payload.endswith(b"\n"))
                self.assertFalse(payload.endswith(b"\n\n"))
        records = [payload.decode("utf-8").lower() for payload in payloads]
        primary = next(
            (
                text
                for text in records
                if "acceptance mapping" in text and "exact commands and results" in text
            ),
            None,
        )
        self.assertIsNotNone(primary, "one retained P16 record must be the primary evidence")
        assert primary is not None
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
            "product-data gate disposition",
        ):
            self.assertIn(heading, primary)
        self.assertGreaterEqual(primary.count("| pass"), 8)
        self.assertGreaterEqual(primary.count("exit `0`"), 8)
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
            "backup/restore",
            "scoring",
        ):
            self.assertIn(marker, primary)
        self.assertNotIn("| unverified", primary)

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
        self.assertEqual(evidence["batch_id"], "P16")
        self.assertEqual(evidence["status"], "pass")
        self.assertGreaterEqual(len(evidence["commands"]), 8)
        self.assertEqual(len(evidence["acceptance"]), 8)
        self.assertTrue(all(item.get("status") == "pass" for item in evidence["acceptance"]))
        self.assertTrue(evidence["changed_invariants"])
        self.assertTrue(evidence["residual_risks"])
        self.assertTrue(evidence["unperformed_validation"])


if __name__ == "__main__":
    unittest.main()
