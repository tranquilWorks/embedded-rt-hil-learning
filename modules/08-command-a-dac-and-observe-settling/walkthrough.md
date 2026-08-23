# Walkthrough: Command a DAC and Observe Settling

1. Read the guiding question and connect P07's analog-to-code path to P08's code-to-target path. A valid code
   at either boundary is not by itself evidence about the physical voltage.
2. Make one prediction only: for a 0.5 V to 2.5 V request, decide whether the 100 us code update or 10 mV
   analog settling happens first.
3. Run `experiment.m`. Inspect only the baseline target/response view. Identify requested voltage, initial and
   command codes, the zero-order-held target, update time, continuous output, and voltage units.
4. Inspect the error view next. Identify the inclusive 10 mV band, analytic settle event, and first 5 us-grid
   sample that enters and stays. Explain why their times differ.
5. Move one lever: inspect the time-constant sweep while code, reference, latency, slew rate, tolerance, and
   observation grid remain fixed. Explain the longer exponential tail before discussing MATLAB mechanics.
6. Reset the time constant to 250 us. Move the second lever through the slew-rate sweep while every other
   input remains fixed. Identify the ramp-to-exponential handoff.
7. Explain both changed views from `de/dt=-e/tau`, `|dy/dt|<=S`, and the target-centered tolerance equations.
8. Open `interactive.m`. Move one control, describe one plot transition, then reset it before moving another.
   Changing DAC bits moves the LSB and quantized target; changing latency moves the target event; neither is
   the same mechanism as changing the output pole or slew rate.
9. Select `Recorded code, update not latched`. Verify that code 3103 is recorded while the active held code,
   target, and output remain at code 621. Name the violated latch assumption from this symptom.
10. Select `Command deadline`. Verify that the 50 us policy rejects the 100 us update, exposes no recorded
    code, and leaves the output unchanged. Distinguish rejection from cancellation of a real peripheral.
11. Select `Short observation` and `Slow output` separately. Distinguish a response not yet observed to settle
    from a command that never applied, then reset to the baseline.
12. State what remains absent: device-specific register timing, glitch and nonlinear errors, reference/load
    behavior, overshoot/stability, driver cancellation, an ADC/oscilloscope capture, and hardware evidence.
13. Run `run_checks.m`, answer one interpretation question at a time, and give the two-sentence teach-back:
    mechanism first, then failure distinctions, deadline boundary, recovery, and physical validation needs.

The calculations are deterministic and synthetic. They do not provide MATLAB-runtime evidence in an
unexecuted environment or DAC, ADC, oscilloscope, bus, bench, HIL, field, RT1/RT2, Unreal, signing, release,
deployment, staging, or production evidence.
