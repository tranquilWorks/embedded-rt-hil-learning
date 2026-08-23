from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
QUESTION = (
    "What inputs, observable effects, and failure modes matter when you compare "
    "Polling and Interrupts?"
)
MODULE_FOLDER = ROOT / "modules/03-compare-polling-and-interrupts"
CORE_ARTIFACTS = {
    "README.md",
    "lesson.m",
    "p03_scenario.m",
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


class P03IdentityAndArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "curriculum/modules.json").read_text(encoding="utf-8"))
        cls.module = next(module for module in cls.manifest["modules"] if module["id"] == "P03")

    def test_permanent_manifest_identity_and_prerequisite(self):
        self.assertEqual(self.module["number"], 3)
        self.assertEqual(self.module["title"], "Compare Polling and Interrupts")
        self.assertEqual(self.module["guiding_question"], QUESTION)
        self.assertEqual(
            self.module["folder"], "modules/03-compare-polling-and-interrupts"
        )
        self.assertEqual(self.module["implementation_batch"], "P03")
        self.assertEqual(self.module["prerequisites"], ["P02"])
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
        self.assertIn("P02", read("lesson.md"))
        self.assertIn("qualified", read("lesson.md").lower())
        self.assertIn("not a hardware measurement", combined.lower())
        self.assertIn("sticky", read("lesson.md").lower())

    def test_no_scaffold_placeholder_or_black_box_residue(self):
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


class P03ModelContractTests(unittest.TestCase):
    def test_model_is_explicit_deterministic_linear_and_resource_bounded(self):
        model = read("model.m")
        code = matlab_code_without_comments(model).lower()
        compact = re.sub(r"\s+", "", code).replace("...", "")
        self.assertIn(
            "functionout=model(eventtimesms,pulsewidthms,horizonms,pollperiodms,"
            "pollcheckcostms,interruptlatencyms,handlercostms,queuecapacity,maskwindowsms)",
            compact,
        )
        self.assertIn(
            "[relation,polltimems]=classifyhalfopentime(polltimems,"
            "eventtimesms(scanindex),eventendms(scanindex),comparisontolerancems)",
            compact,
        )
        self.assertIn(
            "nextpolltimems=max(polltimems+pollperiodms,workfinish);", compact
        )
        self.assertIn("outstandingbeforearrival>=queuecapacity", compact)
        self.assertIn("readyms=max(arrivalms,acceptedfinishms(acceptedcount));", compact)
        self.assertIn("dispatchcandidatems=readyms+interruptlatencyms;", compact)
        self.assertIn("maxrecords=1000000", compact)
        self.assertIn("eventendms<=eventtimesms", compact)
        self.assertIn("pollcheckcostms>0&&checkfinishms<=polltimems", compact)
        self.assertIn("interruptlatencyms>0&&dispatchcandidatems<=readyms", compact)
        self.assertIn("forboundedpollindex=1:projectedpollcount", compact)
        self.assertIn("foreventindex=1:eventcount", compact)
        self.assertNotRegex(
            code,
            r"\b(?:persistent|global|while|rng|rand|randn|pause|timer|eval|system)\b",
        )
        self.assertLess(
            code.index("eventcount = numel(eventtimesms)"),
            code.index("validateeventvalues(eventtimesms)"),
            "event size must be bounded before scanning event values",
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
        self.assertNotIn("stateflow", code)
        self.assertNotIn("simulink", code)

    def test_model_rejects_malformed_timing_capacity_and_oversized_inputs(self):
        model = read("model.m")
        for identifier in (
            "P03:model:Arity",
            "P03:model:EventTimes",
            "P03:model:PulseWidth",
            "P03:model:EventOrder",
            "P03:model:EventBounds",
            "P03:model:PulseOverlap",
            "P03:model:Horizon",
            "P03:model:PollPeriod",
            "P03:model:PollCheckCost",
            "P03:model:InterruptLatency",
            "P03:model:HandlerCost",
            "P03:model:QueueCapacity",
            "P03:model:MaskWindows",
            "P03:model:MaskOrder",
            "P03:model:ResourceBound",
            "P03:model:TimingResourceBound",
        ):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, model)
        self.assertIn("isvector", model)
        self.assertIn("isfinite", model)
        self.assertIn("isreal", model)

    def test_scenario_is_seedless_bounded_and_compatible(self):
        scenario = matlab_code_without_comments(read("p03_scenario.m")).lower()
        self.assertIn("function input = p03_scenario(", scenario)
        for name in ("mixed", "sparse", "burst-recovery"):
            self.assertIn(name, scenario)
        self.assertIn("maxevents = 1000000", scenario)
        self.assertIn("p03:scenario:resourcebound", scenario)
        self.assertIn("pulsewidthms = double(pulsewidthms)", scenario)
        self.assertNotRegex(scenario, r"\b(?:rng|rand|randn|while|timer|pause)\b")


class P03LearningAndRegressionTests(unittest.TestCase):
    def test_experiment_has_baseline_two_independent_sweeps_and_broken_case(self):
        experiment = read("experiment.m").lower()
        compact = re.sub(r"\s+", "", experiment).replace("...", "")
        self.assertIn("%% baseline", experiment)
        self.assertGreaterEqual(experiment.count("%% sweep"), 2)
        self.assertIn("pollperiodsweepms = [0.25 0.5 1 2]", experiment)
        self.assertIn("maskdurationsweepms = [0 1 2 4]", experiment)
        self.assertIn("%% broken case", experiment)
        self.assertIn("brokenmaskms = [6 10]", experiment)
        self.assertIn("broken.metrics.interrupt_dropped_count == 5", experiment)
        self.assertIn("post-drain event must prove interrupt-path recovery", experiment)
        self.assertGreaterEqual(experiment.count("figure("), 5)
        self.assertIn("xlabel(", experiment)
        self.assertIn("ylabel(", experiment)
        self.assertIn("time (ms)", experiment)
        self.assertIn("event count", experiment)
        self.assertIn("cpu fraction (%)", experiment)
        self.assertIn("mechanism for sweep 1", experiment)
        self.assertIn("mechanism for sweep 2", experiment)
        self.assertIn("isequaln(baseline,baselinerepeat)", compact)
        self.assertIn(
            "baseline.poll.detection_time_ms(baseline.poll.detected)", compact
        )
        self.assertIn("pollperiodsweepms(sweepindex)", compact)
        self.assertIn("makemask(input.mask_start_ms,maskdurationsweepms(sweepindex))", compact)
        self.assertIn("poll-period lever must not mutate the interrupt mechanism", experiment)
        self.assertIn("interrupt-mask lever must not mutate the polling mechanism", experiment)

    def test_interactive_exposes_meaningful_controls_and_two_views(self):
        interactive = read("interactive.m").lower()
        self.assertIn("uifigure(", interactive)
        self.assertGreaterEqual(interactive.count("uispinner("), 4)
        self.assertIn("uidropdown(", interactive)
        self.assertIn("poll period (ms)", interactive)
        self.assertIn("pulse width (ms)", interactive)
        self.assertIn("mask duration (ms)", interactive)
        self.assertIn("outstanding capacity", interactive)
        self.assertIn("'roundfractionalvalues', 'on'", interactive)
        self.assertIn("valuechangedfcn", interactive)
        self.assertIn("@model", interactive)
        self.assertIn("@p03_scenario", interactive)
        self.assertGreaterEqual(interactive.count("uiaxes("), 2)
        self.assertIn("not a hardware measurement", interactive)
        self.assertIn("n/a (no serviced event)", interactive)

    def test_interactive_callbacks_bind_p03_dependencies_before_path_cleanup(self):
        interactive = matlab_code_without_comments(read("interactive.m")).lower()
        compact = re.sub(r"\s+", "", interactive).replace("...", "")
        self.assertIn("modelfcn=@model;", compact)
        self.assertIn("scenariofcn=@p03_scenario;", compact)
        self.assertIn(
            "input=scenariofcn(scenarioname,pulsewidthcontrol.value);", compact
        )
        self.assertIn(
            "out=modelfcn(input.event_times_ms,input.pulse_width_ms,input.horizon_ms,"
            "pollperiodcontrol.value,0.02,0.05,0.20,capacitycontrol.value,maskwindowsms);",
            compact,
        )

    def test_executable_checks_cover_limits_overrun_timeout_recovery_and_rejection(self):
        checks = matlab_code_without_comments(read("run_checks.m"))
        lower = checks.lower()
        self.assertGreaterEqual(len(re.findall(r"\bassert\s*\(", checks)), 40)
        for marker in (
            "no-event input must retain zero events",
            "arrival exactly on a poll",
            "pulse end exactly on a poll",
            "accumulated poll-grid roundoff",
            "half-open horizon must not become an extra check",
            "capacity release at the next arrival",
            "rounded just below a mask start must remain masked",
            "touching decimal mask windows must normalize and chain",
            "mask end mathematically at the horizon must normalize",
            "finishing mathematically at the horizon",
            "polling handler finishing mathematically at the horizon",
            "must not report a pre-arrival detection or negative response",
            "handler work longer than the period",
            "fifo service start",
            "finish exactly at the next arrival",
            "backlog timeout",
            "response as n/a rather than zero latency",
            "five finite-capacity overruns",
            "post-drain event must prove recovery",
            "roll back the broken configuration",
            "repeated calls and omitted versus empty masks",
            "callback-bound p03 dependencies must survive module path cleanup",
            "p03:model:eventtimes",
            "p03:model:pulsewidth",
            "p03:model:eventorder",
            "p03:model:eventbounds",
            "p03:model:pulseoverlap",
            "p03:model:pollperiod",
            "p03:model:queuecapacity",
            "p03:model:maskwindows",
            "p03:model:maskorder",
            "p03:model:resourcebound",
            "p03:model:timingresourcebound",
            "p03 checks passed",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, lower)

    def test_half_open_roundoff_boundary_behavior_is_retained(self):
        checks = re.sub(r"\s+", "", matlab_code_without_comments(read("run_checks.m")).lower())
        model = re.sub(r"\s+", "", matlab_code_without_comments(read("model.m")).lower())
        self.assertIn(
            "roundoffboundary=model([0.80.91],[0.050.09],1.2,0.1,0,0,0,2);",
            checks,
        )
        self.assertIn(
            "isequal(roundoffboundary.poll.detected,[truefalse])", checks
        )
        self.assertIn("roundoffboundary.poll.response_latency_ms(1)==0", checks)
        self.assertIn("classifyhalfopentime(polltimems", model)
        self.assertIn("normalizedtimems=startms", model)
        self.assertIn("normalizedtimems=endms", model)
        self.assertIn("distancetostartms<=tolerancems", model)
        self.assertIn("distancetoendms<=tolerancems", model)

    def test_tutor_text_is_mechanism_first_and_ends_in_teach_back(self):
        lesson = re.sub(r"\s+", " ", read("lesson.md").lower())
        walkthrough = read("walkthrough.md").lower()
        checks = read("checks.md").lower()
        self.assertIn("a_i <= p_k < a_i + w_i", lesson)
        self.assertIn("p_(k+1) = max", lesson)
        self.assertIn("ready_j = max", lesson)
        self.assertIn("candidate_j = ready_j + l_irq", lesson)
        self.assertEqual(lesson.count("## one prediction"), 1)
        self.assertIn("move one control", walkthrough)
        self.assertIn("reset", walkthrough)
        self.assertIn("interpretation", checks)
        self.assertIn("teach-back", checks)
        self.assertIn("there is no asynchronous cancellation", checks)
        self.assertIn("mechanism first", walkthrough)

    def test_cpu_claim_language_keeps_work_components_and_outcomes_distinct(self):
        readme = read("README.md").lower()
        lesson = re.sub(r"\s+", " ", read("lesson.md").lower())
        experiment = read("experiment.m").lower()
        checks = read("checks.md").lower()
        combined = "\n".join((readme, lesson, experiment, checks))
        self.assertNotIn("isolates periodic check work", combined)
        self.assertIn("do not isolate check cost", lesson)
        self.assertIn("combines periodic checks with handlers", experiment)
        self.assertIn("different numbers of requests", checks)


class P03RetainedEvidenceTests(unittest.TestCase):
    def test_date_agnostic_retained_evidence_is_complete_and_honest(self):
        evidence_files = sorted((ROOT / "docs/evidence").glob("P03-*.md"))
        self.assertTrue(evidence_files, "P03 requires a retained evidence record")
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
