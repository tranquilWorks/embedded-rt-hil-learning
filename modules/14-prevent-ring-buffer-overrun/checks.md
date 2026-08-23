# P14 checks: Prevent Ring-Buffer Overrun

Run `run_module_checks('P14')` in MATLAB, or run `run_checks` while this module folder is first on the MATLAB
path. The executable checks own deterministic calculations; these prompts own interpretation and teach-back.

## Independent baseline calculations

Without reading model output first, calculate:

1. Producer rate for `T_p=50 us`: `1e6/50 = 20,000 sample/s`.
2. Consumer capacity for `B=4`, `T_c=200 us`: `4e6/200 = 20,000 sample/s`.
3. Offered load: `rho=T_c/(B T_p)=1`.
4. Records ready before the first `200 us` consumer visit: IDs 1–4.
5. With consumer-before-producer ordering at `200 us`, occupancy after record five: one sample.
6. Baseline required capacity and peak: four samples.
7. Residence ages per group: `[200 150 100 50] us`; minimum/mean/maximum `50/125/200 us`.
8. Final drain: `1600 us`.

The model must repeat exactly, consume IDs `1:32`, preserve source values, finish empty, and report zero
classification residual.

## Sweep invariants

### Capacity only

For `C=[1 2 3 4 6 8]`, expect:

- loss `[24 16 8 0 0 0]` records;
- peak occupancy `[1 2 3 4 4 4]` samples;
- consumed count `[8 16 24 32 32 32]` records;
- fixed timing, quota, policy, and `rho=1`.

Explain why capacity four is a threshold for this phase, while capacity eight changes no delivered ID.

### Reset, then consumer quota only

For `B=[1 2 3 4 5 8]`, expect:

- offered load `[400 200 133.333... 100 80 50]%`;
- no-loss finite-trace required capacity `[25 18 11 4 4 4]` samples;
- configured-ring peak `[8 8 8 4 4 4]` samples;
- loss `[17 10 3 0 0 0]` records;
- drain `[3000 2200 2000 1600 1600 1600] us`.

Explain why clipped occupancy is not the same metric as no-loss required capacity.

## Broken-case and policy checks

With `C=4`, `B=1`, and overwrite-oldest:

- all 32 incoming writes are accepted;
- occupancy always remains within `[0,4]`;
- consumed IDs are `[1 5 9 13 17 21 25 29 30 31 32]`;
- overwritten IDs are `[2 3 4 6 7 8 10 11 12 14 15 16 18 19 20 22 23 24 26 27 28]`;
- authoritative loss is 21 records.

State why “bounded occupancy and no rejected incoming write” is a broken health criterion. Compare the
survivors with drop-newest. Then verify that throttleable backpressure consumes `1:32`, loses nothing, stalls
27 producer actions for `4050 us`, makes the final producer decision at `5600 us`, and drains at `6400 us`.

## Timeout, cancellation, rollback, and recovery

- A drain timeout of `50 us` must pass because the final consumer event at the deadline runs first.
- At `49 us`, continue-waiting must record timeout and still consume all 32 records.
- At `49 us`, cancel-consumer must retain pending IDs `29:32`, consume `1:28`, and report zero loss.
- Re-running clean baseline input after overload, overwrite, backpressure, timeout, cancellation, malformed
  input, and resource rejection must reproduce the exact baseline.

Explain why pending is not loss and why a pure-function reset is not peripheral, driver, plant, or
transactional rollback.

## Limiting, compatibility, isolation, and resource checks

- Capacity one, quota one, equal `50 us` periods, and consumer-before-producer ties must remain loss-free.
- Equal fractional `0.1 us` periods with a `0.2 us` consumer start and capacity two must preserve anchored
  ties, consume IDs `1:7`, and report no full encounter or loss.
- Filling `C` slots is full but is not itself overrun; the next full write triggers policy.
- Capacity at least the finite source count with delayed consumption must retain every record.
- Duplicate sample values must not confuse source-ID accounting.
- Row/column vectors, integer numeric classes through `flintmax`, scalar strings, and empty defaults must
  normalize compatibly.
- Callback-bound model and scenario handles must survive module-path cleanup and a conflicting generic model.
- Empty, logical, complex, nonfinite, matrix, precision-losing, zero-period, negative-time, fractional-count,
  unknown-policy/action, excessive-arity, oversized-source/capacity, derived-horizon, event, and timestamp-
  precision inputs must reject before unsafe allocation.
- No rejected or canceled call may contaminate the next clean call.

## Interpretation questions

1. What do `T_p`, `T_c`, `B`, `C`, start phase, and equal-time ordering each control?
2. Which metric separates a full encounter from actual data loss?
3. Why can head equal tail at both full and empty?
4. Why does `rho<=1` not directly determine required finite capacity?
5. Which data does drop-newest preserve, and which data does overwrite-oldest preserve?
6. What contract must exist before backpressure is a credible prevention mechanism?
7. Why must cancellation report pending records separately from loss?
8. Which observations would require MATLAB runtime, real concurrency, bench, or HIL evidence?

## Teach-back

Give two sentences answering: “What inputs, observable effects, and failure modes matter when you prevent
Ring-Buffer Overrun?”

- Sentence one: connect producer/consumer timing and quota, usable capacity, phase, and event ordering to
  occupancy and long-run load.
- Sentence two: use record identity to distinguish prevention from drop, overwrite, backpressure, timeout,
  and cancellation.

Passing source and numerical checks does not record learner completion. A short teach-back remains the manual
gate. Static and independent simulated evidence is not MATLAB-runtime, rendered-UI, numerical-fidelity,
atomicity, DMA, hardware, bench, HIL, field, or production validation.
