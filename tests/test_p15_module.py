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
MODULE_FOLDER = ROOT / "modules/15-align-clocks-with-pps-and-timestamps"
QUESTION = (
    "What inputs, observable effects, and failure modes matter when you align "
    "Clocks with PPS and Timestamps?"
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
    "p15_scenario.m",
    "run_checks.m",
    "walkthrough.md",
}
INSTRUCTIONAL_ARTIFACTS = CORE_ARTIFACTS - {"evidence.json"}
BASELINE_EVENTS_US = [250000 + 500000 * index for index in range(8)]
BASELINE_PPS_IDS = list(range(5))


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


def clock_reference(
    events: list[float] | None = None,
    pps_ids: list[int] | None = None,
    *,
    pps_period: float = 1_000_000,
    offset: float = 2500,
    skew_ppm: float = 40,
    tick: float = 1,
    timeout: float = math.inf,
    timeout_action: str = "continue-waiting",
    association: str = "sequence-id",
) -> dict[str, object]:
    event_reference = list(BASELINE_EVENTS_US if events is None else events)
    sequence_ids = list(BASELINE_PPS_IDS if pps_ids is None else pps_ids)
    rate = 1 + skew_ppm * 1e-6
    true_pps = [sequence_id * pps_period for sequence_id in sequence_ids]
    if association == "sequence-id":
        assumed_pps = list(true_pps)
    elif association == "arrival-index":
        assumed_pps = [
            (sequence_ids[0] + index) * pps_period
            for index in range(len(sequence_ids))
        ]
    else:
        raise AssertionError(f"unknown association in oracle: {association}")

    def quantize(value: float) -> float:
        scaled = (offset + rate * value) / tick
        if scaled > 1_000_000_000_000:
            raise ValueError("absolute timestamp tick index exceeds 1e12")
        nearest_integer = round(scaled)
        if abs(scaled - nearest_integer) <= 8 * math.ulp(max(abs(scaled), 1.0)):
            scaled = float(nearest_integer)
        return tick * math.floor(scaled)

    local_events = [quantize(value) for value in event_reference]
    local_pps = [quantize(value) for value in true_pps]
    gaps = [
        (right - left) * pps_period
        for left, right in zip(sequence_ids, sequence_ids[1:])
    ]
    late = []
    for gap in gaps:
        if math.isinf(timeout):
            late.append(False)
            continue
        tolerance = math.ulp(max(abs(gap), abs(timeout)))
        comparison_gap = (
            timeout
            if timeout > 0 and abs(gap - timeout) <= tolerance
            else gap
        )
        late.append(comparison_gap > timeout)
    first_late = next((index for index, value in enumerate(late) if value), None)
    timed_out = first_late is not None
    cancelled = timed_out and timeout_action == "cancel-alignment"
    retained_count = first_late + 1 if cancelled and first_late is not None else len(sequence_ids)
    retained = list(range(retained_count))
    offset_only = local_pps[0] - assumed_pps[0]
    offset_only_errors = [
        local - offset_only - reference
        for local, reference in zip(local_events, event_reference)
    ]
    raw_errors = [
        local - reference
        for local, reference in zip(local_events, event_reference)
    ]
    available = retained_count >= 2
    if available:
        first_index = retained[0]
        last_index = retained[-1]
        estimated_rate = (
            (local_pps[last_index] - local_pps[first_index])
            / (assumed_pps[last_index] - assumed_pps[first_index])
        )
        estimated_offset = (
            local_pps[first_index] - estimated_rate * assumed_pps[first_index]
        )
        estimated_skew = (estimated_rate - 1) * 1e6
        aligned = [
            (local - estimated_offset) / estimated_rate for local in local_events
        ]
        corrected_errors = [
            value - reference for value, reference in zip(aligned, event_reference)
        ]
        residuals = [math.nan] * len(sequence_ids)
        for index in retained:
            residuals[index] = local_pps[index] - (
                estimated_offset + estimated_rate * assumed_pps[index]
            )
    else:
        estimated_rate = math.nan
        estimated_offset = math.nan
        estimated_skew = math.nan
        corrected_errors = [math.nan] * len(event_reference)
        residuals = [math.nan] * len(sequence_ids)
    return {
        "events": event_reference,
        "ids": sequence_ids,
        "true_pps": true_pps,
        "assumed_pps": assumed_pps,
        "local_events": local_events,
        "local_pps": local_pps,
        "raw_errors": raw_errors,
        "offset_only_errors": offset_only_errors,
        "estimated_rate": estimated_rate,
        "estimated_offset": estimated_offset,
        "estimated_skew": estimated_skew,
        "corrected_errors": corrected_errors,
        "residuals": residuals,
        "missing_count": sum(
            right - left - 1 for left, right in zip(sequence_ids, sequence_ids[1:])
        ),
        "association_consistent": assumed_pps == true_pps,
        "timed_out": timed_out,
        "cancelled": cancelled,
        "retained_count": retained_count,
        "censored_count": len(sequence_ids) - retained_count,
        "available": available,
    }


class P15IdentityAndArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        manifest = json.loads(
            (ROOT / "curriculum/modules.json").read_text(encoding="utf-8")
        )
        cls.modules = manifest["modules"]
        cls.module = next(module for module in cls.modules if module["id"] == "P15")

    def test_permanent_manifest_identity_prerequisite_status_and_evidence(self) -> None:
        self.assertEqual(self.module["number"], 15)
        self.assertEqual(self.module["title"], "Align Clocks with PPS and Timestamps")
        self.assertEqual(self.module["guiding_question"], QUESTION)
        self.assertEqual(self.module["phase"], 4)
        self.assertEqual(self.module["phase_title"], "Data movement and timing")
        self.assertEqual(self.module["slug"], "align-clocks-with-pps-and-timestamps")
        self.assertEqual(
            self.module["folder"], "modules/15-align-clocks-with-pps-and-timestamps"
        )
        self.assertEqual(self.module["implementation_batch"], "P15")
        self.assertEqual(self.module["prerequisites"], ["P14"])
        self.assertEqual(self.module["status"], "implemented")
        self.assertEqual(self.module["evidence_level"], "simulated")
        p14 = next(module for module in self.modules if module["id"] == "P14")
        p16 = next(module for module in self.modules if module["id"] == "P16")
        self.assertEqual(p14["status"], "implemented")
        self.assertEqual(p16["prerequisites"], ["P15"])

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

    def test_guiding_question_p14_connection_p16_boundary_and_claims_are_explicit(self) -> None:
        combined = "\n".join(read(name) for name in INSTRUCTIONAL_ARTIFACTS).lower()
        self.assertIn(QUESTION.lower(), combined)
        for concept in (
            "p14",
            "p16",
            "offset",
            "skew",
            "pps",
            "sequence id",
            "timestamp tick",
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
            "black-box fit",
        ):
            self.assertNotIn(residue, combined)


class P15ModelContractTests(unittest.TestCase):
    def test_model_is_transparent_affine_deterministic_and_resource_bounded(self) -> None:
        source = read("model.m")
        normalized = compact(matlab_code_without_comments(source))
        self.assertIn("functionout=model(", normalized)
        for token in (
            "clockrateratio=1+clockskewppm.*1e-6",
            "ppstruereferenceus=ppssequenceid.*ppsperiodus",
            "ppsgapus=diff(ppssequenceid).*ppsperiodus",
            "nearestinteger=round(scaled)",
            "boundarytolerance=8.*eps(max(abs(scaled),1))",
            "scaled(nearinteger)=nearestinteger(nearinteger)",
            "tickus.*floor(scaled)",
            "estimatedrateratio=localspanus./referencespanus",
            "eventalignedus=...(eventlocaltimestampus-estimatedoffsetus)./estimatedrateratio",
            "sequence-id",
            "arrival-index",
            "continue-waiting",
            "cancel-alignment",
            "neartimeoutboundary=abs(ppsgapus-ppswaittimeoutus)<=...timeoutboundarytoleranceus",
            "gapfortimeoutcomparisonus(neartimeoutboundary)=ppswaittimeoutus",
            "gapfortimeoutcomparisonus>ppswaittimeoutus",
        ):
            with self.subTest(token=token):
                self.assertIn(token, normalized)
        self.assertRegex(source, r"maxEventCount\s*=\s*10000")
        self.assertRegex(source, r"maxPpsCount\s*=\s*10000")
        self.assertRegex(source, r"maxTimestampUs\s*=\s*1e12")
        self.assertRegex(source, r"maxTimestampTickIndex\s*=\s*1e12")
        self.assertIn("uint64(flintmax)", source)
        self.assertLess(source.index("validateTimeVector"), source.index("eventLocalIdealUs"))
        self.assertLess(source.index("validateSequenceIds"), source.index("ppsTrueReferenceUs"))

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
            "polyfit",
            "fit",
            "table",
            "timetable",
            "timeseries",
            "daq",
            "gps",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotRegex(code, rf"\b{forbidden}\s*\(")
        self.assertNotIn("simulink", code)

    def test_model_rejects_malformed_precision_choices_and_resources(self) -> None:
        source = read("model.m")
        for identifier in (
            "P15:model:Arity",
            "P15:model:PpsSequenceId",
            "P15:model:PpsSequenceOrder",
            "P15:model:PpsSequencePrecision",
            "P15:model:PpsResourceBound",
            "P15:model:ClockSkew",
            "P15:model:PpsWaitTimeout",
            "P15:model:TimelineResourceBound",
            "P15:model:TimestampResourceBound",
            "P15:model:TimestampPrecision",
            "P15:model:FitResolution",
            "P15:model:FitPrecision",
        ):
            self.assertIn(identifier, source)
        for dynamic_label in (
            "'EventReference'",
            "'PpsPeriod'",
            "'ClockOffset'",
            "'TimestampTick'",
            "'TimeoutAction'",
            "'AssociationMode'",
            "['P15:model:' label]",
            "['P15:model:' label 'ResourceBound']",
        ):
            self.assertIn(dynamic_label, source)
        self.assertLess(source.index("validateDerivedClock"), source.index("quantizeDown"))

    def test_scenario_is_seedless_bounded_and_model_compatible(self) -> None:
        scenario = read("p15_scenario.m")
        for name in (
            "baseline",
            "zero-error",
            "missing-id-correct",
            "broken-arrival-index",
            "coarse-timestamp",
            "timeout-continue",
            "timeout-cancel",
        ):
            self.assertIn(name, scenario)
        for field in (
            "event_reference_us",
            "pps_sequence_id",
            "pps_period_us",
            "clock_offset_us",
            "clock_skew_ppm",
            "timestamp_tick_us",
            "pps_wait_timeout_us",
            "timeout_action",
            "association_mode",
        ):
            self.assertIn(field, scenario)
        self.assertIn("if strcmp(name, 'baseline')", scenario)
        scenario_code = matlab_code_without_comments(scenario).lower()
        self.assertNotRegex(scenario_code, r"\b(?:rng|rand|randn|while|timer|pause)\b")

    def test_independent_baseline_affine_equations_and_quantization(self) -> None:
        result = clock_reference()
        self.assertEqual(
            result["local_pps"], [2500, 1002540, 2002580, 3002620, 4002660]
        )
        self.assertEqual(
            result["local_events"],
            [252510, 752530, 1252550, 1752570, 2252590, 2752610, 3252630, 3752650],
        )
        self.assertEqual(result["raw_errors"], list(range(2510, 2651, 20)))
        self.assertEqual(result["offset_only_errors"], list(range(10, 151, 20)))
        self.assertAlmostEqual(result["estimated_offset"], 2500)
        self.assertAlmostEqual(result["estimated_skew"], 40)
        self.assertTrue(all(abs(value) < 1e-9 for value in result["corrected_errors"]))
        self.assertTrue(all(abs(value) < 1e-9 for value in result["residuals"]))

    def test_decimal_tick_boundary_does_not_lose_a_full_tick(self) -> None:
        tick = 0.1
        result = clock_reference(
            events=[0.1, 0.2, 0.3],
            pps_ids=[0, 3],
            pps_period=0.1,
            offset=0,
            skew_ppm=0,
            tick=tick,
        )
        self.assertEqual(result["local_events"], [tick * index for index in (1, 2, 3)])
        self.assertEqual(result["local_pps"], [tick * index for index in (0, 3)])
        self.assertEqual(result["estimated_rate"], 1)
        self.assertEqual(result["estimated_skew"], 0)
        self.assertLess(
            max(abs(value) for value in result["corrected_errors"]), math.ulp(1.0)
        )
        operation_chain = clock_reference(
            events=[3.5],
            pps_ids=[0, 1],
            pps_period=3.5,
            offset=0,
            skew_ppm=800_000,
            tick=tick,
        )
        distinguishably_below = clock_reference(
            events=[6.3 - 1e-10],
            pps_ids=[0, 1],
            pps_period=1,
            offset=0,
            skew_ppm=0,
            tick=tick,
        )
        self.assertEqual(operation_chain["local_events"], [tick * 63])
        self.assertEqual(operation_chain["local_pps"][-1], tick * 63)
        self.assertEqual(distinguishably_below["local_events"], [tick * 62])
        ambiguous_tick = (2**48 + 0.75) * 1e-3
        ambiguous_scaled = ambiguous_tick / 1e-3
        unbounded_tolerance = 8 * math.ulp(ambiguous_scaled)
        unbounded_reported = 1e-3 * math.floor(round(ambiguous_scaled))
        self.assertGreaterEqual(unbounded_tolerance, 0.5)
        self.assertGreater(unbounded_reported, ambiguous_tick)
        with self.assertRaisesRegex(ValueError, "tick index exceeds 1e12"):
            clock_reference(
                events=[ambiguous_tick],
                pps_ids=[0, 1],
                pps_period=1,
                offset=0,
                skew_ppm=0,
                tick=1e-3,
            )
        equality = clock_reference(
            events=[0.1, 0.2, 0.3],
            pps_ids=[0, 3],
            pps_period=0.1,
            offset=0,
            skew_ppm=0,
            tick=tick,
            timeout=0.3,
            timeout_action="cancel-alignment",
        )
        late = clock_reference(
            events=[0.1, 0.2, 0.3],
            pps_ids=[0, 3],
            pps_period=0.1,
            offset=0,
            skew_ppm=0,
            tick=tick,
            timeout=0.29,
            timeout_action="cancel-alignment",
        )
        self.assertFalse(equality["timed_out"])
        self.assertFalse(equality["cancelled"])
        self.assertEqual(equality["retained_count"], 2)
        self.assertTrue(late["timed_out"])
        self.assertTrue(late["cancelled"])
        self.assertEqual(late["retained_count"], 1)
        higher_epoch = clock_reference(
            events=[4.05],
            pps_ids=[40, 41],
            pps_period=0.1,
            offset=0,
            skew_ppm=0,
            tick=tick,
            timeout=0.1,
            timeout_action="cancel-alignment",
        )
        adjacent = clock_reference(
            events=[0.1],
            pps_ids=[0, 1],
            pps_period=0.3 + math.ulp(0.3),
            offset=0,
            skew_ppm=0,
            tick=tick,
            timeout=0.3,
            timeout_action="cancel-alignment",
        )
        distinct = clock_reference(
            events=[0.1],
            pps_ids=[0, 1],
            pps_period=0.3 + 4 * math.ulp(0.3),
            offset=0,
            skew_ppm=0,
            tick=tick,
            timeout=0.3,
            timeout_action="cancel-alignment",
        )
        self.assertFalse(higher_epoch["timed_out"])
        self.assertFalse(adjacent["timed_out"])
        self.assertTrue(distinct["timed_out"])
        smallest_positive = math.ulp(0.0)
        zero_timeout = clock_reference(
            events=[smallest_positive],
            pps_ids=[0, 1],
            pps_period=smallest_positive,
            offset=0,
            skew_ppm=0,
            tick=smallest_positive,
            timeout=0,
            timeout_action="cancel-alignment",
        )
        self.assertTrue(zero_timeout["timed_out"])
        self.assertTrue(zero_timeout["cancelled"])

    def test_independent_offset_and_skew_sweeps_isolate_two_parameters(self) -> None:
        offset_results = [clock_reference(offset=value) for value in [0, 1000, 2500, 5000, 10000]]
        self.assertEqual(
            [result["raw_errors"][0] for result in offset_results],
            [10, 1010, 2510, 5010, 10010],
        )
        self.assertEqual(
            [result["raw_errors"][-1] for result in offset_results],
            [150, 1150, 2650, 5150, 10150],
        )
        self.assertEqual(
            [result["estimated_offset"] for result in offset_results],
            [0, 1000, 2500, 5000, 10000],
        )
        skew_values = [-80, -40, 0, 40, 80]
        skew_results = [clock_reference(skew_ppm=value) for value in skew_values]
        self.assertEqual(
            [result["local_pps"][-1] - result["local_pps"][0] - 4_000_000 for result in skew_results],
            [-320, -160, 0, 160, 320],
        )
        self.assertEqual(
            [result["raw_errors"][-1] for result in skew_results],
            [2200, 2350, 2500, 2650, 2800],
        )
        self.assertEqual(
            [max(abs(value) for value in result["offset_only_errors"]) for result in skew_results],
            [300, 150, 0, 150, 300],
        )
        for actual, expected in zip(
            [result["estimated_skew"] for result in skew_results], skew_values
        ):
            self.assertAlmostEqual(actual, expected, places=8)

    def test_independent_missing_id_and_broken_arrival_association(self) -> None:
        correct = clock_reference(pps_ids=[0, 2, 3, 4])
        broken = clock_reference(pps_ids=[0, 2, 3, 4], association="arrival-index")
        self.assertEqual(correct["missing_count"], 1)
        self.assertTrue(correct["association_consistent"])
        self.assertTrue(all(abs(value) < 1e-9 for value in correct["corrected_errors"]))
        self.assertFalse(broken["association_consistent"])
        self.assertAlmostEqual(broken["estimated_skew"], 333386.666666667, places=6)
        for actual, expected in zip(
            broken["corrected_errors"],
            [-62500, -187500, -312500, -437500, -562500, -687500, -812500, -937500],
        ):
            self.assertAlmostEqual(actual, expected, places=6)
        for actual, expected in zip(
            broken["residuals"],
            [0, 666693.333333333, 333346.666666667, 0],
        ):
            self.assertAlmostEqual(actual, expected, places=6)

    def test_independent_timeout_cancellation_limits_and_recovery(self) -> None:
        equality = clock_reference(
            pps_ids=[0, 2, 3, 4], timeout=2_000_000, timeout_action="cancel-alignment"
        )
        continued = clock_reference(pps_ids=[0, 2, 3, 4], timeout=1_500_000)
        cancelled = clock_reference(
            pps_ids=[0, 2, 3, 4], timeout=1_500_000, timeout_action="cancel-alignment"
        )
        self.assertFalse(equality["timed_out"])
        self.assertTrue(equality["available"])
        self.assertTrue(continued["timed_out"])
        self.assertFalse(continued["cancelled"])
        self.assertEqual(continued["retained_count"], 4)
        self.assertTrue(cancelled["timed_out"])
        self.assertTrue(cancelled["cancelled"])
        self.assertEqual(cancelled["retained_count"], 1)
        self.assertEqual(cancelled["censored_count"], 3)
        self.assertFalse(cancelled["available"])
        self.assertTrue(all(math.isnan(value) for value in cancelled["corrected_errors"]))
        zero = clock_reference(events=[0, 250000, 500000], pps_ids=[0, 1, 2], offset=0, skew_ppm=0)
        self.assertEqual(zero["raw_errors"], [0, 0, 0])
        one = clock_reference(pps_ids=[0])
        self.assertFalse(one["available"])
        self.assertEqual(one["offset_only_errors"], list(range(10, 151, 20)))
        self.assertEqual(clock_reference(), clock_reference())


class P15LearningAndRegressionTests(unittest.TestCase):
    def test_experiment_has_baseline_two_isolated_sweeps_and_broken_case(self) -> None:
        experiment = read("experiment.m").lower()
        normalized = compact(experiment)
        self.assertIn("%% baseline", experiment)
        self.assertIn("isequaln(baseline,baselinerepeat)", normalized)
        self.assertGreaterEqual(experiment.count("%% sweep"), 2)
        self.assertRegex(experiment, r"offset\w*sweep\w*\s*=\s*\[0 1000 2500 5000 10000\]")
        self.assertRegex(experiment, r"skew\w*sweep\w*\s*=\s*\[-80 -40 0 40 80\]")
        for vector in (
            "[10 1010 2510 5010 10010]",
            "[150 1150 2650 5150 10150]",
            "[-320 -160 0 160 320]",
            "[2200 2350 2500 2650 2800]",
            "[-62500 -187500 -312500 -437500 -562500 -687500 -812500 -937500]",
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
        self.assertIn("(ppm)", experiment)

    def test_public_lesson_launches_one_interactive_session(self) -> None:
        lesson_code = matlab_code_without_comments(read("lesson.m"))
        experiment_code = matlab_code_without_comments(read("experiment.m"))
        interactive_call = re.compile(r"^\s*interactive\s*;\s*$", re.MULTILINE)
        self.assertEqual(len(interactive_call.findall(lesson_code)), 1)
        self.assertFalse(
            interactive_call.search(experiment_code),
            "experiment must not open a second interactive session from launch_lesson",
        )

    def test_interactive_exposes_controls_scenarios_two_views_and_bound_callbacks(self) -> None:
        interactive = read("interactive.m").lower()
        normalized = compact(interactive)
        self.assertIn("modelfcn=@model;", normalized)
        self.assertIn("scenariofcn=@p15_scenario;", normalized)
        self.assertIn("uifigure(", interactive)
        self.assertGreaterEqual(interactive.count("numericspinner("), 4)
        self.assertGreaterEqual(interactive.count("uidropdown("), 3)
        self.assertGreaterEqual(interactive.count("uiaxes("), 2)
        self.assertIn("valuechangedfcn", interactive)
        for label in (
            "clock offset",
            "oscillator skew",
            "timestamp tick",
            "pps timeout",
            "sequence id",
            "arrival index",
            "cancel alignment",
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
            interactive.index("functionscenariochanged"):interactive.index("functionupdateviews")
        ]
        self.assertIn("fixedinput=scenariofcn(", selector)
        self.assertGreaterEqual(selector.count(".value="), 6)
        self.assertIn("controls{controlindex}.enable=onoff(~fixedscenario);", selector)
        self.assertIn("elsefixedinput=scenariofcn('baseline');", selector)
        self.assertLess(selector.rindex(".value="), selector.index("updateviews();"))

    def test_executable_checks_cover_complete_failure_and_recovery_contract(self) -> None:
        checks = read("run_checks.m")
        lower = checks.lower()
        self.assertGreaterEqual(len(re.findall(r"\bassert\s*\(", checks)), 25)
        for marker in (
            "deterministic",
            "independent affine",
            "offset sweep",
            "oscillator skew",
            "missing-pps association",
            "arrival-index",
            "timeout equality",
            "continue-waiting",
            "cancellation",
            "rollback",
            "recovery",
            "one pps anchor",
            "two distinct ideal anchors",
            "decimal tick boundary",
            "tick-index precision",
            "strict positive subnormal gap",
            "callback-bound",
            "path cleanup",
            "flintmax",
            "realmin",
            "resource-bound",
            "malformed",
            "not matlab-runtime",
            "p15 checks passed",
        ):
            self.assertIn(marker, lower)
        for identifier in (
            "p15:model:arity",
            "p15:model:eventreference",
            "p15:model:ppssequenceid",
            "p15:model:ppsperiod",
            "p15:model:clockoffset",
            "p15:model:clockskew",
            "p15:model:timestamptick",
            "p15:model:ppswaittimeout",
            "p15:model:timeoutaction",
            "p15:model:associationmode",
            "p15:model:timelineresourcebound",
            "p15:model:timestampresourcebound",
            "p15:model:timestampprecision",
            "p15:model:fitresolution",
        ):
            self.assertIn(identifier, lower)

    def test_tutor_text_is_mechanism_first_one_prediction_and_teach_back(self) -> None:
        lesson = read("lesson.md").lower()
        walkthrough = read("walkthrough.md").lower()
        checks = read("checks.md").lower()
        self.assertEqual(lesson.count("## prediction before the baseline"), 1)
        for equation in (
            "c(t) = b + r t",
            "r_hat = (c_n-c_1)/(t_n-t_1)",
            "t_pps(k) = k t_pps",
            "drift_us = s_ppm * duration_us / 10^6",
        ):
            self.assertIn(equation, lesson)
        self.assertLess(lesson.index("## read:"), lesson.index("## prediction"))
        self.assertLess(lesson.index("## prediction"), lesson.index("## baseline"))
        self.assertLess(lesson.index("## baseline"), lesson.index("## lever 1"))
        self.assertIn("reset", lesson)
        self.assertIn("p14", lesson)
        self.assertIn("p16", lesson)
        self.assertIn("reset", walkthrough)
        self.assertIn("interpretation questions", checks)
        self.assertIn("teach-back", checks)

    def test_claim_language_separates_simulated_runtime_clock_and_physical_evidence(self) -> None:
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
            "pps/gnss",
            "oscillator",
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

    def test_cli_start_routes_p15_and_persists_only_isolated_progress(self) -> None:
        root_state_path = ROOT / ".learning/progress.json"
        original_root_state = root_state_path.read_bytes() if root_state_path.exists() else None
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary) / "repo"
            shutil.copytree(ROOT / "bin", fixture / "bin")
            shutil.copytree(ROOT / "curriculum", fixture / "curriculum")
            target = fixture / "modules/15-align-clocks-with-pps-and-timestamps"
            target.mkdir(parents=True)
            for name in ("README.md", "lesson.md", "walkthrough.md", "checks.md"):
                shutil.copy2(MODULE_FOLDER / name, target / name)
            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            result = subprocess.run(
                [str(fixture / "bin/learn"), "start", "P15"],
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
            self.assertEqual(state["current"], "P15")
        final_root_state = root_state_path.read_bytes() if root_state_path.exists() else None
        self.assertEqual(final_root_state, original_root_state)

    def test_cli_check_resolves_p15_public_matlab_entry_point(self) -> None:
        result = subprocess.run(
            [str(ROOT / "bin/learn"), "check", "P15"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=10,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "Run in MATLAB: run_module_checks('P15')\n")

    @unittest.skipUnless(shutil.which("matlab"), "MATLAB executable unavailable")
    def test_matlab_executes_module_checks_and_callback_lifetime(self) -> None:
        command = (
            "addpath('" + str(MODULE_FOLDER).replace("'", "''") + "'); run_checks;"
        )
        result = subprocess.run(
            ["matlab", "-batch", command],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("P15 checks passed", result.stdout)


class P15RetainedEvidenceTests(unittest.TestCase):
    def test_date_agnostic_retained_evidence_is_complete_and_honest(self) -> None:
        evidence_files = sorted((ROOT / "docs/evidence").glob("P15-*.md"))
        self.assertTrue(evidence_files, "P15 requires a retained evidence record")
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
        self.assertIsNotNone(primary, "one retained P15 record must be the primary evidence")
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
        self.assertEqual(evidence["batch_id"], "P15")
        self.assertEqual(evidence["status"], "pass")
        self.assertGreaterEqual(len(evidence["commands"]), 8)
        self.assertEqual(len(evidence["acceptance"]), 8)
        self.assertTrue(all(item.get("status") == "pass" for item in evidence["acceptance"]))
        self.assertTrue(evidence["changed_invariants"])
        self.assertTrue(evidence["residual_risks"])
        self.assertTrue(evidence["unperformed_validation"])


if __name__ == "__main__":
    unittest.main()
