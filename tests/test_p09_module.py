from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
QUESTION = (
    "What inputs, observable effects, and failure modes matter when you schedule "
    "Tasks by Priority?"
)
MODULE_FOLDER = ROOT / "modules/09-schedule-tasks-by-priority"
CORE_ARTIFACTS = {
    "README.md",
    "lesson.m",
    "p09_scenario.m",
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


def scheduler_reference(
    periods: list[int],
    execution: list[int],
    deadlines: list[int],
    priorities: list[int],
    phases: list[int],
    horizon: int,
    deadline_action: str = "continue-late",
):
    """Independent small integer-grid fixed-priority scheduler oracle."""
    jobs: list[dict[str, int | bool | None]] = []
    sequence = [0] * len(periods)
    owner_tasks: list[int] = []
    owner_jobs: list[int] = []
    last_owner: int | None = None

    for boundary in range(horizon + 1):
        for job in jobs:
            if (
                job["deadline"] == boundary
                and job["remaining"]
                and not job["cancelled"]
                and job["completion"] is None
            ):
                job["missed"] = True
                job["miss"] = boundary
                if deadline_action == "cancel-at-deadline":
                    job["cancelled"] = True
                    job["cancel"] = boundary
                    job["cancelled_work"] = job["remaining"]
                    job["remaining"] = 0

        if boundary == horizon:
            break

        for task_id, (period, cost, deadline, phase) in enumerate(
            zip(periods, execution, deadlines, phases), start=1
        ):
            if boundary >= phase and (boundary - phase) % period == 0:
                sequence[task_id - 1] += 1
                job = {
                    "id": len(jobs) + 1,
                    "task": task_id,
                    "sequence": sequence[task_id - 1],
                    "release": boundary,
                    "deadline": boundary + deadline,
                    "execution": cost,
                    "remaining": cost,
                    "service": 0,
                    "cancelled_work": 0,
                    "start": boundary if cost == 0 else None,
                    "completion": boundary if cost == 0 else None,
                    "miss": None,
                    "cancel": None,
                    "missed": False,
                    "cancelled": False,
                    "preemptions": 0,
                }
                jobs.append(job)

        ready = [
            job
            for job in jobs
            if job["remaining"]
            and not job["cancelled"]
            and job["completion"] is None
        ]
        selected = min(
            ready,
            key=lambda job: (
                -priorities[int(job["task"]) - 1],
                job["release"],
                job["task"],
                job["sequence"],
            ),
            default=None,
        )

        if last_owner is not None and selected is not None:
            previous = jobs[last_owner - 1]
            if (
                selected["id"] != last_owner
                and previous["remaining"]
                and not previous["cancelled"]
            ):
                assert priorities[int(selected["task"]) - 1] > priorities[
                    int(previous["task"]) - 1
                ]
                previous["preemptions"] = int(previous["preemptions"]) + 1

        if selected is None:
            owner_tasks.append(0)
            owner_jobs.append(0)
            last_owner = None
            continue

        owner_tasks.append(int(selected["task"]))
        owner_jobs.append(int(selected["id"]))
        if selected["start"] is None:
            selected["start"] = boundary
        selected["remaining"] = int(selected["remaining"]) - 1
        selected["service"] = int(selected["service"]) + 1
        if selected["remaining"] == 0:
            selected["completion"] = boundary + 1
        last_owner = int(selected["id"])

    release_counts = [
        sum(job["task"] == task_id for job in jobs)
        for task_id in range(1, len(periods) + 1)
    ]
    miss_counts = [
        sum(job["task"] == task_id and job["missed"] for job in jobs)
        for task_id in range(1, len(periods) + 1)
    ]
    service = [
        sum(int(job["service"]) for job in jobs if job["task"] == task_id)
        for task_id in range(1, len(periods) + 1)
    ]
    worst_response: list[int | None] = []
    for task_id in range(1, len(periods) + 1):
        responses = [
            int(job["completion"]) - int(job["release"])
            for job in jobs
            if job["task"] == task_id and job["completion"] is not None
        ]
        worst_response.append(max(responses) if responses else None)
    return {
        "jobs": jobs,
        "owner_tasks": owner_tasks,
        "owner_jobs": owner_jobs,
        "release_counts": release_counts,
        "miss_counts": miss_counts,
        "service": service,
        "worst_response": worst_response,
        "preemptions": sum(int(job["preemptions"]) for job in jobs),
        "busy": sum(owner != 0 for owner in owner_tasks),
    }


def response_time_reference(
    periods: list[int], execution: list[int], priorities: list[int]
) -> list[int]:
    responses: list[int] = []
    for task_id, cost in enumerate(execution):
        candidate = cost
        for _ in range(100):
            next_candidate = cost + sum(
                ((candidate + periods[higher] - 1) // periods[higher])
                * execution[higher]
                for higher in range(len(periods))
                if priorities[higher] > priorities[task_id]
            )
            if next_candidate == candidate:
                break
            candidate = next_candidate
        responses.append(candidate)
    return responses


class P09IdentityAndArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(
            (ROOT / "curriculum/modules.json").read_text(encoding="utf-8")
        )
        cls.module = next(
            module for module in cls.manifest["modules"] if module["id"] == "P09"
        )

    def test_permanent_manifest_identity_prerequisite_status_and_evidence(self):
        self.assertEqual(self.module["number"], 9)
        self.assertEqual(self.module["title"], "Schedule Tasks by Priority")
        self.assertEqual(self.module["guiding_question"], QUESTION)
        self.assertEqual(self.module["phase"], 3)
        self.assertEqual(self.module["phase_title"], "RTOS behavior")
        self.assertEqual(self.module["slug"], "schedule-tasks-by-priority")
        self.assertEqual(
            self.module["folder"], "modules/09-schedule-tasks-by-priority"
        )
        self.assertEqual(self.module["implementation_batch"], "P09")
        self.assertEqual(self.module["prerequisites"], ["P08"])
        self.assertEqual(self.module["status"], "implemented")
        self.assertEqual(self.module["evidence_level"], "simulated")

    def test_complete_artifact_set_has_clean_terminal_newlines_and_bounds(self):
        names = {path.name for path in MODULE_FOLDER.iterdir() if path.is_file()}
        self.assertTrue(CORE_ARTIFACTS <= names)
        for name in CORE_ARTIFACTS:
            with self.subTest(name=name):
                payload = (MODULE_FOLDER / name).read_bytes()
                self.assertTrue(payload.endswith(b"\n"))
                self.assertFalse(payload.endswith(b"\n\n"))
                self.assertLess(len(payload), 100000)

    def test_guiding_question_p08_connection_and_claim_boundary_are_explicit(self):
        combined = "\n".join(
            read(name) for name in ("README.md", "lesson.md", "walkthrough.md")
        )
        lower = combined.lower()
        self.assertIn(QUESTION, combined)
        self.assertIn("P08", combined)
        self.assertIn("scheduling", lower)
        self.assertIn("dac", lower)
        self.assertIn("one cpu", lower)
        self.assertIn("fixed-priority", lower)
        self.assertIn("not matlab-runtime evidence", lower)
        self.assertRegex(lower, r"\bnot\b[^.]{0,240}\brtos trace\b")
        self.assertIn("hardware", lower)

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


class P09ModelContractTests(unittest.TestCase):
    def test_model_is_transparent_per_job_deterministic_and_resource_bounded(self):
        source = read("model.m")
        code = matlab_code_without_comments(source).lower()
        compact = re.sub(r"\s+", "", code).replace("...", "")
        self.assertIn(
            "functionout=model(periodms,executionms,relativedeadlinems,"
            "priority,phasems,tickms,horizonms,deadlineaction)",
            compact,
        )
        for token in (
            "periodms",
            "executionms",
            "relativedeadlinems",
            "priority",
            "phasems",
            "tickms",
            "horizonms",
            "deadlineaction",
            "readyqueues",
            "deadlinebuckets",
            "jobreleasetick",
            "jobdeadlinetick",
            "jobremainingticks",
            "jobcompletiontick",
            "jobdeadlinemissed",
            "jobcancelled",
            "ownertask",
            "ownerjob",
        ):
            with self.subTest(token=token):
                self.assertIn(token, compact)
        self.assertIn("forboundarytick=0:horizonticks", compact)
        self.assertIn("boundarytick==horizonticks", compact)
        self.assertIn("priority(taskid)>priority(selectedtask)", compact)
        self.assertIn("jobreleasetick(proposedjob)<jobreleasetick(selectedjob)", compact)
        self.assertIn("taskid<selectedtask", compact)
        self.assertIn("continue-late", code)
        self.assertIn("cancel-at-deadline", code)
        self.assertIn("jobcount=jobcount+1", compact)
        self.assertIn("jobremainingticks(selectedjob)=jobremainingticks(selectedjob)-1", compact)
        self.assertNotRegex(
            code,
            r"\b(?:persistent|global|while|rng|rand|randn|pause|eval|system|parfor|parpool)\b",
        )
        self.assertLess(
            compact.index("scaledhorizon>maxticks"),
            compact.index("ownertask=zeros"),
        )
        self.assertLess(
            compact.index("totaljobcount>maxjobs"),
            compact.index("jobtask=zeros"),
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
            "serialport",
            "arduino",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotRegex(code, rf"\b{forbidden}\s*\(")
        self.assertNotIn("simulink", code)
        self.assertNotIn("real-time toolbox", code)

    def test_model_rejects_malformed_timing_policy_and_resources(self):
        model_source = read("model.m")
        for identifier in (
            "P09:model:Arity",
            "P09:model:Period",
            "P09:model:Execution",
            "P09:model:Deadline",
            "P09:model:Priority",
            "P09:model:Phase",
            "P09:model:VectorLength",
            "P09:model:Tick",
            "P09:model:Horizon",
            "P09:model:GridAlignment",
            "P09:model:DeadlineAction",
            "P09:model:ResourceBound",
            "P09:model:TimingResourceBound",
            "P09:model:JobResourceBound",
        ):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, model_source)
        self.assertIn("isnumeric", model_source)
        self.assertIn("~islogical", model_source)
        self.assertIn("isreal", model_source)
        self.assertIn("isfinite", model_source)
        self.assertIn("positiveCollapsedToZero", model_source)
        checks_source = read("run_checks.m")
        self.assertGreaterEqual(checks_source.count("eps(1)"), 5)

    def test_scenario_is_seedless_bounded_and_compatible(self):
        scenario = matlab_code_without_comments(read("p09_scenario.m")).lower()
        self.assertIn("function input = p09_scenario(", scenario)
        for name in (
            "baseline",
            "priority-misassigned",
            "deadline-cancel",
            "heavy-logger",
        ):
            with self.subTest(name=name):
                self.assertIn(name, scenario)
        self.assertRegex(scenario, r"period_ms\s*=\s*\[5 10 20\]")
        self.assertRegex(scenario, r"execution_ms\s*=\s*\[1 2 5\]")
        self.assertRegex(scenario, r"relative_deadline_ms\s*=\s*\[5 10 20\]")
        self.assertRegex(scenario, r"priority\s*=\s*\[3 2 1\]")
        self.assertRegex(scenario, r"phase_ms\s*=\s*\[0 0 0\]")
        self.assertRegex(scenario, r"tick_ms\s*=\s*1")
        self.assertRegex(scenario, r"horizonms\s*<=\s*100000")
        self.assertRegex(scenario, r"maxjobs\s*=\s*10000")
        self.assertIn("p09:scenario:jobresourcebound", scenario)
        self.assertNotRegex(scenario, r"\b(?:rng|rand|randn|while|timer|pause)\b")

    def test_scenario_and_model_share_exact_job_resource_boundary(self):
        periods = (5, 10, 20)

        def released_jobs(horizon: int) -> int:
            return sum((horizon - 1) // period + 1 for period in periods)

        self.assertEqual(released_jobs(28_570), 10_000)
        self.assertGreater(released_jobs(28_571), 10_000)
        self.assertRegex(read("model.m"), r"maxJobs\s*=\s*10000")
        scenario = re.sub(
            r"\s+", "", matlab_code_without_comments(read("p09_scenario.m")).lower()
        ).replace("...", "")
        self.assertIn("releasecount>maxjobs", scenario)
        checks = re.sub(
            r"\s+", "", matlab_code_without_comments(read("run_checks.m")).lower()
        ).replace("...", "")
        self.assertIn("scenariofcn('baseline',28570)", checks)
        self.assertIn("scenariofcn('baseline',28571)", checks)
        self.assertIn("p09:scenario:jobresourcebound", checks)

    def test_independent_baseline_priority_and_wcet_references(self):
        baseline = scheduler_reference(
            [5, 10, 20], [1, 2, 5], [5, 10, 20], [3, 2, 1], [0, 0, 0], 40
        )
        expected_owner = [int(character) for character in (
            "1223313330122001000012233133301220010000"
        )]
        self.assertEqual(baseline["owner_tasks"], expected_owner)
        self.assertEqual(baseline["release_counts"], [8, 4, 2])
        self.assertEqual(baseline["service"], [8, 8, 10])
        self.assertEqual(baseline["worst_response"], [1, 3, 9])
        self.assertEqual(baseline["miss_counts"], [0, 0, 0])
        self.assertEqual(baseline["preemptions"], 2)
        self.assertEqual(baseline["busy"], 26)
        self.assertEqual(response_time_reference([5, 10, 20], [1, 2, 5], [3, 2, 1]), [1, 3, 9])

        safe_priorities = ([3, 2, 1], [2, 3, 1], [3, 1, 2])
        expected_responses = ([1, 3, 9], [3, 2, 9], [1, 9, 7])
        for priority, expected in zip(safe_priorities, expected_responses):
            with self.subTest(priority=priority):
                result = scheduler_reference(
                    [5, 10, 20], [1, 2, 5], [5, 10, 20], priority, [0, 0, 0], 40
                )
                self.assertEqual(result["worst_response"], list(expected))
                self.assertEqual(result["miss_counts"], [0, 0, 0])

        for logger_cost, utilization, logger_response in (
            (2, 0.50, 5),
            (5, 0.65, 9),
            (8, 0.80, 15),
        ):
            with self.subTest(logger_cost=logger_cost):
                result = scheduler_reference(
                    [5, 10, 20],
                    [1, 2, logger_cost],
                    [5, 10, 20],
                    [3, 2, 1],
                    [0, 0, 0],
                    40,
                )
                self.assertAlmostEqual(1 / 5 + 2 / 10 + logger_cost / 20, utilization)
                self.assertEqual(result["worst_response"], [1, 3, logger_response])
                self.assertEqual(result["miss_counts"], [0, 0, 0])

    def test_independent_broken_timeout_cancellation_and_backlog_references(self):
        broken = scheduler_reference(
            [5, 10, 20], [1, 2, 5], [5, 10, 20], [2, 1, 3], [0, 0, 0], 40
        )
        self.assertEqual(broken["worst_response"], [6, 9, 5])
        self.assertEqual(broken["miss_counts"], [2, 0, 0])
        self.assertEqual(broken["release_counts"], [8, 4, 2])
        self.assertEqual(broken["busy"], 26)

        exact = scheduler_reference([5], [5], [5], [1], [0], 5)
        self.assertEqual(exact["jobs"][0]["completion"], 5)
        self.assertFalse(exact["jobs"][0]["missed"])

        continued = scheduler_reference([5], [6], [5], [1], [0], 7)
        self.assertTrue(continued["jobs"][0]["missed"])
        self.assertEqual(continued["jobs"][0]["miss"], 5)
        self.assertEqual(continued["jobs"][0]["completion"], 6)
        self.assertFalse(continued["jobs"][1]["missed"])
        self.assertIsNone(continued["jobs"][1]["completion"])

        cancelled = scheduler_reference(
            [5], [6], [5], [1], [0], 7, "cancel-at-deadline"
        )
        self.assertTrue(cancelled["jobs"][0]["cancelled"])
        self.assertEqual(cancelled["jobs"][0]["service"], 5)
        self.assertEqual(cancelled["jobs"][0]["cancelled_work"], 1)
        self.assertEqual(cancelled["owner_jobs"][5], 2)

        backlog = scheduler_reference([2], [3], [2], [1], [0], 7)
        self.assertEqual([job["release"] for job in backlog["jobs"]], [0, 2, 4, 6])
        self.assertEqual([job["deadline"] for job in backlog["jobs"]], [2, 4, 6, 8])
        self.assertEqual([job["completion"] for job in backlog["jobs"]], [3, 6, None, None])
        self.assertEqual([job["missed"] for job in backlog["jobs"]], [True, True, True, False])


class P09LearningAndRegressionTests(unittest.TestCase):
    def test_experiment_has_baseline_two_isolated_sweeps_and_broken_case(self):
        experiment = read("experiment.m").lower()
        compact = re.sub(r"\s+", "", experiment).replace("...", "")
        self.assertIn("%% baseline", experiment)
        self.assertIn("isequaln(baseline,baselinerepeat)", compact)
        self.assertGreaterEqual(experiment.count("%% sweep"), 2)
        self.assertIn("prioritysweep = [3 2 1; 2 3 1; 3 1 2]", experiment)
        self.assertIn("loggerexecutionsweepms = [2 5 8]", experiment)
        self.assertIn("%% broken case", experiment)
        self.assertIn("p09_scenario('priority-misassigned')", experiment)
        self.assertIn("isequaln(recovered,baseline)", compact)
        self.assertGreaterEqual(experiment.count("figure("), 5)
        self.assertIn("xlabel(", experiment)
        self.assertIn("ylabel(", experiment)
        self.assertIn("time (ms)", experiment)
        self.assertIn("response time (ms)", experiment)
        self.assertIn("processor owner", experiment)
        self.assertIn("mechanism for sweep 1", experiment)
        self.assertIn("mechanism for sweep 2", experiment)
        self.assertIn("priority lever must not mutate", experiment)
        self.assertIn("execution-time lever must not mutate", experiment)

    def test_interactive_exposes_meaningful_controls_and_two_views(self):
        interactive = re.sub(r"\s+", " ", read("interactive.m").lower())
        self.assertIn("uifigure(", interactive)
        self.assertGreaterEqual(interactive.count("uispinner("), 1)
        self.assertGreaterEqual(interactive.count("uidropdown("), 3)
        for label in (
            "control wcet (ms)",
            "telemetry wcet (ms)",
            "logger wcet (ms)",
            "control deadline (ms)",
            "horizon (ms)",
            "priority order",
            "deadline action",
            "scenario",
        ):
            with self.subTest(label=label):
                self.assertIn(label, interactive)
        self.assertGreaterEqual(interactive.count("uiaxes("), 2)
        self.assertIn("valuechangedfcn", interactive)
        self.assertIn("bad priority map", interactive)
        self.assertIn("deadline cancellation", interactive)
        self.assertIn("not an rtos", interactive)

    def test_interactive_callbacks_bind_p09_dependencies_before_path_cleanup(self):
        interactive = matlab_code_without_comments(read("interactive.m")).lower()
        compact = re.sub(r"\s+", "", interactive).replace("...", "")
        self.assertIn("modelfcn=@model;", compact)
        self.assertIn("scenariofcn=@p09_scenario;", compact)
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
            "controlexecution",
            "telemetryexecution",
            "loggerexecution",
            "controldeadline",
            "telemetrydeadline",
            "loggerdeadline",
            "horizoncontrol",
            "prioritycontrol",
            "deadlineactioncontrol",
        ):
            with self.subTest(control=control):
                self.assertIn(f"{control}.value=", selector)
        self.assertIn("controls{controlindex}.enable='off';", selector)
        self.assertLess(selector.rindex(".value="), selector.index("updateviews();"))

    def test_executable_checks_cover_full_scheduler_failure_contract(self):
        checks = matlab_code_without_comments(read("run_checks.m"))
        lower = checks.lower()
        self.assertGreaterEqual(len(re.findall(r"\bassert\s*\(", checks)), 55)
        marker_groups = {
            "determinism": ("deterministic and state-isolated",),
            "release": ("half-open 40 ms horizon", "release [8 4 2]"),
            "preemption": ("preempted by control",),
            "resume": ("logger must resume",),
            "tie": ("equal-priority simultaneous jobs",),
            "exact deadline": ("completion exactly at the final deadline",),
            "timeout": ("time out once",),
            "cancellation": ("cancel-at-deadline",),
            "backlog": ("overlapping releases",),
            "rollback": ("roll back exactly",),
            "recovery": ("clean retry after deadline cancellation",),
            "compatibility": ("integer-class column vectors",),
            "callback": ("callback-bound p09 dependencies",),
            "resource": ("accepted job resource bound",),
            "isolation": ("must isolate priority", "must isolate execution"),
        }
        for contract, alternatives in marker_groups.items():
            with self.subTest(contract=contract):
                self.assertTrue(any(marker in lower for marker in alternatives))
        for identifier in (
            "p09:model:arity",
            "p09:model:period",
            "p09:model:execution",
            "p09:model:deadline",
            "p09:model:priority",
            "p09:model:phase",
            "p09:model:vectorlength",
            "p09:model:tick",
            "p09:model:horizon",
            "p09:model:gridalignment",
            "p09:model:deadlineaction",
            "p09:model:resourcebound",
            "p09:model:timingresourcebound",
            "p09:model:jobresourcebound",
        ):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, lower)
        self.assertIn("malformed call must not contaminate", lower)
        self.assertIn("not an asynchronous rtos cancellation api", lower)
        self.assertIn("p09 checks passed", lower)

    def test_tutor_text_is_mechanism_first_and_ends_in_teach_back(self):
        lesson = re.sub(r"\s+", " ", read("lesson.md").lower())
        walkthrough = read("walkthrough.md").lower()
        checks = read("checks.md").lower()
        self.assertEqual(lesson.count("## one prediction"), 1)
        self.assertIn("r_i,k = phase_i + k t_i", lesson)
        self.assertIn("d_i,k = r_i,k + d_i", lesson)
        self.assertIn("r_i,k = f_i,k - r_i,k", lesson)
        self.assertIn("largest priority", lesson)
        self.assertIn("ready", lesson)
        self.assertIn("preempt", lesson)
        self.assertIn("resume", lesson)
        self.assertIn("ceil(r_i/t_h)", lesson)
        self.assertIn("continue-late", lesson)
        self.assertIn("cancel-at-deadline", lesson)
        self.assertIn("move one control", walkthrough)
        self.assertIn("reset", walkthrough)
        self.assertIn("mechanism first", walkthrough)
        self.assertIn("interpretation", checks)
        self.assertIn("teach-back", checks)

    def test_claim_language_separates_model_runtime_physical_and_p10_boundaries(self):
        combined = "\n".join(
            read(name).lower()
            for name in ("README.md", "lesson.md", "checks.md", "experiment.m")
        )
        self.assertIn("synthetic", combined)
        self.assertIn("not matlab-runtime evidence", combined)
        self.assertIn("not an rtos trace", combined)
        self.assertIn("hardware", combined)
        self.assertIn("measured wcet", combined)
        self.assertIn("p10", combined)
        self.assertIn("locks", combined)
        self.assertIn("priority inversion", combined)
        self.assertNotIn("hardware-validated", combined)
        self.assertNotIn("rtos-validated", combined)

    def test_cli_check_resolves_p09_public_matlab_entry_point(self):
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [str(ROOT / "bin/learn"), "check", "P09"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env=environment,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "Run in MATLAB: run_module_checks('P09')\n")

    @unittest.skipUnless(shutil.which("matlab"), "MATLAB executable unavailable")
    def test_matlab_executes_module_checks_and_callback_lifetime(self):
        result = subprocess.run(
            [shutil.which("matlab"), "-batch", "run_module_checks('P09')"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=300,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"MATLAB P09 checks failed:\n{result.stdout}\n{result.stderr}",
        )
        self.assertIn("P09 checks passed", result.stdout)


class P09RetainedEvidenceTests(unittest.TestCase):
    def test_date_agnostic_retained_evidence_is_complete_and_honest(self):
        evidence_files = sorted((ROOT / "docs/evidence").glob("P09-*.md"))
        self.assertTrue(evidence_files, "P09 requires a retained evidence record")
        for path in evidence_files:
            with self.subTest(path=path.name):
                payload = path.read_bytes()
                self.assertTrue(payload.endswith(b"\n"))
                self.assertFalse(payload.endswith(b"\n\n"))
                text = payload.decode("utf-8").lower()
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
                    "bench",
                    "hil",
                    "field",
                    "rt1/rt2",
                    "unreal",
                    "signing",
                    "deployment",
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
