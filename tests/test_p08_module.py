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
    "What inputs, observable effects, and failure modes matter when you command "
    "a DAC and Observe Settling?"
)
MODULE_FOLDER = ROOT / "modules/08-command-a-dac-and-observe-settling"
CORE_ARTIFACTS = {
    "README.md",
    "lesson.m",
    "p08_scenario.m",
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


def ideal_dac(command_v: float, bits: int = 12, reference_v: float = 3.3):
    """Independent nearest-code unipolar DAC fixture used by P08."""
    level_count = 2**bits
    max_code = level_count - 1
    lsb_v = reference_v / level_count
    clipped_v = min(max(command_v, 0.0), reference_v)
    code = min(math.floor(clipped_v / lsb_v + 0.5), max_code)
    return code, code * lsb_v, lsb_v


def slew_limited_response_v(
    elapsed_s: float,
    initial_v: float,
    target_v: float,
    time_constant_s: float,
    slew_rate_v_per_s: float,
) -> float:
    """Analytical first-order response with a symmetric derivative limit."""
    delta_v = target_v - initial_v
    distance_v = abs(delta_v)
    if distance_v == 0:
        return target_v
    direction = math.copysign(1.0, delta_v)
    slew_boundary_v = slew_rate_v_per_s * time_constant_s
    slew_time_s = max(
        0.0, (distance_v - slew_boundary_v) / slew_rate_v_per_s
    )
    if elapsed_s <= slew_time_s:
        return initial_v + direction * slew_rate_v_per_s * elapsed_s
    exponential_start_v = min(distance_v, slew_boundary_v)
    return target_v - direction * exponential_start_v * math.exp(
        -(elapsed_s - slew_time_s) / time_constant_s
    )


def settling_time_s(
    initial_v: float,
    target_v: float,
    time_constant_s: float,
    slew_rate_v_per_s: float,
    tolerance_v: float,
) -> float:
    """First time the monotone fixture enters and stays in its tolerance band."""
    distance_v = abs(target_v - initial_v)
    if distance_v <= tolerance_v:
        return 0.0
    slew_boundary_v = slew_rate_v_per_s * time_constant_s
    if distance_v <= slew_boundary_v:
        return time_constant_s * (
            math.log(distance_v) - math.log(tolerance_v)
        )
    if tolerance_v >= slew_boundary_v:
        return (distance_v - tolerance_v) / slew_rate_v_per_s
    slew_time_s = (distance_v - slew_boundary_v) / slew_rate_v_per_s
    return slew_time_s + time_constant_s * (
        math.log(slew_boundary_v) - math.log(tolerance_v)
    )


class P08IdentityAndArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(
            (ROOT / "curriculum/modules.json").read_text(encoding="utf-8")
        )
        cls.module = next(
            module for module in cls.manifest["modules"] if module["id"] == "P08"
        )

    def test_permanent_manifest_identity_prerequisite_status_and_evidence(self):
        self.assertEqual(self.module["number"], 8)
        self.assertEqual(self.module["title"], "Command a DAC and Observe Settling")
        self.assertEqual(self.module["guiding_question"], QUESTION)
        self.assertEqual(self.module["phase"], 2)
        self.assertEqual(self.module["phase_title"], "Buses and acquisition")
        self.assertEqual(self.module["slug"], "command-a-dac-and-observe-settling")
        self.assertEqual(
            self.module["folder"],
            "modules/08-command-a-dac-and-observe-settling",
        )
        self.assertEqual(self.module["implementation_batch"], "P08")
        self.assertEqual(self.module["prerequisites"], ["P07"])
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
                self.assertLess(
                    len(payload), 100000, "educational artifact should stay bounded"
                )

    def test_guiding_question_p07_connection_and_claim_boundary_are_explicit(self):
        combined = "\n".join(
            read(name) for name in ("README.md", "lesson.md", "walkthrough.md")
        )
        lesson = read("lesson.md").lower()
        self.assertIn(QUESTION, combined)
        self.assertIn("P07", read("lesson.md"))
        self.assertIn("adc", lesson)
        self.assertIn("dac", lesson)
        self.assertTrue(
            any(
                marker in lesson
                for marker in (
                    "code to voltage",
                    "codes into voltage",
                    "reverses that chain",
                    "other direction",
                )
            ),
            "P08 must connect P07's conversion direction to DAC reconstruction",
        )
        claim_text = re.sub(r"\s+", " ", combined.lower())
        self.assertIn("hardware measurement", claim_text)
        self.assertRegex(claim_text, r"\bnot\b[^.]{0,240}\bhardware measurement\b")
        self.assertIn("first-order", combined.lower())
        self.assertIn("slew", combined.lower())

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


class P08ModelContractTests(unittest.TestCase):
    def test_model_is_transparent_deterministic_and_resource_bounded(self):
        model = read("model.m")
        code = matlab_code_without_comments(model).lower()
        compact = re.sub(r"\s+", "", code).replace("...", "")
        self.assertIn(
            "functionout=model(commandvoltagev,initialvoltagev,"
            "referencevoltagev,dacbits,updatelatencys,timeconstants,"
            "slewratevpers,tolerancev,sampleperiods,samplecount,fault,"
            "commanddeadlines)",
            compact,
        )
        for token in (
            "commandvoltagev",
            "initialvoltagev",
            "referencevoltagev",
            "dacbits",
            "updatelatencys",
            "timeconstants",
            "slewratevpers",
            "tolerancev",
            "sampleperiods",
            "samplecount",
            "commanddeadlines",
        ):
            with self.subTest(token=token):
                self.assertIn(token, compact)
        self.assertIn("levelcount=2.^dacbits;", compact)
        self.assertIn("maxcode=levelcount-1;", compact)
        self.assertIn("lsbv=referencevoltagev./levelcount;", compact)
        self.assertIn("if~isfinite(lsbv)||lsbv<=0", compact)
        self.assertLess(
            compact.index("if~isfinite(lsbv)||lsbv<=0"),
            compact.index("quantizevoltage(initialvoltagev,lsbv,maxcode)"),
            "a zero derived LSB must be rejected before quantization",
        )
        self.assertIn("commandcode", compact)
        self.assertIn("initialcode", compact)
        self.assertIn("round(", compact)
        self.assertIn("min(", compact)
        self.assertIn("max(", compact)
        self.assertRegex(
            compact,
            r"(?:(?:quantizedtarget|quantizedcommand|targetlevel|commandlevel)v="
            r"commandcode|quantizedv=code)\.\*lsbv;",
        )
        self.assertRegex(compact, r"slewratevpers\.\*timeconstants")
        self.assertRegex(
            compact,
            r"(?:sampletime|tracetime|time)s=\(0:\(samplecount-1\)\)"
            r"\.?\*sampleperiods;",
        )
        self.assertIn("exp(", compact)
        self.assertIn("analyticsettling", compact)
        self.assertIn("sampledsettling", compact)
        self.assertIn(
            "(log(stepmagnitudev)-log(tolerancev))",
            compact,
        )
        self.assertIn(
            "(log(slewratevpers.*timeconstants)-log(tolerancev))",
            compact,
        )
        self.assertNotIn("log(stepmagnitudev./tolerancev)", compact)
        self.assertIn("updatelatencys", compact)
        self.assertIn("timedout=updatelatencys>commanddeadlines;", compact)
        self.assertIn("update-not-latched", code)
        self.assertTrue(
            "committed" in compact or "recordedcode" in compact,
            "timeout must expose an explicit accepted-result boundary",
        )
        self.assertRegex(code, r"max(?:samples|tracepoints)\s*=\s*\d+")
        self.assertLess(
            compact.index("samplecount>maxsamples"),
            compact.index("(0:(samplecount-1))"),
            "sample cardinality must be bounded before trace allocation",
        )
        self.assertNotRegex(
            code,
            r"\b(?:persistent|global|while|rng|rand|randn|pause|timer|eval|system)\b",
        )
        if "linspace" in code:
            bound_tokens = [
                token
                for token in ("maxsamples", "maxtracepoints")
                if token in code
            ]
            self.assertTrue(bound_tokens)
            self.assertLess(
                min(code.index(token) for token in bound_tokens),
                code.index("linspace"),
                "trace cardinality must be bounded before allocation",
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
            "step",
            "lsim",
            "tf",
            "ode45",
            "daq",
            "arduino",
            "writevoltage",
            "analogoutput",
            "audioplayer",
            "serialport",
            "fopen",
            "timetable",
            "timeseries",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotRegex(code, rf"\b{forbidden}\s*\(")
        self.assertNotIn("simulink", code)
        self.assertNotIn("control system toolbox", code)
        self.assertNotIn("data acquisition toolbox", code)

    def test_model_rejects_malformed_fault_timing_and_resource_inputs(self):
        model = read("model.m")
        for identifier in (
            "P08:model:Arity",
            "P08:model:CommandVoltage",
            "P08:model:InitialVoltage",
            "P08:model:ReferenceVoltage",
            "P08:model:ReferenceResolution",
            "P08:model:DACBits",
            "P08:model:UpdateLatency",
            "P08:model:TimeConstant",
            "P08:model:SlewRate",
            "P08:model:Tolerance",
            "P08:model:SamplePeriod",
            "P08:model:SampleCount",
            "P08:model:CommandDeadline",
            "P08:model:Fault",
            "P08:model:FaultMode",
            "P08:model:ResourceBound",
            "P08:model:TimingResourceBound",
        ):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, model)
        self.assertIn("isfinite", model)
        self.assertIn("isreal", model)
        self.assertIn("isscalar", model)

    def test_scenario_fixtures_are_seedless_bounded_and_compatible(self):
        scenario = matlab_code_without_comments(read("p08_scenario.m")).lower()
        self.assertIn("function input = p08_scenario(", scenario)
        for name in (
            "baseline",
            "update-not-latched",
            "deadline",
            "short-observation",
            "slow-output",
        ):
            with self.subTest(name=name):
                self.assertIn(name, scenario)
        self.assertRegex(scenario, r"dac_bits\s*=\s*12")
        self.assertRegex(scenario, r"reference_voltage_v\s*=\s*3\.3")
        self.assertRegex(scenario, r"command_voltage_v\s*=\s*2\.5")
        self.assertRegex(scenario, r"initial_voltage_v\s*=\s*0\.5")
        self.assertRegex(scenario, r"samplecount\s*=\s*601")
        self.assertRegex(scenario, r"samplecount\s*<=\s*\d+")
        self.assertIn("input.sample_count = double(samplecount)", scenario)
        self.assertRegex(
            scenario, r"update_latency_s\s*=\s*(?:100e-6|1e-4|0\.0001)"
        )
        self.assertRegex(
            scenario,
            r"time_constant_s\s*=\s*(?:250e-6|2\.5e-4|0\.00025)",
        )
        self.assertRegex(scenario, r"slew_rate_v_per_s\s*=\s*4000")
        self.assertRegex(scenario, r"tolerance_v\s*=\s*(?:0\.01|10e-3)")
        self.assertRegex(
            scenario, r"sample_period_s\s*=\s*(?:5e-6|0\.000005)"
        )
        self.assertNotRegex(
            scenario, r"\b(?:rng|rand|randn|while|timer|pause)\b"
        )

    def test_independent_dac_first_order_slew_and_settling_references(self):
        command_code, target_v, lsb_v = ideal_dac(2.5)
        initial_code, initial_v, _ = ideal_dac(0.5)
        self.assertEqual(2**12, 4096)
        self.assertEqual(command_code, 3103)
        self.assertEqual(initial_code, 621)
        self.assertAlmostEqual(lsb_v, 3.3 / 4096)
        self.assertAlmostEqual(target_v, 2.4999755859375)
        self.assertAlmostEqual(initial_v, 0.5003173828125)
        self.assertLess(abs(target_v - 2.5), lsb_v / 2)
        self.assertLess(abs(initial_v - 0.5), lsb_v / 2)
        self.assertEqual(ideal_dac(-1.0)[0], 0)
        self.assertEqual(ideal_dac(3.3)[0], 4095)
        self.assertAlmostEqual(ideal_dac(3.3)[1], 3.3 - lsb_v)
        self.assertEqual(ideal_dac(0.5001)[0], initial_code)

        tau_s = 250e-6
        slew_v_per_s = 4000.0
        _small_code, small_initial_v, _ = ideal_dac(2.25)
        one_tau_v = slew_limited_response_v(
            tau_s, small_initial_v, target_v, tau_s, slew_v_per_s
        )
        self.assertAlmostEqual(
            one_tau_v,
            target_v - (target_v - small_initial_v) / math.e,
        )
        self.assertAlmostEqual(
            (one_tau_v - small_initial_v) / (target_v - small_initial_v),
            1 - math.exp(-1),
        )

        slew_boundary_v = slew_v_per_s * tau_s
        self.assertAlmostEqual(slew_boundary_v, 1.0)
        distance_v = target_v - initial_v
        slew_time_s = (distance_v - slew_boundary_v) / slew_v_per_s
        self.assertAlmostEqual(slew_time_s, 0.00024991455078125)
        before = slew_limited_response_v(
            math.nextafter(slew_time_s, 0.0),
            initial_v,
            target_v,
            tau_s,
            slew_v_per_s,
        )
        at_boundary = slew_limited_response_v(
            slew_time_s,
            initial_v,
            target_v,
            tau_s,
            slew_v_per_s,
        )
        after = slew_limited_response_v(
            math.nextafter(slew_time_s, math.inf),
            initial_v,
            target_v,
            tau_s,
            slew_v_per_s,
        )
        self.assertAlmostEqual(at_boundary, target_v - slew_boundary_v)
        self.assertLessEqual(abs(before - at_boundary), 1e-12)
        self.assertLessEqual(abs(after - at_boundary), 1e-12)

        settle_s = settling_time_s(
            initial_v,
            target_v,
            tau_s,
            slew_v_per_s,
            0.01,
        )
        self.assertAlmostEqual(
            settle_s,
            slew_time_s + tau_s * math.log(1.0 / 0.01),
        )
        self.assertLessEqual(
            abs(
                target_v
                - slew_limited_response_v(
                    settle_s,
                    initial_v,
                    target_v,
                    tau_s,
                    slew_v_per_s,
                )
            ),
            0.01 * (1 + 1e-12),
        )
        just_early_s = settle_s - 1e-12
        self.assertGreater(
            abs(
                target_v
                - slew_limited_response_v(
                    just_early_s,
                    initial_v,
                    target_v,
                    tau_s,
                    slew_v_per_s,
                )
            ),
            0.01,
        )
        self.assertEqual(
            settling_time_s(target_v, target_v, tau_s, slew_v_per_s, 0.01),
            0.0,
        )
        boundary_rate_v_per_s = distance_v / tau_s
        self.assertAlmostEqual(
            slew_limited_response_v(
                tau_s,
                initial_v,
                target_v,
                tau_s,
                boundary_rate_v_per_s,
            ),
            target_v - distance_v / math.e,
        )
        self.assertAlmostEqual(
            slew_limited_response_v(
                tau_s,
                initial_v,
                target_v,
                tau_s,
                math.inf,
            ),
            target_v - distance_v / math.e,
        )

        subnormal_tolerance_v = math.nextafter(0.0, 1.0)
        self.assertTrue(
            math.isfinite(
                settling_time_s(
                    small_initial_v,
                    target_v,
                    tau_s,
                    math.inf,
                    subnormal_tolerance_v,
                )
            )
        )
        self.assertTrue(
            math.isfinite(
                settling_time_s(
                    initial_v,
                    target_v,
                    tau_s,
                    slew_v_per_s,
                    subnormal_tolerance_v,
                )
            )
        )
        self.assertEqual(
            math.nextafter(0.0, 1.0) / (2**12),
            0.0,
            "the smallest positive reference must not reach quantization with a zero LSB",
        )

        update_latency_s = 100e-6
        exact_deadline_s = update_latency_s
        just_short_deadline_s = math.nextafter(update_latency_s, 0.0)
        self.assertFalse(update_latency_s > exact_deadline_s)
        self.assertTrue(update_latency_s > just_short_deadline_s)

    def test_subnormal_sampled_settling_retains_remaining_error_state(self):
        _command_code, target_v, _lsb_v = ideal_dac(2.5)
        _initial_code, initial_v, _ = ideal_dac(2.25)
        distance_v = target_v - initial_v
        tau_s = 250e-6
        sample_period_s = 1e-3
        tolerance_v = math.nextafter(0.0, 1.0)
        analytic_s = tau_s * (math.log(distance_v) - math.log(tolerance_v))
        sample_times_s = [index * sample_period_s for index in range(201)]
        remaining_errors_v = [
            distance_v * math.exp(-time_s / tau_s)
            for time_s in sample_times_s
        ]
        subtractive_errors_v = [
            abs(target_v - (target_v - error_v))
            for error_v in remaining_errors_v
        ]
        retained_first_s = next(
            time_s
            for time_s, error_v in zip(sample_times_s, remaining_errors_v)
            if error_v <= tolerance_v
        )
        cancellation_first_s = next(
            time_s
            for time_s, error_v in zip(sample_times_s, subtractive_errors_v)
            if error_v <= tolerance_v
        )

        self.assertEqual(retained_first_s, 0.186)
        self.assertGreaterEqual(retained_first_s, analytic_s)
        self.assertLess(retained_first_s, analytic_s + sample_period_s)
        self.assertEqual(cancellation_first_s, 0.009000000000000001)
        self.assertLess(cancellation_first_s, analytic_s / 10)

        model = re.sub(
            r"\s+", "", matlab_code_without_comments(read("model.m")).lower()
        ).replace("...", "")
        self.assertIn(
            "intendederrorv=stepmagnitudev.*ones(1,samplecount);", model
        )
        self.assertIn("intendederrorv(updatemask)=remainingerrorv;", model)
        self.assertNotIn(
            "intendederrorv=abs(outputv-quantizedcommandv);", model
        )
        checks = read("run_checks.m").lower()
        self.assertIn("subnormal sampled settling must use the remaining-error state", checks)


class P08LearningAndRegressionTests(unittest.TestCase):
    def test_experiment_has_baseline_two_isolated_sweeps_and_broken_case(self):
        experiment = read("experiment.m").lower()
        compact = re.sub(r"\s+", "", experiment).replace("...", "")
        self.assertIn("%% baseline", experiment)
        self.assertGreaterEqual(experiment.count("%% sweep"), 2)
        self.assertRegex(
            compact,
            r"(?:timeconstant|tau)sweep[a-z]*=\[[^]]+\]",
        )
        self.assertRegex(
            compact,
            r"slew(?:rate)?sweep[a-z]*=\[[^]]+\]",
        )
        self.assertIn("%% broken case", experiment)
        self.assertIn("p08_scenario('update-not-latched')", experiment)
        self.assertIn("p08_scenario('deadline')", experiment)
        self.assertIn("isequaln(recovered,baseline)", compact)
        self.assertGreaterEqual(experiment.count("figure("), 5)
        self.assertIn("xlabel(", experiment)
        self.assertIn("ylabel(", experiment)
        self.assertTrue(
            "time (us)" in experiment or "time (ms)" in experiment,
            "waveform time axes must state units",
        )
        self.assertIn("voltage (v)", experiment)
        self.assertIn("settling time (us)", experiment)
        self.assertIn("mechanism for sweep 1", experiment)
        self.assertIn("mechanism for sweep 2", experiment)
        self.assertGreaterEqual(
            experiment.count("lever must not mutate"),
            2,
            "each sweep must assert isolation from its reset baseline",
        )

    def test_interactive_exposes_meaningful_controls_and_two_views(self):
        interactive_source = read("interactive.m")
        interactive = re.sub(r"\s+", " ", interactive_source.lower())
        self.assertIn("uifigure(", interactive)
        self.assertGreaterEqual(interactive.count("uispinner("), 8)
        self.assertIn("uidropdown(", interactive)
        for label_pattern in (
            r"command voltage.*\(v\)",
            r"initial voltage.*\(v\)",
            r"update latency.*\(us\)",
            r"time constant.*\(us\)",
            r"dac bits",
            r"sample period.*\(us\)",
            r"sample count",
        ):
            with self.subTest(label_pattern=label_pattern):
                self.assertRegex(interactive, label_pattern)
        self.assertRegex(interactive, r"slew rate \(v/(?:s|ms|us)\)")
        self.assertRegex(interactive, r"settling tolerance \((?:v|mv)\)")
        self.assertIn("slew-limited", interactive)
        self.assertRegex(interactive, r"update(?:-| )not(?:-| )latched")
        self.assertIn("command deadline", interactive)
        self.assertIn("fixed", interactive)
        self.assertIn("valuechangedfcn", interactive)
        self.assertGreaterEqual(interactive.count("uiaxes("), 2)
        self.assertIn("not a hardware measurement", interactive)

    def test_interactive_callbacks_bind_p08_dependencies_before_path_cleanup(self):
        interactive = matlab_code_without_comments(read("interactive.m")).lower()
        compact = re.sub(r"\s+", "", interactive).replace("...", "")
        self.assertIn("modelfcn=@model;", compact)
        self.assertIn("scenariofcn=@p08_scenario;", compact)
        self.assertRegex(compact, r"input=scenariofcn\(scenarioname,[^)]+\);")
        self.assertRegex(compact, r"out=modelfcn\([^;]+\);")
        callback_region = compact[compact.index("functionupdateviews") :]
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
        for control_pattern in (
            r"commandcontrol",
            r"initialcontrol",
            r"(?:latency|updatelatency)control",
            r"(?:timeconstant|tau)control",
            r"slewratecontrol",
            r"bitscontrol",
            r"tolerancecontrol",
            r"(?:sampleperiod|period)control",
            r"samplecountcontrol",
        ):
            with self.subTest(control_pattern=control_pattern):
                self.assertRegex(
                    selector,
                    rf"(?:{control_pattern})\.value=fixedinput\.[a-z0-9_]+;",
                )
        self.assertIn("controls{controlindex}.enable='off';", selector)
        self.assertLess(selector.index("fixedinput=scenariofcn("), selector.index("updateviews();"))
        self.assertLess(selector.rindex(".value=fixedinput."), selector.index("updateviews();"))

    def test_executable_checks_cover_full_failure_and_recovery_contract(self):
        checks = matlab_code_without_comments(read("run_checks.m"))
        lower = checks.lower()
        self.assertGreaterEqual(len(re.findall(r"\bassert\s*\(", checks)), 45)
        marker_groups = {
            "positive quantization": (
                "4096 levels",
                "3.3/4096",
                "half-scale code",
            ),
            "positive settling": (
                "one time constant",
                "63.2",
                "settling boundary",
            ),
            "slew transition": (
                "slew threshold",
                "slew-to-exponential",
                "continuous at the handoff",
            ),
            "negative command": (
                "negative command",
                "code zero",
                "low rail",
            ),
            "upper rail": (
                "full-scale command",
                "maximum code",
                "high rail",
            ),
            "broken observation": (
                "update not latched",
                "digital command can complete",
                "register command completes",
            ),
            "exact timeout boundary": (
                "deadline exactly at update latency",
                "exact command deadline",
            ),
            "strict timeout boundary": (
                "one representable step before",
                "just before update latency",
            ),
            "rollback": (
                "removing fault and deadline",
                "rollback",
            ),
            "recovery": (
                "clean retry after",
                "recovery",
            ),
            "isolation": (
                "deterministic and state-isolated",
                "must not contaminate",
            ),
            "compatibility": (
                "integer inputs",
                "scalar numeric compatibility",
                "callback-bound p08 dependencies",
            ),
            "resource bound": (
                "accepted upper bound",
                "resource bound",
                "p08:model:resourcebound",
            ),
            "reference-resolution underflow": (
                "p08:model:referenceresolution",
                "lsb underflows",
            ),
        }
        for contract, alternatives in marker_groups.items():
            with self.subTest(contract=contract):
                self.assertTrue(
                    any(marker in lower for marker in alternatives),
                    f"run_checks.m lacks {contract}: expected one of {alternatives}",
                )
        for identifier in (
            "p08:model:commandvoltage",
            "p08:model:initialvoltage",
            "p08:model:referenceresolution",
            "p08:model:dacbits",
            "p08:model:updatelatency",
            "p08:model:timeconstant",
            "p08:model:slewrate",
            "p08:model:tolerance",
            "p08:model:sampleperiod",
            "p08:model:samplecount",
            "p08:model:commanddeadline",
            "p08:model:fault",
            "p08:model:resourcebound",
            "p08:model:timingresourcebound",
        ):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, lower)
        self.assertIn("malformed call must not contaminate", lower)
        self.assertIn("no asynchronous wait or cancellation api", lower)
        self.assertIn("p08 checks passed", lower)

    def test_cli_check_resolves_p08_public_matlab_entry_point(self):
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [str(ROOT / "bin/learn"), "check", "P08"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env=environment,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "Run in MATLAB: run_module_checks('P08')\n")

    @unittest.skipUnless(shutil.which("matlab"), "MATLAB executable unavailable")
    def test_matlab_executes_module_checks_and_callback_lifetime(self):
        result = subprocess.run(
            [
                shutil.which("matlab"),
                "-batch",
                "run_module_checks('P08')",
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
            msg=f"MATLAB P08 checks failed:\n{result.stdout}\n{result.stderr}",
        )
        self.assertIn("P08 checks passed", result.stdout)

    def test_tutor_text_is_mechanism_first_and_ends_in_teach_back(self):
        lesson = re.sub(r"\s+", " ", read("lesson.md").lower())
        walkthrough = read("walkthrough.md").lower()
        checks = read("checks.md").lower()
        self.assertIn("l = 2^b", lesson)
        self.assertRegex(lesson, r"(?:lsb|q)\s*=\s*v_ref/l")
        self.assertRegex(
            lesson,
            r"v(?:_dac|_target|_code)\s*=\s*(?:d|k|code)\s*(?:\*\s*)?(?:lsb|q)",
        )
        self.assertRegex(lesson, r"exp\(-(?:t|u)/tau\)")
        self.assertRegex(
            lesson,
            r"(?:delta v|slew threshold|remaining error)[^.\n]*s tau",
        )
        self.assertIn("t_settle", lesson)
        self.assertIn("update latency", lesson)
        self.assertIn("deadline", lesson)
        self.assertIn("update-not-latched", lesson)
        self.assertIn("digital", lesson)
        self.assertIn("analog", lesson)
        self.assertEqual(lesson.count("## one prediction"), 1)
        self.assertIn("move one control", walkthrough)
        self.assertIn("reset", walkthrough)
        self.assertIn("mechanism first", walkthrough)
        self.assertIn("interpretation", checks)
        self.assertIn("teach-back", checks)
        self.assertIn("cancellation is not applicable", lesson)

    def test_claim_language_separates_model_runtime_and_physical_evidence(self):
        combined = "\n".join(
            read(name).lower()
            for name in ("README.md", "lesson.md", "checks.md", "experiment.m")
        )
        self.assertIn("hardware measurement", combined)
        self.assertRegex(combined, r"\bnot\b[^.]{0,240}\bhardware measurement\b")
        self.assertTrue(
            "ideal dac" in combined
            or "ideal-dac" in combined
            or "ideal unipolar" in combined
        )
        self.assertIn("first-order", combined)
        self.assertIn("slew", combined)
        self.assertIn("quantization", combined)
        self.assertTrue(
            "settling tolerance" in combined or "target-centered tolerance" in combined
        )
        self.assertTrue(
            "op-amp" in combined
            or "amplifier" in combined
            or "output stage" in combined,
            "physical fidelity exclusions must mention the unmodeled output stage",
        )
        self.assertNotIn("hardware-validated", combined)
        self.assertNotIn("measured dac", combined)


class P08RetainedEvidenceTests(unittest.TestCase):
    def test_date_agnostic_retained_evidence_is_complete_and_honest(self):
        evidence_files = sorted((ROOT / "docs/evidence").glob("P08-*.md"))
        self.assertTrue(evidence_files, "P08 requires a retained evidence record")
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
                    "static validation",
                    "matlab runtime",
                    "ui",
                    "numerical",
                    "bench",
                    "hil",
                    "field",
                    "not performed",
                    "no learner state is tracked or included in the batch diff",
                ):
                    with self.subTest(path=path.name, marker=marker):
                        self.assertIn(marker, text)
                self.assertNotIn("final-manifest gate pending", text)


if __name__ == "__main__":
    unittest.main()
