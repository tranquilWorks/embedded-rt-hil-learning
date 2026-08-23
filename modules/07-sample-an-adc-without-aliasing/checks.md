# Checks: Sample an ADC Without Aliasing

## Observation check

On the baseline time view, identify the physical input, analog-filter output, sample instants, and ADC
code-center values. Then use the frequency view to explain why 180 Hz remains 180 Hz. Which operation occurs
before sampling, and why could the same operation performed on codes afterward not prevent aliasing?

## Independent calculations

- Calculate `f_N=1000/2=500 Hz`, strict margin `500-180=320 Hz`, and 5.56 samples per 180 Hz cycle.
- Evaluate `|H(180)|=1/sqrt(1+(180/400)^2)` and `angle H(180)=-atan(180/400)`.
- Calculate `4096` levels, `LSB=3.3/4096 V`, and raw traffic `1000*12=12000 bit/s`.
- Derive signed folds `[180 180 180 -120 -70] Hz` for sample rates
  `[1000 600 400 300 250] sample/s`.
- At 1 ksample/s, derive apparent frequencies `[50 180 350 500 350 180 150] Hz` for physical inputs
  `[50 180 350 500 650 820 1150] Hz`.

## Limiting cases and compatibility

- Why does DC pass the modeled first-order front end with gain one and zero phase?
- What startup transient or initial-condition behavior is excluded by the steady-state component response?
- Why is `f_in=f_s/2` unsafe even when an apparent-frequency plot reports `f_s/2`? Compare phase-zero and
  phase-`pi/2` cosines at that boundary.
- Why do `f`, `f+k f_s`, and the signed positive/negative folds need explicit phase handling?
- Why do supported integer numeric classes and scalar-string fault modes preserve the normalized result?
- Which conclusions change for a multi-pole analog filter, non-sinusoidal source, or nonuniform sample clock?

## Positive, negative, malformed, and resource-bound cases

Confirm exact `t_n=n/f_s`, bounded code range, endpoint behavior, no baseline clipping, half-LSB in-range
quantization error, and payload rate `f_s B`. Then reject wrong arity; nonnumeric, nonfinite, complex, negative,
fractional, or out-of-range frequency, rate, count, amplitude, offset, phase, cutoff, ADC bits, reference,
deadline, fault schema, and scenario values. Reject sample or dense-reference requests beyond their explicit
bounds before allocation. A rejected call must not affect the next valid call.

## Broken assumption, clipping, isolation, rollback, and recovery

Bypass the analog front end and sample separate 180 Hz and 820 Hz, zero-phase cosines at 1 ksample/s. Require
their dense physical traces to differ while every canonical sample and ADC code matches. Repeat across several
ADC resolutions: more voltage codes must not identify the source frequency. Restore the analog front end and
explain that attenuation reduces above-band amplitude but does not make a component strictly Nyquist-safe.

Drive the ideal ADC past both rails and require bounded endpoint codes. This is clipping, not aliasing. Remove
the fault and deadline and require exact `isequaln` rollback to the baseline. A later clean invocation is
state-free recovery and isolation; it does not undo converter or sensor side effects in a real device.

## Timeout and cancellation

The modeled acquisition budget is `N/f_s`: 51 samples at 1 ksample/s consume 51 ms, while their first-to-last
observation span is 50 ms. Accept a deadline exactly at 51 ms, reject one representable step earlier and a zero
deadline, and expose no committed codes for a rejected result. Re-invocation with an infinite deadline must
recover the exact baseline.

This bounded calculation has no asynchronous operation, conversion request, driver wait, persisted partial
capture, or cancellation API. Deadline classification does not prove that hardware stopped conversions,
discarded DMA data, reset a peripheral, or canceled a bus transaction.

## Interpretation and transfer

Choose one real sensor acquisition requirement. State its desired band and unwanted source content, sample
rate and guard band, analog filter transition and required stop-band attenuation, ADC input rails and voltage
resolution, aperture/jitter/settling and reference limits, raw and framed transport capacity, buffer policy,
deadline/drop behavior, retry rule, and application commit rule. Keep those physical and operational inputs
separate from what this single-tone ideal calculation proves.

## Teach-back

In two sentences, answer the guiding question. Sentence one must connect analog bandwidth and filtering,
`t_n=n/f_s`, the strict Nyquist boundary, signed folding, voltage rails, quantization, and `f_s B` transport.
Sentence two must distinguish exact alias ambiguity, Nyquist phase loss, clipping, deterministic deadline,
cancellation boundary, rollback, and clean retry without relying on MATLAB syntax.

## Executable check

Run:

```matlab
run_checks
```

All assertions must pass before personal learner completion is recorded.
