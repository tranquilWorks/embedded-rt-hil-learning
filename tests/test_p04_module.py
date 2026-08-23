from __future__ import annotations

import json
import math
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
QUESTION = (
    "What inputs, observable effects, and failure modes matter when you measure "
    "Timer Quantization?"
)
MODULE_FOLDER = ROOT / "modules/04-measure-timer-quantization"
CORE_ARTIFACTS = {
    "README.md",
    "lesson.m",
    "p04_scenario.m",
    "model.m",
    "experiment.m",
    "interactive.m",
    "lesson.md",
    "walkthrough.md",
    "checks.md",
    "run_checks.m",
}


def read(name: str) -> str:
    return (MODULE_FOLDER / name).read_text(encoding="utf-8")


def matlab_code_without_comments(text: str) -> str:
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


class P04IdentityAndArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "curriculum/modules.json").read_text(encoding="utf-8"))
        cls.module = next(module for module in cls.manifest["modules"] if module["id"] == "P04")

    def test_permanent_manifest_identity_and_prerequisite(self):
        self.assertEqual(self.module["number"], 4)
        self.assertEqual(self.module["title"], "Measure Timer Quantization")
        self.assertEqual(self.module["guiding_question"], QUESTION)
        self.assertEqual(
            self.module["folder"], "modules/04-measure-timer-quantization"
        )
        self.assertEqual(self.module["implementation_batch"], "P04")
        self.assertEqual(self.module["prerequisites"], ["P03"])
        self.assertEqual(self.module["status"], "implemented")
        self.assertEqual(self.module["evidence_level"], "simulated")

    def test_complete_artifact_set_has_clean_terminal_newlines(self):
        names = {path.name for path in MODULE_FOLDER.iterdir() if path.is_file()}
        self.assertTrue(CORE_ARTIFACTS <= names)
        for name in CORE_ARTIFACTS:
            with self.subTest(name=name):
                payload = (MODULE_FOLDER / name).read_bytes()
                self.assertTrue(payload.endswith(b"\n"))
                self.assertFalse(payload.endswith(b"\n\n"))
                self.assertLess(len(payload), 75000, "educational artifact should stay bounded")

    def test_guiding_question_prerequisite_and_claim_boundary_are_explicit(self):
        combined = "\n".join(read(name) for name in ("README.md", "lesson.md", "walkthrough.md"))
        self.assertIn(QUESTION, combined)
        self.assertIn("P03", read("lesson.md"))
        self.assertIn("event", read("lesson.md").lower())
        self.assertIn("not a hardware measurement", combined.lower())
        self.assertIn("resolution is not oscillator accuracy", combined.lower())

    def test_no_scaffold_placeholder_or_opaque_residue(self):
        combined = "\n".join(read(name).lower() for name in CORE_ARTIFACTS)
        for residue in (
            "scaffolded",
            "activate its governed",
            "todo",
            "tbd",
            "placeholder",
            "black box",
        ):
            with self.subTest(residue=residue):
                self.assertNotIn(residue, combined)


class P04ModelContractTests(unittest.TestCase):
    def test_model_is_explicit_deterministic_vectorized_and_resource_bounded(self):
        model = read("model.m")
        code = matlab_code_without_comments(model).lower()
        compact = re.sub(r"\s+", "", code).replace("...", "")
        self.assertIn(
            "functionout=model(starttimeus,trueintervalus,tickperiodus,"
            "timerphaseus,counterbits)",
            compact,
        )
        self.assertIn("countermodulus=2^counterbits;", compact)
        self.assertIn(
            "modularelapsedticks=mod(endcount-startcount,countermodulus);", compact
        )
        self.assertIn(
            "measurementvalid=fullelapsedticks<countermodulus;", compact
        )
        self.assertIn(
            "measuredintervalus(measurementrangeambiguous)=nan;", compact
        )
        self.assertIn("naiveelapsedticks=endcount-startcount;", compact)
        self.assertIn(
            "pairscaledmagnitude=max(ones(size(scaledstarttick)),"
            "max(abs(scaledstarttick),abs(scaledendtick)));",
            compact,
        )
        self.assertIn(
            "comparisontoleranceticks=8.*eps(pairscaledmagnitude);", compact
        )
        self.assertNotIn("maxscaledmagnitude", compact)
        self.assertIn(
            "startfulltick=quantizedtick(scaledstarttick,comparisontoleranceticks);",
            compact,
        )
        self.assertIn(
            "endfulltick=quantizedtick(scaledendtick,comparisontoleranceticks);",
            compact,
        )
        self.assertIn("'normalization_tolerance_us'", code)
        self.assertIn("maxmeasurements=1000000", compact)
        self.assertIn("maxfulltick=1e12", compact)
        self.assertNotRegex(
            code,
            r"\b(?:persistent|global|while|rng|rand|randn|eval|system)\b",
        )
        self.assertNotRegex(code, r"\b(?:pause|timer)\s*\(")
        self.assertLess(
            code.index("measurementcount = numel(starttimeus)"),
            code.index("starttimeus = validatevector"),
            "resource size must be bounded before scanning capture values",
        )
        self.assertLess(
            code.index("intervalcount = numel(trueintervalus)"),
            code.index("trueintervalus = validatevector"),
            "interval size must be bounded before scanning interval values",
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
            "arduino",
            "digitalio",
            "fopen",
            "timetable",
            "timeseries",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotRegex(code, rf"\b{forbidden}\s*\(")
        self.assertNotIn("simulink", code)
        self.assertNotIn("stateflow", code)

    def test_model_rejects_malformed_timing_counter_and_oversized_inputs(self):
        model = read("model.m")
        for identifier in (
            "P04:model:Arity",
            "P04:model:StartTime",
            "P04:model:TrueInterval",
            "P04:model:LengthMismatch",
            "P04:model:StartBounds",
            "P04:model:IntervalBounds",
            "P04:model:TickPeriod",
            "P04:model:TimerPhase",
            "P04:model:CounterBits",
            "P04:model:ResourceBound",
            "P04:model:TimingResourceBound",
        ):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, model)
        self.assertIn("isvector", model)
        self.assertIn("isfinite", model)
        self.assertIn("isreal", model)

    def test_scenario_is_seedless_bounded_and_compatible(self):
        scenario = matlab_code_without_comments(read("p04_scenario.m")).lower()
        self.assertIn("function input = p04_scenario(", scenario)
        for name in ("baseline", "wrap-recovery", "range-recovery"):
            self.assertIn(name, scenario)
        self.assertIn("trueintervalus = double(trueintervalus)", scenario)
        self.assertNotRegex(scenario, r"\b(?:rng|rand|randn|while|timer|pause)\b")

    def test_independent_reference_fixture_retains_expected_quantization(self):
        starts = [100 + index * 37 for index in range(12)]
        elapsed_ticks = [
            math.floor((start + 37) / 10) - math.floor(start / 10)
            for start in starts
        ]
        errors = [ticks * 10 - 37 for ticks in elapsed_ticks]
        self.assertEqual(elapsed_ticks, [3, 4, 4, 3, 4, 4, 3, 4, 4, 4, 3, 4])
        self.assertEqual(errors, [-7, 3, 3, -7, 3, 3, -7, 3, 3, 3, -7, 3])
        self.assertTrue(all(abs(error) < 10 for error in errors))
        near_boundary_gap = 1.0 - 0.9995
        self.assertGreater(near_boundary_gap, 8 * math.ulp(1.0))
        self.assertLess(near_boundary_gap, 8 * math.ulp(1e12))


class P04LearningAndRegressionTests(unittest.TestCase):
    def test_experiment_has_baseline_two_independent_sweeps_and_broken_case(self):
        experiment = read("experiment.m").lower()
        compact = re.sub(r"\s+", "", experiment).replace("...", "")
        self.assertIn("%% baseline", experiment)
        self.assertGreaterEqual(experiment.count("%% sweep"), 2)
        self.assertIn("tickperiodsweepus = [1 2 5 10 20]", experiment)
        self.assertIn("phasesweepus = 0:1:9", experiment)
        self.assertIn("%% broken case", experiment)
        self.assertIn("p04_scenario('wrap-recovery', 37)", experiment)
        self.assertIn("[-2530 30]", experiment)
        self.assertIn("later non-wrapping pair must prove diagnostic recovery", experiment)
        self.assertGreaterEqual(experiment.count("figure("), 4)
        self.assertIn("xlabel(", experiment)
        self.assertIn("ylabel(", experiment)
        self.assertIn("interval (us)", experiment)
        self.assertIn("measurement error (us)", experiment)
        self.assertIn("timer count (ticks)", experiment)
        self.assertIn("mechanism for sweep 1", experiment)
        self.assertIn("mechanism for sweep 2", experiment)
        self.assertIn("isequaln(baseline, baselinerepeat)", experiment)
        self.assertIn("tickperiodsweepus(sweepindex)", compact)
        self.assertIn("phasesweepus(sweepindex)", compact)
        self.assertIn("roll back the broken view", experiment)

    def test_interactive_exposes_meaningful_controls_and_two_views(self):
        interactive = read("interactive.m").lower()
        self.assertIn("uifigure(", interactive)
        self.assertGreaterEqual(interactive.count("uispinner("), 4)
        self.assertIn("uidropdown(", interactive)
        self.assertIn("timer tick q (us)", interactive)
        self.assertIn("true interval (us)", interactive)
        self.assertIn("phase (tick fraction)", interactive)
        self.assertIn("counter width (bits)", interactive)
        self.assertIn("'roundfractionalvalues', 'on'", interactive)
        self.assertIn("valuechangedfcn", interactive)
        self.assertIn("@model", interactive)
        self.assertIn("@p04_scenario", interactive)
        self.assertGreaterEqual(interactive.count("uiaxes("), 2)
        self.assertIn("not a hardware measurement", interactive)
        self.assertIn("n/a (no valid interval)", interactive)
        self.assertIn("fixed q=10, b=8", interactive)
        self.assertIn("tickcontrol.enable = 'off'", interactive)
        self.assertIn("intervalcontrol.enable = 'off'", interactive)
        self.assertIn("counterbitscontrol.enable = 'off'", interactive)

    def test_interactive_callbacks_bind_p04_dependencies_before_path_cleanup(self):
        interactive = matlab_code_without_comments(read("interactive.m")).lower()
        compact = re.sub(r"\s+", "", interactive).replace("...", "")
        self.assertIn("modelfcn=@model;", compact)
        self.assertIn("scenariofcn=@p04_scenario;", compact)
        self.assertIn(
            "input=scenariofcn(scenarioname,intervalcontrol.value);", compact
        )
        self.assertIn(
            "out=modelfcn(input.start_time_us,input.true_interval_us,"
            "tickperiodus,timerphaseus,counterbitscontrol.value);",
            compact,
        )

    def test_diagnostic_scenario_resets_phase_before_fixed_wrap_view(self):
        interactive = matlab_code_without_comments(read("interactive.m")).lower()
        compact = re.sub(r"\s+", "", interactive).replace("...", "")
        selector = compact[
            compact.index("functionselectscenario") : compact.index("functionupdateviews")
        ]
        self.assertIn("phasefractioncontrol.enable='on';", selector)
        self.assertIn("phasefractioncontrol.value=0;", selector)
        self.assertIn("phasefractioncontrol.enable='off';", selector)
        self.assertLess(
            selector.index("phasefractioncontrol.value=0;"),
            selector.index("updateviews();"),
            "diagnostic phase must reset before the fixed fixture is rendered",
        )
        self.assertIn("fixedq=10,b=8,phase=0", compact)

        def wrap_capture(phase_us: float) -> tuple[int, int, int]:
            start_tick = math.floor((2550 + phase_us) / 10)
            end_tick = math.floor((2587 + phase_us) / 10)
            return start_tick % 256, end_tick % 256, (end_tick - start_tick) * 10

        self.assertEqual(wrap_capture(0), (255, 2, 30))
        self.assertEqual(
            wrap_capture(9),
            (255, 3, 40),
            "a stale phase would contradict the named 255-to-2, 30 us fixture",
        )

    def test_executable_checks_cover_limits_range_recovery_and_rejection(self):
        checks = matlab_code_without_comments(read("run_checks.m"))
        lower = checks.lower()
        self.assertGreaterEqual(len(re.findall(r"\bassert\s*\(", checks)), 45)
        for marker in (
            "empty input must retain zero paired captures",
            "zero-length interval",
            "exact two-tick interval",
            "positive sub-tick interval",
            "decimal tick boundaries",
            "distinguishably below a boundary",
            "paired endpoints across an exponent boundary",
            "unrelated far-future capture must not change",
            "normalization tolerance must remain isolated per capture pair",
            "interval error must equal stop endpoint error",
            "strict one-tick error bound",
            "baseline completed-tick deltas",
            "tick-period sweep",
            "timer-phase sweep",
            "more counter bits must extend range",
            "naive signed rollover subtraction",
            "exactly one full counter cycle must report range ambiguity",
            "multi-wrap interval",
            "widening the counter must recover",
            "roll back the broken configuration",
            "repeated calls must be deterministic and state-isolated",
            "callback-bound p04 dependencies must survive module path cleanup",
            "p04:model:starttime",
            "p04:model:trueinterval",
            "p04:model:lengthmismatch",
            "p04:model:tickperiod",
            "p04:model:timerphase",
            "p04:model:counterbits",
            "p04:model:resourcebound",
            "p04:model:timingresourcebound",
            "p04 checks passed",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, lower)

    def test_tutor_text_is_mechanism_first_and_ends_in_teach_back(self):
        lesson = re.sub(r"\s+", " ", read("lesson.md").lower())
        walkthrough = read("walkthrough.md").lower()
        checks = read("checks.md").lower()
        self.assertIn("k(t) = floor((t + phi) / q)", lesson)
        self.assertIn("c(t) = mod(k(t), 2^b)", lesson)
        self.assertIn("abs(epsilon_t) < q", lesson)
        self.assertEqual(lesson.count("## one prediction"), 1)
        self.assertIn("move one control", walkthrough)
        self.assertIn("reset", walkthrough)
        self.assertIn("interpretation", checks)
        self.assertIn("teach-back", checks)
        self.assertIn("there is no asynchronous timeout, cancellation", checks)
        self.assertIn("mechanism first", walkthrough)

    def test_claim_language_separates_resolution_accuracy_and_range(self):
        combined = "\n".join(
            read(name).lower()
            for name in ("README.md", "lesson.md", "checks.md", "experiment.m")
        )
        self.assertIn("resolution is not oscillator accuracy", combined)
        self.assertIn("more counter bits extend range", combined)
        self.assertIn("not random jitter", combined)
        self.assertIn("modular subtraction cannot", combined)
        self.assertNotIn("measured clock accuracy", combined)


class P04RetainedEvidenceTests(unittest.TestCase):
    def test_date_agnostic_retained_evidence_is_complete_and_honest(self):
        evidence_files = sorted((ROOT / "docs/evidence").glob("P04-*.md"))
        self.assertTrue(evidence_files, "P04 requires a retained evidence record")
        for path in evidence_files:
            with self.subTest(path=path.name):
                payload = path.read_bytes()
                self.assertTrue(payload.endswith(b"\n"))
                self.assertFalse(payload.endswith(b"\n\n"))
                text = payload.decode("utf-8").lower()
                for marker in (
                    "## acceptance mapping",
                    "## figure, control, metric, and unit inventory",
                    "## exact commands and results",
                    "matlab_learning_verify_profile=contract python3 scripts/verify.py",
                    "matlab_learning_verify_profile=quick python3 -m unittest discover -s tests -v",
                    "matlab_learning_verify_profile=full ./scripts/agent-verify.sh",
                    "## changed invariants",
                    "## preserved invariants and scope",
                    "## rollback",
                    "## residual risks",
                    "## unperformed validation",
                    "matlab runtime",
                    "not performed",
                ):
                    self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
