# Lesson: Sample an ADC Without Aliasing

## Guiding question

What inputs, observable effects, and failure modes matter when you sample an ADC Without Aliasing?

## Connection to P06

P06 separated transmitted clock cells, protocol-visible responses, and payload meaning. P07 keeps that
discipline and moves one boundary upstream. Correctly transported ADC codes can still describe the wrong
apparent frequency because distinct analog inputs became identical at the sample instants.
Transport capacity still matters—an unpacked `B`-bit stream offers `f_s B` bit/s before framing—but a faster
SPI or I2C clock cannot reconstruct analog information lost before conversion.

## One physical source, front end, sample clock, and ADC

The baseline source is a 180 Hz cosine with 1 V peak amplitude, 1.65 V offset, and zero phase. A declared
first-order analog low-pass with 400 Hz cutoff acts before 51 ideal sample conversions at 1 ksample/s:

```text
x(t) = V_0 + A cos(2 pi f_in t + phi)
H(f) = 1 / (1 + j f/f_c)
|H|  = 1 / sqrt(1 + (f/f_c)^2)
arg H = -atan(f/f_c)
t_n  = n/f_s,  n = 0, 1, ..., N-1.
```

This steady-state component response is applied in the analog calculation; filter startup transient and
initial state are not modeled. It is not a digital filter applied to codes. A post-sampling filter can remove
an unwanted apparent component only when that component remains distinguishable; it cannot tell which
physical Nyquist zone produced an already folded sinusoid.

The ideal unipolar ADC uses `L=2^B` codes over `[0,V_ref]` with this explicit fixture convention:

```text
LSB        = V_ref/L
v_clip     = min(max(v_sample, 0), V_ref)
code       = min(floor(v_clip/LSB), L-1)
v_center   = (code + 1/2) LSB.
```

For an in-range input, the code-center estimate is within half an LSB of the clipped sample. That bound says
nothing about aliasing. Clipping is the separate loss caused by an input below 0 V or above `V_ref`.

## Sampling and signed folding

Uniform samples cannot distinguish frequencies separated by integer multiples of the sample rate. This lesson
keeps the orientation visible with a signed fold and uses its magnitude for the apparent positive frequency:

```text
f_N        = f_s/2
f_fold     = mod(f_in + f_s/2, f_s) - f_s/2
f_apparent = abs(f_fold).
```

If the signed fold is negative, the apparent cosine phase changes sign. At exact Nyquist, positive and
negative orientation are indistinguishable and the waveform is phase-sensitive, so the fixture calls a source
safe only when `f_in < f_s/2`. Equality is deliberately unsafe. A real design applies this strict condition to
the entire post-front-end bandwidth and adds guard band for a realizable analog transition region, clock error,
and uncertain source content.

A first-order low-pass never reaches zero amplitude. It can reduce an above-Nyquist component before sampling,
but the model still reports that component as an alias risk. Practical acceptance therefore needs a stated
stop-band amplitude or error budget in addition to a nominal cutoff.

## One prediction before the baseline

At `f_in=180 Hz` and `f_s=1000 sample/s`, predict the Nyquist boundary, strict margin, apparent frequency,
and raw 12-bit payload rate. Which of those quantities can ADC bit depth change?

## Baseline observation

The Nyquist boundary is 500 Hz, so the strict margin is `500-180=320 Hz` and the signed fold is +180 Hz.
The first-order front end has gain `1/sqrt(1+(180/400)^2)` and phase `-atan(180/400)`: it changes analog
amplitude and phase before sampling without changing the component's frequency. The 12-bit, 3.3 V fixture has
4096 levels and an LSB of `3.3/4096 V`, about 0.806 mV. No sample clips.

Fifty-one sample conversions occur at `n/1000` seconds from 0 through 50 ms. The first-to-last observation
span is 50 ms; the declared analytical acquisition budget is `N/f_s=51 ms`. Raw unpacked traffic is
`1000*12=12000 bit/s`. P06 framing and transaction overhead would be additional requirements for a device
that transports these codes.

## Lever 1: sample rate

Hold the physical 180 Hz source, analog cutoff, amplitude, phase, ADC bits, and reference fixed. Sweep
`f_s=[1000 600 400 300 250] sample/s`. The signed folds are `[180 180 180 -120 -70] Hz`; displayed magnitudes
are `[180 180 180 120 70] Hz`. Strict Nyquist margins are `[320 120 20 -30 -55] Hz`, so only the first three
cases are safe for this one component.

The analog gain and phase do not change because the physical source and front end did not change. Sample
instants, acquisition time, Nyquist boundary, and raw payload rate do change. Lower data traffic is not a free
optimization when it moves the boundary through real source content.

## Lever 2: physical input frequency

Reset the sample rate to 1 ksample/s and keep the sample count, front end, ADC, amplitude, offset, and phase
fixed. Sweep physical inputs `[50 180 350 500 650 820 1150] Hz`. Their apparent magnitudes are
`[50 180 350 500 350 180 150] Hz`.

Two effects are shown separately. The first-order analog gain decreases as physical frequency rises. The
folding pattern begins at the strict Nyquist boundary regardless of that remaining amplitude. At 500 Hz the
half-open formula reports signed -500 Hz, but its sign is not physically identifiable: one sample per half
cycle cannot preserve arbitrary phase.

## Deliberately broken assumption: a smooth sequence identifies its source

Bypass the analog front end and compare two separate zero-phase inputs at 1 ksample/s:

```text
cos(2 pi 820 n/1000)
  = cos(2 pi n - 2 pi 180 n/1000)
  = cos(2 pi 180 n/1000).
```

The dense 180 Hz and 820 Hz analog traces are different, but every sample voltage and ADC code is identical.
The high input has signed fold -180 Hz; cosine's even symmetry makes its zero-phase samples match the +180 Hz
input. Increasing ADC resolution from 4 through 16 bits still gives matching code sequences. More bits reduce
voltage quantization; they do not create missing time samples. A faster bus moves the ambiguous codes sooner;
it does not identify the physical source.

An actual analog filter is part of preventing this case. Its job is to bound the signal presented to the
sample-and-hold before conversion. The modeled pole shows attenuation and phase transparently, but selecting
a real filter requires source spectrum, allowed in-band distortion, transition width, stop-band attenuation,
component tolerance, impedance, settling, and ADC drive requirements.

## Nyquist phase loss, clipping, deadline, rollback, and recovery

At exactly 500 Hz and 1 ksample/s, a zero-phase cosine alternates between extrema. The same cosine with phase
`pi/2` samples at its offset and loses its amplitude in the ideal sample sequence. This is why equality is not
a safe limiting design.

The clipping diagnostic raises the peak amplitude beyond both 0 V and 3.3 V rails. Endpoint codes remain
bounded, but their repeated saturation is amplitude loss rather than frequency folding. A system can suffer
clipping and aliasing independently or at the same time.

The deterministic deadline compares `N/f_s` with a caller policy. An exact 51 ms boundary passes; one
representable step earlier, the retained 50 ms policy fixture, and zero reject the committed result. The pure
model still calculates offered samples so the reason stays inspectable, but exposes no committed codes. It
does not claim that a real ADC, DMA engine, or bus driver stopped at that instant.

Removing the bypass and deadline inputs exactly reproduces the clean baseline with `isequaln`. That is
state-free rollback and clean retry recovery, not reversal of sensor, converter, buffer, or bus side effects.
A malformed call cannot contaminate the next invocation because the model owns no persistent state.

There is no asynchronous wait, driver request, partial persisted capture, or cancellation API, so cancellation
is not applicable. A real system must separately define trigger cancellation, DMA teardown, stale-buffer
handling, overrun policy, and whether partially acquired data can be committed.

## Common mistakes

- `f_s=2 f_max` is a fragile equality, not a guard-banded design rule.
- Frequency content above Nyquist can fold into a smooth, plausible low-frequency sequence.
- An analog anti-alias filter acts before sampling; a digital filter cannot undo ambiguity already created.
- A finite-order analog filter attenuates stop-band content rather than making it mathematically disappear.
- More ADC bits improve voltage resolution, not time resolution or alias discrimination.
- Clipping, quantization, and aliasing are distinct even though all can corrupt code meaning.
- Sample observation span `(N-1)/f_s` and the declared acquisition budget `N/f_s` answer different questions.
- Raw `f_s B` is not total SPI/I2C traffic; framing, command, response, idle, and buffering costs remain.
- A single-tone ideal model does not establish real source bandwidth, converter fidelity, or hardware timing.

## Completion standard

Explain the strict sampling condition, signed fold, analog front-end placement, and ADC code convention;
predict both lever effects; distinguish the exact alias pair, Nyquist phase loss, clipping, and deadline;
state the cancellation and physical-evidence boundaries; pass `run_checks.m`; and give the teach-back in
`checks.md` without relying on MATLAB syntax.
