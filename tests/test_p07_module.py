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
    "What inputs, observable effects, and failure modes matter when you sample "
    "an ADC Without Aliasing?"
)
MODULE_FOLDER = ROOT / "modules/07-sample-an-adc-without-aliasing"
CORE_ARTIFACTS = {
    "README.md",
    "lesson.m",
    "p07_scenario.m",
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


def signed_fold(frequency_hz: float, sample_rate_hz: float) -> float:
    return (
        (frequency_hz + sample_rate_hz / 2) % sample_rate_hz
        - sample_rate_hz / 2
    )


def ideal_codes(
    frequency_hz: float,
    sample_rate_hz: float,
    sample_count: int,
    bits: int,
    amplitude_v: float = 1.0,
    offset_v: float = 1.65,
    reference_v: float = 3.3,
) -> list[int]:
    folded = signed_fold(frequency_hz, sample_rate_hz)
    apparent = abs(folded)
    phase = -0.0 if folded < 0 else 0.0
    lsb = reference_v / (2**bits)
    values = [
        offset_v
        + amplitude_v
        * math.cos(2 * math.pi * apparent * index / sample_rate_hz + phase)
        for index in range(sample_count)
    ]
    return [
        min(math.floor(min(max(value, 0.0), reference_v) / lsb), 2**bits - 1)
        for value in values
    ]


def dense_reference_point_count(
    frequency_hz: float, sample_rate_hz: float, sample_count: int
) -> int:
    last_sample_time_s = (sample_count - 1) / sample_rate_hz
    frequency_driven = (
        math.ceil(
            24
            * frequency_hz
            * max(last_sample_time_s, 1 / sample_rate_hz)
        )
        + 1
    )
    return max(512, 16 * sample_count, frequency_driven)


class P07IdentityAndArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(
            (ROOT / "curriculum/modules.json").read_text(encoding="utf-8")
        )
        cls.module = next(
            module for module in cls.manifest["modules"] if module["id"] == "P07"
        )

    def test_permanent_manifest_identity_and_prerequisite(self):
        self.assertEqual(self.module["number"], 7)
        self.assertEqual(self.module["title"], "Sample an ADC Without Aliasing")
        self.assertEqual(self.module["guiding_question"], QUESTION)
        self.assertEqual(self.module["phase"], 2)
        self.assertEqual(self.module["phase_title"], "Buses and acquisition")
        self.assertEqual(self.module["slug"], "sample-an-adc-without-aliasing")
        self.assertEqual(
            self.module["folder"],
            "modules/07-sample-an-adc-without-aliasing",
        )
        self.assertEqual(self.module["implementation_batch"], "P07")
        self.assertEqual(self.module["prerequisites"], ["P06"])
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
        self.assertIn("P06", read("lesson.md"))
        self.assertIn("correctly transported adc codes", read("lesson.md").lower())
        self.assertIn("not a hardware measurement", combined.lower())
        self.assertIn("analog anti-alias filter", combined.lower())
        self.assertIn("digital filter cannot undo", combined.lower())

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


class P07ModelContractTests(unittest.TestCase):
    def test_model_is_explicit_deterministic_and_resource_bounded(self):
        model = read("model.m")
        code = matlab_code_without_comments(model).lower()
        compact = re.sub(r"\s+", "", code).replace("...", "")
        self.assertIn(
            "functionout=model(signalfrequencyhz,sampleratehz,samplecount,"
            "amplitudev,offsetv,phaserad,antialiascutoffhz,adcbits,"
            "referencevoltagev,fault,acquisitiondeadlines)",
            compact,
        )
        self.assertIn(
            "signedfoldhz=mod(signalfrequencyhz+nyquisthz,sampleratehz)-nyquisthz;",
            compact,
        )
        self.assertIn("aliasfrequencyhz=abs(signedfoldhz);", compact)
        self.assertIn(
            "strictnyquistsafe=signalfrequencyhz<nyquisthz;", compact
        )
        self.assertIn(
            "filtergain=1./sqrt(1+normalizedfrequency.^2);", compact
        )
        self.assertIn("filterphaserad=-atan(normalizedfrequency);", compact)
        self.assertIn("sampletimes=(0:(samplecount-1))./sampleratehz;", compact)
        self.assertIn("levelcount=2.^adcbits;", compact)
        self.assertIn("lsbv=referencevoltagev./levelcount;", compact)
        self.assertIn("codes=min(floor(clippedsamplev./lsbv),maxcode);", compact)
        self.assertIn("codecenterv=(codes+0.5).*lsbv;", compact)
        self.assertIn(
            "modeledacquisitiontimes=samplecount./sampleratehz;", compact
        )
        self.assertIn("timedout=modeledacquisitiontimes>acquisitiondeadlines;", compact)
        self.assertIn("'raw_payload_rate_bps',sampleratehz.*adcbits", compact)
        self.assertIn("maxsamples=10000", compact)
        self.assertIn("maxreferencepoints=200000", compact)
        self.assertNotRegex(
            code,
            r"\b(?:persistent|global|while|rng|rand|randn|pause|timer|eval|system)\b",
        )
        self.assertLess(
            code.index("if isnumeric(samplecount)"),
            code.index("samplecount = validateintegerscalar"),
            "sample cardinality must be bounded before numeric normalization",
        )
        self.assertLess(
            code.index("if ~isfinite(referencepointcount)"),
            code.index("referencetimes = linspace"),
            "derived reference size must be bounded before allocation",
        )

    def test_model_has_no_presentation_hardware_or_opaque_toolbox_calls(self):
        code = matlab_code_without_comments(read("model.m")).lower()
        for forbidden in (
            "figure",
            "plot",
            "uifigure",
            "fprintf",
            "disp",
            "fft",
            "resample",
            "lowpass",
            "designfilt",
            "sim",
            "daq",
            "analoginput",
            "arduino",
            "fopen",
            "timetable",
            "timeseries",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotRegex(code, rf"\b{forbidden}\s*\(")
        self.assertNotIn("simulink", code)
        self.assertNotIn("data acquisition toolbox", code)

    def test_model_rejects_malformed_fault_timing_and_resources(self):
        model = read("model.m")
        for identifier in (
            "P07:model:Arity",
            "P07:model:SignalFrequency",
            "P07:model:SampleRate",
            "P07:model:SampleCount",
            "P07:model:Amplitude",
            "P07:model:Offset",
            "P07:model:Phase",
            "P07:model:AntiAliasCutoff",
            "P07:model:ADCBits",
            "P07:model:ReferenceVoltage",
            "P07:model:AcquisitionDeadline",
            "P07:model:Fault",
            "P07:model:FaultMode",
            "P07:model:ResourceBound",
            "P07:model:TimingResourceBound",
        ):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, model)
        self.assertIn("isfinite", model)
        self.assertIn("isreal", model)
        self.assertIn("isscalar", model)

    def test_scenario_is_seedless_bounded_and_compatible(self):
        scenario = matlab_code_without_comments(read("p07_scenario.m")).lower()
        self.assertIn("function input = p07_scenario(", scenario)
        for name in (
            "baseline",
            "alias-trap",
            "nyquist-boundary",
            "clipping",
            "deadline",
        ):
            self.assertIn(name, scenario)
        self.assertIn("signal_frequency_hz = 180", scenario)
        self.assertIn("sample_rate_hz = 1000", scenario)
        self.assertIn("sample_count = double(samplecount)", scenario)
        self.assertIn("anti_alias_cutoff_hz = 400", scenario)
        self.assertIn("adc_bits = 12", scenario)
        self.assertIn("reference_voltage_v = 3.3", scenario)
        self.assertIn("acquisition_deadline_s = 0.05", scenario)
        self.assertIn("samplecount <= 10000", scenario)
        self.assertIn("input.offset_v = 1.6", scenario)
        self.assertNotRegex(
            scenario, r"\b(?:rng|rand|randn|while|timer|pause)\b"
        )

    def test_independent_fold_filter_adc_and_alias_references(self):
        sample_rates = [1000, 600, 400, 300, 250]
        folds = [signed_fold(180, rate) for rate in sample_rates]
        self.assertEqual(folds, [180, 180, 180, -120, -70])
        self.assertEqual([abs(value) for value in folds], [180, 180, 180, 120, 70])
        self.assertEqual(
            [rate / 2 - 180 for rate in sample_rates], [320, 120, 20, -30, -55]
        )
        self.assertEqual([180 < rate / 2 for rate in sample_rates], [True, True, True, False, False])

        frequencies = [50, 180, 350, 500, 650, 820, 1150]
        signed = [signed_fold(frequency, 1000) for frequency in frequencies]
        self.assertEqual(signed, [50, 180, 350, -500, -350, -180, 150])
        self.assertEqual([abs(value) for value in signed], [50, 180, 350, 500, 350, 180, 150])
        self.assertEqual([frequency < 500 for frequency in frequencies], [True, True, True, False, False, False, False])

        self.assertAlmostEqual(1 / math.sqrt(1 + (180 / 400) ** 2), 0.9119215051751064)
        self.assertAlmostEqual(-math.atan(180 / 400), -0.4228539261329407)
        self.assertEqual(2**12, 4096)
        self.assertAlmostEqual(3.3 / 4096, 0.0008056640625)
        self.assertEqual(1000 * 12, 12000)
        for bits in (4, 6, 8, 12, 16):
            self.assertEqual(
                ideal_codes(180, 1000, 51, bits),
                ideal_codes(820, 1000, 51, bits),
            )


class P07LearningAndRegressionTests(unittest.TestCase):
    def test_alias_trace_comparison_uses_a_shared_time_base(self):
        low_count = dense_reference_point_count(180, 1000, 51)
        high_count = dense_reference_point_count(820, 1000, 51)
        self.assertEqual(low_count, 816)
        self.assertEqual(high_count, 985)
        self.assertNotEqual(
            low_count,
            high_count,
            "the old direct MATLAB vector subtraction must remain discriminating",
        )

        shared_times = [0.05 * index / 2000 for index in range(2001)]
        low_trace = [
            1.65 + math.cos(2 * math.pi * 180 * time_s)
            for time_s in shared_times
        ]
        high_trace = [
            1.65 + math.cos(2 * math.pi * 820 * time_s)
            for time_s in shared_times
        ]
        self.assertGreater(
            max(abs(low - high) for low, high in zip(low_trace, high_trace)),
            0.5,
        )

        for name in ("experiment.m", "run_checks.m"):
            with self.subTest(name=name):
                compact = re.sub(
                    r"\s+", "", matlab_code_without_comments(read(name)).lower()
                ).replace("...", "")
                self.assertIn("sharedtracetimes=linspace(", compact)
                self.assertIn(
                    "lowphysicalonsharedgridv-highphysicalonsharedgridv",
                    compact,
                )
                self.assertNotIn(
                    "lowphysical.analog.source_v-highphysical.analog.source_v",
                    compact,
                )

    def test_experiment_has_baseline_two_independent_sweeps_and_broken_case(self):
        experiment = read("experiment.m").lower()
        compact = re.sub(r"\s+", "", experiment).replace("...", "")
        self.assertIn("%% baseline", experiment)
        self.assertGreaterEqual(experiment.count("%% sweep"), 2)
        self.assertIn("sampleratesweephz = [1000 600 400 300 250]", experiment)
        self.assertIn(
            "signalfrequencysweephz = [50 180 350 500 650 820 1150]",
            experiment,
        )
        self.assertIn("%% broken case", experiment)
        self.assertIn("p07_scenario('alias-trap')", experiment)
        self.assertIn("p07_scenario('deadline')", experiment)
        self.assertIn("isequal(lowphysical.adc.codes,highphysical.adc.codes)", compact)
        self.assertIn("isequaln(recovered,baseline)", compact)
        self.assertGreaterEqual(experiment.count("figure("), 5)
        self.assertIn("xlabel(", experiment)
        self.assertIn("ylabel(", experiment)
        self.assertIn("time (ms)", experiment)
        self.assertIn("voltage (v)", experiment)
        self.assertIn("sample rate f_s (hz)", experiment)
        self.assertIn("strict nyquist margin (hz)", experiment)
        self.assertIn("physical input frequency (hz)", experiment)
        self.assertIn("sampled apparent frequency (hz)", experiment)
        self.assertIn("mechanism for sweep 1", experiment)
        self.assertIn("mechanism for sweep 2", experiment)
        self.assertIn("sample-rate lever must not mutate", experiment)
        self.assertIn("input-frequency lever must not mutate", experiment)

    def test_interactive_exposes_meaningful_controls_and_two_views(self):
        interactive_source = read("interactive.m")
        interactive = re.sub(r"\s+", " ", interactive_source.lower())
        self.assertIn("uifigure(", interactive)
        self.assertGreaterEqual(interactive.count("uispinner("), 7)
        self.assertIn("uidropdown(", interactive)
        self.assertIn("input frequency (hz)", interactive)
        self.assertIn("sample rate (hz)", interactive)
        self.assertIn("aa cutoff (hz)", interactive)
        self.assertIn("adc bits", interactive)
        self.assertIn("amplitude (v)", interactive)
        self.assertIn("offset (v)", interactive)
        self.assertIn("bypassed 820 hz alias", interactive)
        self.assertIn("nyquist phase loss", interactive)
        self.assertIn("adc rail clipping", interactive)
        self.assertIn("fixed acquisition deadline", interactive)
        self.assertIn("valuechangedfcn", interactive)
        self.assertGreaterEqual(interactive.count("uiaxes("), 2)
        self.assertIn("cannot restore an aliased", interactive)
        self.assertIn("not a hardware measurement", interactive)

    def test_interactive_callbacks_bind_p07_dependencies_before_path_cleanup(self):
        interactive = matlab_code_without_comments(read("interactive.m")).lower()
        compact = re.sub(r"\s+", "", interactive).replace("...", "")
        self.assertIn("modelfcn=@model;", compact)
        self.assertIn("scenariofcn=@p07_scenario;", compact)
        self.assertIn(
            "input=scenariofcn(scenarioname,samplecountcontrol.value);", compact
        )
        self.assertIn(
            "out=modelfcn(input.signal_frequency_hz,input.sample_rate_hz,"
            "input.sample_count,input.amplitude_v,input.offset_v,input.phase_rad,"
            "input.anti_alias_cutoff_hz,input.adc_bits,input.reference_voltage_v,"
            "input.fault,input.acquisition_deadline_s);",
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
            "frequencycontrol.value=fixedinput.signal_frequency_hz;",
            "sampleratecontrol.value=fixedinput.sample_rate_hz;",
            "cutoffcontrol.value=fixedinput.anti_alias_cutoff_hz;",
            "bitscontrol.value=fixedinput.adc_bits;",
            "amplitudecontrol.value=fixedinput.amplitude_v;",
            "offsetcontrol.value=fixedinput.offset_v;",
            "samplecountcontrol.value=fixedinput.sample_count;",
        ):
            self.assertIn(reset, selector)
        self.assertIn("controls{controlindex}.enable='off';", selector)
        self.assertLess(
            selector.index("fixedinput=scenariofcn(scenarioname,51);"),
            selector.index("if~strcmp(scenariocontrol.value,'filteredbaseline')"),
        )
        self.assertLess(
            selector.index("samplecountcontrol.value=fixedinput.sample_count;"),
            selector.index("updateviews();"),
        )

    def test_executable_checks_cover_limits_alias_clipping_deadline_and_rejection(self):
        checks = matlab_code_without_comments(read("run_checks.m"))
        lower = checks.lower()
        self.assertGreaterEqual(len(re.findall(r"\bassert\s*\(", checks)), 50)
        for marker in (
            "baseline sample instants must be n/f_s",
            "first-order analog gain and phase",
            "4096 levels and v_ref/4096",
            "half an lsb",
            "raw adc payload rate",
            "dc must pass",
            "at f=f_c",
            "exact nyquist equality is degenerate",
            "pi/2-phase cosine at exact nyquist",
            "phase-loss diagnostic offset must stay inside one adc bin",
            "fold periodicity",
            "sample-rate sweep fold",
            "input-frequency sweep",
            "canonical signed-fold samples for 180 hz and 820 hz",
            "changing adc resolution must not disambiguate",
            "analog filter attenuates high input",
            "zero volts must map to code zero",
            "reference voltage must saturate",
            "overrange fixture must cross both adc rails",
            "deadline exactly at n/f_s",
            "representably earlier deadline",
            "clean retry after a rejected deadline",
            "repeated calls must be deterministic and state-isolated",
            "callback-bound p07 dependencies must survive module path cleanup",
            "p07:model:signalfrequency",
            "p07:model:samplerate",
            "p07:model:samplecount",
            "p07:model:antialiascutoff",
            "p07:model:adcbits",
            "p07:model:acquisitiondeadline",
            "p07:model:resourcebound",
            "p07:model:timingresourcebound",
            "every advertised scenario count through the accepted upper bound",
            "malformed call must not contaminate",
            "p07 checks passed",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, lower)
        self.assertIn(
            "no asynchronous wait or cancellation api", read("run_checks.m").lower()
        )

    def test_cli_check_resolves_p07_public_matlab_entry_point(self):
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [str(ROOT / "bin/learn"), "check", "P07"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env=environment,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "Run in MATLAB: run_module_checks('P07')\n")

    @unittest.skipUnless(shutil.which("matlab"), "MATLAB executable unavailable")
    def test_matlab_executes_module_checks_and_callback_lifetime(self):
        result = subprocess.run(
            [
                shutil.which("matlab"),
                "-batch",
                "run_module_checks('P07')",
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
            msg=f"MATLAB P07 checks failed:\n{result.stdout}\n{result.stderr}",
        )
        self.assertIn("P07 checks passed", result.stdout)

    def test_tutor_text_is_mechanism_first_and_ends_in_teach_back(self):
        lesson = re.sub(r"\s+", " ", read("lesson.md").lower())
        walkthrough = read("walkthrough.md").lower()
        checks = read("checks.md").lower()
        self.assertIn("h(f) = 1 / (1 + j f/f_c)", lesson)
        self.assertIn("t_n = n/f_s", lesson)
        self.assertIn("f_fold", lesson)
        self.assertIn("lsb = v_ref/l", lesson)
        self.assertEqual(lesson.count("## one prediction"), 1)
        self.assertIn("move one control", walkthrough)
        self.assertIn("reset", walkthrough)
        self.assertIn("interpretation", checks)
        self.assertIn("teach-back", checks)
        self.assertIn("cancellation is not applicable", lesson)
        self.assertIn("mechanism first", walkthrough)

    def test_claim_language_separates_model_runtime_and_physical_evidence(self):
        combined = "\n".join(
            read(name).lower()
            for name in ("README.md", "lesson.md", "checks.md", "experiment.m")
        )
        self.assertIn("not a hardware measurement", combined)
        self.assertIn("first-order", combined)
        self.assertIn("single-tone", combined)
        self.assertIn("strict", combined)
        self.assertIn("guard band", combined)
        self.assertIn("digital filter", combined)
        self.assertIn("clipping", combined)
        self.assertNotIn("hardware-validated", combined)
        self.assertNotIn("measured adc", combined)


class P07RetainedEvidenceTests(unittest.TestCase):
    def test_date_agnostic_retained_evidence_is_complete_and_honest(self):
        evidence_files = sorted((ROOT / "docs/evidence").glob("P07-*.md"))
        self.assertTrue(evidence_files, "P07 requires a retained evidence record")
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
                    "no learner state is tracked or included in the batch diff",
                ):
                    self.assertIn(marker, text)
                self.assertNotIn("final-manifest gate pending", text)


if __name__ == "__main__":
    unittest.main()
