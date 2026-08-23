# P15 — Align Clocks with PPS and Timestamps

**Track:** Embedded, Real-Time, and Hardware-in-the-Loop Systems  
**Phase 4:** Data movement and timing  
**Status:** implemented

## Guiding question

What inputs, observable effects, and failure modes matter when you align Clocks with PPS and Timestamps?

## Computational mental model

P14 established that a finite ring can preserve record identity and order. P15 starts after that handoff:
an intact record may still carry a timestamp from a clock whose origin and rate differ from the reference.
The synthetic local clock is affine:

```text
C(t) = b + r t
r    = 1 + s * 10^-6
```

where reference time `t`, local time `C(t)`, and initial offset `b` are in microseconds, and oscillator skew
`s` is in parts per million. A timestamp register with tick `q` reports

```text
timestamp(t) = q floor(C(t)/q).
```

Before flooring, the implementation normalizes a quotient that is within eight double-precision ULPs of an
integer. That bounded allowance covers the affine multiply/add and tick-division operation chain, matching
the repository's P04 convention. The absolute quotient is capped at `1e12` ticks; beyond that ceiling the ULP
band can consume a material fraction of a tick and turn a declared floor into upward rounding, so the model
rejects instead. Within the bound, a value distinguishably below the eight-ULP band still floors downward;
this is not general round-to-nearest.

PPS is one pulse per second, but a sharp edge alone does not say which second occurred. Each captured edge
therefore carries a sequence ID `k`, and its reference coordinate is

```text
t_pps(k) = k T_pps.
```

For retained first and last anchors `(t_1,c_1)` and `(t_N,c_N)`, the transparent estimate is

```text
r_hat = (c_N-c_1)/(t_N-t_1)
b_hat = c_1-r_hat t_1
t_hat = (c_event-b_hat)/r_hat.
```

One PPS anchor can estimate an offset but cannot identify rate. Two distinct, correctly associated anchors
identify an ideal affine clock. Finite timestamp ticks, capture latency, changing oscillator rate, wrong
epoch labels, or incorrect pulse association require additional error terms and evidence.

## Deterministic baseline

The seedless baseline declares:

- event reference times `[250000 750000 ... 3750000] us`;
- PPS sequence IDs `0:4` with `T_pps=1000000 us`;
- local offset `b=2500 us` and skew `s=40 ppm`;
- a `1 us` timestamp tick;
- sequence-ID association, no finite PPS wait timeout, and continued waiting.

The local PPS timestamps are `[2500 1002540 2002580 3002620 4002660] us`. Local event timestamps are
`[252510 752530 ... 3752650] us`, so raw event errors grow from `2510` to `2650 us`. Removing only the
first-PPS offset leaves errors `[10 30 ... 150] us`. The five ideal anchors recover `b=2500 us` and
`s=40 ppm`; aligned event errors and PPS fit residuals are zero in the governing arithmetic.

## What the learner controls

- **Initial clock offset (us):** the translation between reference and local coordinates at `t=0`.
- **Oscillator skew (ppm):** the local clock's rate error, which accumulates with elapsed time.
- **Timestamp tick (us):** downward quantization of local event and PPS captures.
- **PPS wait timeout (us):** maximum accepted gap between received PPS captures; zero in the UI disables it.
- **Timeout action:** continue waiting for later anchors or cancel alignment and censor the later prefix.
- **PPS association:** use sequence identity or deliberately substitute received array position.
- **Scenario:** editable baseline or fixed zero-error, missing-ID, broken-association, coarse-tick, and timeout
  diagnostics.

## Complete learning flow

1. Connect P14's preserved record identity to the new fact that local timestamp coordinates can still differ.
2. Make one prediction about what remains after a one-PPS offset correction.
3. Read raw, offset-only, and affine-corrected baseline error before the PPS-anchor residual view.
4. Sweep only offset `[0 1000 2500 5000 10000] us`. First-event error is
   `[10 1010 2510 5010 10010] us`; final-event error is `[150 1150 2650 5150 10150] us`.
5. Reset, then sweep only skew `[-80 -40 0 40 80] ppm`. Four-second drift is
   `[-320 -160 0 160 320] us`; offset-only maximum error is `[300 150 0 150 300] us`.
6. Explain offset as translation and skew as slope after both isolated changes are visible.
7. Drop PPS ID `1`. Show that sequence-ID association still recovers the clock, then deliberately pair the
   four received captures with positions `0:3` and inspect the large timestamp error.
8. Compare exact-timeout equality, continuation, cancellation, pure rollback, and clean recovery.
9. Run independent checks and give the two-sentence teach-back.

## Deliberately broken association

The broken case receives PPS IDs `[0 2 3 4]`, so ID `1` is missing. Correct association uses reference times
`[0 2000000 3000000 4000000] us` and still recovers the ideal affine clock. The broken implementation
silently pairs those same captures with received positions `[0 1000000 2000000 3000000] us`.

The endpoint fit exists and its endpoint residuals are zero, but it estimates `333386.666... ppm`. Interior
PPS residuals become approximately `[0 666693.333 333346.667 0] us`, and aligned event errors become

```text
[-62500 -187500 -312500 -437500 -562500 -687500 -812500 -937500] us.
```

The violated assumption is “received position still identifies the PPS epoch after a pulse is missing.” A
sharp edge gives phase; a trusted timestamp/sequence association gives epoch. Neither can substitute for the
other.

## Timeout, cancellation, rollback, and recovery

The PPS timeout applies to each observed gap. A pulse at the deadline is captured before timeout evaluation,
so the missing-ID gap of `2000000 us` passes a `2000000 us` timeout. At `1500000 us`, continue-waiting marks
the gap late but retains later captures and recovers the correct sequence-ID fit. Cancel-alignment retains
only ID `0`, censors IDs `2:4`, and reports that an affine estimate is unavailable because one anchor cannot
identify rate.

Gaps are derived from sequence-ID deltas times the PPS period, avoiding cancellation between large absolute
epoch coordinates. At a positive timeout, an adjacent value within one gap-scale ULP is treated as the
declared equality boundary; a gap outside that band remains late. A zero timeout receives no tolerance, so
every positive model gap is late.

Cancellation does not change true event times, previously captured local timestamps, the physical oscillator,
a receiver, an interrupt, or an external time service. Calling the state-free model again with clean inputs
is computational rollback and recovery only.

## Boundaries and dependencies

The model owns one ideal affine local clock, downward timestamp quantization, ordered integer PPS identities,
endpoint affine estimation, a per-gap wait boundary, and synthetic truth for diagnostics. It validates vector
shape and order, exact integer identity through `flintmax`, positive rate and tick, timestamp horizon, fit
resolution, an absolute `1e12` timestamp-tick-index ceiling, enum values, and event/PPS resource ceilings
before unsafe allocation.

P14 supplies preserved record identity and ordering; P15 does not re-model ring occupancy, DMA, cache
visibility, or concurrency. P16 will schedule a multi-rate processing graph in a declared time coordinate;
P15 does not execute, retime, or verify that graph.

The source uses base MATLAB arithmetic, arrays, `floor`, plots, and UI controls. It does not use a fitting,
navigation, mapping, communications, instrument, data-acquisition, or parallel toolbox; Simulink; a timer;
PTP/NTP; a GNSS/PPS receiver; a timestamp peripheral; an ISR; a device driver; or a physical oscillator.
Results are deterministic simulated calculations, not MATLAB-runtime, rendered-UI, MATLAB numerical-fidelity,
hardware, bench, HIL, field, RT1/RT2, Unreal, signing, release, deployment, staging, or production evidence.

## Files

- `p15_scenario.m` owns bounded seedless baseline and diagnostic fixtures.
- `model.m` owns validation, quantized affine-clock arithmetic, PPS association, timeout, cancellation, and
  diagnostics.
- `experiment.m` owns the deterministic baseline, labeled complementary views, two isolated sweeps, broken
  association, and recovery diagnostics.
- `interactive.m` owns immediate offset, skew, tick, timeout, association, and scenario controls.
- `lesson.m`, `lesson.md`, and `walkthrough.md` own the mechanism-first learner sequence.
- `checks.md` and `run_checks.m` own interpretation prompts and executable invariants.
