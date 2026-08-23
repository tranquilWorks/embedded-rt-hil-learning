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
MODULE_FOLDER = ROOT / "modules/13-move-samples-with-dma"
QUESTION = (
    "What inputs, observable effects, and failure modes matter when you move "
    "Samples with DMA?"
)
CORE_ARTIFACTS = {
    "README.md",
    "checks.md",
    "experiment.m",
    "interactive.m",
    "lesson.m",
    "lesson.md",
    "model.m",
    "p13_scenario.m",
    "run_checks.m",
    "walkthrough.md",
}
BASELINE_SOURCE = [(37 * index + 11) % 4096 for index in range(32)]


def read(name: str) -> str:
    return (MODULE_FOLDER / name).read_text(encoding="utf-8")


def matlab_code_without_comments(text: str) -> str:
    """Remove MATLAB comments without treating percent signs in strings as comments."""
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


def dma_reference(
    source_samples: list[float] = BASELINE_SOURCE,
    sample_period_us: float = 50,
    bytes_per_sample: float = 2,
    bus_rate_bytes_per_us: float = 0.2,
    arbitration_us: float = 1,
    block_samples: int = 8,
    dma_setup_cpu_us: float = 8,
    completion_isr_cpu_us: float = 3,
    processor_copy_cpu_us_per_sample: float = 4,
    descriptor_timeout_us: float = math.inf,
    timeout_action: str = "continue-waiting",
    destination_mode: str = "increment",
) -> dict[str, object]:
    """Independent serialized-beat oracle for the finite P13 teaching model."""
    source = [float(value) for value in source_samples]
    sample_count = len(source)
    beat_service_us = arbitration_us + bytes_per_sample / bus_rate_bytes_per_us
    request_us = [index * sample_period_us for index in range(sample_count)]
    start_us: list[float] = []
    completion_us: list[float] = []
    previous_completion_us = 0.0
    for request in request_us:
        start = max(request, previous_completion_us)
        completion = start + beat_service_us
        start_us.append(start)
        completion_us.append(completion)
        previous_completion_us = completion

    descriptor_reference_completion_us = completion_us[-1]
    descriptor_timed_out = descriptor_reference_completion_us > descriptor_timeout_us
    aborted = descriptor_timed_out and timeout_action == "abort-transfer"
    if aborted:
        committed_count = sum(
            completion <= descriptor_timeout_us for completion in completion_us
        )
    else:
        committed_count = sample_count

    destination: list[float | None] = [None] * sample_count
    destination_address: list[int | None] = [None] * sample_count
    overwrite_count = 0
    for sample_index in range(committed_count):
        address = sample_index if destination_mode == "increment" else 0
        destination_address[sample_index] = address + 1
        if destination[address] is not None:
            overwrite_count += 1
        destination[address] = source[sample_index]

    block_end_sample = list(range(block_samples, sample_count + 1, block_samples))
    if not block_end_sample or block_end_sample[-1] != sample_count:
        block_end_sample.append(sample_count)
    completed_block_end_sample = [
        endpoint for endpoint in block_end_sample if endpoint <= committed_count
    ]
    block_completion_us = [
        completion_us[endpoint - 1] for endpoint in completed_block_end_sample
    ]
    block_ready_latency_us: list[float | None] = [None] * sample_count
    first_sample = 0
    for endpoint, completion in zip(
        completed_block_end_sample, block_completion_us
    ):
        for sample_index in range(first_sample, endpoint):
            block_ready_latency_us[sample_index] = (
                completion - request_us[sample_index]
            )
        first_sample = endpoint
    retained_ready_latency = [
        value for value in block_ready_latency_us if value is not None
    ]

    peak_pending = 0
    for observation in request_us:
        pending = sum(
            request <= observation and completion > observation
            for request, completion in zip(request_us, completion_us)
        )
        peak_pending = max(peak_pending, pending)

    request_latency_us = [
        completion - request
        for request, completion in zip(request_us, completion_us)
    ]
    completed_block_count = len(completed_block_end_sample)
    cancelled_count = sample_count - committed_count
    if aborted:
        active_before_abort_us = [
            max(min(completion, descriptor_timeout_us) - start, 0)
            for start, completion in zip(start_us, completion_us)
        ]
        observed_bus_active_us = sum(active_before_abort_us)
        partial_beat_in_flight_at_abort = any(
            start < descriptor_timeout_us < completion
            for start, completion in zip(start_us, completion_us)
        )
    else:
        observed_bus_active_us = sample_count * beat_service_us
        partial_beat_in_flight_at_abort = False
    dma_cpu_demand_us = (
        dma_setup_cpu_us + completed_block_count * completion_isr_cpu_us
    )
    processor_copy_cpu_demand_us = (
        sample_count * processor_copy_cpu_us_per_sample
    )
    committed_processor_copy_cpu_demand_us = (
        committed_count * processor_copy_cpu_us_per_sample
    )
    return {
        "source": source,
        "sample_count": sample_count,
        "beat_service_us": beat_service_us,
        "request_us": request_us,
        "start_us": start_us,
        "completion_us": completion_us,
        "request_latency_us": request_latency_us,
        "max_request_latency_us": max(request_latency_us),
        "descriptor_reference_completion_us": descriptor_reference_completion_us,
        "descriptor_completion_us": (
            None if aborted else descriptor_reference_completion_us
        ),
        "descriptor_timed_out": descriptor_timed_out,
        "aborted": aborted,
        "committed_count": committed_count,
        "cancelled_count": cancelled_count,
        "destination": destination,
        "destination_address": destination_address,
        "overwrite_count": overwrite_count,
        "unwritten_count": sum(value is None for value in destination),
        "destination_integrity": destination == source,
        "block_end_sample": block_end_sample,
        "completed_block_end_sample": completed_block_end_sample,
        "block_completion_us": block_completion_us,
        "block_ready_latency_us": block_ready_latency_us,
        "completed_block_count": completed_block_count,
        "partial_block_sample_count": committed_count % block_samples,
        "mean_block_ready_latency_us": (
            sum(retained_ready_latency) / len(retained_ready_latency)
            if retained_ready_latency
            else None
        ),
        "max_block_ready_latency_us": (
            max(retained_ready_latency) if retained_ready_latency else None
        ),
        "offered_load_percent": 100 * beat_service_us / sample_period_us,
        "request_slack_us": sample_period_us - beat_service_us,
        "peak_pending": peak_pending,
        "request_period_exceed_count": sum(
            latency > sample_period_us for latency in request_latency_us
        ),
        "reference_bus_service_us": sample_count * beat_service_us,
        "committed_bus_service_us": committed_count * beat_service_us,
        "observed_bus_active_us": observed_bus_active_us,
        "partial_beat_in_flight_at_abort": partial_beat_in_flight_at_abort,
        "processor_copy_cpu_demand_us": processor_copy_cpu_demand_us,
        "committed_processor_copy_cpu_demand_us": (
            committed_processor_copy_cpu_demand_us
        ),
        "dma_cpu_demand_us": dma_cpu_demand_us,
        "processor_cpu_saved_us": processor_copy_cpu_demand_us
        - dma_cpu_demand_us,
        "observed_processor_cpu_saved_us": (
            committed_processor_copy_cpu_demand_us - dma_cpu_demand_us
        ),
        "work_conservation_error_samples": committed_count
        + cancelled_count
        - sample_count,
    }


class P13IdentityAndArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (ROOT / "curriculum/modules.json").read_text(encoding="utf-8")
        )
        cls.module = next(
            module for module in cls.manifest["modules"] if module["id"] == "P13"
        )

    def test_permanent_manifest_identity_prerequisite_status_and_evidence(self):
        self.assertEqual(self.module["number"], 13)
        self.assertEqual(self.module["title"], "Move Samples with DMA")
        self.assertEqual(self.module["guiding_question"], QUESTION)
        self.assertEqual(self.module["phase"], 4)
        self.assertEqual(self.module["phase_title"], "Data movement and timing")
        self.assertEqual(self.module["slug"], "move-samples-with-dma")
        self.assertEqual(
            self.module["folder"], "modules/13-move-samples-with-dma"
        )
        self.assertEqual(self.module["implementation_batch"], "P13")
        self.assertEqual(self.module["prerequisites"], ["P12"])
        self.assertEqual(self.module["status"], "implemented")
        self.assertEqual(self.module["evidence_level"], "simulated")

        p14 = next(
            module for module in self.manifest["modules"] if module["id"] == "P14"
        )
        self.assertEqual(p14["prerequisites"], ["P13"])

    def test_complete_artifact_set_has_clean_terminal_newlines_and_bounds(self):
        names = {path.name for path in MODULE_FOLDER.iterdir() if path.is_file()}
        self.assertTrue(CORE_ARTIFACTS <= names)
        for name in CORE_ARTIFACTS:
            with self.subTest(name=name):
                payload = (MODULE_FOLDER / name).read_bytes()
                self.assertTrue(payload.endswith(b"\n"))
                self.assertFalse(payload.endswith(b"\n\n"))
                self.assertLess(len(payload), 100_000)

    def test_guiding_question_p12_connection_p14_boundary_and_claims_are_explicit(self):
        combined = "\n".join(
            read(name) for name in ("README.md", "lesson.md", "walkthrough.md")
        )
        lower = re.sub(r"\s+", " ", combined.lower())
        self.assertIn(QUESTION, combined)
        self.assertIn("P12", combined)
        self.assertIn("P14", combined)
        for concept in (
            "serial",
            "beat",
            "block",
            "fixed",
            "not matlab-runtime",
            "processor",
            "hardware",
            "cache",
            "coherency",
        ):
            with self.subTest(concept=concept):
                self.assertIn(concept, lower)
        self.assertRegex(lower, r"\bnot\b[^.]{0,260}\bdma\b")

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


class P13ModelContractTests(unittest.TestCase):
    def test_model_is_transparent_deterministic_and_resource_bounded(self):
        source = read("model.m")
        code = matlab_code_without_comments(source).lower()
        compact = re.sub(r"\s+", "", code).replace("...", "")
        self.assertIn(
            "functionout=model(sourcesamples,sampleperiodus,bytespersample,"
            "busratebytesperus,arbitrationus,blocksamples,dmasetupcpuus,"
            "completionisrcpuus,processorcopycpuuspersample,"
            "descriptortimeoutus,timeoutaction,destinationmode)",
            compact,
        )
        for token in (
            "beatserviceus",
            "requestus",
            "startus",
            "completionus",
            "blockcompletionus",
            "destination",
            "planneddestinationslot",
            "committeddestinationslot",
            "pending",
            "offered_bus_load_pct",
            "timedout",
            "abortissued",
            "processorcopy",
            "dmacpu",
            "overwrite",
            "unwritten",
            "byte_conservation_error",
            "queue_conservation_error",
        ):
            with self.subTest(token=token):
                self.assertIn(token, compact)
        self.assertIn(
            "payloadserviceus=bytespersample./busratebytesperus;", compact
        )
        self.assertIn(
            "beatserviceus=arbitrationus+payloadserviceus;", compact
        )
        self.assertIn(
            "sampleindex=1:samplecount;requestus=(sampleindex-1).*sampleperiodus;",
            compact,
        )
        self.assertIn(
            "max(requestus(sampleindexvalue),previouscompletionus)", compact
        )
        self.assertIn(
            "completionus(sampleindexvalue)="
            "startus(sampleindexvalue)+beatserviceus",
            compact,
        )
        self.assertIn("completionus<=descriptortimeoutus", compact)
        self.assertNotRegex(
            code,
            r"\b(?:persistent|global|rng|rand|randn|pause|eval|system|parfor|parpool)\b",
        )
        self.assertIn("pendingatarrival", compact)
        self.assertIn("completedbyarrival", compact)
        self.assertIn("queueconservationerror", compact)
        self.assertIn(
            "committedprocessorcopycpudemandus="
            "committedcount.*processorcopycpuuspersample;",
            compact,
        )
        self.assertIn(
            "'observed_cpu_service_saved_us',"
            "committedprocessorcopycpudemandus-observeddmacpudemandus",
            compact,
        )
        self.assertIn("maxsamples", compact)
        self.assertLess(
            compact.index("sourcesamples=validatefinitevector"),
            compact.index("startus=zeros"),
        )
        validation_helper = compact[compact.index("functionvalues=validatefinitevector") :]
        self.assertLess(
            validation_helper.index("numel(values)>maxcount"),
            validation_helper.index("values=reshape(double(values)"),
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
            "daq",
            "arduino",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotRegex(code, rf"\b{forbidden}\s*\(")
        self.assertNotIn("simulink", code)
        self.assertNotIn("data acquisition toolbox", code)
        self.assertNotIn("real-time toolbox", code)

    def test_model_rejects_malformed_policy_timing_and_resources(self):
        source = read("model.m")
        for identifier in (
            "P13:model:Arity",
            "P13:model:SourceSamples",
            "P13:model:SampleResourceBound",
            "P13:model:SourcePrecision",
            "P13:model:SamplePeriod",
            "P13:model:BytesPerSample",
            "P13:model:BusRate",
            "P13:model:Arbitration",
            "P13:model:BlockSamples",
            "P13:model:BlockResourceBound",
            "P13:model:DmaSetupCpu",
            "P13:model:CompletionIsrCpu",
            "P13:model:ProcessorCopyCpu",
            "P13:model:DescriptorTimeout",
            "P13:model:TimeoutAction",
            "P13:model:DestinationMode",
            "P13:model:TimingResourceBound",
            "P13:model:TimingPrecision",
            "P13:model:CpuResourceBound",
        ):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, source)
        for marker in ("isnumeric", "~islogical", "isreal", "isfinite"):
            self.assertIn(marker, source)
        self.assertRegex(source, r"maxSamples\s*=\s*\d+")
        self.assertRegex(source, r"maxTimelineUs\s*=\s*[0-9.eE+]+")
        self.assertIn("values(:) > uint64(flintmax)", source)
        self.assertIn("values(:) > int64(flintmax)", source)
        self.assertIn("values(:) < -int64(flintmax)", source)

    def test_scenario_is_seedless_bounded_and_model_compatible(self):
        scenario = matlab_code_without_comments(read("p13_scenario.m")).lower()
        for name in (
            "baseline",
            "fixed-destination",
            "overloaded-bus",
            "timeout-continue",
            "timeout-abort",
        ):
            with self.subTest(name=name):
                self.assertIn(name, scenario)
        for field in (
            "source_samples",
            "sample_period_us",
            "bytes_per_sample",
            "bus_rate_bytes_per_us",
            "arbitration_us",
            "block_samples",
            "dma_setup_cpu_us",
            "completion_isr_cpu_us",
            "processor_copy_cpu_us_per_sample",
            "descriptor_timeout_us",
            "timeout_action",
            "destination_mode",
        ):
            with self.subTest(field=field):
                self.assertIn(field, scenario)
        self.assertRegex(scenario, r"mod\s*\(\s*37\s*\.\*")
        self.assertIn("4096", scenario)
        self.assertNotRegex(scenario, r"\b(?:rng|rand|randn|while|timer|pause)\b")

    def test_independent_baseline_serial_timing_destination_and_cpu_accounting(self):
        result = dma_reference()
        self.assertEqual(result["source"], [float(value) for value in BASELINE_SOURCE])
        self.assertEqual(BASELINE_SOURCE[0], 11)
        self.assertEqual(BASELINE_SOURCE[-1], 1158)
        self.assertEqual(result["sample_count"], 32)
        self.assertEqual(result["beat_service_us"], 11)
        self.assertEqual(result["request_us"], list(range(0, 1600, 50)))
        self.assertEqual(result["start_us"], result["request_us"])
        self.assertEqual(result["completion_us"], list(range(11, 1562, 50)))
        self.assertEqual(result["block_end_sample"], [8, 16, 24, 32])
        self.assertEqual(result["block_completion_us"], [361, 761, 1161, 1561])
        expected_ready = [361, 311, 261, 211, 161, 111, 61, 11] * 4
        self.assertEqual(result["block_ready_latency_us"], expected_ready)
        self.assertEqual(result["mean_block_ready_latency_us"], 186)
        self.assertEqual(result["max_block_ready_latency_us"], 361)
        self.assertEqual(result["offered_load_percent"], 22)
        self.assertEqual(result["request_slack_us"], 39)
        self.assertEqual(result["peak_pending"], 1)
        self.assertEqual(result["reference_bus_service_us"], 352)
        self.assertEqual(result["processor_copy_cpu_demand_us"], 128)
        self.assertEqual(result["dma_cpu_demand_us"], 20)
        self.assertEqual(result["processor_cpu_saved_us"], 108)
        self.assertEqual(result["destination"], result["source"])
        self.assertTrue(result["destination_integrity"])
        self.assertEqual(result["work_conservation_error_samples"], 0)

    def test_independent_block_size_sweep_isolates_handoff_and_cpu_demand(self):
        block_sizes = [1, 2, 4, 8, 16, 32]
        results = [dma_reference(block_samples=value) for value in block_sizes]
        self.assertEqual(
            [result["completed_block_count"] for result in results],
            [32, 16, 8, 4, 2, 1],
        )
        self.assertEqual(
            [result["dma_cpu_demand_us"] for result in results],
            [104, 56, 32, 20, 14, 11],
        )
        self.assertEqual(
            [result["mean_block_ready_latency_us"] for result in results],
            [11, 36, 86, 186, 386, 786],
        )
        self.assertEqual(
            [result["max_block_ready_latency_us"] for result in results],
            [11, 61, 161, 361, 761, 1561],
        )
        self.assertEqual(
            [result["descriptor_reference_completion_us"] for result in results],
            [1561] * 6,
        )
        self.assertEqual(
            [result["reference_bus_service_us"] for result in results],
            [352] * 6,
        )
        self.assertTrue(all(result["destination_integrity"] for result in results))

    def test_independent_bus_rate_sweep_exposes_serial_backlog(self):
        rates = [0.025, 0.04, 0.05, 0.1, 0.2]
        results = [dma_reference(bus_rate_bytes_per_us=value) for value in rates]
        self.assertEqual(
            [result["beat_service_us"] for result in results],
            [81, 51, 41, 21, 11],
        )
        self.assertEqual(
            [result["offered_load_percent"] for result in results],
            [162, 102, 82, 42, 22],
        )
        self.assertEqual(
            [result["max_request_latency_us"] for result in results],
            [1042, 82, 41, 21, 11],
        )
        self.assertEqual(
            [result["peak_pending"] for result in results],
            [13, 2, 1, 1, 1],
        )
        self.assertEqual(
            [result["descriptor_reference_completion_us"] for result in results],
            [2592, 1632, 1591, 1571, 1561],
        )
        self.assertEqual(
            [result["request_period_exceed_count"] for result in results],
            [32, 32, 0, 0, 0],
        )
        self.assertEqual(
            [result["dma_cpu_demand_us"] for result in results], [20] * 5
        )

    def test_independent_fixed_address_corruption_preserves_timing_symptom(self):
        clean = dma_reference()
        broken = dma_reference(destination_mode="fixed")
        self.assertEqual(broken["completion_us"], clean["completion_us"])
        self.assertEqual(broken["block_completion_us"], clean["block_completion_us"])
        self.assertEqual(broken["committed_count"], 32)
        self.assertEqual(broken["completed_block_count"], 4)
        self.assertEqual(broken["destination"][0], 1158)
        self.assertEqual(broken["destination"][1:], [None] * 31)
        self.assertEqual(broken["destination_address"], [1] * 32)
        self.assertEqual(broken["overwrite_count"], 31)
        self.assertEqual(broken["unwritten_count"], 31)
        self.assertFalse(broken["destination_integrity"])
        recovered = dma_reference()
        self.assertEqual(recovered, clean)

    def test_independent_timeout_equality_continue_abort_and_recovery(self):
        equality = dma_reference(
            descriptor_timeout_us=1561, timeout_action="abort-transfer"
        )
        self.assertFalse(equality["descriptor_timed_out"])
        self.assertFalse(equality["aborted"])
        self.assertEqual(equality["committed_count"], 32)
        self.assertTrue(equality["destination_integrity"])

        continued = dma_reference(descriptor_timeout_us=1161)
        self.assertTrue(continued["descriptor_timed_out"])
        self.assertFalse(continued["aborted"])
        self.assertEqual(continued["committed_count"], 32)
        self.assertEqual(continued["completed_block_count"], 4)
        self.assertTrue(continued["destination_integrity"])
        self.assertEqual(continued["descriptor_completion_us"], 1561)

        boundary_abort = dma_reference(
            descriptor_timeout_us=1161, timeout_action="abort-transfer"
        )
        self.assertTrue(boundary_abort["descriptor_timed_out"])
        self.assertTrue(boundary_abort["aborted"])
        self.assertEqual(boundary_abort["committed_count"], 24)
        self.assertEqual(boundary_abort["cancelled_count"], 8)
        self.assertEqual(boundary_abort["completed_block_count"], 3)
        self.assertEqual(boundary_abort["partial_block_sample_count"], 0)
        self.assertFalse(boundary_abort["partial_beat_in_flight_at_abort"])
        self.assertEqual(boundary_abort["committed_bus_service_us"], 264)
        self.assertEqual(boundary_abort["observed_bus_active_us"], 264)
        self.assertEqual(
            boundary_abort["committed_processor_copy_cpu_demand_us"], 96
        )
        self.assertEqual(boundary_abort["dma_cpu_demand_us"], 17)
        self.assertEqual(boundary_abort["observed_processor_cpu_saved_us"], 79)
        self.assertEqual(boundary_abort["destination"][:24], [float(v) for v in BASELINE_SOURCE[:24]])
        self.assertEqual(boundary_abort["destination"][24:], [None] * 8)
        self.assertIsNone(boundary_abort["descriptor_completion_us"])
        self.assertEqual(boundary_abort["work_conservation_error_samples"], 0)

        partial_abort = dma_reference(
            descriptor_timeout_us=1160, timeout_action="abort-transfer"
        )
        self.assertEqual(partial_abort["committed_count"], 23)
        self.assertEqual(partial_abort["cancelled_count"], 9)
        self.assertEqual(partial_abort["completed_block_count"], 2)
        self.assertEqual(partial_abort["partial_block_sample_count"], 7)
        self.assertTrue(partial_abort["partial_beat_in_flight_at_abort"])
        self.assertEqual(partial_abort["committed_bus_service_us"], 253)
        self.assertEqual(partial_abort["observed_bus_active_us"], 263)
        self.assertEqual(partial_abort["destination"][:23], [float(v) for v in BASELINE_SOURCE[:23]])
        self.assertEqual(partial_abort["destination"][23:], [None] * 9)

        recovered = dma_reference()
        self.assertEqual(recovered, dma_reference())

    def test_independent_limiting_cases_and_completion_before_equal_arrival(self):
        one = dma_reference(source_samples=[11], block_samples=8)
        self.assertEqual(one["request_us"], [0])
        self.assertEqual(one["completion_us"], [11])
        self.assertEqual(one["block_end_sample"], [1])
        self.assertEqual(one["completed_block_count"], 1)
        self.assertEqual(one["dma_cpu_demand_us"], 11)
        self.assertEqual(one["work_conservation_error_samples"], 0)

        exact_budget = dma_reference(
            source_samples=BASELINE_SOURCE[:4],
            bus_rate_bytes_per_us=0.25,
            arbitration_us=42,
            block_samples=2,
        )
        self.assertAlmostEqual(exact_budget["beat_service_us"], 50)
        self.assertEqual(exact_budget["request_us"], [0, 50, 100, 150])
        self.assertEqual(exact_budget["start_us"], [0, 50, 100, 150])
        self.assertEqual(exact_budget["completion_us"], [50, 100, 150, 200])
        self.assertEqual(exact_budget["peak_pending"], 1)
        self.assertEqual(exact_budget["request_period_exceed_count"], 0)

        partial_final = dma_reference(
            source_samples=BASELINE_SOURCE[:10], block_samples=8
        )
        self.assertEqual(partial_final["block_end_sample"], [8, 10])
        self.assertEqual(partial_final["completed_block_count"], 2)
        self.assertEqual(partial_final["block_completion_us"], [361, 461])
        self.assertEqual(partial_final["work_conservation_error_samples"], 0)

    def test_independent_final_short_block_uses_its_actual_tail_endpoint(self):
        result = dma_reference(
            source_samples=BASELINE_SOURCE[:10], block_samples=8
        )
        self.assertEqual(result["block_end_sample"], [8, 10])
        self.assertEqual(result["block_completion_us"], [361, 461])
        self.assertEqual(
            result["block_ready_latency_us"],
            [361, 311, 261, 211, 161, 111, 61, 11, 61, 11],
        )
        self.assertEqual(result["completed_block_count"], 2)
        self.assertEqual(result["dma_cpu_demand_us"], 14)
        self.assertEqual(result["mean_block_ready_latency_us"], 156)
        self.assertEqual(result["max_block_ready_latency_us"], 361)
        self.assertTrue(result["destination_integrity"])


class P13LearningAndRegressionTests(unittest.TestCase):
    def test_experiment_has_baseline_two_isolated_sweeps_and_broken_case(self):
        experiment = read("experiment.m").lower()
        normalized = re.sub(r"\s+", " ", experiment)
        compact = re.sub(r"\s+", "", experiment).replace("...", "")
        self.assertIn("%% baseline", experiment)
        self.assertIn("isequaln(baseline,baselinerepeat)", compact)
        self.assertGreaterEqual(experiment.count("%% sweep"), 2)
        self.assertRegex(experiment, r"block\w*sweep\w*\s*=\s*\[1 2 4 8 16 32\]")
        self.assertRegex(
            experiment,
            r"(?:bus|payload)\w*rate\w*sweep\w*\s*=\s*\[0\.025 0\.04 0\.05 0\.1 0\.2\]",
        )
        for expected in (
            "[32 16 8 4 2 1]",
            "[104 56 32 20 14 11]",
            "[11 36 86 186 386 786]",
            "[11 61 161 361 761 1561]",
            "[81 51 41 21 11]",
            "[162 102 82 42 22]",
            "[1042 82 41 21 11]",
            "[13 2 1 1 1]",
            "[2592 1632 1591 1571 1561]",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, normalized)
        self.assertIn("%% broken case", experiment)
        for scenario in (
            "fixed-destination",
            "timeout-continue",
            "timeout-abort",
        ):
            with self.subTest(scenario=scenario):
                self.assertRegex(
                    experiment,
                    rf"(?:p13_scenario|scenariofcn)\('{scenario}'\)",
                )
        self.assertIn("q>t_s", experiment)
        self.assertIn("isequaln(recovered,baseline)", compact)
        self.assertIn("rollback", experiment)
        self.assertGreaterEqual(experiment.count("figure("), 5)
        self.assertIn("xlabel(", experiment)
        self.assertIn("ylabel(", experiment)
        self.assertIn("(us)", experiment)
        self.assertIn("byte/us", experiment)
        self.assertIn("mechanism for sweep 1", experiment)
        self.assertIn("mechanism for sweep 2", experiment)
        self.assertIn("must isolate", experiment)
        bus_sweep_plot = experiment[
            experiment.index("figure('name', 'p13 dma bus-rate sweep')") :
            experiment.index("%% broken case")
        ]
        self.assertIn("yyaxis left", bus_sweep_plot)
        self.assertIn("offered bus-engine load (%)", bus_sweep_plot)
        self.assertIn("yyaxis right", bus_sweep_plot)
        self.assertIn("maximum request latency (us)", bus_sweep_plot)
        self.assertNotIn("offered load (%) or", bus_sweep_plot)

    def test_interactive_exposes_meaningful_controls_scenarios_and_two_views(self):
        interactive = re.sub(r"\s+", " ", read("interactive.m").lower())
        self.assertIn("uifigure(", interactive)
        self.assertGreaterEqual(interactive.count("uispinner("), 1)
        self.assertGreaterEqual(interactive.count("uidropdown("), 2)
        label_groups = {
            "sample period": ("sample period",),
            "block size": ("block size",),
            "bytes per sample": ("bytes per sample", "bytes/sample"),
            "payload rate": ("payload rate", "bus rate"),
            "arbitration": ("arbitration",),
            "dma setup": ("dma setup",),
            "completion isr": ("completion isr",),
            "processor copy": ("processor copy",),
            "descriptor timeout": ("descriptor timeout", "timeout (us"),
            "timeout action": ("timeout action",),
            "scenario": ("scenario",),
        }
        for label, alternatives in label_groups.items():
            with self.subTest(label=label):
                self.assertTrue(any(value in interactive for value in alternatives))
        self.assertGreaterEqual(interactive.count("uiaxes("), 2)
        self.assertIn("valuechangedfcn", interactive)
        self.assertIn("fixed destination", interactive)
        self.assertIn("overloaded bus", interactive)
        self.assertIn("continue", interactive)
        self.assertIn("abort", interactive)
        self.assertIn("not matlab-runtime", interactive)
        self.assertIn("hardware", interactive)
        self.assertIn("reference no-abort finish", interactive)
        self.assertIn("committed dma finish", interactive)

    def test_interactive_masks_cancelled_dma_tail_and_discretizes_byte_width(self):
        interactive = matlab_code_without_comments(read("interactive.m")).lower()
        compact = re.sub(r"\s+", "", interactive).replace("...", "")
        self.assertIn(
            "observedcompletionus(~out.memory.committed)=nan;", compact
        )
        self.assertIn(
            "startedbeforeabort=out.timeline.start_us<"
            "input.descriptor_timeout_us;",
            compact,
        )
        self.assertIn("observedstartus(~startedbeforeabort)=nan;", compact)
        self.assertIn("out.observation.descriptor_completion_us", interactive)
        self.assertIn("arrayfun(@num2str,1:16", compact)
        self.assertIn("input.bytes_per_sample=str2double(bytescontrol.value);", compact)
        summary_region = interactive[
            interactive.index("summary.text = sprintf") : interactive.index(
                ");", interactive.index("summary.text = sprintf")
            )
        ]
        conversions = re.findall(r"%(?!%)(?:\.\d+)?[dgfs]", summary_region)
        self.assertEqual(len(conversions), len(re.findall(r"\bout\.", summary_region)))
        self.assertIn("request-budget excesses %d", summary_region)

    def test_interactive_callbacks_bind_p13_dependencies_before_path_cleanup(self):
        interactive = matlab_code_without_comments(read("interactive.m")).lower()
        compact = re.sub(r"\s+", "", interactive).replace("...", "")
        self.assertIn("modelfcn=@model;", compact)
        self.assertIn("scenariofcn=@p13_scenario;", compact)
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
        self.assertGreaterEqual(selector.count(".value="), 9)
        self.assertIn("controls{controlindex}.enable='off';", selector)
        self.assertLess(selector.rindex(".value="), selector.index("updateviews();"))

    def test_executable_checks_cover_full_dma_failure_contract(self):
        checks = matlab_code_without_comments(read("run_checks.m"))
        lower = checks.lower()
        self.assertGreaterEqual(len(re.findall(r"\bassert\s*\(", checks)), 65)
        marker_groups = {
            "determinism": ("deterministic and state-isolated",),
            "serialized service": ("serialized", "previous completion"),
            "beat equation": ("a+b/r", "arbitration plus payload"),
            "boundary order": ("completion before", "equality"),
            "block ownership": ("block completion", "block-ready"),
            "cpu accounting": ("processor-copy", "cpu demand"),
            "block sweep": ("block-size sweep", "block sweep"),
            "rate sweep": ("payload-rate sweep", "bus-rate sweep"),
            "backlog": ("pending", "overloaded"),
            "address fault": ("fixed-destination", "fixed destination"),
            "timeout equality": ("equal to the timeout", "timeout equality"),
            "continue": ("continue-waiting",),
            "abort": ("abort-transfer",),
            "partial block": ("partial block", "partly written"),
            "rollback": ("roll back exactly", "rollback"),
            "recovery": ("recover exact baseline", "clean recovery"),
            "compatibility": ("integer-class", "scalar strings"),
            "callback": ("callback-bound p13 dependencies",),
            "resource": ("resource bound", "resource ceiling"),
            "conservation": ("conserve", "work conservation"),
            "isolation": ("must isolate",),
        }
        for contract, alternatives in marker_groups.items():
            with self.subTest(contract=contract):
                self.assertTrue(any(marker in lower for marker in alternatives))
        for identifier in (
            "p13:model:arity",
            "p13:model:sourcesamples",
            "p13:model:sampleresourcebound",
            "p13:model:sourceprecision",
            "p13:model:sampleperiod",
            "p13:model:bytespersample",
            "p13:model:busrate",
            "p13:model:arbitration",
            "p13:model:blocksamples",
            "p13:model:blockresourcebound",
            "p13:model:dmasetupcpu",
            "p13:model:completionisrcpu",
            "p13:model:processorcopycpu",
            "p13:model:descriptortimeout",
            "p13:model:timeoutaction",
            "p13:model:destinationmode",
            "p13:model:timingresourcebound",
            "p13:model:timingprecision",
            "p13:model:cpuresourcebound",
        ):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, lower)
        self.assertIn("malformed call must not contaminate", lower)
        self.assertIn("not an asynchronous dma cancellation api", lower)
        self.assertIn("p13 checks passed", lower)

    def test_tutor_text_is_mechanism_first_and_ends_in_teach_back(self):
        lesson_source = read("lesson.md").lower()
        lesson = re.sub(r"\s+", " ", lesson_source)
        walkthrough = read("walkthrough.md").lower()
        checks = read("checks.md").lower()
        self.assertEqual(
            len(re.findall(r"(?m)^## [^\n]*prediction[^\n]*$", lesson_source)), 1
        )
        self.assertIn("q = a + b/r", lesson)
        self.assertIn("s_i = max", lesson)
        self.assertIn("f_i = s_i + q", lesson)
        self.assertRegex(lesson, r"rho\s*=\s*q/t_s")
        self.assertIn("block-ready", lesson)
        self.assertIn("processor", lesson)
        self.assertIn("p12", lesson)
        self.assertIn("p14", lesson)
        self.assertIn("fixed", lesson)
        self.assertTrue(
            "move one lever" in walkthrough or "move only" in walkthrough
        )
        self.assertIn("reset", walkthrough)
        self.assertIn("interpretation", checks)
        self.assertIn("teach-back", checks)

    def test_claim_language_separates_model_runtime_dma_and_physical_evidence(self):
        combined = "\n".join(
            read(name).lower()
            for name in ("README.md", "lesson.md", "checks.md", "experiment.m")
        )
        for marker in (
            "synthetic",
            "not matlab-runtime",
            "dma",
            "bus",
            "processor",
            "cache",
            "coherency",
            "hardware",
            "bench",
            "hil",
            "field",
            "p12",
            "p14",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, combined)
        self.assertNotIn("hardware-validated", combined)
        self.assertNotIn("dma-validated", combined)
        self.assertNotIn("processor-validated", combined)

    def test_cli_start_routes_p13_and_persists_only_isolated_progress(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary) / "repo"
            fixture.mkdir()
            shutil.copytree(ROOT / "bin", fixture / "bin")
            shutil.copytree(ROOT / "curriculum", fixture / "curriculum")
            module_fixture = fixture / "modules/13-move-samples-with-dma"
            module_fixture.mkdir(parents=True)
            for name in ("README.md", "lesson.md", "walkthrough.md", "checks.md"):
                shutil.copy2(MODULE_FOLDER / name, module_fixture / name)

            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            result = subprocess.run(
                [str(fixture / "bin/learn"), "start", "P13"],
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
                "P13 — Move Samples with DMA\n"
                "Status: implemented\n"
                f"Guiding question: {QUESTION}\n"
                "Folder: modules/13-move-samples-with-dma\n"
                "\nMATLAB:\n"
                "  launch_lesson('P13')\n"
                "\nTutor files:\n"
                "  modules/13-move-samples-with-dma/README.md\n"
                "  modules/13-move-samples-with-dma/lesson.md\n"
                "  modules/13-move-samples-with-dma/walkthrough.md\n"
                "  modules/13-move-samples-with-dma/checks.md\n",
            )
            progress = json.loads(
                (fixture / ".learning/progress.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                progress, {"current": "P13", "completed": {}, "notes": {}}
            )

    def test_cli_check_resolves_p13_public_matlab_entry_point(self):
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [str(ROOT / "bin/learn"), "check", "P13"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env=environment,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "Run in MATLAB: run_module_checks('P13')\n")

    @unittest.skipUnless(shutil.which("matlab"), "MATLAB executable unavailable")
    def test_matlab_executes_module_checks_and_callback_lifetime(self):
        result = subprocess.run(
            [shutil.which("matlab"), "-batch", "run_module_checks('P13')"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=300,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"MATLAB P13 checks failed:\n{result.stdout}\n{result.stderr}",
        )
        self.assertIn("P13 checks passed", result.stdout)


class P13RetainedEvidenceTests(unittest.TestCase):
    def test_date_agnostic_retained_evidence_is_complete_and_honest(self):
        evidence_files = sorted((ROOT / "docs/evidence").glob("P13-*.md"))
        self.assertTrue(evidence_files, "P13 requires a retained evidence record")
        for path in evidence_files:
            with self.subTest(path=path.name):
                payload = path.read_bytes()
                self.assertTrue(payload.endswith(b"\n"))
                self.assertFalse(payload.endswith(b"\n\n"))
                text = payload.decode("utf-8").lower()
                for unfinished in (
                    "pending final retained result",
                    "<source-focused p13 test selectors>",
                    "at this checkpoint",
                    "real manifest remains `scaffolded`",
                    "has not been performed",
                    "have not been performed",
                    "required commands remain",
                    "after they are run",
                ):
                    with self.subTest(path=path.name, unfinished=unfinished):
                        self.assertNotIn(unfinished, text)
                self.assertNotRegex(
                    text,
                    r"<[^>\n]*(?:command|result|selector)[^>\n]*>",
                )
                self.assertNotIn("| unverified", text)
                self.assertIn("verify pass: 24 modules", text)
                self.assertIn("intended-final-state", text)
                self.assertIn("post-transition", text)
                self.assertGreaterEqual(text.count("exit `0`"), 8)
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
                    "dma",
                    "bus",
                    "processor",
                    "cache",
                    "coherency",
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
                    "final-short-block ownership",
                    "separate percent and microsecond",
                ):
                    with self.subTest(path=path.name, marker=marker):
                        self.assertIn(marker, text)

    def test_structured_evidence_matches_the_retained_acceptance_record(self):
        path = MODULE_FOLDER / "evidence.json"
        payload = path.read_bytes()
        self.assertTrue(payload.endswith(b"\n"))
        self.assertFalse(payload.endswith(b"\n\n"))
        evidence = json.loads(payload.decode("utf-8"))
        required = {
            "schema_version",
            "batch_id",
            "status",
            "commands",
            "acceptance",
            "residual_risks",
            "unperformed_validation",
        }
        allowed = required | {"changed_invariants"}
        self.assertEqual(set(evidence), allowed)
        self.assertEqual(evidence["schema_version"], 1)
        self.assertEqual(evidence["batch_id"], "P13")
        self.assertEqual(evidence["status"], "pass")
        self.assertGreaterEqual(len(evidence["commands"]), 8)
        self.assertEqual(len(evidence["acceptance"]), 8)
        self.assertTrue(
            all(item.get("status") == "pass" for item in evidence["acceptance"])
        )
        self.assertTrue(evidence["changed_invariants"])
        self.assertTrue(evidence["residual_risks"])
        self.assertTrue(evidence["unperformed_validation"])


if __name__ == "__main__":
    unittest.main()
