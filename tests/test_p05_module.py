from __future__ import annotations

import json
import math
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
QUESTION = (
    "What inputs, observable effects, and failure modes matter when you frame "
    "Bytes over UART?"
)
MODULE_FOLDER = ROOT / "modules/05-frame-bytes-over-uart"
CORE_ARTIFACTS = {
    "README.md",
    "lesson.m",
    "p05_scenario.m",
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


def uart_8n1(byte: int) -> list[int]:
    return [0, *[(byte // (2**bit)) % 2 for bit in range(8)], 1]


class P05IdentityAndArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(
            (ROOT / "curriculum/modules.json").read_text(encoding="utf-8")
        )
        cls.module = next(
            module for module in cls.manifest["modules"] if module["id"] == "P05"
        )

    def test_permanent_manifest_identity_and_prerequisite(self):
        self.assertEqual(self.module["number"], 5)
        self.assertEqual(self.module["title"], "Frame Bytes over UART")
        self.assertEqual(self.module["guiding_question"], QUESTION)
        self.assertEqual(self.module["phase"], 2)
        self.assertEqual(self.module["phase_title"], "Buses and acquisition")
        self.assertEqual(self.module["slug"], "frame-bytes-over-uart")
        self.assertEqual(
            self.module["folder"], "modules/05-frame-bytes-over-uart"
        )
        self.assertEqual(self.module["implementation_batch"], "P05")
        self.assertEqual(self.module["prerequisites"], ["P04"])
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
                self.assertLess(
                    len(payload), 100000, "educational artifact should stay bounded"
                )

    def test_guiding_question_prerequisite_and_claim_boundary_are_explicit(self):
        combined = "\n".join(
            read(name) for name in ("README.md", "lesson.md", "walkthrough.md")
        )
        self.assertIn(QUESTION, combined)
        self.assertIn("P04", read("lesson.md"))
        self.assertIn("finite clock", read("lesson.md").lower())
        self.assertIn("not a hardware measurement", combined.lower())
        self.assertIn("uart character framing", combined.lower())
        self.assertIn("packet boundaries", combined.lower())

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


class P05ModelContractTests(unittest.TestCase):
    def test_model_is_explicit_deterministic_and_resource_bounded(self):
        model = read("model.m")
        code = matlab_code_without_comments(model).lower()
        compact = re.sub(r"\s+", "", code).replace("...", "")
        self.assertIn(
            "functionout=model(payloadbytes,txbaudbps,receivererrorpct,"
            "paritymode,stopbits,interframegapbits,fault,receivetimeoutus)",
            compact,
        )
        self.assertIn("receiverbaudbps=txbaudbps.*(1+receivererrorpct./100);", compact)
        self.assertIn("txbitperiodus=1e6./txbaudbps;", compact)
        self.assertIn("bitsperframe=1+8+paritybitcount+stopbits;", compact)
        self.assertIn("mod(floor(payloadbytes(:)./(2.^bitindex)),2)", compact)
        self.assertIn("sampleoffsets=(0:(bitsperframe-1))+0.5;", compact)
        self.assertIn("receiverbitperiodus.*sampleoffsets", compact)
        self.assertIn(
            "linelevelat(frameindex,receiversamplepositionsbits", compact
        )
        self.assertIn("decodedbytes(frameindex)=sum(sampleddatabits.*(2.^(0:7)));", compact)
        self.assertIn("startedgeavailable(frameindex)=interframegapbits>0||", compact)
        self.assertIn("actualframebits(frameindex-1,end)==1;", compact)
        self.assertIn("maxframes=100000", compact)
        self.assertIn("maxlinebitcells=1000000", compact)
        self.assertIn("maxsamplepoints=1000000", compact)
        self.assertIn("forframeindex=1:framecount", compact)
        self.assertNotRegex(
            code,
            r"\b(?:persistent|global|while|rng|rand|randn|pause|timer|eval|system)\b",
        )
        self.assertLess(
            code.index("framecount = numel(payloadbytes)"),
            code.index("payloadbytes = validatepayload(payloadbytes)"),
            "payload size must be bounded before scanning byte values",
        )
        self.assertLess(
            code.index("if samplepointcount > maxsamplepoints"),
            code.index("nominalframebits = zeros"),
            "derived sample budget must be checked before frame allocation",
        )
        self.assertLess(
            code.index("if numel(bitindices) > 8"),
            code.index("reshape(double(bitindices)"),
            "fault-index cardinality must be bounded before conversion",
        )
        self.assertLess(
            code.index("if numel(bitindices) > 8"),
            code.index("unique(bitindices)"),
            "fault-index cardinality must be bounded before scanning uniqueness",
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
            "serialport",
            "serial",
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

    def test_model_rejects_malformed_format_fault_timing_and_resources(self):
        model = read("model.m")
        for identifier in (
            "P05:model:Arity",
            "P05:model:PayloadBytes",
            "P05:model:BaudRate",
            "P05:model:ReceiverError",
            "P05:model:ParityMode",
            "P05:model:StopBits",
            "P05:model:InterFrameGap",
            "P05:model:Fault",
            "P05:model:FaultFrame",
            "P05:model:FaultBit",
            "P05:model:ReceiveTimeout",
            "P05:model:ResourceBound",
            "P05:model:TimingResourceBound",
        ):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, model)
        self.assertIn("isvector", model)
        self.assertIn("isfinite", model)
        self.assertIn("isreal", model)
        self.assertIn("unique(bitIndices)", model)

    def test_scenario_is_seedless_bounded_and_compatible(self):
        scenario = matlab_code_without_comments(read("p05_scenario.m")).lower()
        self.assertIn("function input = p05_scenario(", scenario)
        for name in ("baseline", "parity-fault", "stop-fault-recovery", "deadline"):
            self.assertIn(name, scenario)
        self.assertIn("payload_bytes = [163 85 60 126]", scenario)
        self.assertIn("receive_timeout_us = 170", scenario)
        self.assertNotRegex(scenario, r"\b(?:rng|rand|randn|while|timer|pause)\b")

    def test_independent_uart_reference_vectors_and_clock_margins(self):
        self.assertEqual(uart_8n1(0), [0, 0, 0, 0, 0, 0, 0, 0, 0, 1])
        self.assertEqual(uart_8n1(85), [0, 1, 0, 1, 0, 1, 0, 1, 0, 1])
        self.assertEqual(uart_8n1(163), [0, 1, 1, 0, 0, 0, 1, 0, 1, 1])
        self.assertNotEqual(uart_8n1(163)[1:9], uart_8n1(163)[1:9][::-1])
        self.assertEqual(uart_8n1(255), [0, 1, 1, 1, 1, 1, 1, 1, 1, 1])

        errors = [-6, -4, -2, 0, 2, 4, 6]
        margins = []
        for error in errors:
            ratio = 1 + error / 100
            positions = [(slot + 0.5) / ratio for slot in range(10)]
            margins.append(
                min(
                    min(position - slot, slot + 1 - position)
                    for slot, position in enumerate(positions)
                )
            )
        expected = [-5 / 47, 5 / 48, 15 / 49, 1 / 2, 16 / 51, 7 / 52, -2 / 53]
        for observed, reference in zip(margins, expected, strict=True):
            self.assertAlmostEqual(observed, reference, places=14)
        self.assertEqual(4 * 10 * 1_000_000 / 115200, 347.22222222222223)
        self.assertEqual(8 / 10, 0.8)
        self.assertTrue(math.isclose(0.8 * 115200, 92160.0))

    def test_receiver_readiness_is_frame_local_at_late_indices(self):
        completion_bits = 10 + 1e-10
        error_pct = 100 * (9.5 / completion_bits - 1)
        tx_period_us = 1_000_000.0
        completion_offset_us = 9.5 * tx_period_us / (1 + error_pct / 100)

        early_start_us = 10 * tx_period_us
        early_tolerance_us = 16 * math.ulp(
            max(1.0, completion_offset_us, early_start_us)
        )
        self.assertLess(early_start_us, completion_offset_us - early_tolerance_us)

        late_frame = 10_000
        late_start_us = (late_frame - 1) * 10 * tx_period_us
        late_ready_us = (late_frame - 2) * 10 * tx_period_us + completion_offset_us
        late_tolerance_us = 16 * math.ulp(
            max(1.0, late_ready_us, late_start_us)
        )
        self.assertFalse(late_start_us < late_ready_us - late_tolerance_us)

        model = matlab_code_without_comments(read("model.m")).lower()
        compact = re.sub(r"\s+", "", model).replace("...", "")
        self.assertIn(
            "elapsedfromreadysourcebits=(frameindex-"
            "receiverreadysourceframeindex).*framestridebits;",
            compact,
        )
        self.assertIn(
            "receiverSamplePositionsBits(end) - readyToleranceBits",
            read("model.m"),
        )
        self.assertNotIn("receiverReadyUs", read("model.m"))

        checks = read("run_checks.m").lower()
        self.assertIn("largebatchnearready.rx.receiver_busy(10000)", checks)
        self.assertIn(
            "late absolute timestamps must not change the frame-local receiver",
            checks,
        )


class P05LearningAndRegressionTests(unittest.TestCase):
    def test_experiment_has_baseline_two_independent_sweeps_and_broken_case(self):
        experiment = read("experiment.m").lower()
        compact = re.sub(r"\s+", "", experiment).replace("...", "")
        self.assertIn("%% baseline", experiment)
        self.assertGreaterEqual(experiment.count("%% sweep"), 2)
        self.assertIn("baudsweepbps = [9600 19200 57600 115200]", experiment)
        self.assertIn("receivererrorsweeppct = [-8 -6 -4 0 4 6 8]", experiment)
        self.assertIn("%% broken case", experiment)
        self.assertIn("p05_scenario('stop-fault-recovery')", experiment)
        self.assertIn("[true true false true]", experiment)
        self.assertIn("recovery_frame_index == 4", experiment)
        self.assertIn("isequaln(rolledback,baseline)", compact)
        self.assertIn(
            "stairs(badedgesus,[broken.tx.nominal_frame_bits(badframe,:)", compact
        )
        self.assertGreaterEqual(experiment.count("figure("), 4)
        self.assertIn("xlabel(", experiment)
        self.assertIn("ylabel(", experiment)
        self.assertIn("time from frame start (us)", experiment)
        self.assertIn("transmitter baud (bit/s)", experiment)
        self.assertIn("receiver baud error (%)", experiment)
        self.assertIn("minimum sample margin (tx bit times)", experiment)
        self.assertIn("mechanism for sweep 1", experiment)
        self.assertIn("mechanism for sweep 2", experiment)
        self.assertIn("the baud lever must scale time without changing", experiment)
        self.assertIn("receiver-clock lever must not mutate", experiment)

    def test_interactive_exposes_meaningful_controls_and_two_views(self):
        interactive = re.sub(r"\s+", " ", read("interactive.m").lower())
        self.assertIn("uifigure(", interactive)
        self.assertGreaterEqual(interactive.count("uispinner("), 4)
        self.assertGreaterEqual(interactive.count("uidropdown("), 2)
        self.assertIn("transmit baud (bit/s)", interactive)
        self.assertIn("receiver error (%)", interactive)
        self.assertIn("parity", interactive)
        self.assertIn("stop bits", interactive)
        self.assertIn("idle gap (bit times)", interactive)
        self.assertIn("forced-low stop and recovery", interactive)
        self.assertIn("valuechangedfcn", interactive)
        self.assertGreaterEqual(interactive.count("uiaxes("), 2)
        self.assertIn("character frames do not supply packet", interactive)
        self.assertIn("boundaries.", interactive)
        self.assertIn("not a hardware measurement", interactive)

    def test_interactive_callbacks_bind_p05_dependencies_before_path_cleanup(self):
        interactive = matlab_code_without_comments(read("interactive.m")).lower()
        compact = re.sub(r"\s+", "", interactive).replace("...", "")
        self.assertIn("modelfcn=@model;", compact)
        self.assertIn("scenariofcn=@p05_scenario;", compact)
        self.assertIn("input=scenariofcn(scenarioname);", compact)
        self.assertIn(
            "out=modelfcn(input.payload_bytes,baudcontrol.value,"
            "receivererrorcontrol.value,paritycontrol.value,"
            "stopbitscontrol.value,gapcontrol.value,input.fault,"
            "input.receive_timeout_us);",
            compact,
        )

    def test_fixed_diagnostics_reset_before_rendering(self):
        interactive = re.sub(
            r"\s+", "", matlab_code_without_comments(read("interactive.m")).lower()
        ).replace("...", "")
        selector = interactive[
            interactive.index("functionselectscenario") : interactive.index(
                "functionupdateviews"
            )
        ]
        for reset in (
            "receivererrorcontrol.value=0;",
            "paritycontrol.value='none';",
            "stopbitscontrol.value=1;",
            "gapcontrol.value=0;",
            "baudcontrol.value=115200;",
        ):
            self.assertIn(reset, selector)
        self.assertIn("gapcontrol.enable='off';", selector)
        self.assertIn("baudcontrol.enable='off';", selector)
        self.assertLess(selector.index("gapcontrol.value=0;"), selector.index("updateviews();"))

    def test_executable_checks_cover_limits_faults_timeout_recovery_and_rejection(self):
        checks = matlab_code_without_comments(read("run_checks.m"))
        lower = checks.lower()
        self.assertGreaterEqual(len(re.findall(r"\bassert\s*\(", checks)), 45)
        for marker in (
            "empty input must retain zero frames",
            "known bytes must encode start-low",
            "matched continuous 8-n-1 goodput",
            "two-stop-bit format",
            "receiver-error sweep margins",
            "sample exactly on a slot transition",
            "large-index batched-versus-isolated sampling",
            "slow receiver must still be sampling",
            "baud sweep line time",
            "one post-parity data-bit flip",
            "two flipped one-bits",
            "forced-low stop fixture",
            "frame four must prove later recovery",
            "resetting fault and deadline inputs",
            "deadline exactly at frame two final sample",
            "deadline just before frame two final sample",
            "repeated calls must be deterministic and state-isolated",
            "column and integer byte inputs",
            "omitted and empty optional fault/deadline inputs",
            "callback-bound p05 dependencies must survive module path cleanup",
            "p05:model:payloadbytes",
            "p05:model:receivetimeout",
            "p05:model:faultframe",
            "p05:model:faultbit",
            "p05:model:resourcebound",
            "malformed call must not contaminate",
            "p05 checks passed",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, lower)
        self.assertIn(
            "no asynchronous wait or cancellation api", read("run_checks.m").lower()
        )

    def test_tutor_text_is_mechanism_first_and_ends_in_teach_back(self):
        lesson = re.sub(r"\s+", " ", read("lesson.md").lower())
        walkthrough = read("walkthrough.md").lower()
        checks = read("checks.md").lower()
        self.assertIn("n_frame = 1 + 8 + n_parity + n_stop", lesson)
        self.assertIn("t_sample(j) = t_start + (j + 1/2) * t_rx", lesson)
        self.assertIn("b_rx = b_tx * (1 + e/100)", lesson)
        self.assertEqual(lesson.count("## one prediction"), 1)
        self.assertIn("move one control", walkthrough)
        self.assertIn("reset", walkthrough)
        self.assertIn("interpretation", checks)
        self.assertIn("teach-back", checks)
        self.assertIn("cancellation is not applicable", lesson)
        self.assertIn("mechanism first", walkthrough)

    def test_claim_language_separates_character_protocol_and_physical_evidence(self):
        combined = "\n".join(
            read(name).lower()
            for name in ("README.md", "lesson.md", "checks.md", "experiment.m")
        )
        self.assertIn("no universal uart mismatch percentage", combined)
        self.assertIn("parity is not", combined)
        self.assertIn("uart character framing", combined)
        self.assertIn("not a hardware measurement", combined)
        self.assertIn("rs-232", combined)
        self.assertNotIn("hardware-validated", combined)
        self.assertNotIn("measured uart", combined)


class P05RetainedEvidenceTests(unittest.TestCase):
    def test_date_agnostic_retained_evidence_is_complete_and_honest(self):
        evidence_files = sorted((ROOT / "docs/evidence").glob("P05-*.md"))
        self.assertTrue(evidence_files, "P05 requires a retained evidence record")
        for path in evidence_files:
            with self.subTest(path=path.name):
                payload = path.read_bytes()
                self.assertTrue(payload.endswith(b"\n"))
                self.assertFalse(payload.endswith(b"\n\n"))
                text = payload.decode("utf-8").lower()
                for marker in (
                    "## acceptance mapping",
                    "## deterministic model and failure contract",
                    "## figure, control, metric, and unit inventory",
                    "## exact commands and results",
                    "matlab_learning_verify_profile=contract python3 scripts/verify.py",
                    "matlab_learning_verify_profile=quick python3 -m unittest discover -s tests -v",
                    "matlab_learning_verify_profile=full ./scripts/agent-verify.sh",
                    "## changed invariants",
                    "## preserved invariants and scope",
                    "## profile applicability",
                    "## rollback",
                    "## residual risks",
                    "## unperformed validation",
                    "matlab runtime",
                    "not performed",
                ):
                    self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
