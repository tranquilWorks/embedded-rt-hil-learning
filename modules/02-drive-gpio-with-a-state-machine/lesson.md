# Lesson: Drive GPIO with a State Machine

## Guiding question

What inputs, observable effects, and failure modes matter when you drive GPIO with a State Machine?

## Connection to P01

P01 made completion time observable: a correct calculation can still arrive after its deadline. P02
uses that sampled-time view at an I/O boundary. A controller sees one button level per sample, must
decide whether the level is credible, and must make the safe output transition on time.

## Mental model

Treat the raw button, cancellation request, sample period, debounce time, and maximum-on time as
inputs. The state is the controller's memory. The simulated GPIO command is a Moore output: it is
high only in `ACTIVE` and `QUALIFY_RELEASE`, so a noisy sample cannot write the output directly.

The requested times become integer sample counts:

```text
N_d = max(1, ceil(debounce_ms / sample_period_ms))
N_t = floor(max_on_ms / sample_period_ms), with max_on_ms >= sample_period_ms
```

The quantization directions are observable. A 4.1 ms debounce request at a 1 ms sample period needs
five agreeing samples: qualification cannot finish early. A 17.2 ms maximum-on request permits 17
high samples: energization cannot exceed the requested limit. A sub-sample maximum is rejected
because this sampled model cannot honestly enforce it.

## One prediction before the baseline

If debounce time increases while the same bouncing input is replayed, which changes first: the raw
input trace, the accepted state transition, or the GPIO trace?

## Baseline observation

Read the three views in causal order: raw button and cancel, state, then GPIO. The raw contact can
alternate without output chatter because `QUALIFY_PRESS` and `QUALIFY_RELEASE` count consecutive
samples. The output changes only when qualification crosses a state boundary.

## Lever 1: debounce time

Increasing debounce time increases `N_d`. Short reversals are rejected, but the first valid output
transition moves later. Reducing debounce to zero still quantizes to one sample; it does not disable
sampling, but it does let every sampled reversal cross the state boundary.

## Lever 2: maximum-on time

Reset debounce and replay the fixed stuck-high trace. Increasing maximum-on time changes `N_t` and
the longest high run, but not the input or qualification rule. After exactly `N_t` high samples, the
next sample enters safe-low `LOCKOUT`. A held-high request cannot retrigger the output.

## Cancellation and recovery

Cancel has priority over all other transitions and makes GPIO low in the same simulated sample. The
controller stays in `LOCKOUT` until it observes `N_d` consecutive low samples. That qualified release
is the recovery boundary: a later qualified press can drive GPIO again.

## Deliberately broken assumption

The broken case sets debounce to zero and assumes every sampled button level is a clean user command.
The symptom is extra GPIO edges during deterministic contact bounce. The mechanism is not mysterious:
`N_d = 1`, so every one-sample reversal can enter or leave an active state.

## Common mistakes

- Debounce is not a delay inserted after a press; it is an evidence requirement on consecutive samples.
- A timeout makes the output safe but does not make a held input trustworthy again.
- A commanded GPIO logic level is not proof of pin voltage, current, load motion, or hardware timing.
- Cancellation and recovery are different transitions: cancel enters lockout; qualified release re-arms.

## Completion standard

Explain which inputs cross which state boundaries, predict the output and timing units for both levers,
diagnose the broken assumption, pass `run_checks.m`, and give the teach-back in `checks.md`.
