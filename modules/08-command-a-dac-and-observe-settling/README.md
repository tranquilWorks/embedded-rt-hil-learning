# P08 — Command a DAC and Observe Settling

**Track:** Embedded, Real-Time, and Hardware-in-the-Loop Systems  
**Phase 2:** Buses and acquisition  
**Status:** implemented

## Guiding question

What inputs, observable effects, and failure modes matter when you command a DAC and Observe Settling?

## Physical mental model

P07 showed that an ADC code is meaningful only when analog bandwidth, sample timing, rails, and quantization
are understood. P08 follows the signal path in the other direction. A digital DAC command first selects a
quantized target; an output latch holds that target; the analog output then needs finite time to approach it.
A successful command or matching register readback is therefore not proof that the pin has settled.

This fixture declares one ideal unipolar transfer convention:

```text
L        = 2^B
LSB      = V_ref/L
k        = clamp(round(V_request/LSB), 0, L-1)
V_target = k LSB
```

The largest code produces `V_ref-LSB`, not exactly `V_ref`. After an accepted update at `t_u`, the target is
held. For error magnitude `e=|V_target-y|`, a first-order output would obey `de/dt=-e/tau`; this lesson caps
the initial magnitude of slope at a declared slew rate `S`. A large step can therefore begin as a linear ramp
and transition continuously to an exponential tail. Settling means the output enters and remains inside the
inclusive band `|y-V_target| <= V_tol`, not that one plotted sample merely touches the band.

## What the learner controls

- **Requested and initial voltage (V):** choose the digital target and step magnitude before quantization.
- **DAC bits and reference (V):** set code count, LSB size, full-scale code voltage, and quantization error.
- **Update latency (us):** delays when the active output code changes after the command is issued.
- **Output time constant (us):** moves the exponential pole and its settling tail.
- **Slew rate (V/ms):** caps large-signal slope independently of the quantized target.
- **Tolerance (mV):** defines the stated entry-and-remain requirement.
- **Scenario:** selects the normal response, an update that is recorded but not latched, a command deadline,
  a short observation, or a slow output stage.

## Complete learning flow

1. Connect P07 ADC-code meaning to the inverse DAC path and predict whether a recorded code proves settling.
2. Inspect the deterministic 0.5 V to 2.5 V request, its 12-bit codes, held target, analog response, error,
   and inclusive 10 mV tolerance.
3. Sweep only `tau=[100 250 500 1000 2000] us` and explain the changed exponential tail.
4. Reset `tau`, then sweep only `S=[Inf 8000 4000 2000 1000] V/s` and explain the large-signal limit.
5. Explain both views with the hybrid ramp-plus-exponential equations, then distinguish analytic settling from
   the first sampled stay on a 5 us observation grid.
6. Break the latch assumption: retain the recorded digital code while the active output code and voltage stay
   at the initial level.
7. Compare an exact command-deadline boundary with a rejected update, reset inputs, run checks, and teach back.

## Boundaries and dependencies

This is a deterministic, single-step, ideal-DAC and synthetic output-stage calculation using base MATLAB
arithmetic, plots, and UI controls. It uses no Control System Toolbox, Simulink, device support package, DAC
driver, bus peripheral, oscilloscope, or physical converter. The command is assumed to be offered at `t=0`;
P05/P06 framing, bus arbitration, device-specific register protocol, and synchronization are outside the
fixture. P07 explains why a real ADC/oscilloscope observation also needs adequate bandwidth, sampling, and
input fidelity. A reference/bit-depth combination whose LSB underflows to zero in double precision is rejected
before quantization rather than being exposed as a valid code result.

The fixture omits glitch impulse, monotonicity, INL/DNL, missing codes, reference noise and drift, output
amplifier/op-amp impedance and current limit, capacitive-load stability, overshoot/ringing, thermal effects, power-up behavior,
clock uncertainty, channel crosstalk, and device-specific double buffering. Its deadline is an analytical
policy: it does not sleep, stop a bus request, cancel a driver, or reverse an already latched output. Removing
fault and deadline inputs is state-free computational rollback and clean retry, not reversal of external side
effects.

The outputs are not a MATLAB-runtime result, converter characterization, standards-conformance result,
hardware measurement, bench result, HIL result, field result, or production result.

## Files

- `p08_scenario.m` owns bounded deterministic command and diagnostic fixtures.
- `model.m` owns validation, quantization, latch/deadline semantics, hybrid response, and settling metrics.
- `experiment.m` owns the baseline, labeled views, two isolated sweeps, and deliberately broken case.
- `interactive.m` owns immediate controls and complementary target/response and error/tolerance views.
- `lesson.m`, `lesson.md`, and `walkthrough.md` own the mechanism-first learner sequence.
- `checks.md` and `run_checks.m` own interpretation prompts and executable invariants.
