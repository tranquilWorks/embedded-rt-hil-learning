# Lesson: Measure Timer Quantization

## Guiding question

What inputs, observable effects, and failure modes matter when you measure Timer Quantization?

## Connection to P03

P03 compared mechanisms that notice and service request edges. Its event arrival, polling detection,
and interrupt service times were ideal real-valued times. P04 holds the edge meaning fixed and changes
the representation: a finite timer must turn each edge time into an integer counter value. This separates
observation latency from timestamp resolution.

## Mental model

Let `q` be the timer tick period in microseconds, `phi` the timer phase in `[0, q)`, and `B` the counter
width. A capture latches the number of completed ticks, first as an unwrapped teaching quantity and then
as the finite register value:

```text
k(t) = floor((t + phi) / q)
c(t) = mod(k(t), 2^B).
```

For a start edge at `t_0` and stop edge at `t_1`, software should subtract finite counts modulo the
counter size:

```text
delta_k = mod(c(t_1) - c(t_0), 2^B)
T_hat = q * delta_k.
```

That result is valid only under an external range promise:

```text
k(t_1) - k(t_0) < 2^B.
```

The model knows the unwrapped ticks and can enforce the promise. A real device needs an overflow count or
another source of range information. With unknown phase, a duration limit no greater than `(2^B - 1)q`
guarantees fewer than `2^B` captured tick advances; merely requiring duration below the wrap period `2^B q`
does not. Exactly one full cycle can produce equal start and stop registers, indistinguishable from zero
elapsed ticks without that context.

The quantized endpoint time is `q*k(t) - phi`. For an ideal floor, each endpoint error lies from almost
`-q` through `0`. The implementation normalizes a value within `tau` ticks of a mathematical boundary,
so the retained numeric bound is `(-q, tau*q]`. The interval error is the stop endpoint error minus the
start endpoint error:

```text
epsilon_T = T_hat - (t_1 - t_0) = epsilon_stop - epsilon_start
abs(epsilon_T) < q                 for a valid measurement.
```

This explains why floor-quantized interval error can have either sign. Quantization is deterministic for
fixed inputs and phase; it is not random jitter. Tick resolution also says nothing about oscillator
tolerance or drift.

Floating division can place a mathematically exact decimal boundary a few representation units to one
side. The model uses one pair-local scale-aware tolerance shared by that pair's start and stop, snaps only
near an integer tick before applying `floor`, and bounds absolute tick indices. This preserves one uniform
tick grid across an exponent boundary without allowing an unrelated far-future pair to change the result.

## One prediction before the baseline

With `q = 10 us`, can repeated true `37 us` intervals all produce the same integer-tick measurement, or
will edge alignment make both `30 us` and `40 us` appear?

## Baseline observation

The true interval stays at 37 us while the fixture's start edges visit different positions in the 10 us
tick grid. Each captured delta is three or four completed ticks, so the measurements are 30 or 40 us and
the errors are -7 or +3 us. Read the interval view first and the signed error view second.

The strict error bound is one tick, not half a tick, because two independently floored endpoints are
subtracted. An interval that is an exact integer number of ticks measures exactly at every phase, provided
the counter-range promise still holds.

## Lever 1: tick period

Reset phase to zero and keep the event fixture and eight-bit width fixed. Sweeping `q` through
`[1 2 5 10 20] us` changes the size of the quantization staircase. Finer ticks resolve the 37 us fixture
more closely; coarser ticks increase the wrap period `2^B q` at fixed width. This is a resolution/range
tradeoff, not an accuracy calibration result.

## Lever 2: timer phase

Reset `q` to 10 us, use one 37 us interval, and sweep `phi` from 0 through 9 us. The true duration, tick
period, and counter width do not change. The stop edge eventually crosses one extra tick boundary, so the
measurement steps from 30 to 40 us. The phase is controlled alignment, not simulated clock noise.

## Deliberately broken assumption and recovery

The diagnostic selector resets and pins `q = 10 us`, `T = 37 us`, `phi = 0`, and `B = 8` so prior lever
state cannot change the named fixture. The broken view treats wrapped register values like ordinary signed
integers. One pair captures count 255 then count 2. Raw `stop - start` reports -253 ticks, or -2530 us,
even though the modular three-tick result is 30 us. The next non-wrapping pair produces a positive raw
result and demonstrates local recovery; it does not make the broken rule safe.

Modular subtraction repairs a single range-valid wrap. It cannot repair a measurement whose unwrapped
captured delta reaches 256 ticks on an eight-bit counter. That case is marked range-ambiguous and the
primary interval is `NaN`, while the zero modular residue remains visible only as a diagnostic alias.

## Common mistakes

- A finer timer has better resolution, not automatically better oscillator accuracy.
- Quantization error is deterministic at fixed phase and is not the same as execution jitter.
- More counter bits extend range but do not change `q`.
- A counter wrap is not automatically a failure; modular subtraction is valid under the range promise.
- Modular subtraction cannot infer one or more unseen full counter cycles.
- Input synchronization, metastability, capture latency, register tearing, overflow races, clock drift,
  ISR latency, and device-specific prescaler encoding are outside this model.

## Completion standard

Explain the capture equation, predict both lever transitions, distinguish resolution from range and
accuracy, diagnose naive rollover subtraction, identify full-wrap ambiguity, pass `run_checks.m`, and
give the teach-back in `checks.md`.
