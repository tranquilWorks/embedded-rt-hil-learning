# Curriculum modules

The canonical order is foundational and cumulative. Each `P##` is one governed,
reviewable implementation batch. `implemented` means the complete learner slice exists;
`scaffolded` means the batch is intentionally non-runnable.

| Batch | Phase | Module | Guiding question | Status |
| --- | --- | --- | --- | --- |
| P01 | 1: Microcontroller execution | [See a Periodic Scheduler Miss a Deadline](../modules/01-see-a-periodic-scheduler-miss-a-deadline/README.md) | When does logically correct software become physically late? | implemented |
| P02 | 1: Microcontroller execution | [Drive GPIO with a State Machine](../modules/02-drive-gpio-with-a-state-machine/README.md) | What inputs, observable effects, and failure modes matter when you drive GPIO with a State Machine? | implemented |
| P03 | 1: Microcontroller execution | [Compare Polling and Interrupts](../modules/03-compare-polling-and-interrupts/README.md) | What inputs, observable effects, and failure modes matter when you compare Polling and Interrupts? | implemented |
| P04 | 1: Microcontroller execution | [Measure Timer Quantization](../modules/04-measure-timer-quantization/README.md) | What inputs, observable effects, and failure modes matter when you measure Timer Quantization? | implemented |
| P05 | 2: Buses and acquisition | [Frame Bytes over UART](../modules/05-frame-bytes-over-uart/README.md) | What inputs, observable effects, and failure modes matter when you frame Bytes over UART? | implemented |
| P06 | 2: Buses and acquisition | [Compare SPI and I2C Transactions](../modules/06-compare-spi-and-i2c-transactions/README.md) | What inputs, observable effects, and failure modes matter when you compare SPI and I2C Transactions? | scaffolded |
| P07 | 2: Buses and acquisition | [Sample an ADC Without Aliasing](../modules/07-sample-an-adc-without-aliasing/README.md) | What inputs, observable effects, and failure modes matter when you sample an ADC Without Aliasing? | scaffolded |
| P08 | 2: Buses and acquisition | [Command a DAC and Observe Settling](../modules/08-command-a-dac-and-observe-settling/README.md) | What inputs, observable effects, and failure modes matter when you command a DAC and Observe Settling? | scaffolded |
| P09 | 3: RTOS behavior | [Schedule Tasks by Priority](../modules/09-schedule-tasks-by-priority/README.md) | What inputs, observable effects, and failure modes matter when you schedule Tasks by Priority? | scaffolded |
| P10 | 3: RTOS behavior | [Trigger Priority Inversion](../modules/10-trigger-priority-inversion/README.md) | What inputs, observable effects, and failure modes matter when you trigger Priority Inversion? | scaffolded |
| P11 | 3: RTOS behavior | [Protect Shared Data Without Excess Blocking](../modules/11-protect-shared-data-without-excess-blocking/README.md) | What inputs, observable effects, and failure modes matter when you protect Shared Data Without Excess Blocking? | scaffolded |
| P12 | 3: RTOS behavior | [Measure Jitter and Worst-Case Response Time](../modules/12-measure-jitter-and-worst-case-response-time/README.md) | What inputs, observable effects, and failure modes matter when you measure Jitter and Worst-Case Response Time? | scaffolded |
| P13 | 4: Data movement and timing | [Move Samples with DMA](../modules/13-move-samples-with-dma/README.md) | What inputs, observable effects, and failure modes matter when you move Samples with DMA? | scaffolded |
| P14 | 4: Data movement and timing | [Prevent Ring-Buffer Overrun](../modules/14-prevent-ring-buffer-overrun/README.md) | What inputs, observable effects, and failure modes matter when you prevent Ring-Buffer Overrun? | scaffolded |
| P15 | 4: Data movement and timing | [Align Clocks with PPS and Timestamps](../modules/15-align-clocks-with-pps-and-timestamps/README.md) | What inputs, observable effects, and failure modes matter when you align Clocks with PPS and Timestamps? | scaffolded |
| P16 | 4: Data movement and timing | [Execute a Multi-Rate Processing Graph](../modules/16-execute-a-multi-rate-processing-graph/README.md) | What inputs, observable effects, and failure modes matter when you execute a Multi-Rate Processing Graph? | scaffolded |
| P17 | 5: Health and fault handling | [Recover with a Watchdog](../modules/17-recover-with-a-watchdog/README.md) | What inputs, observable effects, and failure modes matter when you recover with a Watchdog? | scaffolded |
| P18 | 5: Health and fault handling | [Detect a Stuck Sensor](../modules/18-detect-a-stuck-sensor/README.md) | What inputs, observable effects, and failure modes matter when you detect a Stuck Sensor? | scaffolded |
| P19 | 5: Health and fault handling | [Inject Communication Faults](../modules/19-inject-communication-faults/README.md) | What inputs, observable effects, and failure modes matter when you inject Communication Faults? | scaffolded |
| P20 | 5: Health and fault handling | [Enter and Exit a Safe State](../modules/20-enter-and-exit-a-safe-state/README.md) | What inputs, observable effects, and failure modes matter when you enter and Exit a Safe State? | scaffolded |
| P21 | 6: SIL, PIL, and HIL | [Compare Software, Processor, and Hardware Loops](../modules/21-compare-software-processor-and-hardware-loops/README.md) | What inputs, observable effects, and failure modes matter when you compare Software, Processor, and Hardware Loops? | scaffolded |
| P22 | 6: SIL, PIL, and HIL | [Replay an Input Deterministically](../modules/22-replay-an-input-deterministically/README.md) | What inputs, observable effects, and failure modes matter when you replay an Input Deterministically? | scaffolded |
| P23 | 6: SIL, PIL, and HIL | [Define a Device Command and Telemetry Contract](../modules/23-define-a-device-command-and-telemetry-contract/README.md) | What inputs, observable effects, and failure modes matter when you define a Device Command and Telemetry Contract? | scaffolded |
| P24 | 6: SIL, PIL, and HIL | [Produce Repeatable Verification Evidence](../modules/24-produce-repeatable-verification-evidence/README.md) | What inputs, observable effects, and failure modes matter when you produce Repeatable Verification Evidence? | scaffolded |
