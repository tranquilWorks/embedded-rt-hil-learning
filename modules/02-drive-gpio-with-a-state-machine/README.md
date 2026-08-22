# P02 — Drive GPIO with a State Machine

**Track:** Embedded, Real-Time, and Hardware-in-the-Loop Systems  
**Phase 1:** Microcontroller execution  
**Status:** implemented

## Guiding question

What inputs, observable effects, and failure modes matter when you drive GPIO with a State Machine?

## Computational mental model

A sampled button is not automatically a trustworthy command. The controller qualifies a press for
`N_d = max(1, ceil(debounce_ms / sample_period_ms))` consecutive samples before entering `ACTIVE`.
GPIO is high only in `ACTIVE` and `QUALIFY_RELEASE`. A cancellation or the maximum-on limit moves the
controller to safe-low `LOCKOUT`, where a held button cannot retrigger it.

The maximum-on request must be at least one sample period and is conservatively quantized as
`N_t = floor(max_on_ms / sample_period_ms)`. Therefore `N_t * sample_period_ms` never exceeds the
requested maximum.

The plotted GPIO is a deterministic simulated logic command, not a hardware measurement. It is not
a measured voltage, current, pin register, or hardware result.

## What the learner controls

- **Debounce time (ms):** trades response latency for rejection of contact bounce.
- **Maximum-on time (ms):** bounds how long a stuck request can keep the output high.
- **Input scenario and bounce time:** expose a normal press, a stuck-high request, and
  cancellation followed by recovery.

## Complete learning flow

1. Read the state/output rule and connect sampling to P01's timing model.
2. Run the deterministic baseline and inspect raw input, controller state, and GPIO separately.
3. Sweep debounce time while holding the input trace and maximum-on time fixed.
4. Reset, then sweep maximum-on time on one fixed stuck-high trace.
5. Explain each changed view from the consecutive-sample and timeout mechanisms.
6. Run the broken debounce-bypass case and identify input chatter at GPIO.
7. Run the numerical checks and give the requested teach-back.

## Files

- `p02_scenario.m` creates bounded deterministic input traces without random data or path ambiguity.
- `model.m` owns validation, state transitions, events, metrics, and the simulated GPIO output.
- `experiment.m` owns the baseline, labeled plots, two independent sweeps, and broken case.
- `interactive.m` owns the UI controls and complementary views.
- `lesson.m`, `lesson.md`, and `walkthrough.md` own the concept-first learner sequence.
- `checks.md` and `run_checks.m` own interpretation prompts and executable invariants.

Only base MATLAB operations are used. No support package, Stateflow, Simulink, or hardware API is
required.
