# P04 — Measure Timer Quantization

**Track:** Embedded, Real-Time, and Hardware-in-the-Loop Systems  
**Phase 1:** Microcontroller execution  
**Status:** implemented

## Guiding question

What inputs, observable effects, and failure modes matter when you measure Timer Quantization?

## Computational mental model

P03 treated event and service times as ideal real numbers. P04 asks what a finite free-running timer
can encode when those event edges are captured. If the timer tick is `q` microseconds, its phase is
`phi`, and it has `B` bits, then

```text
k(t) = floor((t + phi) / q)
c(t) = mod(k(t), 2^B).
```

`k(t)` is the transparent unwrapped completed-tick count. `c(t)` is the register value available to
software. For start and stop edges, modular subtraction gives

```text
delta_k = mod(c_stop - c_start, 2^B)
T_hat = q * delta_k.
```

This is unambiguous only when the model's unwrapped captured delta is strictly less than `2^B` ticks.
At or beyond one complete counter cycle, the wrapped values cannot reveal how many whole cycles were
missed; the primary result is therefore range ambiguity, not a plausible zero-length measurement.

Ideal endpoint flooring is less than one tick. Within each capture pair, the implementation treats values
inside a small shared normalization tolerance `tau` (in ticks) as an exact boundary, so endpoint timestamp
error lies in `(-q, tau*q]`. Because both endpoints in that pair use one uniformly shifted tick grid, their
interval error can be positive or negative but still has magnitude strictly less than `q` while the
measurement is valid. An unrelated capture pair cannot change that pair's tolerance.
Resolution is not oscillator accuracy, clock drift, synchronization delay, or interrupt latency. For a
source clock `f_clk` and prescaler `P`, `q = P / f_clk`; this lesson exposes `q` directly so the governing
operation remains visible.

These are deterministic synthetic capture calculations, not measurements of a timer peripheral,
oscillator, MCU, input-capture path, or physical hardware. This is not a hardware measurement.

## What the learner controls

- **Timer tick `q` (us):** sets completed-tick resolution and, at fixed width, the wrap period.
- **True interval (us):** changes the edge separation offered to the timer.
- **Timer phase (fraction of a tick):** moves both edges relative to the tick grid without adding jitter.
- **Counter width (bits):** changes range without changing tick resolution.
- **Capture scenario:** selects repeated intervals or fixed 10 us/eight-bit/zero-phase wrap and
  range-ambiguity fixtures.

## Complete learning flow

1. Connect P03's ideal request/detection times to start/stop edges captured here.
2. Predict what a 10 us tick can report for a true 37 us interval.
3. Inspect the fixed baseline interval view, then its signed error view.
4. Sweep only tick period and observe error resolution plus wrap range.
5. Reset tick period, then sweep only timer phase and observe the 30/40 us transition.
6. Explain both changed views from the two floored endpoint counts.
7. Break ordinary signed subtraction across one counter wrap, then observe modular recovery.
8. Distinguish a recoverable wrap from an ambiguous interval of a full modulus or more.
9. Run independent checks and give the requested teach-back.

## Files and dependencies

- `p04_scenario.m` owns bounded seedless capture fixtures.
- `model.m` owns input validation, normalized tick capture, modular arithmetic, range classification, and metrics.
- `experiment.m` owns the repeated baseline, labeled plots, independent sweeps, and broken case.
- `interactive.m` owns immediate controls and complementary interval/error views.
- `lesson.m`, `lesson.md`, and `walkthrough.md` own the mechanism-first learner sequence.
- `checks.md` and `run_checks.m` own interpretation prompts and executable invariants.

Only base MATLAB operations are used. No toolbox, Simulink, support package, asynchronous timer,
operating-system timing API, hardware API, or device-specific register model is required.
