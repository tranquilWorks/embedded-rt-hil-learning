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
QUESTION = (
    "What inputs, observable effects, and failure modes matter when you trigger "
    "Priority Inversion?"
)
MODULE_FOLDER = ROOT / "modules/10-trigger-priority-inversion"
CORE_ARTIFACTS = {
    "README.md",
    "lesson.m",
    "p10_scenario.m",
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


def mutex_reference(
    release: list[int],
    pre: list[int],
    critical: list[int],
    post: list[int],
    deadlines: list[int],
    priorities: list[int],
    horizon: int = 16,
    protocol: str = "priority-inheritance",
    wait_timeout: list[float] | None = None,
    timeout_action: str = "continue-waiting",
):
    """Independent integer-grid one-shot, one-mutex scheduler oracle."""
    task_count = len(release)
    total = [pre[i] + critical[i] + post[i] for i in range(task_count)]
    wait_timeout = wait_timeout or [math.inf] * task_count
    released = [False] * task_count
    completed = [False] * task_count
    cancelled = [False] * task_count
    blocked = [False] * task_count
    acquired = [False] * task_count
    remaining = total.copy()
    service = [0] * task_count
    critical_service = [0] * task_count
    blocked_ticks = [0] * task_count
    direct = [0] * task_count
    third_party = [0] * task_count
    cancelled_work = [0] * task_count
    start: list[int | None] = [None] * task_count
    completion: list[int | None] = [None] * task_count
    request: list[int | None] = [None] * task_count
    acquire: list[int | None] = [None] * task_count
    unlock: list[int | None] = [None] * task_count
    deadline_miss: list[int | None] = [None] * task_count
    timed_out: list[int | None] = [None] * task_count
    cancel_time: list[int | None] = [None] * task_count
    cpu_owner: list[int] = []
    mutex_owner: list[int] = []
    effective_trace: list[list[int]] = [[] for _ in range(task_count)]
    blocked_trace: list[list[bool]] = [[] for _ in range(task_count)]
    owner: int | None = None

    for boundary in range(horizon + 1):
        for task in range(task_count):
            if (
                released[task]
                and not completed[task]
                and not cancelled[task]
                and release[task] + deadlines[task] == boundary
                and deadline_miss[task] is None
            ):
                deadline_miss[task] = boundary

        for task in range(task_count):
            if (
                blocked[task]
                and timed_out[task] is None
                and blocked_ticks[task] >= wait_timeout[task]
            ):
                timed_out[task] = boundary
                if timeout_action == "cancel-waiter":
                    assert owner != task
                    cancelled[task] = True
                    blocked[task] = False
                    cancel_time[task] = boundary
                    cancelled_work[task] = remaining[task]
                    remaining[task] = 0

        if boundary == horizon:
            break

        for task in range(task_count):
            if not released[task] and release[task] == boundary:
                released[task] = True
                if total[task] == 0:
                    completed[task] = True
                    start[task] = boundary
                    completion[task] = boundary

        selected: int | None = None
        effective = priorities.copy()
        for _transition in range(task_count + 1):
            effective = priorities.copy()
            if protocol == "priority-inheritance" and owner is not None:
                waiters = [
                    priorities[task]
                    for task in range(task_count)
                    if blocked[task]
                ]
                if waiters:
                    effective[owner] = max(effective[owner], max(waiters))
            ready = [
                task
                for task in range(task_count)
                if released[task]
                and not completed[task]
                and not cancelled[task]
                and not blocked[task]
                and remaining[task] > 0
            ]
            selected = min(
                ready,
                key=lambda task: (-effective[task], release[task], task),
                default=None,
            )
            if selected is None:
                break
            needs_resource = (
                critical[selected] > 0
                and not acquired[selected]
                and service[selected] == pre[selected]
            )
            if needs_resource:
                if request[selected] is None:
                    request[selected] = boundary
                if owner is None:
                    owner = selected
                    acquired[selected] = True
                    acquire[selected] = boundary
                elif owner != selected:
                    blocked[selected] = True
                    selected = None
                    continue
            break
        else:  # pragma: no cover - guarded by the model's transition bound
            raise AssertionError("unresolved zero-time mutex transitions")

        effective = priorities.copy()
        if protocol == "priority-inheritance" and owner is not None:
            waiters = [
                priorities[task]
                for task in range(task_count)
                if blocked[task]
            ]
            if waiters:
                effective[owner] = max(effective[owner], max(waiters))

        cpu_owner.append(0 if selected is None else selected + 1)
        mutex_owner.append(0 if owner is None else owner + 1)
        for task in range(task_count):
            effective_trace[task].append(effective[task])
            blocked_trace[task].append(blocked[task])

        for waiter in range(task_count):
            if not blocked[waiter]:
                continue
            blocked_ticks[waiter] += 1
            if selected == owner and owner is not None:
                direct[waiter] += 1
            elif selected is not None:
                third_party[waiter] += 1

        if selected is not None:
            if start[selected] is None:
                start[selected] = boundary
            service[selected] += 1
            remaining[selected] -= 1
            if owner == selected:
                critical_service[selected] += 1
                if critical_service[selected] == critical[selected]:
                    owner = None
                    unlock[selected] = boundary + 1
                    blocked = [False] * task_count
            if remaining[selected] == 0:
                assert owner != selected
                completed[selected] = True
                completion[selected] = boundary + 1

    response = [
        None if completion[task] is None else completion[task] - release[task]
        for task in range(task_count)
    ]
    released_demand = sum(total[task] for task in range(task_count) if released[task])
    remaining_released = sum(
        remaining[task] for task in range(task_count) if released[task]
    )
    return {
        "cpu_owner": cpu_owner,
        "mutex_owner": mutex_owner,
        "effective": effective_trace,
        "blocked_trace": blocked_trace,
        "released": released,
        "service": service,
        "remaining": remaining,
        "completion": completion,
        "response": response,
        "request": request,
        "acquire": acquire,
        "unlock": unlock,
        "blocked": blocked_ticks,
        "direct": direct,
        "third_party": third_party,
        "deadline_miss": deadline_miss,
        "timed_out": timed_out,
        "cancelled": cancelled,
        "cancel_time": cancel_time,
        "cancelled_work": cancelled_work,
        "released_demand": released_demand,
        "served": sum(service),
        "remaining_released": remaining_released,
        "busy": sum(owner_id != 0 for owner_id in cpu_owner),
    }


class P10IdentityAndArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(
            (ROOT / "curriculum/modules.json").read_text(encoding="utf-8")
        )
        cls.module = next(
            module for module in cls.manifest["modules"] if module["id"] == "P10"
        )

    def test_permanent_manifest_identity_prerequisite_status_and_evidence(self):
        self.assertEqual(self.module["number"], 10)
        self.assertEqual(self.module["title"], "Trigger Priority Inversion")
        self.assertEqual(self.module["guiding_question"], QUESTION)
        self.assertEqual(self.module["phase"], 3)
        self.assertEqual(self.module["phase_title"], "RTOS behavior")
        self.assertEqual(self.module["slug"], "trigger-priority-inversion")
        self.assertEqual(
            self.module["folder"], "modules/10-trigger-priority-inversion"
        )
        self.assertEqual(self.module["implementation_batch"], "P10")
        self.assertEqual(self.module["prerequisites"], ["P09"])
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

    def test_guiding_question_p09_connection_p11_boundary_and_claims_are_explicit(self):
        combined = "\n".join(
            read(name) for name in ("README.md", "lesson.md", "walkthrough.md")
        )
        lower = re.sub(r"\s+", " ", combined.lower())
        self.assertIn(QUESTION, combined)
        self.assertIn("P09", combined)
        self.assertIn("P11", combined)
        self.assertIn("mutex", lower)
        self.assertIn("blocked", lower)
        self.assertIn("priority inheritance", lower)
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


class P10ModelContractTests(unittest.TestCase):
    def test_model_is_transparent_deterministic_and_resource_bounded(self):
        source = read("model.m")
        code = matlab_code_without_comments(source).lower()
        compact = re.sub(r"\s+", "", code).replace("...", "")
        self.assertIn(
            "functionout=model(releasems,precriticalms,criticalms,"
            "postcriticalms,relativedeadlinems,basepriority,protocol,"
            "tickms,horizonms,waittimeoutms,timeoutaction)",
            compact,
        )
        for token in (
            "resourceowner",
            "blocked",
            "effectivepriority",
            "basepriority",
            "criticalserviceticks",
            "directblockingticks",
            "thirdpartyinterferenceticks",
            "waittimeoutticks",
            "cancelledworkticks",
            "deadlineMissed".lower(),
            "work_conservation_error_ms",
        ):
            with self.subTest(token=token):
                self.assertIn(token, compact)
        self.assertIn("forboundarytick=0:horizonticks", compact)
        self.assertIn("forboundedtransition=1:(taskcount+1)", compact)
        self.assertIn("priority-inheritance", code)
        self.assertIn("cancel-waiter", code)
        self.assertIn("blocked(:)=false", compact)
        self.assertIn("effectivepriority(resourceowner)=max", compact)
        self.assertNotRegex(
            code,
            r"\b(?:persistent|global|rng|rand|randn|pause|eval|system|parfor|parpool)\b",
        )
        self.assertNotRegex(code, r"(?m)^\s*while\b")
        self.assertLess(
            compact.index("taskcount>maxtasks"), compact.index("ownertask=zeros")
        )
        self.assertLess(
            compact.index("scaledhorizon>maxticks"), compact.index("ownertask=zeros")
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
            "P10:model:Arity",
            "P10:model:Release",
            "P10:model:PreCritical",
            "P10:model:Critical",
            "P10:model:PostCritical",
            "P10:model:Deadline",
            "P10:model:Priority",
            "P10:model:VectorLength",
            "P10:model:Protocol",
            "P10:model:Tick",
            "P10:model:Horizon",
            "P10:model:WaitTimeout",
            "P10:model:TimeoutAction",
            "P10:model:GridAlignment",
            "P10:model:ResourceBound",
            "P10:model:TimingResourceBound",
        ):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, model_source)
        self.assertIn("isnumeric", model_source)
        self.assertIn("~islogical", model_source)
        self.assertIn("isreal", model_source)
        self.assertIn("isfinite", model_source)
        self.assertIn("positiveCollapsedToZero", model_source)
        self.assertGreaterEqual(read("run_checks.m").count("eps(1)"), 7)

    def test_scenario_is_seedless_bounded_and_model_compatible(self):
        scenario = matlab_code_without_comments(read("p10_scenario.m")).lower()
        for name in (
            "baseline",
            "plain-mutex",
            "wait-continue",
            "wait-cancel",
            "high-first",
            "direct-block-only",
        ):
            with self.subTest(name=name):
                self.assertIn(name, scenario)
        self.assertRegex(scenario, r"release_ms\s*=\s*\[0 1 2\]")
        self.assertRegex(scenario, r"relative_deadline_ms\s*=\s*\[20 20 6\]")
        self.assertRegex(scenario, r"base_priority\s*=\s*\[1 2 3\]")
        self.assertRegex(scenario, r"tick_ms\s*=\s*1")
        self.assertIn("100000", scenario)
        self.assertNotRegex(scenario, r"\b(?:rng|rand|randn|while|timer|pause)\b")

    def test_independent_baseline_plain_and_trigger_references(self):
        protected = mutex_reference(
            [0, 1, 2], [0, 5, 0], [4, 0, 1], [2, 0, 1],
            [20, 20, 6], [1, 2, 3]
        )
        self.assertEqual(
            protected["cpu_owner"],
            [1, 2, 1, 1, 1, 3, 3, 2, 2, 2, 2, 1, 1, 0, 0, 0],
        )
        self.assertEqual(
            protected["mutex_owner"],
            [1, 1, 1, 1, 1, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        )
        self.assertEqual(protected["effective"][0], [1, 1, 3, 3, 3] + [1] * 11)
        self.assertEqual(protected["completion"], [13, 11, 7])
        self.assertEqual(protected["response"], [13, 10, 5])
        self.assertEqual(protected["blocked"], [0, 0, 3])
        self.assertEqual(protected["direct"], [0, 0, 3])
        self.assertEqual(protected["third_party"], [0, 0, 0])
        self.assertEqual(protected["deadline_miss"], [None, None, None])
        self.assertEqual(protected["service"], [6, 5, 2])
        self.assertEqual(protected["busy"], 13)
        self.assertEqual(protected["released_demand"], 13)

        plain = mutex_reference(
            [0, 1, 2], [0, 5, 0], [4, 0, 1], [2, 0, 1],
            [20, 20, 6], [1, 2, 3], protocol="none"
        )
        self.assertEqual(
            plain["cpu_owner"],
            [1, 2, 2, 2, 2, 2, 1, 1, 1, 3, 3, 1, 1, 0, 0, 0],
        )
        self.assertEqual(plain["completion"], [13, 6, 11])
        self.assertEqual(plain["response"], [13, 5, 9])
        self.assertEqual(plain["blocked"], [0, 0, 7])
        self.assertEqual(plain["direct"], [0, 0, 3])
        self.assertEqual(plain["third_party"], [0, 0, 4])
        self.assertEqual(plain["deadline_miss"], [None, None, 8])
        self.assertEqual(plain["service"], protected["service"])

        high_first = mutex_reference(
            [0, 1, 0], [0, 5, 0], [4, 0, 1], [2, 0, 1],
            [20, 20, 6], [1, 2, 3]
        )
        self.assertEqual(
            high_first["cpu_owner"],
            [3, 3, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 0, 0, 0],
        )
        self.assertEqual(high_first["blocked"][2], 0)
        self.assertEqual(high_first["response"][2], 2)

    def test_independent_two_sweeps_timeout_cancellation_and_limits(self):
        for medium, plain_wait, plain_response, third_party, missed in (
            (1, 3, 5, 0, False),
            (3, 5, 7, 2, True),
            (5, 7, 9, 4, True),
            (7, 9, 11, 6, True),
        ):
            with self.subTest(medium=medium):
                plain = mutex_reference(
                    [0, 1, 2], [0, medium, 0], [4, 0, 1], [2, 0, 1],
                    [20, 20, 6], [1, 2, 3], protocol="none"
                )
                protected = mutex_reference(
                    [0, 1, 2], [0, medium, 0], [4, 0, 1], [2, 0, 1],
                    [20, 20, 6], [1, 2, 3]
                )
                self.assertEqual(plain["blocked"][2], plain_wait)
                self.assertEqual(plain["response"][2], plain_response)
                self.assertEqual(plain["third_party"][2], third_party)
                self.assertEqual(plain["deadline_miss"][2] is not None, missed)
                self.assertEqual(protected["blocked"][2], 3)
                self.assertEqual(protected["response"][2], 5)
                self.assertEqual(protected["third_party"][2], 0)

        for held_work, expected_wait, expected_response in (
            (1, 0, 2), (2, 1, 3), (3, 2, 4), (4, 3, 5), (5, 4, 6)
        ):
            with self.subTest(held_work=held_work):
                result = mutex_reference(
                    [0, 1, 2], [0, 5, 0], [held_work, 0, 1],
                    [6 - held_work, 0, 1], [20, 20, 6], [1, 2, 3]
                )
                self.assertEqual(result["blocked"][2], expected_wait)
                self.assertEqual(result["direct"][2], expected_wait)
                self.assertEqual(result["third_party"][2], 0)
                self.assertEqual(result["response"][2], expected_response)
                self.assertIsNone(result["deadline_miss"][2])
                self.assertEqual(result["released_demand"], 13)

        continued = mutex_reference(
            [0, 1, 2], [0, 5, 0], [4, 0, 1], [2, 0, 1],
            [20, 20, 6], [1, 2, 3], wait_timeout=[math.inf, math.inf, 2]
        )
        self.assertEqual(continued["timed_out"][2], 4)
        self.assertFalse(continued["cancelled"][2])
        self.assertEqual(continued["completion"][2], 7)

        exact_handoff = mutex_reference(
            [0, 1, 2], [0, 5, 0], [4, 0, 1], [2, 0, 1],
            [20, 20, 6], [1, 2, 3], wait_timeout=[math.inf, math.inf, 3],
            timeout_action="cancel-waiter"
        )
        self.assertIsNone(exact_handoff["timed_out"][2])
        self.assertEqual(exact_handoff["acquire"][2], 5)

        cancelled = mutex_reference(
            [0, 1, 2], [0, 5, 0], [4, 0, 1], [2, 0, 1],
            [20, 20, 6], [1, 2, 3], wait_timeout=[math.inf, math.inf, 2],
            timeout_action="cancel-waiter"
        )
        self.assertEqual(
            cancelled["cpu_owner"],
            [1, 2, 1, 1, 2, 2, 2, 2, 1, 1, 1, 0, 0, 0, 0, 0],
        )
        self.assertEqual(cancelled["timed_out"][2], 4)
        self.assertEqual(cancelled["cancel_time"][2], 4)
        self.assertEqual(cancelled["cancelled_work"][2], 2)
        self.assertEqual(cancelled["unlock"][0], 9)
        self.assertEqual(cancelled["served"], 11)
        self.assertEqual(cancelled["remaining_released"], 0)
        self.assertEqual(sum(cancelled["cancelled_work"]), 2)

        short = mutex_reference(
            [0, 1, 2], [0, 5, 0], [4, 0, 1], [2, 0, 1],
            [20, 20, 6], [1, 2, 3], horizon=4
        )
        self.assertEqual(short["cpu_owner"], [1, 2, 1, 1])
        self.assertEqual(short["service"], [3, 1, 0])
        self.assertEqual(short["remaining"], [3, 4, 2])
        self.assertEqual(short["released_demand"], 13)
        self.assertEqual(short["served"] + short["remaining_released"], 13)


class P10LearningAndRegressionTests(unittest.TestCase):
    def test_experiment_has_baseline_two_isolated_sweeps_and_broken_case(self):
        experiment = read("experiment.m").lower()
        compact = re.sub(r"\s+", "", experiment).replace("...", "")
        self.assertIn("%% baseline", experiment)
        self.assertIn("isequaln(baseline,baselinerepeat)", compact)
        self.assertGreaterEqual(experiment.count("%% sweep"), 2)
        self.assertIn("mediumworksweepms = [1 3 5 7]", experiment)
        self.assertIn("lowcriticalsweepms = [1 2 3 4 5]", experiment)
        self.assertIn("%% broken case", experiment)
        self.assertIn("p10_scenario('plain-mutex')", experiment)
        self.assertIn("isequaln(recovered,baseline)", compact)
        self.assertGreaterEqual(experiment.count("figure("), 5)
        self.assertIn("xlabel(", experiment)
        self.assertIn("ylabel(", experiment)
        self.assertIn("time (ms)", experiment)
        self.assertIn("cpu owner", experiment)
        self.assertIn("mutex owner", experiment)
        self.assertIn("mechanism for sweep 1", experiment)
        self.assertIn("mechanism for sweep 2", experiment)
        self.assertIn("must not mutate", experiment)
        self.assertIn("must keep low total work", experiment)

    def test_interactive_exposes_meaningful_controls_and_two_views(self):
        interactive = re.sub(r"\s+", " ", read("interactive.m").lower())
        self.assertIn("uifigure(", interactive)
        self.assertGreaterEqual(interactive.count("uispinner("), 1)
        self.assertGreaterEqual(interactive.count("uidropdown("), 3)
        for label in (
            "medium work (ms)",
            "low mutex work (ms)",
            "high deadline (ms)",
            "horizon (ms)",
            "mutex protocol",
            "high wait timeout",
            "timeout action",
            "scenario",
        ):
            with self.subTest(label=label):
                self.assertIn(label, interactive)
        self.assertGreaterEqual(interactive.count("uiaxes("), 2)
        self.assertIn("valuechangedfcn", interactive)
        self.assertIn("plain mutex inversion", interactive)
        self.assertIn("cancel blocked waiter", interactive)
        self.assertIn("not an rtos", interactive)

    def test_interactive_callbacks_bind_p10_dependencies_before_path_cleanup(self):
        interactive = matlab_code_without_comments(read("interactive.m")).lower()
        compact = re.sub(r"\s+", "", interactive).replace("...", "")
        self.assertIn("modelfcn=@model;", compact)
        self.assertIn("scenariofcn=@p10_scenario;", compact)
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
            "mediumworkcontrol",
            "lowcriticalcontrol",
            "highdeadlinecontrol",
            "horizoncontrol",
            "protocolcontrol",
            "waittimeoutcontrol",
            "timeoutactioncontrol",
        ):
            with self.subTest(control=control):
                self.assertIn(f"{control}.value=", selector)
        self.assertIn("controls{controlindex}.enable='off';", selector)
        self.assertLess(selector.rindex(".value="), selector.index("updateviews();"))

    def test_executable_checks_cover_full_mutex_failure_contract(self):
        checks = matlab_code_without_comments(read("run_checks.m"))
        lower = checks.lower()
        self.assertGreaterEqual(len(re.findall(r"\bassert\s*\(", checks)), 60)
        marker_groups = {
            "determinism": ("deterministic and state-isolated",),
            "mutex ownership": ("mutex ownership",),
            "blocked execution": ("mutex-blocked high task must never execute",),
            "donation": ("inherit priority 3", "donation must be temporary"),
            "direct blocking": ("three direct",),
            "inversion": ("four inversion ticks",),
            "deadline": ("completion exactly at the absolute deadline",),
            "timeout": ("continue-waiting",),
            "cancellation": ("cancel-waiter",),
            "owner-safe cancellation": ("without unlocking low",),
            "rollback": ("roll back exactly",),
            "recovery": ("clean retry after waiter cancellation",),
            "compatibility": ("integer-class columns",),
            "callback": ("callback-bound p10 dependencies",),
            "resource": ("accepted horizon resource bound",),
            "isolation": ("sweep must isolate",),
        }
        for contract, alternatives in marker_groups.items():
            with self.subTest(contract=contract):
                self.assertTrue(any(marker in lower for marker in alternatives))
        for identifier in (
            "p10:model:arity",
            "p10:model:release",
            "p10:model:precritical",
            "p10:model:critical",
            "p10:model:postcritical",
            "p10:model:deadline",
            "p10:model:priority",
            "p10:model:vectorlength",
            "p10:model:protocol",
            "p10:model:tick",
            "p10:model:horizon",
            "p10:model:waittimeout",
            "p10:model:timeoutaction",
            "p10:model:gridalignment",
            "p10:model:resourcebound",
            "p10:model:timingresourcebound",
        ):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, lower)
        self.assertIn("malformed call must not contaminate", lower)
        self.assertIn("not an asynchronous rtos cancellation api", lower)
        self.assertIn("p10 checks passed", lower)

    def test_tutor_text_is_mechanism_first_and_ends_in_teach_back(self):
        lesson = re.sub(r"\s+", " ", read("lesson.md").lower())
        walkthrough = read("walkthrough.md").lower()
        checks = read("checks.md").lower()
        self.assertEqual(lesson.count("## one prediction"), 1)
        self.assertIn("w_h = t_acquire,h - t_request,h", lesson)
        self.assertIn("w_h = b_direct + i_third-party", lesson)
        self.assertIn("r_h = w_h + c_h", lesson)
        self.assertIn("p_effective,owner = max", lesson)
        self.assertIn("cpu owner and mutex owner", lesson)
        self.assertIn("continue-waiting", lesson)
        self.assertIn("cancel-waiter", lesson)
        self.assertIn("move one control", walkthrough)
        self.assertIn("reset", walkthrough)
        self.assertIn("mechanism first", walkthrough)
        self.assertIn("interpretation", checks)
        self.assertIn("teach-back", checks)

    def test_claim_language_separates_model_runtime_rtos_and_physical_evidence(self):
        combined = "\n".join(
            read(name).lower()
            for name in ("README.md", "lesson.md", "checks.md", "experiment.m")
        )
        self.assertIn("synthetic", combined)
        self.assertIn("not matlab-runtime evidence", combined)
        self.assertIn("not an rtos trace", combined)
        self.assertIn("processor", combined)
        self.assertIn("hardware", combined)
        self.assertIn("measured wcet", combined)
        self.assertIn("p11", combined)
        self.assertIn("does not define periodic utilization", combined)
        self.assertNotIn("utilization did not change", combined)
        self.assertNotIn("hardware-validated", combined)
        self.assertNotIn("rtos-validated", combined)

    def test_cli_start_routes_p10_and_persists_only_isolated_progress(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary) / "repo"
            fixture.mkdir()
            shutil.copytree(ROOT / "bin", fixture / "bin")
            shutil.copytree(ROOT / "curriculum", fixture / "curriculum")
            module_fixture = fixture / "modules/10-trigger-priority-inversion"
            module_fixture.mkdir(parents=True)
            for name in ("README.md", "lesson.md", "walkthrough.md", "checks.md"):
                shutil.copy2(MODULE_FOLDER / name, module_fixture / name)

            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            result = subprocess.run(
                [str(fixture / "bin/learn"), "start", "P10"],
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
                "P10 — Trigger Priority Inversion\n"
                "Status: implemented\n"
                f"Guiding question: {QUESTION}\n"
                "Folder: modules/10-trigger-priority-inversion\n"
                "\nMATLAB:\n"
                "  launch_lesson('P10')\n"
                "\nTutor files:\n"
                "  modules/10-trigger-priority-inversion/README.md\n"
                "  modules/10-trigger-priority-inversion/lesson.md\n"
                "  modules/10-trigger-priority-inversion/walkthrough.md\n"
                "  modules/10-trigger-priority-inversion/checks.md\n",
            )
            progress = json.loads(
                (fixture / ".learning/progress.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                progress, {"current": "P10", "completed": {}, "notes": {}}
            )

    def test_cli_check_resolves_p10_public_matlab_entry_point(self):
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [str(ROOT / "bin/learn"), "check", "P10"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env=environment,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "Run in MATLAB: run_module_checks('P10')\n")

    @unittest.skipUnless(shutil.which("matlab"), "MATLAB executable unavailable")
    def test_matlab_executes_module_checks_and_callback_lifetime(self):
        result = subprocess.run(
            [shutil.which("matlab"), "-batch", "run_module_checks('P10')"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=300,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"MATLAB P10 checks failed:\n{result.stdout}\n{result.stderr}",
        )
        self.assertIn("P10 checks passed", result.stdout)


class P10RetainedEvidenceTests(unittest.TestCase):
    def test_date_agnostic_retained_evidence_is_complete_and_honest(self):
        evidence_files = sorted((ROOT / "docs/evidence").glob("P10-*.md"))
        self.assertTrue(evidence_files, "P10 requires a retained evidence record")
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
                    "rtos",
                    "processor",
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
