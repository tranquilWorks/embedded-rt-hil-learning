# P15 checks: Align Clocks with PPS and Timestamps

## Before completion

Run in MATLAB:

```matlab
run_module_checks("P15")
```

Passing source checks is not learner completion. Give the teach-back after interpreting the plots.

## Deterministic baseline and independent invariants

- Repeat the baseline and require an identical structure.
- Independently construct `C(t)=2500+(1+40e-6)t` and `floor(C/q)q` with `q=1 us`.
- Confirm PPS local timestamps `[2500 1002540 2002580 3002620 4002660] us`.
- Confirm event local timestamps `[252510 752530 ... 3752650] us`.
- Confirm raw errors `[2510 2530 ... 2650] us` and offset-only errors `[10 30 ... 150] us`.
- Derive `r_hat` and `b_hat` independently from the endpoint anchors; require `40 ppm`, `2500 us`, zero
  ideal corrected error, and zero ideal fit residual.

## Two isolated sweeps

- Offset `[0 1000 2500 5000 10000] us` must change only the additive translation. First-event error is
  `[10 1010 2510 5010 10010] us`; final-event error is `[150 1150 2650 5150 10150] us`.
- Reset, then skew `[-80 -40 0 40 80] ppm` must change only slope. Four-second drift is
  `[-320 -160 0 160 320] us`; final raw error is `[2200 2350 2500 2650 2800] us`; offset-only maximum
  error is `[300 150 0 150 300] us`.
- Both ideal sweeps must recover the swept affine parameter and retain zero governing corrected error.

## Broken association and limiting cases

- For IDs `[0 2 3 4]`, sequence-ID association must report one missing pulse and still recover the ideal
  affine clock.
- Arrival-index association must be marked inconsistent, estimate about `333386.667 ppm`, expose interior
  fit residuals near `666693` and `333347 us`, and end at `-937500 us` aligned event error.
- Zero offset and zero skew must reduce to the identity map.
- Zero skew with nonzero offset must produce constant raw error.
- One PPS anchor must permit offset-only display but leave affine alignment unavailable.
- Two distinct ideal anchors must remove any accepted affine offset and skew.
- Coarse quantization may collapse local anchor span; it must never silently claim an estimate.
- A decimal tick boundary such as `0.3 us` on a `0.1 us` grid must not lose a full tick because the affine
  operation chain lands a few ULPs below an integer. The eight-ULP guard matches P04; a value distinguishably
  below that band must still floor down, so this is not round-to-nearest.
- The exact `1e12` absolute tick-index boundary must execute. A finer configuration whose quotient exceeds
  that ceiling must reject before the eight-ULP band can cover a material fraction of a tick and round a
  genuinely below-boundary timestamp upward.

## Timeout, cancellation, rollback, and recovery

- A `2000000 us` missing-PPS gap at a `2000000 us` timeout must pass because capture precedes timeout at
  equality.
- Derive gaps from sequence-ID deltas rather than subtracting large absolute epochs. Decimal equality such as
  a computed `3*0.1 us` gap against `0.3 us` receives one gap-scale ULP of normalization. The adjacent-value
  policy treats one ULP as equality; a gap four ULPs above the deadline and `0.3 us > 0.29 us` remain late.
- A zero timeout has no equality tolerance: even the smallest accepted positive PPS gap remains strictly
  late. The interactive control maps its displayed zero to `Inf` before calling the model when disabling wait.
- At `1500000 us`, continue-waiting must mark lateness, retain all four captures, and recover the correct
  sequence-ID fit.
- Cancel-alignment must retain only ID `0`, censor IDs `2:4`, leave affine outputs unavailable/`NaN`, and
  preserve raw event timestamps.
- A canceled or rejected call must not contaminate an exact repeated baseline. That is computational reset
  only, not hardware rollback.

## Malformed input, compatibility, isolation, and resources

- Row/column vectors, integer numeric values through `flintmax`, scalar strings, character choices, and empty
  timeout/action/association defaults must normalize compatibly.
- Empty, logical, complex, nonfinite, matrix, negative, duplicate, decreasing, fractional-ID, zero-period,
  nonpositive-rate, zero-tick, unknown-choice, excessive-arity, oversized-event/PPS, derived-timeline,
  timestamp-precision, and fit-resolution inputs must reject before unsafe allocation.
- Bound model and scenario handles must survive module-path cleanup and a conflicting generic `model.m`.
- No cancellation or rejection may leave persistent state for the next clean call.

## Interpretation questions

1. Which observations separate initial offset from oscillator skew?
2. Why does one PPS edge fail to identify rate?
3. What does the edge provide, and what does its sequence/timestamp label provide?
4. Why is a missing sequence ID compatible with correct alignment but not with arrival-index pairing?
5. Why can the broken endpoint residuals be zero?
6. How does timestamp tick bound what the calculation can know?
7. Why is timeout equality different from a strictly late PPS gap?
8. Why does cancellation censor an observation without rolling back a clock?
9. Which results would require MATLAB runtime, rendered UI, receiver, bench, HIL, or field evidence?

## Teach-back

Give two sentences answering: “What inputs, observable effects, and failure modes matter when you align
Clocks with PPS and Timestamps?”

- Sentence one: connect offset, skew, timestamp tick, PPS phase, and trusted sequence/timestamp identity to
  affine correction.
- Sentence two: connect missing or wrong association, fit residuals, timeout/cancellation, and recovery to
  the evidence boundary.

Static source and independent simulated checks do not prove MATLAB-runtime behavior, rendered UI, MATLAB
numerical fidelity, PPS/GNSS hardware, oscillator stability, interrupt capture, PTP/NTP, bench, HIL, field,
RT1/RT2, Unreal, signing, deployment, staging, or production behavior.
