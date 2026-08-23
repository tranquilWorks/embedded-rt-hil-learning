from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_FOLDER = ROOT / "modules/12-measure-jitter-and-worst-case-response-time"
QUESTION = (
    "What inputs, observable effects, and failure modes matter when you measure "
    "Jitter and Worst-Case Response Time?"
)
CORE_ARTIFACTS = {
    "README.md",
    "checks.md",
    "experiment.m",
    "interactive.m",
    "lesson.m",
    "lesson.md",
    "model.m",
    "p12_scenario.m",
    "run_checks.m",
    "walkthrough.md",
}


def read(name: str) -> str:
    return (MODULE_FOLDER / name).read_text(encoding="utf-8")


def matlab_code_without_comments(source: str) -> str:
    return "\n".join(line.split("%", 1)[0] for line in source.splitlines())


def expand(values: float | list[float], count: int) -> list[float]:
    if isinstance(values, (int, float)):
        return [float(values)] * count
    if len(values) != count:
        raise ValueError("one value per job required")
    return [float(value) for value in values]


def timestamp_reference(
    period: float = 20,
    offsets: float | list[float] = (0, 1, -1, 0, 1, -1, 0, 1),
    execution: float | list[float] = 2,
    blocking: float | list[float] = (0, 1, 0, 1, 0, 1, 0, 1),
    interference: float | list[float] = (0, 0, 1, 0, 2, 0, 1, 3),
    deadline: float = 7,
    tick: float = 1,
    timeout: float = math.inf,
    action: str = "continue-observing",
    count: int = 8,
) -> dict[str, object]:
    offset = expand(offsets, count)
    own = expand(execution, count)
    blocked = expand(blocking, count)
    interfered = expand(interference, count)
    nominal = [index * period for index in range(count)]
    actual = [nominal[index] + offset[index] for index in range(count)]
    start = [
        actual[index] + blocked[index] + interfered[index]
        for index in range(count)
    ]
    finish = [start[index] + own[index] for index in range(count)]
    response = [finish[index] - actual[index] for index in range(count)]
    nominal_latency = [finish[index] - nominal[index] for index in range(count)]

    def capture(value: float, tolerance: float) -> float:
        scaled = value / tick
        nearest = round(scaled)
        if abs(scaled - nearest) <= tolerance:
            scaled = float(nearest)
        return math.floor(scaled) * tick

    captured_release: list[float] = []
    captured_start: list[float] = []
    captured_finish: list[float] = []
    normalization_tolerance: list[float] = []
    for index in range(count):
        scaled_magnitude = max(
            1.0,
            abs(actual[index] / tick),
            abs(start[index] / tick),
            abs(finish[index] / tick),
        )
        tolerance = 8 * math.ulp(scaled_magnitude)
        normalization_tolerance.append(tolerance)
        captured_release.append(capture(actual[index], tolerance))
        captured_start.append(capture(start[index], tolerance))
        captured_finish.append(capture(finish[index], tolerance))
    timed_out = [value > timeout for value in response]
    censored = [value and action == "cancel-observation" for value in timed_out]
    measured_response = [
        None
        if censored[index]
        else captured_finish[index] - captured_release[index]
        for index in range(count)
    ]
    retained = [value for value in measured_response if value is not None]
    incomplete_worst_lower_bound = None
    if any(censored):
        retained_lower_bound = max(0, max(retained) - tick) if retained else 0
        incomplete_worst_lower_bound = max(timeout, retained_lower_bound)
    completion_deviation = [
        (finish[index] - finish[index - 1]) - period
        for index in range(1, count)
    ]
    prefix_maximum: list[float] = []
    for value in response:
        prefix_maximum.append(max(prefix_maximum[-1], value) if prefix_maximum else value)
    return {
        "nominal": nominal,
        "actual": actual,
        "start": start,
        "finish": finish,
        "offset": offset,
        "response": response,
        "nominal_latency": nominal_latency,
        "release_jitter_pp": max(offset) - min(offset),
        "response_jitter_pp": max(response) - min(response),
        "observed_worst": max(response),
        "component_envelope": max(blocked) + max(interfered) + max(own),
        "deadline_miss": [value > deadline for value in response],
        "completion_deviation": completion_deviation,
        "captured_release": captured_release,
        "captured_start": captured_start,
        "captured_finish": captured_finish,
        "normalization_tolerance": normalization_tolerance,
        "measured_response": measured_response,
        "measured_worst": max(retained) if retained else None,
        "measured_jitter_pp": max(retained) - min(retained) if retained else None,
        "timed_out": timed_out,
        "censored": censored,
        "incomplete_worst_lower_bound": incomplete_worst_lower_bound,
        "prefix_maximum": prefix_maximum,
    }


class P12IdentityAndArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (ROOT / "curriculum/modules.json").read_text(encoding="utf-8")
        )
        cls.module = next(
            module for module in cls.manifest["modules"] if module["id"] == "P12"
        )

    def test_permanent_manifest_identity_prerequisite_status_and_evidence(self):
        self.assertEqual(self.module["number"], 12)
        self.assertEqual(
            self.module["title"], "Measure Jitter and Worst-Case Response Time"
        )
        self.assertEqual(self.module["guiding_question"], QUESTION)
        self.assertEqual(self.module["phase"], 3)
        self.assertEqual(self.module["phase_title"], "RTOS behavior")
        self.assertEqual(
            self.module["slug"], "measure-jitter-and-worst-case-response-time"
        )
        self.assertEqual(
            self.module["folder"],
            "modules/12-measure-jitter-and-worst-case-response-time",
        )
        self.assertEqual(self.module["implementation_batch"], "P12")
        self.assertEqual(self.module["prerequisites"], ["P11"])
        self.assertEqual(self.module["status"], "implemented")
        self.assertEqual(self.module["evidence_level"], "simulated")

        p13 = next(
            module for module in self.manifest["modules"] if module["id"] == "P13"
        )
        self.assertEqual(p13["prerequisites"], ["P12"])

    def test_complete_artifact_set_has_clean_terminal_newlines_and_bounds(self):
        names = {path.name for path in MODULE_FOLDER.iterdir() if path.is_file()}
        self.assertTrue(CORE_ARTIFACTS <= names)
        for name in CORE_ARTIFACTS:
            with self.subTest(name=name):
                payload = (MODULE_FOLDER / name).read_bytes()
                self.assertTrue(payload.endswith(b"\n"))
                self.assertFalse(payload.endswith(b"\n\n"))
                self.assertLess(len(payload), 100_000)

    def test_guiding_question_p11_connection_p13_boundary_and_claims_are_explicit(self):
        combined = "\n".join(
            read(name) for name in ("README.md", "lesson.md", "walkthrough.md")
        )
        lower = re.sub(r"\s+", " ", combined.lower())
        self.assertIn(QUESTION, combined)
        self.assertIn("P11", combined)
        self.assertIn("P13", combined)
        for concept in (
            "nominal release",
            "actual release",
            "observed worst response",
            "finite trace",
            "peak-to-peak",
            "censored",
            "not matlab-runtime",
            "rtos",
            "processor",
            "hardware",
        ):
            with self.subTest(concept=concept):
                self.assertIn(concept, lower)
        self.assertRegex(lower, r"\bnot\b[^.]{0,220}\bwcrt\b")

    def test_no_scaffold_placeholder_or_opaque_residue(self):
        combined = "\n".join(read(name).lower() for name in CORE_ARTIFACTS)
        for residue in (
            "scaffolded",
            "activate its governed",
            "not implemented yet",
            "todo",
            "tbd",
            "placeholder",
            "black box",
        ):
            with self.subTest(residue=residue):
                self.assertNotIn(residue, combined)


class P12ModelContractTests(unittest.TestCase):
    def test_model_is_transparent_deterministic_and_resource_bounded(self):
        source = read("model.m")
        code = matlab_code_without_comments(source).lower()
        compact = re.sub(r"\s+", "", code).replace("...", "")
        self.assertIn(
            "functionout=model(periodms,jobcount,releaseoffsetms,executionms,"
            "blockingms,interferencems,deadlinems,timestamptickms,"
            "responsetimeoutms,timeoutaction)",
            compact,
        )
        for token in (
            "nominalreleasems",
            "actualreleasems",
            "startms",
            "completionms",
            "responsems",
            "nominalcompletionlatencyms",
            "measuredreleaseoffsetms",
            "prefixobservedworstresponsems",
            "componentresponseenvelopems",
            "waittimedout",
            "censored",
            "retained",
            "finite_trace_is_wcrt_guarantee",
        ):
            with self.subTest(token=token):
                self.assertIn(token, compact)
        self.assertIn("dispatchdelayms=blockingms+interferencems;", compact)
        self.assertIn("responsems=dispatchdelayms+executionms;", compact)
        self.assertIn("completiontick(censored)=nan;", compact)
        self.assertIn("releaseoffsetcollapsed=", compact)
        self.assertIn("relativecomponentcollapsed=", compact)
        self.assertIn("absoluteadvancecollapsed=", compact)
        self.assertIn("referencediagnostics=", compact)
        self.assertIn("measurementdiagnostics=", compact)
        self.assertIn(
            "retainedobservedworstresponsems-timestamptickms", compact
        )
        self.assertIn(
            "scale.*(sum(values./scale)./numel(values))", compact
        )
        self.assertIn("values=values(~isnan(values));", compact)
        self.assertIn("forprefixindex=2:jobcount", compact)
        self.assertNotRegex(
            code,
            r"\b(?:persistent|global|rng|rand|randn|pause|eval|system|parfor|parpool)\b",
        )
        self.assertNotRegex(code, r"(?m)^\s*while\b")
        self.assertLess(compact.index("jobcount>maxjobs"), compact.index("jobid=1:jobcount"))
        self.assertLess(
            compact.index("numel(values)>maxcount"), compact.index("values=reshape(double(values)")
        )

    def test_model_has_no_presentation_hardware_or_opaque_toolbox_calls(self):
        code = matlab_code_without_comments(read("model.m")).lower()
        for forbidden in (
            "figure",
            "plot",
            "uifigure",
            "fprintf",
            "disp",
            "sim",
            "timer",
            "pause",
            "system",
            "eval",
            "parpool",
            "table",
            "timetable",
            "timeseries",
            "prctile",
            "serialport",
            "arduino",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotRegex(code, rf"\b{forbidden}\s*\(")
        self.assertNotIn("simulink", code)
        self.assertNotIn("real-time toolbox", code)

    def test_model_rejects_malformed_timing_policy_and_resources(self):
        source = read("model.m")
        for identifier in (
            "P12:model:Arity",
            "P12:model:Period",
            "P12:model:JobCount",
            "P12:model:JobResourceBound",
            "P12:model:ReleaseOffset",
            "P12:model:ReleaseOffsetLength",
            "P12:model:Execution",
            "P12:model:ExecutionLength",
            "P12:model:Blocking",
            "P12:model:BlockingLength",
            "P12:model:Interference",
            "P12:model:InterferenceLength",
            "P12:model:Deadline",
            "P12:model:TimestampTick",
            "P12:model:ResponseTimeout",
            "P12:model:TimeoutAction",
            "P12:model:ReleaseOrder",
            "P12:model:TimingResourceBound",
            "P12:model:TimingPrecision",
        ):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, source)
        self.assertIn("~islogical", source)
        self.assertIn("isreal", source)
        self.assertIn("isfinite", source)
        self.assertIn("maxJobs = 10000", source)
        self.assertIn("maxTimestampTicks = 1e12", source)
        self.assertIn("any(~isfinite(derivedTimes(:)))", source)
        self.assertIn("any(~isfinite(scaledTimes(:)))", source)
        self.assertIn("any(abs(scaledTimes(:)) > maxTimestampTicks)", source)
        compact = re.sub(r"\s+", "", source).replace("...", "")
        self.assertIn(
            "captureScaledMagnitude=max(ones(1,jobCount),"
            "max(abs(releaseScaledTick),max(abs(startScaledTick),"
            "abs(completionScaledTick))))",
            compact,
        )
        self.assertIn(
            "captureComparisonToleranceTicks=8.*eps(captureScaledMagnitude)",
            compact,
        )
        self.assertEqual(
            compact.count("captureComparisonToleranceTicks);"),
            3,
        )

    def test_scenario_is_seedless_bounded_and_model_compatible(self):
        scenario = matlab_code_without_comments(read("p12_scenario.m")).lower()
        for name in (
            "baseline",
            "completion-jitter-trap",
            "coarse-clock",
            "timeout-continue",
            "timeout-cancel",
            "deadline-boundary",
        ):
            with self.subTest(name=name):
                self.assertIn(name, scenario)
        for field in (
            "period_ms",
            "job_count",
            "release_offset_ms",
            "execution_ms",
            "blocking_ms",
            "interference_ms",
            "deadline_ms",
            "timestamp_tick_ms",
            "response_timeout_ms",
            "timeout_action",
        ):
            with self.subTest(field=field):
                self.assertIn(field, scenario)
        self.assertIn("100", scenario)
        self.assertNotRegex(scenario, r"\b(?:rng|rand|randn|while|timer|pause)\b")

    def test_independent_baseline_timestamps_equations_and_metrics(self):
        result = timestamp_reference()
        self.assertEqual(result["nominal"], [0, 20, 40, 60, 80, 100, 120, 140])
        self.assertEqual(result["actual"], [0, 21, 39, 60, 81, 99, 120, 141])
        self.assertEqual(result["start"], [0, 22, 40, 61, 83, 100, 121, 145])
        self.assertEqual(result["finish"], [2, 24, 42, 63, 85, 102, 123, 147])
        self.assertEqual(result["response"], [2, 3, 3, 3, 4, 3, 3, 6])
        self.assertEqual(result["nominal_latency"], [2, 4, 2, 3, 5, 2, 3, 7])
        self.assertEqual(result["release_jitter_pp"], 2)
        self.assertEqual(result["response_jitter_pp"], 4)
        self.assertEqual(result["observed_worst"], 6)
        self.assertEqual(result["component_envelope"], 6)
        self.assertEqual(result["deadline_miss"], [False] * 8)
        self.assertEqual(result["prefix_maximum"], [2, 3, 3, 3, 4, 4, 4, 6])

    def test_independent_two_sweeps_and_broken_completion_proxy(self):
        release_jitter: list[float] = []
        release_worst: list[float] = []
        response_jitter: list[float] = []
        nominal_worst: list[float] = []
        shape = [0, 1, -1, 0, 1, -1, 0, 1]
        for amplitude in range(4):
            result = timestamp_reference(offsets=[amplitude * value for value in shape])
            release_jitter.append(result["release_jitter_pp"])
            release_worst.append(result["observed_worst"])
            response_jitter.append(result["response_jitter_pp"])
            nominal_worst.append(max(result["nominal_latency"]))
        self.assertEqual(release_jitter, [0, 2, 4, 6])
        self.assertEqual(release_worst, [6, 6, 6, 6])
        self.assertEqual(response_jitter, [4, 4, 4, 4])
        self.assertEqual(nominal_worst, [6, 7, 8, 9])

        blocking_worst: list[float] = []
        blocking_jitter: list[float] = []
        blocking_release_jitter: list[float] = []
        blocking_misses: list[int] = []
        mask = [0, 1, 0, 1, 0, 1, 0, 1]
        for budget in range(4):
            result = timestamp_reference(blocking=[budget * value for value in mask])
            blocking_worst.append(result["observed_worst"])
            blocking_jitter.append(result["response_jitter_pp"])
            blocking_release_jitter.append(result["release_jitter_pp"])
            blocking_misses.append(sum(result["deadline_miss"]))
        self.assertEqual(blocking_worst, [5, 6, 7, 8])
        self.assertEqual(blocking_jitter, [3, 4, 5, 6])
        self.assertEqual(blocking_release_jitter, [2, 2, 2, 2])
        self.assertEqual(blocking_misses, [0, 0, 0, 1])

        broken = timestamp_reference(offsets=0)
        self.assertEqual(broken["release_jitter_pp"], 0)
        self.assertEqual(broken["completion_deviation"], [1, 0, 0, 1, -1, 0, 3])
        self.assertEqual(
            max(broken["completion_deviation"]) - min(broken["completion_deviation"]),
            4,
        )

    def test_independent_quantization_timeout_cancellation_and_limits(self):
        coarse = timestamp_reference(period=10, offsets=0, tick=4)
        self.assertEqual(coarse["response"], [2, 3, 3, 3, 4, 3, 3, 6])
        self.assertEqual(coarse["measured_response"], [0, 4, 0, 4, 4, 4, 0, 8])
        for reference, measured in zip(coarse["response"], coarse["measured_response"]):
            self.assertLess(abs(reference - measured), 4)

        exact = timestamp_reference(timeout=6, action="cancel-observation")
        self.assertFalse(any(exact["timed_out"]))
        self.assertFalse(any(exact["censored"]))
        self.assertEqual(exact["measured_worst"], 6)

        continued = timestamp_reference(timeout=5)
        self.assertEqual(continued["timed_out"], [False] * 7 + [True])
        self.assertFalse(any(continued["censored"]))
        self.assertEqual(continued["measured_worst"], 6)

        cancelled = timestamp_reference(timeout=5, action="cancel-observation")
        self.assertEqual(cancelled["censored"], [False] * 7 + [True])
        self.assertEqual(cancelled["measured_response"], [2, 3, 3, 3, 4, 3, 3, None])
        self.assertEqual(cancelled["measured_worst"], 4)
        self.assertEqual(cancelled["finish"][-1], 147)

        all_censored = timestamp_reference(timeout=1, action="cancel-observation")
        self.assertTrue(all(all_censored["censored"]))
        self.assertIsNone(all_censored["measured_worst"])
        self.assertIsNone(all_censored["measured_jitter_pp"])

        one = timestamp_reference(
            offsets=0,
            execution=2,
            blocking=1,
            interference=3,
            count=1,
        )
        self.assertEqual(one["release_jitter_pp"], 0)
        self.assertEqual(one["response_jitter_pp"], 0)
        self.assertEqual(one["completion_deviation"], [])

        exponent = 2.0**20
        lower_ulp = math.ulp(exponent - 1)
        release = exponent - 9 * lower_ulp
        finish = exponent + 1 - 14 * lower_ulp
        boundary = timestamp_reference(
            period=20,
            offsets=release,
            execution=finish - release,
            blocking=0,
            interference=0,
            deadline=2,
            tick=1,
            count=1,
        )
        self.assertEqual(boundary["captured_release"], [exponent])
        self.assertEqual(boundary["captured_finish"], [exponent + 1])
        self.assertEqual(boundary["measured_response"], [1])
        self.assertLess(
            abs(boundary["measured_response"][0] - boundary["response"][0]),
            1,
        )

        coarse_cancel = timestamp_reference(
            period=10,
            offsets=[3, 0],
            execution=[1, 2],
            blocking=0,
            interference=0,
            deadline=10,
            tick=4,
            timeout=1.5,
            action="cancel-observation",
            count=2,
        )
        self.assertEqual(coarse_cancel["response"], [1, 2])
        self.assertEqual(coarse_cancel["measured_response"], [4, None])
        self.assertEqual(coarse_cancel["incomplete_worst_lower_bound"], 1.5)
        self.assertLessEqual(
            coarse_cancel["incomplete_worst_lower_bound"],
            coarse_cancel["observed_worst"],
        )

        large_responses = [1e308, 1e308]
        self.assertTrue(math.isinf(sum(large_responses)))
        scale = max(map(abs, large_responses))
        stable_mean = scale * (
            sum(value / scale for value in large_responses)
            / len(large_responses)
        )
        self.assertEqual(stable_mean, 1e308)
        self.assertLess(stable_mean, sys.float_info.max)

        near_negative_offset = -1e308 + 1e293
        second_release = 1e308 + near_negative_offset
        self.assertGreater(second_release, 0)
        old_completion_deviation = (second_release - 1e308) - 1e308
        self.assertTrue(math.isinf(old_completion_deviation))
        self.assertLess(old_completion_deviation, 0)


class P12LearningAndRegressionTests(unittest.TestCase):
    def test_experiment_has_baseline_two_isolated_sweeps_and_broken_case(self):
        experiment = read("experiment.m").lower()
        compact = re.sub(r"\s+", "", experiment).replace("...", "")
        self.assertIn("%% baseline", experiment)
        self.assertIn("isequaln(baseline,baselinerepeat)", compact)
        self.assertGreaterEqual(experiment.count("%% sweep"), 2)
        self.assertIn("releaseamplitudesweepms = [0 1 2 3]", experiment)
        self.assertIn("blockingbudgetsweepms = [0 1 2 3]", experiment)
        self.assertIn("isequal(releasejitterppms, [0 2 4 6])", experiment)
        self.assertIn("isequal(observedworstresponsems, [6 6 6 6])", experiment)
        self.assertIn("isequal(worstnominallatencyms, [6 7 8 9])", experiment)
        self.assertIn("isequal(blockingworstresponsems, [5 6 7 8])", experiment)
        self.assertIn("isequal(blockingresponsejitterppms, [3 4 5 6])", experiment)
        self.assertIn("isequal(deadlinemisscount, [0 0 0 1])", experiment)
        self.assertIn("%% broken case", experiment)
        self.assertIn("p12_scenario('completion-jitter-trap')", experiment)
        self.assertIn("isequaln(recovered,baseline)", compact)
        self.assertIn("p12_scenario('coarse-clock')", experiment)
        self.assertIn("p12_scenario('timeout-continue')", experiment)
        self.assertIn("p12_scenario('timeout-cancel')", experiment)
        self.assertIn("isequaln(rollback,baseline)", compact)
        self.assertGreaterEqual(experiment.count("figure("), 5)
        self.assertIn("xlabel(", experiment)
        self.assertIn("ylabel(", experiment)
        self.assertIn("(ms)", experiment)
        self.assertIn("mechanism for sweep 1", experiment)
        self.assertIn("mechanism for sweep 2", experiment)
        self.assertIn("must isolate", experiment)

    def test_interactive_exposes_meaningful_controls_scenarios_and_two_views(self):
        interactive = re.sub(r"\s+", " ", read("interactive.m").lower())
        self.assertIn("uifigure(", interactive)
        self.assertGreaterEqual(interactive.count("uispinner("), 1)
        self.assertGreaterEqual(interactive.count("uidropdown("), 2)
        for label in (
            "release-offset amplitude (ms)",
            "p11 blocking bound (ms)",
            "nominal period (ms)",
            "own execution c (ms)",
            "relative deadline d (ms)",
            "timestamp tick (ms)",
            "response timeout (ms; 0=off)",
            "timeout action",
            "scenario",
        ):
            with self.subTest(label=label):
                self.assertIn(label, interactive)
        self.assertGreaterEqual(interactive.count("uiaxes("), 2)
        self.assertIn("valuechangedfcn", interactive)
        self.assertIn("completion spacing trap (fixed)", interactive)
        self.assertIn("coarse timestamp clock (fixed)", interactive)
        self.assertIn("cancel rare observation (fixed)", interactive)
        self.assertIn("not matlab-runtime", interactive)
        self.assertIn("finite trace is not a wcrt guarantee", interactive)

    def test_interactive_callbacks_bind_p12_dependencies_before_path_cleanup(self):
        interactive = matlab_code_without_comments(read("interactive.m")).lower()
        compact = re.sub(r"\s+", "", interactive).replace("...", "")
        self.assertIn("modelfcn=@model;", compact)
        self.assertIn("scenariofcn=@p12_scenario;", compact)
        callback_region = compact[compact.index("functionupdateviews") :]
        self.assertIn("scenariofcn(", callback_region)
        self.assertIn("modelfcn(", callback_region)
        self.assertNotRegex(callback_region, r"(?<!model)\bmodel\(")

    def test_fixed_diagnostics_reset_controls_before_rendering(self):
        interactive = re.sub(
            r"\s+", "", matlab_code_without_comments(read("interactive.m")).lower()
        ).replace("...", "")
        selector = interactive[
            interactive.index("functionselectscenario") : interactive.index(
                "functionupdateviews"
            )
        ]
        self.assertIn("fixedinput=scenariofcn(", selector)
        for control in (
            "releaseamplitudecontrol",
            "blockingbudgetcontrol",
            "periodcontrol",
            "executioncontrol",
            "deadlinecontrol",
            "timestamptickcontrol",
            "responsetimeoutcontrol",
            "timeoutactioncontrol",
        ):
            with self.subTest(control=control):
                self.assertIn(f"{control}.value=", selector)
        self.assertIn("controls{controlindex}.enable='off';", selector)
        self.assertLess(selector.rindex(".value="), selector.index("updateviews();"))

    def test_executable_checks_cover_full_measurement_failure_contract(self):
        checks = matlab_code_without_comments(read("run_checks.m"))
        lower = checks.lower()
        self.assertGreaterEqual(len(re.findall(r"\bassert\s*\(", checks)), 65)
        marker_groups = {
            "determinism": ("deterministic and state-isolated",),
            "timestamp order": ("start after release",),
            "response equation": ("b+i+c",),
            "nominal identity": ("j+r",),
            "prefix maximum": ("longer prefix",),
            "deadline": ("equal to deadline",),
            "clock": ("strictly below one tick",),
            "exponent boundary": ("across an exponent boundary",),
            "tolerance isolation": ("unrelated far-future job",),
            "timeout": ("equal to timeout",),
            "cancellation": ("cancel-observation",),
            "censoring": ("no fake response",),
            "rollback": ("roll back exactly",),
            "recovery": ("recover exact baseline",),
            "compatibility": ("integer-class scalars",),
            "callback": ("callback-bound p12 dependencies",),
            "resource": ("10,000-job resource bound",),
            "finite mean": ("finite large-response mean",),
            "derived overflow": ("nearnegativeoffset",),
            "isolation": ("must isolate",),
            "finite trace": ("wcrt guarantee",),
        }
        for contract, alternatives in marker_groups.items():
            with self.subTest(contract=contract):
                self.assertTrue(any(marker in lower for marker in alternatives))
        for identifier in (
            "p12:model:arity",
            "p12:model:period",
            "p12:model:jobcount",
            "p12:model:jobresourcebound",
            "p12:model:releaseoffset",
            "p12:model:releaseoffsetlength",
            "p12:model:execution",
            "p12:model:executionlength",
            "p12:model:blocking",
            "p12:model:blockinglength",
            "p12:model:interference",
            "p12:model:interferencelength",
            "p12:model:deadline",
            "p12:model:timestamptick",
            "p12:model:responsetimeout",
            "p12:model:timeoutaction",
            "p12:model:releaseorder",
            "p12:model:timingresourcebound",
            "p12:model:timingprecision",
        ):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, lower)
        self.assertIn("malformed call must not contaminate", lower)
        self.assertIn("not an asynchronous rtos cancellation api", lower)
        self.assertIn("p12 checks passed", lower)

    def test_tutor_text_is_mechanism_first_and_ends_in_teach_back(self):
        lesson = re.sub(r"\s+", " ", read("lesson.md").lower())
        walkthrough = read("walkthrough.md").lower()
        checks = read("checks.md").lower()
        self.assertEqual(lesson.count("## one prediction"), 1)
        self.assertIn("j_k = a_k - n_k", lesson)
        self.assertIn("r_k = f_k - a_k = b_k + i_k + c_k", lesson)
        self.assertIn("l_k = f_k - n_k = j_k + r_k", lesson)
        self.assertIn("j_release,pp", lesson)
        self.assertIn("j_response,pp", lesson)
        self.assertIn("p11", lesson)
        self.assertIn("completion spacing", lesson)
        self.assertIn("cancel-observation", lesson)
        self.assertIn("move one lever", walkthrough)
        self.assertIn("reset", walkthrough)
        self.assertIn("interpretation", checks)
        self.assertIn("teach-back", checks)

    def test_claim_language_separates_model_runtime_rtos_and_physical_evidence(self):
        combined = "\n".join(
            read(name).lower()
            for name in ("README.md", "lesson.md", "checks.md", "experiment.m")
        )
        self.assertIn("synthetic", combined)
        self.assertIn("not matlab-runtime", combined)
        self.assertIn("finite trace", combined)
        self.assertIn("not a wcrt guarantee", combined)
        self.assertIn("rtos", combined)
        self.assertIn("processor", combined)
        self.assertIn("hardware", combined)
        self.assertIn("measured wcet/wcrt", combined)
        self.assertIn("p11", combined)
        self.assertIn("p13", combined)
        self.assertNotIn("hardware-validated", combined)
        self.assertNotIn("rtos-validated", combined)

    def test_cli_start_routes_p12_and_persists_only_isolated_progress(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary) / "repo"
            fixture.mkdir()
            shutil.copytree(ROOT / "bin", fixture / "bin")
            shutil.copytree(ROOT / "curriculum", fixture / "curriculum")
            module_fixture = (
                fixture / "modules/12-measure-jitter-and-worst-case-response-time"
            )
            module_fixture.mkdir(parents=True)
            for name in ("README.md", "lesson.md", "walkthrough.md", "checks.md"):
                shutil.copy2(MODULE_FOLDER / name, module_fixture / name)

            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            result = subprocess.run(
                [str(fixture / "bin/learn"), "start", "P12"],
                cwd=fixture,
                text=True,
                capture_output=True,
                env=environment,
                timeout=10,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                result.stdout,
                "P12 — Measure Jitter and Worst-Case Response Time\n"
                "Status: implemented\n"
                f"Guiding question: {QUESTION}\n"
                "Folder: modules/12-measure-jitter-and-worst-case-response-time\n"
                "\nMATLAB:\n"
                "  launch_lesson('P12')\n"
                "\nTutor files:\n"
                "  modules/12-measure-jitter-and-worst-case-response-time/README.md\n"
                "  modules/12-measure-jitter-and-worst-case-response-time/lesson.md\n"
                "  modules/12-measure-jitter-and-worst-case-response-time/walkthrough.md\n"
                "  modules/12-measure-jitter-and-worst-case-response-time/checks.md\n",
            )
            progress = json.loads(
                (fixture / ".learning/progress.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                progress, {"current": "P12", "completed": {}, "notes": {}}
            )

    def test_cli_check_resolves_p12_public_matlab_entry_point(self):
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [str(ROOT / "bin/learn"), "check", "P12"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env=environment,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "Run in MATLAB: run_module_checks('P12')\n")

    @unittest.skipUnless(shutil.which("matlab"), "MATLAB executable unavailable")
    def test_matlab_executes_module_checks_and_callback_lifetime(self):
        result = subprocess.run(
            [shutil.which("matlab"), "-batch", "run_module_checks('P12')"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=300,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"MATLAB P12 checks failed:\n{result.stdout}\n{result.stderr}",
        )
        self.assertIn("P12 checks passed", result.stdout)


class P12RetainedEvidenceTests(unittest.TestCase):
    def test_date_agnostic_retained_evidence_is_complete_and_honest(self):
        evidence_files = sorted((ROOT / "docs/evidence").glob("P12-*.md"))
        self.assertTrue(evidence_files, "P12 requires a retained evidence record")
        for path in evidence_files:
            with self.subTest(path=path.name):
                payload = path.read_bytes()
                self.assertTrue(payload.endswith(b"\n"))
                self.assertFalse(payload.endswith(b"\n\n"))
                text = payload.decode("utf-8").lower()
                for unfinished in (
                    "pending final retained result",
                    "<source-focused p12 test selectors>",
                ):
                    with self.subTest(path=path.name, unfinished=unfinished):
                        self.assertNotIn(unfinished, text)
                for marker in (
                    "## result and claim boundary",
                    "## acceptance mapping",
                    "## deterministic model and failure contract",
                    "## figure, control, metric, and unit inventory",
                    "## runtime inventory",
                    "## exact commands and results",
                    "matlab_learning_verify_profile=contract",
                    "python3 scripts/verify.py",
                    "matlab_learning_verify_profile=quick",
                    "python3 -m unittest discover -s tests -v",
                    "matlab_learning_verify_profile=full",
                    "./scripts/agent-verify.sh",
                    "## changed invariants",
                    "## preserved invariants and scope",
                    "## profile applicability",
                    "## rollback",
                    "## residual risks",
                    "## unperformed validation",
                    "static validation",
                    "matlab runtime",
                    "ui",
                    "numerical",
                    "rtos",
                    "processor",
                    "hardware",
                    "bench",
                    "hil",
                    "field",
                    "rt1/rt2",
                    "unreal",
                    "signing",
                    "release",
                    "deployment",
                    "staging",
                    "production",
                    "not performed",
                    "portfolio control validation",
                    "target quality workflow",
                    "no learner state is tracked or included in the batch diff",
                ):
                    with self.subTest(path=path.name, marker=marker):
                        self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
