# Checks: Drive GPIO with a State Machine

## Observation check

On the baseline plots, which changes first—raw button, state, or GPIO—and why does GPIO remain low in
`QUALIFY_PRESS`?

## Independent calculation

For a 1 ms sample period, 4.1 ms debounce request, and 17.2 ms maximum-on request, calculate `N_d`,
`N_t`, and both quantized durations without reading model output. Explain why debounce uses ceiling
so qualification cannot finish early, while maximum-on uses floor so energization cannot exceed its
requested bound.

## Limiting cases

- What does debounce equal to zero mean after sample quantization?
- What happens to a pulse shorter than `N_d` samples?
- How many high samples are permitted when `N_t = 1`?
- Why is a maximum-on request shorter than one sample period rejected?
- Why can a held-high input not retrigger from `LOCKOUT`?

## Cancellation, rollback, and recovery

Identify the sample where cancel forces safe-low output. Then identify the qualified release that
re-arms `IDLE` and the later accepted press that proves recovery. This safe-state transition is the
domain rollback; P02 has no persistent-data migration or transaction to reverse.

## Broken-case check

The broken case bypasses multi-sample qualification. Name the violated clean-input assumption, the
extra-edge symptom, and the exact state-transition mechanism. Do not answer only “the button bounces.”

## Interpretation and transfer

Explain why the state plot and GPIO plot are complementary rather than redundant. Then name one real
output whose maximum energized time should be bounded, while keeping simulated logic distinct from
claims about that hardware.

## Teach-back

In two sentences, answer the guiding question. Sentence one must connect sampled inputs, qualification,
state, and GPIO. Sentence two must connect timeout or cancellation, lockout, qualified release, and
recovery without relying on MATLAB syntax.

## Executable check

Run:

```matlab
run_checks
```

All assertions must pass before personal learner completion is recorded.
