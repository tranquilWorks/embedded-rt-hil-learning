# P05 — Frame Bytes over UART

**Track:** Embedded, Real-Time, and Hardware-in-the-Loop Systems  
**Phase 2:** Buses and acquisition  
**Status:** implemented

## Guiding question

What inputs, observable effects, and failure modes matter when you frame Bytes over UART?

## Computational mental model

P04 showed that a receiver cannot observe continuous time without a clock. P05 applies that idea to an
asynchronous binary UART line. The line rests high. Each character frame carries one low start bit, eight
data bits least-significant bit first, an optional parity bit, and one or two high stop bits:

```text
[start=0, d0, d1, d2, d3, d4, d5, d6, d7, parity?, stop=1, ...]
N_frame = 1 + 8 + N_parity + N_stop
T_tx = 10^6 / B_tx microseconds.
```

For receiver baud error `e` in percent, `B_rx = B_tx(1 + e/100)`. After each qualified start edge, the
receiver samples slot `j` at

```text
t_sample(j) = t_start + (j + 1/2) * 10^6 / B_rx.
```

The model shows the sample against half-open transmitter slots and reports its minimum distance from the
intended slot boundaries in transmitter-bit times. Positive margin is a pattern-independent timing
guarantee in this abstraction. Nonpositive margin is a risk diagnostic, not proof that every data pattern
must visibly fail. There is no universal UART mismatch percentage: format, phase, start qualification,
data pattern, clock behavior, and receiver implementation all matter.

The receiver deliberately recognizes only qualified transmitter frame-start edges. It does not emulate
oversampling filters or false acquisition on falling data edges. A forced-low stop followed immediately by
a low start therefore has no new edge; one frame is missed, and a later high stop permits reacquisition.

## What the learner controls

- **Transmit baud (binary symbols/s):** changes bit period, line time, and matched-clock goodput.
- **Receiver baud error (%):** moves center samples within each independently re-anchored frame.
- **Parity (`none`, `even`, `odd`):** adds one slot and can flag some data corruption.
- **Stop bits (1 or 2):** adds high idle slots and lowers payload efficiency.
- **Inter-frame idle gap (transmitter-bit times):** adds explicit high time between starts.
- **Scenario:** selects a clean stream, a flipped data bit, a forced-low stop with recovery, or a fixed
  deterministic receive deadline.

## Complete learning flow

1. Connect P04 clock representation to UART bit-center sampling.
2. Predict the bit count and efficiency of one 8-N-1 byte frame.
3. Inspect one logic-level frame, then compare transmitted and decoded bytes.
4. Sweep only transmitter baud with the receiver matched; observe time scale and goodput.
5. Reset transmitter baud, then sweep only receiver error; observe sample margin and byte outcomes.
6. Explain both views from `T_bit` and the receiver sample equation.
7. Force one stop low, observe a framing error and missing next edge, then identify later recovery.
8. Compare no parity with even parity for a flipped bit, and state parity's limitation.
9. Run independent checks and give the requested teach-back.

## Boundaries and dependencies

UART character framing does not identify packets or messages. This lesson does not add a delimiter,
length field, checksum, retransmission, flow control, or application parser. Its absolute receive deadline
is a deterministic classification cutoff, not an asynchronous operating-system or device timeout.
Cancellation is not applicable because the pure calculation contains no wait or external operation.

Only base MATLAB arithmetic, structs, plots, and UI controls are used. No Communications Toolbox,
`serialport`, Simulink, support package, operating-system serial API, or device register model is required.
The plotted zero/one levels are logical values, not TTL, CMOS, RS-232 voltage or polarity measurements.
This is not a hardware measurement, serial-port test, bench result, or HIL result.

## Files

- `p05_scenario.m` owns bounded seedless byte and fault fixtures.
- `model.m` owns validation, explicit frame construction, timing, sampling, errors, deadline, and metrics.
- `experiment.m` owns the deterministic baseline, labeled views, two isolated sweeps, and broken case.
- `interactive.m` owns immediate controls and complementary line/byte views.
- `lesson.m`, `lesson.md`, and `walkthrough.md` own the mechanism-first learner sequence.
- `checks.md` and `run_checks.m` own interpretation prompts and executable invariants.
