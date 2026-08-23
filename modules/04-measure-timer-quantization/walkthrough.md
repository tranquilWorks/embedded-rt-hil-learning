# Walkthrough: Measure Timer Quantization

1. Read the guiding question and connect each P03 event time to an edge offered to a finite timer.
2. Make one prediction only: decide whether repeated true 37 us intervals become only 30 us, only 40 us,
   or both when `q = 10 us`.
3. Run `experiment.m`. Inspect only the first baseline view and name the true and measured interval units.
4. Inspect the signed-error view next. Account for -7 us and +3 us as the difference between two endpoint
   flooring errors; do not call the pattern jitter.
5. Move one control: inspect the tick-period sweep while phase, edges, and width remain fixed. Explain the
   error staircase and the eight-bit wrap-period change.
6. Reset tick period to 10 us. Move the second control: inspect the phase sweep while duration, tick, and
   width remain fixed. Locate the one extra completed stop tick.
7. Read the mechanism before opening the next view: `k=floor((t+phi)/q)`, finite count `mod(k,2^B)`, and
   modular elapsed ticks under a less-than-one-modulus promise.
8. Open `interactive.m`. Move one control, describe one plot transition, then reset it before moving another.
9. Select the fixed 10 us/eight-bit wrap fixture. Confirm that the selector resets and locks phase at zero,
   then compare counts 255 to 2, the valid 30 us modular result, and the broken -2530 us signed result.
   Locate the later non-wrapping recovery pair.
10. Select the fixed full-range ambiguity fixture. Explain why equal finite counts cannot distinguish zero
    ticks from 256 ticks without overflow information, and why the later short pair is still valid.
11. Run `run_checks.m`, answer the interpretation questions, and give a two-sentence teach-back:
    mechanism first, resolution/range tradeoff and failure boundary second.

The calculations are deterministic and synthetic. They do not provide MATLAB-runtime evidence in an
unexecuted environment or measured timer, oscillator, MCU, bench, HIL, field, RT1/RT2, Unreal, signing,
deployment, or production behavior.
