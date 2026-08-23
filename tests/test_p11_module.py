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
    "What inputs, observable effects, and failure modes matter when you protect "
    "Shared Data Without Excess Blocking?"
)
MODULE_FOLDER = ROOT / "modules/11-protect-shared-data-without-excess-blocking"
CORE_ARTIFACTS = {
    "README.md",
    "lesson.m",
    "p11_scenario.m",
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


def shared_record_reference(
    writer_prepare: int,
    record_words: int,
    reader_release: int,
    reader_process: int,
    *,
    protection: str = "short-mutex",
    horizon: int = 16,
    wait_timeout: float = math.inf,
    timeout_action: str = "continue-waiting",
):
    """Independent integer-grid oracle for the two-task shared-record lesson."""
    assert writer_prepare >= 0
    assert record_words >= 2
    assert reader_release >= 0
    assert reader_process >= 0
    assert horizon >= 1
    assert protection in {"short-mutex", "coarse-mutex", "unprotected"}
    assert wait_timeout > 0
    assert timeout_action in {"continue-waiting", "cancel-reader"}

    writer_prepare_remaining = writer_prepare
    writer_commit_remaining = record_words
    reader_copy_remaining = record_words
    reader_process_remaining = reader_process

    initial_record = list(range(1, record_words + 1))
    target_record = [100 + word for word in initial_record]
    shared_record = initial_record.copy()
    observed: list[int | None] = [None] * record_words

    writer_completed = False
    reader_released = False
    reader_completed = False
    reader_cancelled = False
    reader_blocked = False
    reader_timed_out = False
    mutex_owner = 0

    writer_commit_index = 0
    reader_copy_index = 0
    writer_service = 0
    reader_service = 0
    reader_blocked_ticks = 0
    commit_blocking = 0
    scope_excess = 0
    cancelled_reader_work = 0

    writer_start = None
    writer_completion = None
    reader_start = None
    reader_completion = None
    writer_request = None
    writer_acquire = None
    writer_unlock = None
    reader_request = None
    reader_acquire = None
    reader_unlock = None
    reader_block_start = None
    reader_timeout = None
    reader_cancellation = None

    cpu_owner: list[int] = []
    mutex_timeline: list[int] = []
    stage_code: list[int] = []
    blocked_timeline: list[bool] = []
    writer_priority: list[int] = []
    committed_words: list[int] = [0]
    copied_words: list[int] = [0]
    live_min_generation: list[int] = [0]
    live_max_generation: list[int] = [0]

    for boundary in range(horizon + 1):
        if (
            reader_blocked
            and not reader_timed_out
            and reader_blocked_ticks >= wait_timeout
        ):
            reader_timed_out = True
            reader_timeout = boundary
            if timeout_action == "cancel-reader":
                assert mutex_owner != 2
                reader_cancelled = True
                reader_blocked = False
                reader_cancellation = boundary
                cancelled_reader_work = (
                    reader_copy_remaining + reader_process_remaining
                )
                reader_copy_remaining = 0
                reader_process_remaining = 0

        if boundary == horizon:
            break

        if not reader_released and reader_release == boundary:
            reader_released = True

        selected = 0
        for _transition in range(3):
            reader_ready = (
                reader_released
                and not reader_completed
                and not reader_cancelled
                and not reader_blocked
            )
            if reader_ready:
                selected = 2
            elif not writer_completed:
                selected = 1
            else:
                selected = 0

            if selected == 0:
                break

            if selected == 1:
                needs_mutex = protection == "coarse-mutex" or (
                    protection == "short-mutex"
                    and writer_prepare_remaining == 0
                )
                if needs_mutex and writer_request is None:
                    writer_request = boundary
            else:
                needs_mutex = protection == "coarse-mutex" or (
                    protection == "short-mutex" and reader_copy_remaining > 0
                )
                if needs_mutex and reader_request is None:
                    reader_request = boundary

            if needs_mutex and mutex_owner != selected:
                if mutex_owner == 0:
                    mutex_owner = selected
                    if selected == 1 and writer_acquire is None:
                        writer_acquire = boundary
                    elif selected == 2 and reader_acquire is None:
                        reader_acquire = boundary
                elif selected == 2:
                    reader_blocked = True
                    if reader_block_start is None:
                        reader_block_start = boundary
                    selected = 0
                    continue
                else:  # pragma: no cover - impossible for two fixed-priority tasks
                    raise AssertionError("writer selected while reader owns mutex")
            break
        else:  # pragma: no cover - guarded by the fixed two-task transition bound
            raise AssertionError("unresolved mutex transition")

        effective_writer_priority = (
            2
            if reader_blocked
            and mutex_owner == 1
            and protection != "unprotected"
            else 1
        )

        cpu_owner.append(selected)
        mutex_timeline.append(mutex_owner)
        blocked_timeline.append(reader_blocked)
        writer_priority.append(effective_writer_priority)
        if selected == 1:
            stage_code.append(1 if writer_prepare_remaining else 2)
        elif selected == 2:
            stage_code.append(3 if reader_copy_remaining else 4)
        else:
            stage_code.append(0)

        if reader_blocked:
            reader_blocked_ticks += 1
            if selected == 1 and writer_prepare_remaining:
                scope_excess += 1
            elif selected == 1 and writer_commit_remaining:
                commit_blocking += 1

        if selected == 1:
            if writer_start is None:
                writer_start = boundary
            writer_service += 1
            if writer_prepare_remaining:
                writer_prepare_remaining -= 1
            else:
                shared_record[writer_commit_index] = target_record[writer_commit_index]
                writer_commit_index += 1
                writer_commit_remaining -= 1
                if writer_commit_remaining == 0:
                    writer_completed = True
                    writer_completion = boundary + 1
                    if mutex_owner == 1:
                        mutex_owner = 0
                        writer_unlock = boundary + 1
                        reader_blocked = False
        elif selected == 2:
            if reader_start is None:
                reader_start = boundary
            reader_service += 1
            if reader_copy_remaining:
                observed[reader_copy_index] = shared_record[reader_copy_index]
                reader_copy_index += 1
                reader_copy_remaining -= 1
                if (
                    reader_copy_remaining == 0
                    and protection == "short-mutex"
                    and mutex_owner == 2
                ):
                    mutex_owner = 0
                    reader_unlock = boundary + 1
                if reader_copy_remaining == 0 and reader_process_remaining == 0:
                    reader_completed = True
                    reader_completion = boundary + 1
                    if mutex_owner == 2:
                        mutex_owner = 0
                        reader_unlock = boundary + 1
            else:
                reader_process_remaining -= 1
                if reader_process_remaining == 0:
                    reader_completed = True
                    reader_completion = boundary + 1
                    if mutex_owner == 2:
                        mutex_owner = 0
                        reader_unlock = boundary + 1

        committed_words.append(writer_commit_index)
        copied_words.append(reader_copy_index)
        live_generations = [
            (value - index) // 100
            for index, value in enumerate(shared_record, start=1)
        ]
        live_min_generation.append(min(live_generations))
        live_max_generation.append(max(live_generations))

    snapshot_complete = reader_copy_index == record_words
    observed_generations = [
        None if value is None else (value - index) // 100
        for index, value in enumerate(observed, start=1)
    ]
    snapshot_consistent = snapshot_complete and len(set(observed_generations)) == 1
    observed_version = observed_generations[0] if snapshot_consistent else None
    torn = snapshot_complete and not snapshot_consistent
    stale = snapshot_consistent and observed_version is not None and observed_version < 1

    final_generations = [
        (value - index) // 100
        for index, value in enumerate(shared_record, start=1)
    ]
    writer_remaining = writer_prepare_remaining + writer_commit_remaining
    reader_remaining = 0
    if reader_released and not reader_cancelled:
        reader_remaining = reader_copy_remaining + reader_process_remaining
    released_demand = writer_prepare + record_words
    if reader_released:
        released_demand += record_words + reader_process
    served = writer_service + reader_service
    remaining = writer_remaining + reader_remaining

    assert reader_blocked_ticks == commit_blocking + scope_excess
    assert released_demand == served + cancelled_reader_work + remaining

    return {
        "state_time": list(range(horizon + 1)),
        "cpu_owner": cpu_owner,
        "mutex_owner": mutex_timeline,
        "stage_code": stage_code,
        "reader_blocked_trace": blocked_timeline,
        "writer_effective_priority": writer_priority,
        "committed_words": committed_words,
        "copied_words": copied_words,
        "live_min_generation": live_min_generation,
        "live_max_generation": live_max_generation,
        "record": {
            "initial": initial_record,
            "target": target_record,
            "final": shared_record,
            "final_generation": final_generations,
            "published": writer_completed,
            "consistent": len(set(final_generations)) == 1,
        },
        "writer": {
            "start": writer_start,
            "completion": writer_completion,
            "service": writer_service,
            "remaining": writer_remaining,
            "request": writer_request,
            "acquire": writer_acquire,
            "unlock": writer_unlock,
            "completed": writer_completed,
        },
        "reader": {
            "released": reader_released,
            "start": reader_start,
            "completion": reader_completion,
            "response": (
                None
                if reader_completion is None
                else reader_completion - reader_release
            ),
            "service": reader_service,
            "remaining": reader_remaining,
            "request": reader_request,
            "acquire": reader_acquire,
            "unlock": reader_unlock,
            "block_start": reader_block_start,
            "blocked": reader_blocked_ticks,
            "commit_blocking": commit_blocking,
            "scope_excess": scope_excess,
            "timed_out": reader_timed_out,
            "timeout": reader_timeout,
            "cancelled": reader_cancelled,
            "cancellation": reader_cancellation,
            "cancelled_work": cancelled_reader_work,
            "completed": reader_completed,
            "observed": observed,
            "observed_generation": observed_generations,
            "observed_version": observed_version,
            "snapshot_complete": snapshot_complete,
            "snapshot_consistent": snapshot_consistent,
            "torn": torn,
            "stale": stale,
        },
        "metrics": {
            "released_demand": released_demand,
            "served": served,
            "cancelled": cancelled_reader_work,
            "remaining": remaining,
            "busy": sum(owner != 0 for owner in cpu_owner),
            "idle": sum(owner == 0 for owner in cpu_owner),
        },
    }


class P11IdentityAndArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(
            (ROOT / "curriculum/modules.json").read_text(encoding="utf-8")
        )
        cls.module = next(
            module for module in cls.manifest["modules"] if module["id"] == "P11"
        )

    def test_permanent_manifest_identity_prerequisite_status_and_evidence(self):
        self.assertEqual(self.module["number"], 11)
        self.assertEqual(
            self.module["title"], "Protect Shared Data Without Excess Blocking"
        )
        self.assertEqual(self.module["guiding_question"], QUESTION)
        self.assertEqual(self.module["phase"], 3)
        self.assertEqual(self.module["phase_title"], "RTOS behavior")
        self.assertEqual(
            self.module["slug"], "protect-shared-data-without-excess-blocking"
        )
        self.assertEqual(
            self.module["folder"],
            "modules/11-protect-shared-data-without-excess-blocking",
        )
        self.assertEqual(self.module["implementation_batch"], "P11")
        self.assertEqual(self.module["prerequisites"], ["P10"])
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

    def test_guiding_question_p10_connection_p12_boundary_and_claims_are_explicit(self):
        combined = "\n".join(
            read(name) for name in ("README.md", "lesson.md", "walkthrough.md")
        )
        lower = re.sub(r"\s+", " ", combined.lower())
        self.assertIn(QUESTION, combined)
        self.assertIn("P10", combined)
        self.assertIn("P12", combined)
        for concept in (
            "short mutex",
            "coarse mutex",
            "priority inheritance",
            "coherence",
            "freshness",
            "torn",
            "not matlab-runtime evidence",
            "processor",
            "hardware",
        ):
            with self.subTest(concept=concept):
                self.assertIn(concept, lower)
        self.assertRegex(lower, r"\bnot\b[^.]{0,240}\brtos\b")

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


class P11ModelContractTests(unittest.TestCase):
    def test_model_is_transparent_deterministic_and_resource_bounded(self):
        source = read("model.m")
        code = matlab_code_without_comments(source).lower()
        compact = re.sub(r"\s+", "", code).replace("...", "")
        self.assertIn(
            "functionout=model(writerpreparems,recordwords,readerreleasems,"
            "readerprocessms,protection,tickms,horizonms,waittimeoutms,"
            "timeoutaction)",
            compact,
        )
        for token in (
            "writerprepareremaining",
            "writercommitremaining",
            "readercopyremaining",
            "readerprocessremaining",
            "mutexowner",
            "readerblocked",
            "writereffectivepriority",
            "commitblockingticks",
            "scopeexcessblockingticks",
            "cancelledreaderworkticks",
            "sharedrecord",
            "readerobserved",
            "observedversions",
            "readersnapshotconsistent",
            "work_conservation_error_ms",
        ):
            with self.subTest(token=token):
                self.assertIn(token, compact)
        self.assertIn("forboundarytick=0:horizonticks", compact)
        self.assertIn("forboundedtransition=1:3", compact)
        self.assertIn("sharedrecord(writercommitindex)=", compact)
        self.assertIn("readerobserved(readercopyindex)=", compact)
        self.assertIn("short-mutex", code)
        self.assertIn("coarse-mutex", code)
        self.assertIn("unprotected", code)
        self.assertIn("cancel-reader", code)
        self.assertIn("writerpriority=2", compact)
        self.assertIn(
            "needsmutex=strcmp(protection,'coarse-mutex')||(strcmp(protection,"
            "'short-mutex')&&readercopyremaining>0)",
            compact,
        )
        self.assertNotRegex(
            code,
            r"\b(?:persistent|global|rng|rand|randn|pause|eval|system|parfor|parpool)\b",
        )
        self.assertNotRegex(code, r"(?m)^\s*while\b")
        self.assertLess(
            compact.index("recordwords=validaterecordwords"),
            compact.index("cpuowner=zeros"),
        )
        self.assertLess(
            compact.index("horizonticks>maxhorizonticks"),
            compact.index("cpuowner=zeros"),
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
        source = read("model.m")
        for identifier in (
            "P11:model:Arity",
            "P11:model:WriterPrepare",
            "P11:model:RecordWords",
            "P11:model:RecordResourceBound",
            "P11:model:ReaderRelease",
            "P11:model:ReaderProcess",
            "P11:model:Protection",
            "P11:model:Tick",
            "P11:model:Horizon",
            "P11:model:WaitTimeout",
            "P11:model:TimeoutAction",
            "P11:model:GridAlignment",
            "P11:model:TimingResourceBound",
        ):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, source)
        self.assertIn("isnumeric", source)
        self.assertIn("~islogical", source)
        self.assertIn("isreal", source)
        self.assertIn("isfinite", source)
        self.assertIn("positiveCollapsedToZero", source)
        self.assertIn("maxRecordWords = 64", source)
        self.assertIn("maxHorizonTicks = 100000", source)
        self.assertIn("maxInputTicks = 1e9", source)

    def test_scenario_is_seedless_bounded_and_model_compatible(self):
        scenario = matlab_code_without_comments(read("p11_scenario.m")).lower()
        for name in (
            "baseline",
            "coarse-lock",
            "unprotected-torn",
            "timeout-continue",
            "timeout-cancel",
            "early-reader",
        ):
            with self.subTest(name=name):
                self.assertIn(name, scenario)
        self.assertRegex(scenario, r"writer_prepare_ms\s*=\s*double\(writerpreparems\)")
        self.assertRegex(scenario, r"record_words\s*=\s*double\(recordwords\)")
        self.assertRegex(scenario, r"reader_release_ms\s*=\s*double\(readerreleasems\)")
        self.assertRegex(scenario, r"reader_process_ms\s*=\s*double\(readerprocessms\)")
        self.assertRegex(scenario, r"tick_ms\s*=\s*1")
        self.assertIn("64", scenario)
        self.assertIn("100000", scenario)
        self.assertNotRegex(scenario, r"\b(?:rng|rand|randn|while|timer|pause)\b")

    def test_independent_short_coarse_and_unprotected_references(self):
        short = shared_record_reference(2, 2, 3, 2, horizon=10)
        self.assertEqual(short["cpu_owner"], [1, 1, 1, 1, 2, 2, 2, 2, 0, 0])
        self.assertEqual(short["mutex_owner"], [0, 0, 1, 1, 2, 2, 0, 0, 0, 0])
        self.assertEqual(short["stage_code"], [1, 1, 2, 2, 3, 3, 4, 4, 0, 0])
        self.assertEqual(
            short["reader_blocked_trace"],
            [False, False, False, True, False, False, False, False, False, False],
        )
        self.assertEqual(
            short["writer_effective_priority"], [1, 1, 1, 2, 1, 1, 1, 1, 1, 1]
        )
        self.assertEqual(short["writer"]["acquire"], 2)
        self.assertEqual(short["writer"]["completion"], 4)
        self.assertEqual(short["writer"]["unlock"], 4)
        self.assertEqual(short["reader"]["request"], 3)
        self.assertEqual(short["reader"]["acquire"], 4)
        self.assertEqual(short["reader"]["unlock"], 6)
        self.assertEqual(short["reader"]["completion"], 8)
        self.assertEqual(short["reader"]["response"], 5)
        self.assertEqual(short["reader"]["blocked"], 1)
        self.assertEqual(short["reader"]["commit_blocking"], 1)
        self.assertEqual(short["reader"]["scope_excess"], 0)
        self.assertEqual(short["reader"]["observed"], [101, 102])
        self.assertEqual(short["reader"]["observed_generation"], [1, 1])
        self.assertTrue(short["reader"]["snapshot_consistent"])
        self.assertFalse(short["reader"]["torn"])
        self.assertEqual(short["metrics"]["released_demand"], 8)
        self.assertEqual(short["metrics"]["served"], 8)
        self.assertEqual(short["metrics"]["remaining"], 0)

        coarse = shared_record_reference(
            2, 2, 3, 2, protection="coarse-mutex", horizon=10
        )
        self.assertEqual(coarse["cpu_owner"], short["cpu_owner"])
        self.assertEqual(
            coarse["mutex_owner"], [1, 1, 1, 1, 2, 2, 2, 2, 0, 0]
        )
        self.assertEqual(coarse["writer"]["acquire"], 0)
        self.assertEqual(coarse["writer"]["unlock"], 4)
        self.assertEqual(coarse["reader"]["acquire"], 4)
        self.assertEqual(coarse["reader"]["unlock"], 8)
        self.assertEqual(coarse["reader"]["response"], 5)
        self.assertTrue(coarse["reader"]["snapshot_consistent"])

        unprotected = shared_record_reference(
            2, 2, 3, 2, protection="unprotected", horizon=10
        )
        self.assertEqual(
            unprotected["cpu_owner"], [1, 1, 1, 2, 2, 2, 2, 1, 0, 0]
        )
        self.assertEqual(unprotected["mutex_owner"], [0] * 10)
        self.assertEqual(unprotected["writer"]["completion"], 8)
        self.assertEqual(unprotected["reader"]["completion"], 7)
        self.assertEqual(unprotected["reader"]["response"], 4)
        self.assertEqual(unprotected["reader"]["blocked"], 0)
        self.assertEqual(unprotected["reader"]["observed"], [101, 2])
        self.assertEqual(unprotected["reader"]["observed_generation"], [1, 0])
        self.assertFalse(unprotected["reader"]["snapshot_consistent"])
        self.assertTrue(unprotected["reader"]["torn"])
        self.assertEqual(unprotected["record"]["final"], [101, 102])
        self.assertTrue(unprotected["record"]["consistent"])

    def test_boundary_state_traces_follow_service_completion(self):
        baseline = shared_record_reference(2, 2, 3, 2, horizon=10)
        self.assertEqual(baseline["state_time"], list(range(11)))
        self.assertEqual(baseline["committed_words"][:5], [0, 0, 0, 1, 2])
        self.assertEqual(
            baseline["copied_words"][:7], [0, 0, 0, 0, 0, 1, 2]
        )
        baseline_mixed_times = [
            time
            for time, minimum, maximum in zip(
                baseline["state_time"],
                baseline["live_min_generation"],
                baseline["live_max_generation"],
            )
            if minimum != maximum
        ]
        self.assertEqual(baseline_mixed_times, [3])

        broken = shared_record_reference(
            2, 2, 3, 2, protection="unprotected", horizon=10
        )
        broken_mixed_times = [
            time
            for time, minimum, maximum in zip(
                broken["state_time"],
                broken["live_min_generation"],
                broken["live_max_generation"],
            )
            if minimum != maximum
        ]
        self.assertEqual(broken_mixed_times, [3, 4, 5, 6, 7])

        model = re.sub(
            r"\s+", "", matlab_code_without_comments(read("model.m")).lower()
        ).replace("...", "")
        for allocation in (
            "committedwordcount=zeros(1,horizonticks+1)",
            "copiedwordcount=zeros(1,horizonticks+1)",
            "recordminversion=zeros(1,horizonticks+1)",
            "recordmaxversion=zeros(1,horizonticks+1)",
        ):
            with self.subTest(allocation=allocation):
                self.assertIn(allocation, model)
        self.assertIn("boundarystateindex=slotindex+1", model)
        self.assertIn(
            "committedwordcount(boundarystateindex)=writercommitindex", model
        )
        self.assertIn("copiedwordcount(boundarystateindex)=readercopyindex", model)

        experiment = re.sub(r"\s+", "", read("experiment.m").lower()).replace(
            "...", ""
        )
        interactive = re.sub(r"\s+", "", read("interactive.m").lower()).replace(
            "...", ""
        )
        self.assertIn(
            "stairs(baseline.timeline.time_edges_ms,"
            "baseline.timeline.writer_committed_word_count,",
            experiment,
        )
        self.assertIn(
            "stairs(recordaxes,out.timeline.time_edges_ms,"
            "out.timeline.writer_committed_word_count,",
            interactive,
        )

    def test_independent_sweeps_timeout_cancellation_and_limits(self):
        for prepare, coarse_wait, coarse_response, excess in (
            (2, 3, 7, 1),
            (3, 4, 8, 2),
            (4, 5, 9, 3),
            (5, 6, 10, 4),
        ):
            with self.subTest(sweep="prepare", prepare=prepare):
                short = shared_record_reference(
                    prepare, 2, 1, 2, protection="short-mutex", horizon=12
                )
                coarse = shared_record_reference(
                    prepare, 2, 1, 2, protection="coarse-mutex", horizon=12
                )
                self.assertEqual(short["reader"]["blocked"], 0)
                self.assertEqual(short["reader"]["response"], 4)
                self.assertEqual(short["reader"]["observed_version"], 0)
                self.assertTrue(short["reader"]["snapshot_consistent"])
                self.assertTrue(short["reader"]["stale"])
                self.assertEqual(coarse["reader"]["blocked"], coarse_wait)
                self.assertEqual(coarse["reader"]["response"], coarse_response)
                self.assertEqual(coarse["reader"]["scope_excess"], excess)
                self.assertEqual(coarse["reader"]["commit_blocking"], 2)
                self.assertEqual(coarse["reader"]["observed_version"], 1)
                self.assertTrue(coarse["reader"]["snapshot_consistent"])

        for words, wait, response in (
            (2, 1, 5),
            (3, 2, 7),
            (4, 3, 9),
            (5, 4, 11),
        ):
            with self.subTest(sweep="words", words=words):
                result = shared_record_reference(2, words, 3, 2, horizon=16)
                self.assertEqual(result["reader"]["blocked"], wait)
                self.assertEqual(result["reader"]["commit_blocking"], wait)
                self.assertEqual(result["reader"]["scope_excess"], 0)
                self.assertEqual(result["reader"]["response"], response)
                self.assertEqual(result["writer"]["unlock"] - result["writer"]["acquire"], words)
                self.assertEqual(result["reader"]["unlock"] - result["reader"]["acquire"], words)
                self.assertEqual(result["reader"]["observed_version"], 1)
                self.assertTrue(result["reader"]["snapshot_consistent"])

        exact_handoff = shared_record_reference(
            2,
            2,
            3,
            2,
            horizon=10,
            wait_timeout=1,
            timeout_action="cancel-reader",
        )
        self.assertFalse(exact_handoff["reader"]["timed_out"])
        self.assertFalse(exact_handoff["reader"]["cancelled"])
        self.assertEqual(exact_handoff["reader"]["acquire"], 4)
        self.assertEqual(exact_handoff["reader"]["completion"], 8)

        continued = shared_record_reference(
            2, 4, 3, 2, horizon=16, wait_timeout=1
        )
        self.assertTrue(continued["reader"]["timed_out"])
        self.assertEqual(continued["reader"]["timeout"], 4)
        self.assertFalse(continued["reader"]["cancelled"])
        self.assertEqual(continued["reader"]["blocked"], 3)
        self.assertEqual(continued["reader"]["acquire"], 6)
        self.assertEqual(continued["reader"]["completion"], 12)
        self.assertTrue(continued["reader"]["snapshot_consistent"])

        cancelled = shared_record_reference(
            2,
            4,
            3,
            2,
            horizon=16,
            wait_timeout=1,
            timeout_action="cancel-reader",
        )
        self.assertTrue(cancelled["reader"]["timed_out"])
        self.assertEqual(cancelled["reader"]["timeout"], 4)
        self.assertTrue(cancelled["reader"]["cancelled"])
        self.assertEqual(cancelled["reader"]["cancellation"], 4)
        self.assertEqual(cancelled["reader"]["cancelled_work"], 6)
        self.assertIsNone(cancelled["reader"]["acquire"])
        self.assertIsNone(cancelled["reader"]["completion"])
        self.assertEqual(cancelled["writer"]["unlock"], 6)
        self.assertTrue(cancelled["writer"]["completed"])
        self.assertEqual(cancelled["record"]["final_generation"], [1, 1, 1, 1])
        self.assertEqual(cancelled["metrics"]["released_demand"], 12)
        self.assertEqual(cancelled["metrics"]["served"], 6)
        self.assertEqual(cancelled["metrics"]["cancelled"], 6)
        self.assertEqual(cancelled["metrics"]["remaining"], 0)
        self.assertEqual(cancelled["mutex_owner"][4:6], [1, 1])

        short_horizon = shared_record_reference(2, 2, 3, 2, horizon=4)
        self.assertEqual(short_horizon["cpu_owner"], [1, 1, 1, 1])
        self.assertEqual(short_horizon["mutex_owner"], [0, 0, 1, 1])
        self.assertTrue(short_horizon["writer"]["completed"])
        self.assertEqual(short_horizon["writer"]["completion"], 4)
        self.assertEqual(short_horizon["reader"]["remaining"], 4)
        self.assertEqual(short_horizon["metrics"]["released_demand"], 8)
        self.assertEqual(short_horizon["metrics"]["served"], 4)
        self.assertEqual(short_horizon["metrics"]["remaining"], 4)

        release_at_horizon = shared_record_reference(2, 2, 8, 2, horizon=8)
        self.assertFalse(release_at_horizon["reader"]["released"])
        self.assertEqual(release_at_horizon["metrics"]["released_demand"], 4)

        zero_private_work = shared_record_reference(0, 2, 1, 0, horizon=6)
        self.assertTrue(zero_private_work["writer"]["completed"])
        self.assertTrue(zero_private_work["reader"]["completed"])
        self.assertEqual(zero_private_work["metrics"]["remaining"], 0)


class P11LearningAndRegressionTests(unittest.TestCase):
    def test_experiment_has_baseline_two_isolated_sweeps_and_broken_case(self):
        experiment = read("experiment.m").lower()
        compact = re.sub(r"\s+", "", experiment).replace("...", "")
        self.assertIn("%% baseline", experiment)
        self.assertIn("isequaln(baseline,baselinerepeat)", compact)
        self.assertGreaterEqual(experiment.count("%% sweep"), 2)
        self.assertIn("writerpreparesweepms = [2 3 4 5]", experiment)
        self.assertIn("recordwordssweep = [2 3 4 5]", experiment)
        self.assertIn("isequal(shortwaitms, [0 0 0 0])", experiment)
        self.assertIn("isequal(shortresponsems, [4 4 4 4])", experiment)
        self.assertIn("isequal(coarsewaitms, [3 4 5 6])", experiment)
        self.assertIn("isequal(coarseresponsems, [7 8 9 10])", experiment)
        self.assertIn("isequal(coarseexcessms, [1 2 3 4])", experiment)
        self.assertIn("isequal(wordwaitms, [1 2 3 4])", experiment)
        self.assertIn("isequal(wordresponsems, [5 7 9 11])", experiment)
        self.assertIn("%% broken case", experiment)
        self.assertIn("p11_scenario('unprotected-torn')", experiment)
        self.assertIn("isequaln(recovered,baseline)", compact)
        self.assertIn("p11_scenario('timeout-continue')", experiment)
        self.assertIn("p11_scenario('timeout-cancel')", experiment)
        self.assertIn("isequaln(rollback,baseline)", compact)
        self.assertGreaterEqual(experiment.count("figure("), 5)
        self.assertIn("xlabel(", experiment)
        self.assertIn("ylabel(", experiment)
        self.assertIn("time (ms)", experiment)
        self.assertIn("cpu owner", experiment)
        self.assertIn("mutex owner", experiment)
        self.assertIn("protected record size (words)", experiment)
        self.assertIn("mechanism for sweep 1", experiment)
        self.assertIn("mechanism for sweep 2", experiment)
        self.assertIn("must retain every numeric model input", experiment)
        self.assertIn("must isolate its one protected-work input", experiment)

    def test_interactive_exposes_meaningful_controls_and_two_views(self):
        interactive = re.sub(r"\s+", " ", read("interactive.m").lower())
        self.assertIn("uifigure(", interactive)
        self.assertGreaterEqual(interactive.count("uispinner("), 1)
        self.assertGreaterEqual(interactive.count("uidropdown("), 3)
        for label in (
            "writer private prep (ms)",
            "protected record (words)",
            "reader release (ms)",
            "reader local process (ms)",
            "protection scope",
            "reader wait timeout (ms; 0=off)",
            "timeout action",
            "horizon (ms)",
            "scenario",
        ):
            with self.subTest(label=label):
                self.assertIn(label, interactive)
        self.assertGreaterEqual(interactive.count("uiaxes("), 2)
        self.assertIn("valuechangedfcn", interactive)
        self.assertIn("coarse lock (fixed)", interactive)
        self.assertIn("unprotected torn read (fixed)", interactive)
        self.assertIn("wait timeout continues (fixed)", interactive)
        self.assertIn("cancel blocked reader (fixed)", interactive)
        self.assertIn("not matlab-runtime", interactive)
        self.assertIn("memory-ordering", interactive)

    def test_interactive_callbacks_bind_p11_dependencies_before_path_cleanup(self):
        interactive = matlab_code_without_comments(read("interactive.m")).lower()
        compact = re.sub(r"\s+", "", interactive).replace("...", "")
        self.assertIn("modelfcn=@model;", compact)
        self.assertIn("scenariofcn=@p11_scenario;", compact)
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
            "writerpreparecontrol",
            "recordwordscontrol",
            "readerreleasecontrol",
            "readerprocesscontrol",
            "protectioncontrol",
            "waittimeoutcontrol",
            "timeoutactioncontrol",
            "horizoncontrol",
        ):
            with self.subTest(control=control):
                self.assertIn(f"{control}.value=", selector)
        self.assertIn("controls{controlindex}.enable='off';", selector)
        self.assertLess(selector.rindex(".value="), selector.index("updateviews();"))

    def test_executable_checks_cover_full_shared_data_failure_contract(self):
        checks = matlab_code_without_comments(read("run_checks.m"))
        lower = checks.lower()
        self.assertGreaterEqual(len(re.findall(r"\bassert\s*\(", checks)), 60)
        marker_groups = {
            "determinism": ("deterministic and state-isolated",),
            "mutual exclusion": ("protected reader must never execute", "mutual exclusion"),
            "ownership": ("mutex ownership",),
            "inheritance": ("inherit priority 2", "donation must be temporary"),
            "blocking decomposition": ("commit blocking", "scope excess"),
            "coherence": ("complete generation one", "coherent generation one"),
            "freshness": ("stale but coherent", "stale-but-consistent"),
            "torn negative": ("mixed-generation", "torn read"),
            "timeout": ("continue-waiting", "exact timeout boundary"),
            "cancellation": ("cancel-reader",),
            "owner-safe cancellation": ("without unlocking", "must not unlock"),
            "rollback": ("roll back exactly", "rollback"),
            "recovery": ("clean call after cancellation", "recover exact baseline"),
            "compatibility": ("integer-class scalars", "scalar strings"),
            "callback": ("callback-bound p11 dependencies",),
            "resource": ("accepted horizon resource bound", "accepted record resource bound"),
            "isolation": ("sweep must isolate",),
            "conservation": ("conserve", "work conservation"),
        }
        for contract, alternatives in marker_groups.items():
            with self.subTest(contract=contract):
                self.assertTrue(any(marker in lower for marker in alternatives))
        for identifier in (
            "p11:model:arity",
            "p11:model:writerprepare",
            "p11:model:recordwords",
            "p11:model:recordresourcebound",
            "p11:model:readerrelease",
            "p11:model:readerprocess",
            "p11:model:protection",
            "p11:model:tick",
            "p11:model:horizon",
            "p11:model:waittimeout",
            "p11:model:timeoutaction",
            "p11:model:gridalignment",
            "p11:model:timingresourcebound",
        ):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, lower)
        self.assertIn("malformed call must not contaminate", lower)
        self.assertIn("not an asynchronous rtos cancellation api", lower)
        self.assertIn("p11 checks passed", lower)

    def test_tutor_text_is_mechanism_first_and_ends_in_teach_back(self):
        lesson = re.sub(r"\s+", " ", read("lesson.md").lower())
        walkthrough = read("walkthrough.md").lower()
        checks = read("checks.md").lower()
        self.assertEqual(lesson.count("## one prediction"), 1)
        self.assertIn("h_coarse,writer = c_prepare + c_commit", lesson)
        self.assertIn("h_short,writer = c_commit", lesson)
        self.assertIn("b_reader = t_acquire - t_request", lesson)
        self.assertIn("b_reader = b_commit + b_scope-excess", lesson)
        self.assertIn("r_reader = b_reader + c_copy + c_process", lesson)
        self.assertIn("cpu-owner", lesson)
        self.assertIn("mutex ownership", lesson)
        self.assertIn("coherence", lesson)
        self.assertIn("freshness", lesson)
        self.assertIn("continue-waiting", lesson)
        self.assertIn("cancel-reader", lesson)
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
        self.assertIn("not matlab-runtime evidence", combined)
        self.assertIn("not an rtos", combined)
        self.assertIn("memory-ordering", combined)
        self.assertIn("processor", combined)
        self.assertIn("hardware", combined)
        self.assertIn("measured wcet", combined)
        self.assertIn("p10", combined)
        self.assertIn("p12", combined)
        self.assertIn("coherence", combined)
        self.assertIn("freshness", combined)
        self.assertNotIn("hardware-validated", combined)
        self.assertNotIn("rtos-validated", combined)

    def test_cli_start_routes_p11_and_persists_only_isolated_progress(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary) / "repo"
            fixture.mkdir()
            shutil.copytree(ROOT / "bin", fixture / "bin")
            shutil.copytree(ROOT / "curriculum", fixture / "curriculum")
            module_fixture = (
                fixture / "modules/11-protect-shared-data-without-excess-blocking"
            )
            module_fixture.mkdir(parents=True)
            for name in ("README.md", "lesson.md", "walkthrough.md", "checks.md"):
                shutil.copy2(MODULE_FOLDER / name, module_fixture / name)

            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            result = subprocess.run(
                [str(fixture / "bin/learn"), "start", "P11"],
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
                "P11 — Protect Shared Data Without Excess Blocking\n"
                "Status: implemented\n"
                f"Guiding question: {QUESTION}\n"
                "Folder: modules/11-protect-shared-data-without-excess-blocking\n"
                "\nMATLAB:\n"
                "  launch_lesson('P11')\n"
                "\nTutor files:\n"
                "  modules/11-protect-shared-data-without-excess-blocking/README.md\n"
                "  modules/11-protect-shared-data-without-excess-blocking/lesson.md\n"
                "  modules/11-protect-shared-data-without-excess-blocking/walkthrough.md\n"
                "  modules/11-protect-shared-data-without-excess-blocking/checks.md\n",
            )
            progress = json.loads(
                (fixture / ".learning/progress.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                progress, {"current": "P11", "completed": {}, "notes": {}}
            )

    def test_cli_check_resolves_p11_public_matlab_entry_point(self):
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [str(ROOT / "bin/learn"), "check", "P11"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env=environment,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "Run in MATLAB: run_module_checks('P11')\n")

    @unittest.skipUnless(shutil.which("matlab"), "MATLAB executable unavailable")
    def test_matlab_executes_module_checks_and_callback_lifetime(self):
        result = subprocess.run(
            [shutil.which("matlab"), "-batch", "run_module_checks('P11')"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=300,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"MATLAB P11 checks failed:\n{result.stdout}\n{result.stderr}",
        )
        self.assertIn("P11 checks passed", result.stdout)


class P11RetainedEvidenceTests(unittest.TestCase):
    def test_date_agnostic_retained_evidence_is_complete_and_honest(self):
        evidence_files = sorted((ROOT / "docs/evidence").glob("P11-*.md"))
        self.assertTrue(evidence_files, "P11 requires a retained evidence record")
        for path in evidence_files:
            with self.subTest(path=path.name):
                payload = path.read_bytes()
                self.assertTrue(payload.endswith(b"\n"))
                self.assertFalse(payload.endswith(b"\n\n"))
                text = payload.decode("utf-8").lower()
                for unfinished in (
                    "pending final retained result",
                    "<source-focused p11 test selectors>",
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
                    "memory-ordering",
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
