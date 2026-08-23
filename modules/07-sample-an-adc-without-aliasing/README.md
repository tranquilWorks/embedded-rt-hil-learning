# P07 — Sample an ADC Without Aliasing

**Track:** Embedded, Real-Time, and Hardware-in-the-Loop Systems  
**Phase 2:** Buses and acquisition  
**Status:** implemented

## Guiding question

What inputs, observable effects, and failure modes matter when you sample an ADC Without Aliasing?

## Physical mental model

P06 showed that completed bus clocks do not prove returned bytes are meaningful. P07 moves upstream: even
perfectly transferred ADC codes cannot restore an analog frequency that sampling already folded.

The deterministic source is one cosine with physical frequency `f_in`, peak amplitude `A`, offset `V_0`,
and phase `phi`. A transparent first-order analog low-pass acts before the ideal ADC:

```text
x(t)       = V_0 + A cos(2 pi f_in t + phi)
H(f)       = 1 / (1 + j f/f_c)
f_fold     = mod(f_in + f_s/2, f_s) - f_s/2
f_apparent = abs(f_fold).
```

The strict fixture rule is `f_in < f_s/2`. Equality is a phase-sensitive Nyquist boundary, not a safe
design. A real design needs the entire post-front-end bandwidth below that boundary with guard band and
enough analog attenuation above it; the modeled first-order response only attenuates a component and never
makes an above-Nyquist component mathematically safe.

The ideal unipolar ADC has `L=2^B` levels over `[0,V_ref]`, `LSB=V_ref/L`, floor quantization, endpoint
saturation, and a code-center voltage estimate. Quantization, clipping, and aliasing are separate failure
mechanisms. Raw code traffic is `f_s B` bit/s before any register framing, so the P06 bus budget still
matters after the sampling choice is correct.

## What the learner controls

- **Physical input frequency (Hz):** moves a source component toward and through repeated Nyquist zones.
- **Sample rate (sample/s):** moves the Nyquist boundary, sample instants, acquisition time, and raw bit rate.
- **Analog anti-alias cutoff (Hz):** changes source amplitude and phase before sampling, not after it.
- **ADC bits:** changes voltage resolution and data rate without changing the fold frequency.
- **Amplitude, offset, and sample count:** expose input rails, observation span, and resource cost.
- **Scenario:** selects the filtered baseline, exact alias ambiguity, Nyquist phase loss, rail clipping, or a
  deterministic acquisition deadline.

## Complete learning flow

1. Connect P06 byte transport to the meaning of the codes before they reach the bus.
2. Predict whether 180 Hz is identifiable at 1 ksample/s before viewing the baseline.
3. Inspect the physical/filtered trace, sample instants, ADC codes, and analytical fold separately.
4. Sweep only sample rate through `[1000 600 400 300 250]` sample/s and explain the changed boundary.
5. Reset to 1 ksample/s, then sweep only physical frequency through Nyquist zones.
6. Explain both changes from the fold equation and the pre-sampling filter response.
7. Bypass the front end and compare 180 Hz with 820 Hz at 1 ksample/s: their analog traces differ while
   every sample and code matches.
8. Distinguish alias ambiguity from Nyquist phase loss, voltage clipping, and a rejected acquisition result.
9. Reset inputs, run checks, and give the two-sentence teach-back.

## Boundaries and dependencies

This is a synthetic single-tone, steady-state first-order-front-end, ideal-ADC calculation using base MATLAB
arithmetic, plots, and UI controls. Filter startup transient and initial state are not modeled. It uses no
Signal Processing Toolbox, `fft`, digital resampling, Simulink, Data
Acquisition Toolbox, device support package, ADC driver, sensor, sample-and-hold, or bus peripheral. A
digital operation after sampling is never presented as the analog anti-alias filter.

The fixture omits filter order and tolerances beyond one declared pole, aperture and clock jitter, sample-and-
hold settling, source impedance, thermal noise, INL/DNL, missing codes, reference error, metastability,
electrical rails, DMA buffering, and framed bus overhead. Its analytical deadline does not sleep, stop a
converter, cancel a driver, or undo external side effects. Re-invocation with clean inputs is state-free
rollback and recovery. The outputs are not a hardware measurement, converter characterization, bench result,
HIL result, field result, or production result.

## Files

- `p07_scenario.m` owns bounded deterministic signal and diagnostic fixtures.
- `model.m` owns validation, analog response, signed folding, sample times, ideal codes, deadline, and metrics.
- `experiment.m` owns the deterministic baseline, labeled views, two isolated sweeps, and broken case.
- `interactive.m` owns immediate controls and complementary time/frequency views.
- `lesson.m`, `lesson.md`, and `walkthrough.md` own the mechanism-first learner sequence.
- `checks.md` and `run_checks.m` own interpretation prompts and executable invariants.
