from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
QUESTION = (
    "What inputs, observable effects, and failure modes matter when you compare "
    "SPI and I2C Transactions?"
)
MODULE_FOLDER = ROOT / "modules/06-compare-spi-and-i2c-transactions"
CORE_ARTIFACTS = {
    "README.md",
    "lesson.m",
    "p06_scenario.m",
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


def msb_bits(byte: int) -> list[int]:
    return [(byte // (2**bit)) % 2 for bit in range(7, -1, -1)]


class P06IdentityAndArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(
            (ROOT / "curriculum/modules.json").read_text(encoding="utf-8")
        )
        cls.module = next(
            module for module in cls.manifest["modules"] if module["id"] == "P06"
        )

    def test_permanent_manifest_identity_and_prerequisite(self):
        self.assertEqual(self.module["number"], 6)
        self.assertEqual(self.module["title"], "Compare SPI and I2C Transactions")
        self.assertEqual(self.module["guiding_question"], QUESTION)
        self.assertEqual(self.module["phase"], 2)
        self.assertEqual(self.module["phase_title"], "Buses and acquisition")
        self.assertEqual(self.module["slug"], "compare-spi-and-i2c-transactions")
        self.assertEqual(
            self.module["folder"],
            "modules/06-compare-spi-and-i2c-transactions",
        )
        self.assertEqual(self.module["implementation_batch"], "P06")
        self.assertEqual(self.module["prerequisites"], ["P05"])
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
        self.assertIn("P05", read("lesson.md"))
        self.assertIn("framing overhead", read("lesson.md").lower())
        self.assertIn("not a hardware measurement", combined.lower())
        self.assertIn("device convention", combined.lower())
        self.assertIn("standards-conformance", combined.lower())

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


class P06ModelContractTests(unittest.TestCase):
    def test_model_is_explicit_deterministic_linear_and_resource_bounded(self):
        model = read("model.m")
        code = matlab_code_without_comments(model).lower()
        compact = re.sub(r"\s+", "", code).replace("...", "")
        self.assertIn(
            "functionout=model(payloadbytes,spiclockhz,i2cclockhz,"
            "i2caddress7,registeraddress,fault,transactiontimeoutus)",
            compact,
        )
        self.assertIn("spiclockedbitcount=8.*(payloadcount+1);", compact)
        self.assertIn(
            "i2cnominalclockedbitcount=9.*(payloadcount+3);", compact
        )
        self.assertIn(
            "i2cheaderbytes=[2.*i2caddress7registeraddress2.*i2caddress7+1];",
            compact,
        )
        self.assertIn("i2ccontrollerresponsebits(end)=1;", compact)
        self.assertIn("i2cresponseowners{headerindex}='target';", compact)
        self.assertIn("repmat({'controller'},1,payloadcount)", compact)
        self.assertIn(
            "i2cmodeledelapsedtimeus=i2cclockedtimeus+i2cstretchus;", compact
        )
        self.assertIn("spichipselectlevels=zeros(1,spiclockedbitcount);", compact)
        self.assertIn("'chip_select_active_level',0", compact)
        self.assertIn("'chip_select_assert_clock_index',0", compact)
        self.assertIn(
            "'chip_select_deassert_clock_index',spiclockedbitcount", compact
        )
        self.assertIn("exceeded=durationus>timeoutus;", compact)
        self.assertNotIn("toleranceus", compact)
        self.assertIn("maxpayloadbytes=100000", compact)
        self.assertIn("maxclockedcells=850000", compact)
        self.assertIn("forheaderindex=1:attemptedheadercount", compact)
        self.assertIn("forpayloadindex=1:payloadcount", compact)
        self.assertNotRegex(
            code,
            r"\b(?:persistent|global|while|rng|rand|randn|pause|timer|eval|system)\b",
        )
        self.assertLess(
            code.index("payloadcount = numel(payloadbytes)"),
            code.index("payloadbytes = validatepayload(payloadbytes)"),
            "payload size must be bounded before scanning values",
        )
        self.assertLess(
            code.index("if spiclockedbitcount > maxclockedcells"),
            code.index("spimosibitmatrix = bytebitmatrixmsb"),
            "derived cell counts must be bounded before bit allocation",
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
            "spi",
            "i2cdev",
            "arduino",
            "fopen",
            "timetable",
            "timeseries",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotRegex(code, rf"\b{forbidden}\s*\(")
        self.assertNotIn("simulink", code)
        self.assertNotIn("instrument control", code)

    def test_model_rejects_malformed_fault_timing_and_resources(self):
        model = read("model.m")
        for identifier in (
            "P06:model:Arity",
            "P06:model:PayloadBytes",
            "P06:model:SPIClock",
            "P06:model:I2CClock",
            "P06:model:I2CAddress",
            "P06:model:RegisterAddress",
            "P06:model:TransactionTimeout",
            "P06:model:Fault",
            "P06:model:FaultMode",
            "P06:model:FaultField",
            "P06:model:I2CAckIndex",
            "P06:model:SPIPayloadIndex",
            "P06:model:SPIBitIndex",
            "P06:model:ClockStretch",
            "P06:model:ResourceBound",
            "P06:model:TimingResourceBound",
        ):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, model)
        self.assertIn("isvector", model)
        self.assertIn("isfinite", model)
        self.assertIn("isreal", model)
        self.assertIn("~isempty(payloadBytes)", model)

    def test_scenario_is_seedless_bounded_and_compatible(self):
        scenario = matlab_code_without_comments(read("p06_scenario.m")).lower()
        self.assertIn("function input = p06_scenario(", scenario)
        for name in (
            "baseline",
            "target-nack",
            "spi-corruption",
            "stretch-timeout",
        ):
            self.assertIn(name, scenario)
        self.assertIn("fixturebytes = [163 86 201 30 0 255 90 165]", scenario)
        self.assertIn("spi_clock_hz = 400000", scenario)
        self.assertIn("i2c_clock_hz = 400000", scenario)
        self.assertIn("i2c_stretch_us', 300", scenario)
        self.assertIn("transaction_timeout_us = 250", scenario)
        self.assertIn("payloadcount >= 1", scenario)
        self.assertNotRegex(scenario, r"\b(?:rng|rand|randn|while|timer|pause)\b")

    def test_independent_reference_vectors_counts_and_sweeps(self):
        self.assertEqual(msb_bits(0xAD), [1, 0, 1, 0, 1, 1, 0, 1])
        self.assertEqual(msb_bits(0x90), [1, 0, 0, 1, 0, 0, 0, 0])
        self.assertEqual(msb_bits(0x2D), [0, 0, 1, 0, 1, 1, 0, 1])
        self.assertEqual(msb_bits(0x91), [1, 0, 0, 1, 0, 0, 0, 1])
        self.assertEqual(msb_bits(0xA3), [1, 0, 1, 0, 0, 0, 1, 1])
        self.assertEqual(2 * 0x48, 0x90)
        self.assertEqual(2 * 0x48 + 1, 0x91)

        counts = [1, 2, 4, 8, 16]
        self.assertEqual([8 * (count + 1) for count in counts], [16, 24, 40, 72, 136])
        self.assertEqual(
            [9 * (count + 3) for count in counts], [36, 45, 63, 99, 171]
        )
        self.assertTrue(
            all(
                left < right
                for left, right in zip(
                    [count / (count + 1) for count in counts],
                    [count / (count + 1) for count in counts][1:],
                )
            )
        )
        self.assertTrue(math.isclose(40 / 400_000 * 1_000_000, 100.0))
        self.assertTrue(math.isclose(63 / 400_000 * 1_000_000, 157.5))
        self.assertTrue(math.isclose(32 / 63, 0.5079365079365079))
        self.assertEqual([157.5 + value for value in [0, 25, 100, 250]], [157.5, 182.5, 257.5, 407.5])


class P06LearningAndRegressionTests(unittest.TestCase):
    def test_experiment_has_baseline_two_independent_sweeps_and_broken_case(self):
        experiment = read("experiment.m").lower()
        compact = re.sub(r"\s+", "", experiment).replace("...", "")
        self.assertIn("%% baseline", experiment)
        self.assertGreaterEqual(experiment.count("%% sweep"), 2)
        self.assertIn("payloadcountsweep = [1 2 4 8 16]", experiment)
        self.assertIn("stretchsweepus = [0 25 100 250]", experiment)
        self.assertIn("%% broken case", experiment)
        self.assertIn("p06_scenario('target-nack')", experiment)
        self.assertIn("p06_scenario('spi-corruption')", experiment)
        self.assertIn("p06_scenario('stretch-timeout')", experiment)
        self.assertIn("actual_clocked_bit_count == 18", experiment)
        self.assertIn("received_payload_bytes(2) == 87", experiment)
        self.assertIn("isequaln(recovered,baseline)", compact)
        self.assertGreaterEqual(experiment.count("figure("), 5)
        self.assertIn("xlabel(", experiment)
        self.assertIn("ylabel(", experiment)
        self.assertIn("spi clock pulse index", experiment)
        self.assertIn("i2c scl clock pulse index", experiment)
        self.assertIn("nominal clocked time (us)", experiment)
        self.assertIn("read-payload efficiency (%)", experiment)
        self.assertIn("modeled i2c clock stretch (us)", experiment)
        self.assertIn("mechanism for sweep 1", experiment)
        self.assertIn("mechanism for sweep 2", experiment)
        self.assertIn("payload-length lever must not change", experiment)
        self.assertIn("clock stretch must not add or mutate", experiment)

    def test_interactive_exposes_meaningful_controls_and_two_views(self):
        interactive_source = read("interactive.m")
        interactive = re.sub(r"\s+", " ", interactive_source.lower())
        self.assertIn("uifigure(", interactive)
        self.assertGreaterEqual(interactive.count("uispinner("), 6)
        self.assertIn("uidropdown(", interactive)
        self.assertIn("payload (bytes)", interactive)
        self.assertIn("spi clock (khz)", interactive)
        self.assertIn("i2c clock (khz)", interactive)
        self.assertIn("i2c stretch (us)", interactive)
        self.assertIn("i2c 7-bit address", interactive)
        self.assertIn("register", interactive)
        self.assertIn("target nack on register", interactive)
        self.assertIn("spi returned-bit corruption", interactive)
        self.assertIn("fixed stretch deadline", interactive)
        self.assertIn("'Limits', [1 64]", interactive_source)
        self.assertIn("valuechangedfcn", interactive)
        self.assertGreaterEqual(interactive.count("uiaxes("), 2)
        self.assertIn("final read nack is controller-owned", interactive)
        self.assertIn("not a hardware measurement", interactive)

    def test_interactive_callbacks_bind_p06_dependencies_before_path_cleanup(self):
        interactive = matlab_code_without_comments(read("interactive.m")).lower()
        compact = re.sub(r"\s+", "", interactive).replace("...", "")
        self.assertIn("modelfcn=@model;", compact)
        self.assertIn("scenariofcn=@p06_scenario;", compact)
        self.assertIn(
            "input=scenariofcn(scenarioname,payloadcontrol.value);", compact
        )
        self.assertIn(
            "out=modelfcn(input.payload_bytes,spiclockcontrol.value.*1000,"
            "i2cclockcontrol.value.*1000,addresscontrol.value,"
            "registercontrol.value,fault,timeoutus);",
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
            "payloadcontrol.value=4;",
            "spiclockcontrol.value=400;",
            "i2cclockcontrol.value=400;",
            "stretchcontrol.value=0;",
            "addresscontrol.value=72;",
            "registercontrol.value=45;",
        ):
            self.assertIn(reset, selector)
        self.assertIn("controls{controlindex}.enable='off';", selector)
        self.assertLess(selector.index("stretchcontrol.value=0;"), selector.index("updateviews();"))

    def test_executable_checks_cover_limits_faults_timeout_recovery_and_rejection(self):
        checks = matlab_code_without_comments(read("run_checks.m"))
        lower = checks.lower()
        self.assertGreaterEqual(len(re.findall(r"\bassert\s*\(", checks)), 45)
        for marker in (
            "model([], 400000, 400000, 72, 45)",
            "p06_scenario('baseline', 0)",
            "one returned byte must require 16 spi and 36 i2c pulses",
            "spi mosi must send command ad msb-first",
            "one active-low chip select must span every command and payload clock",
            "i2c headers must be address-write 90",
            "first three responses are target-owned",
            "final controller nack must remain successful termination",
            "four bytes must use 40 simultaneous spi and 63 i2c clock pulses",
            "payload-length sweep pulse counts",
            "fixed-overhead amortization",
            "clock rate must not mutate",
            "stretch sweep must leave pulse count",
            "target nack must stop at its own ninth clock",
            "register-byte nack must prevent repeated start",
            "clean retry after target nack",
            "generic spi must complete",
            "removing fault and deadline inputs",
            "deadline exactly at i2c elapsed time",
            "deadline just before i2c completion",
            "deadline one representable step before completion must be strict",
            "300 us stretch must miss 250 us",
            "repeated calls must be deterministic and state-isolated",
            "column and integer inputs",
            "callback-bound p06 dependencies must survive module path cleanup",
            "p06:model:payloadbytes",
            "p06:model:transactiontimeout",
            "p06:model:i2cackindex",
            "p06:model:spipayloadindex",
            "p06:model:clockstretch",
            "p06:model:resourcebound",
            "malformed call must not contaminate",
            "p06 checks passed",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, lower)
        self.assertIn(
            "no asynchronous wait or cancellation api", read("run_checks.m").lower()
        )

    def test_cli_check_resolves_p06_public_matlab_entry_point(self):
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [str(ROOT / "bin/learn"), "check", "P06"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env=environment,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "Run in MATLAB: run_module_checks('P06')\n")

    @unittest.skipUnless(shutil.which("matlab"), "MATLAB executable unavailable")
    def test_matlab_executes_module_checks_and_callback_lifetime(self):
        result = subprocess.run(
            [
                shutil.which("matlab"),
                "-batch",
                "run_module_checks('P06')",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=300,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"MATLAB P06 checks failed:\n{result.stdout}\n{result.stderr}",
        )
        self.assertIn("P06 checks passed", result.stdout)

    def test_tutor_text_is_mechanism_first_and_ends_in_teach_back(self):
        lesson = re.sub(r"\s+", " ", read("lesson.md").lower())
        walkthrough = read("walkthrough.md").lower()
        checks = read("checks.md").lower()
        self.assertIn("c_spi = 8(n + 1)", lesson)
        self.assertIn("c_i2c = 9(n + 3)", lesson)
        self.assertIn("t_i2c,modeled", lesson)
        self.assertIn("0x90 = 2*0x48 + 0", lesson)
        self.assertEqual(lesson.count("## one prediction"), 1)
        self.assertIn("move one control", walkthrough)
        self.assertIn("reset", walkthrough)
        self.assertIn("interpretation", checks)
        self.assertIn("teach-back", checks)
        self.assertIn("cancellation is not applicable", lesson)
        self.assertIn("mechanism first", walkthrough)

    def test_claim_language_separates_protocol_device_and_physical_evidence(self):
        combined = "\n".join(
            read(name).lower()
            for name in ("README.md", "lesson.md", "checks.md", "experiment.m")
        )
        self.assertIn("not universal spi", combined)
        self.assertIn("device convention", combined)
        self.assertIn("final controller nack", combined)
        self.assertIn("ack does not prove", combined)
        self.assertIn("not a hardware measurement", combined)
        self.assertIn("start, repeated start, and stop", combined)
        self.assertNotIn("spi is always faster", combined)
        self.assertNotIn("hardware-validated", combined)
        self.assertNotIn("measured bus", combined)


class P06RetainedEvidenceTests(unittest.TestCase):
    def test_date_agnostic_retained_evidence_is_complete_and_honest(self):
        evidence_files = sorted((ROOT / "docs/evidence").glob("P06-*.md"))
        self.assertTrue(evidence_files, "P06 requires a retained evidence record")
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
