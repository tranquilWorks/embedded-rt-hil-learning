from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
QUESTION = (
    "What inputs, observable effects, and failure modes matter when you drive GPIO "
    "with a State Machine?"
)
MODULE_FOLDER = ROOT / "modules/02-drive-gpio-with-a-state-machine"
CORE_ARTIFACTS = {
    "README.md",
    "lesson.m",
    "p02_scenario.m",
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
    return "\n".join(line.split("%", 1)[0] for line in text.splitlines())


class P02IdentityAndArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "curriculum/modules.json").read_text(encoding="utf-8"))
        cls.module = next(module for module in cls.manifest["modules"] if module["id"] == "P02")

    def test_permanent_manifest_identity_and_prerequisite(self):
        self.assertEqual(self.module["number"], 2)
        self.assertEqual(self.module["title"], "Drive GPIO with a State Machine")
        self.assertEqual(self.module["guiding_question"], QUESTION)
        self.assertEqual(self.module["folder"], "modules/02-drive-gpio-with-a-state-machine")
        self.assertEqual(self.module["implementation_batch"], "P02")
        self.assertEqual(self.module["prerequisites"], ["P01"])
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
                self.assertLess(len(payload), 50000, "educational artifact should stay bounded")

    def test_guiding_question_prerequisite_and_claim_boundary_are_explicit(self):
        combined = "\n".join(read(name) for name in ("README.md", "lesson.md", "walkthrough.md"))
        self.assertIn(QUESTION, combined)
        self.assertIn("P01", read("lesson.md"))
        self.assertIn("sampled", read("lesson.md").lower())
        self.assertIn("not a hardware measurement", combined.lower())

    def test_no_scaffold_or_placeholder_residue(self):
        combined = "\n".join(read(name).lower() for name in CORE_ARTIFACTS)
        for residue in ("scaffolded", "activate its governed", "todo", "tbd", "placeholder"):
            with self.subTest(residue=residue):
                self.assertNotIn(residue, combined)


class P02ModelContractTests(unittest.TestCase):
    def test_model_is_explicit_deterministic_and_resource_bounded(self):
        model = read("model.m")
        code = matlab_code_without_comments(model).lower()
        compact = re.sub(r"\s+", "", code)
        self.assertIn(
            "functionout=model(rawbutton,sampleperiodms,debouncems,maxonms,cancel)", compact
        )
        self.assertIn("debouncesamples=max(1,ceil(debounceratio));", compact)
        self.assertIn("timeoutsamples=floor(timeoutratio);", compact)
        self.assertIn("maxonms=double(maxonms);", compact)
        for state in ("idle", "qualify_press", "active", "qualify_release", "lockout"):
            self.assertRegex(code, rf"\b{state}\s*=\s*uint8\(")
        self.assertIn("state == active || state == qualify_release", code)
        self.assertIn("for sampleindex = 1:samplecount", code)
        self.assertIn("maxsamples = 1000000", code)
        self.assertIn("false(1, samplecount)", code)
        self.assertIn("zeros(1, samplecount, 'uint8')", code)
        self.assertNotRegex(
            code,
            r"\b(?:persistent|global|while|rng|rand|randn|pause|timer|eval|system)\b",
        )
        self.assertLess(
            code.index("samplecount = numel(rawbutton)"),
            code.index("validatebinaryvectorvalues(rawbutton"),
            "resource size must be checked before scanning signal values",
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
            "writedigitalpin",
            "configurepin",
            "digitalio",
            "fopen",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotRegex(code, rf"\b{forbidden}\s*\(")
        self.assertNotIn("stateflow", code)

    def test_model_rejects_malformed_signals_timing_and_oversized_inputs(self):
        model = read("model.m")
        for identifier in (
            "P02:model:Arity",
            "P02:model:RawButton",
            "P02:model:Cancel",
            "P02:model:LengthMismatch",
            "P02:model:SamplePeriod",
            "P02:model:Debounce",
            "P02:model:MaxOn",
            "P02:model:MaxOnResolution",
            "P02:model:ResourceBound",
            "P02:model:TimingResourceBound",
        ):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, model)
        self.assertIn("isvector", model)
        self.assertIn("isfinite", model)
        self.assertIn("isreal", model)

    def test_scenario_is_seedless_bounded_and_compatible(self):
        scenario = matlab_code_without_comments(read("p02_scenario.m")).lower()
        self.assertIn("function input = p02_scenario(", scenario)
        for name in ("normal", "stuck-high", "cancel-recovery"):
            self.assertIn(name, scenario)
        self.assertIn("maxsamples = 1000000", scenario)
        self.assertIn("p02:scenario:resourcebound", scenario)
        self.assertIn("sampleperiodms = double(sampleperiodms)", scenario)
        self.assertNotRegex(scenario, r"\b(?:rng|rand|randn|while|timer|pause)\b")


class P02LearningAndRegressionTests(unittest.TestCase):
    def test_experiment_has_baseline_two_independent_sweeps_and_broken_case(self):
        experiment = read("experiment.m").lower()
        self.assertIn("%% baseline", experiment)
        self.assertGreaterEqual(experiment.count("%% sweep"), 2)
        self.assertIn("debouncesweepms = [0 3 7]", experiment)
        self.assertIn("maxonsweepms = [15 30 55]", experiment)
        self.assertIn("stuckinput = p02_scenario('stuck-high'", experiment)
        self.assertIn("%% broken case", experiment)
        self.assertIn("broken = model", experiment)
        self.assertIn("broken.metrics.gpio_rising_edges > qualified.metrics.gpio_rising_edges", experiment)
        self.assertGreaterEqual(experiment.count("figure("), 4)
        self.assertIn("xlabel(", experiment)
        self.assertIn("ylabel(", experiment)
        self.assertIn("time (ms)", experiment)
        self.assertIn("event count", experiment)
        self.assertIn("mechanism for sweep 1", experiment)
        self.assertIn("mechanism for sweep 2", experiment)
        compact = re.sub(r"\s+", "", experiment).replace("...", "")
        self.assertIn(
            "swept=model(baselineinput.raw_button,sampleperiodms,"
            "debouncesweepms(sweepindex),maxonms,baselineinput.cancel);",
            compact,
        )
        self.assertIn(
            "swept=model(stuckinput.raw_button,sampleperiodms,debouncems,"
            "maxonsweepms(sweepindex),stuckinput.cancel);",
            compact,
        )

    def test_interactive_exposes_meaningful_controls_and_two_views(self):
        interactive = read("interactive.m").lower()
        self.assertIn("uifigure(", interactive)
        self.assertGreaterEqual(interactive.count("uispinner("), 3)
        self.assertIn("uidropdown(", interactive)
        self.assertIn("debounce (ms)", interactive)
        self.assertIn("maximum on (ms)", interactive)
        self.assertIn("contact bounce (ms)", interactive)
        self.assertIn("valuechangedfcn", interactive)
        self.assertIn("@model", interactive)
        self.assertIn("@p02_scenario", interactive)
        self.assertGreaterEqual(interactive.count("uiaxes("), 2)
        self.assertIn("not a hardware measurement", interactive)

    def test_interactive_callbacks_bind_p02_dependencies_before_path_cleanup(self):
        interactive = matlab_code_without_comments(read("interactive.m")).lower()
        compact = re.sub(r"\s+", "", interactive).replace("...", "")
        self.assertIn("modelfcn=@model;", compact)
        self.assertIn("scenariofcn=@p02_scenario;", compact)
        self.assertIn("input=scenariofcn(scenarioname,1,120,bouncecontrol.value);", compact)
        self.assertIn(
            "out=modelfcn(input.raw_button,input.sample_period_ms,"
            "debouncecontrol.value,maxoncontrol.value,input.cancel);",
            compact,
        )

    def test_executable_checks_cover_positive_negative_timeout_cancel_and_recovery(self):
        checks = matlab_code_without_comments(read("run_checks.m"))
        lower = checks.lower()
        self.assertGreaterEqual(len(re.findall(r"\bassert\s*\(", checks)), 35)
        for marker in (
            "constant-low input must stay idle",
            "pulse shorter than n_d",
            "exactly n_t high samples",
            "same-sample safe-low lockout",
            "re-arm idle",
            "prove recovery",
            "repeated calls must be deterministic and state-isolated",
            "callback-bound p02 dependencies must survive module path cleanup",
            "debounce bypass must expose extra gpio edges",
            "p02:model:rawbutton",
            "p02:model:lengthmismatch",
            "p02:model:sampleperiod",
            "p02:model:debounce",
            "p02:model:maxon",
            "p02:model:maxonresolution",
            "p02:model:resourcebound",
            "p02:model:timingresourcebound",
            "p02:scenario:resourcebound",
            "p02 checks passed",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, lower)

    def test_tutor_text_is_mechanism_first_and_ends_in_teach_back(self):
        lesson = read("lesson.md").lower()
        walkthrough = read("walkthrough.md").lower()
        checks = read("checks.md").lower()
        self.assertIn("n_d = max(1, ceil", lesson)
        self.assertIn("n_t = floor", lesson)
        self.assertEqual(lesson.count("## one prediction"), 1)
        self.assertIn("move one control", walkthrough)
        self.assertIn("reset", walkthrough)
        self.assertIn("interpretation", checks)
        self.assertIn("teach-back", checks)
        self.assertIn("mechanism first", walkthrough)


class P02RetainedEvidenceTests(unittest.TestCase):
    def test_date_agnostic_retained_evidence_is_complete_and_honest(self):
        evidence_files = sorted((ROOT / "docs/evidence").glob("P02-*.md"))
        self.assertTrue(evidence_files, "P02 requires a retained evidence record")
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
                    "## rollback",
                    "## residual risks",
                    "## unperformed validation",
                    "matlab runtime",
                    "not performed",
                ):
                    self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
