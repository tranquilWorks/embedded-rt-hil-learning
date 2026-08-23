# Walkthrough: Sample an ADC Without Aliasing

1. Read the guiding question and connect P06's correctly transported register bytes to the upstream meaning
   of an ADC code. A successful bus transfer cannot recover information already folded at sampling.
2. Make one prediction only: for a 180 Hz input at 1 ksample/s, calculate the 500 Hz Nyquist boundary, 320 Hz
   strict margin, and 180 Hz apparent frequency.
3. Run `experiment.m`. Inspect only the first time view. Identify the physical input, first-order analog
   output, `t_n=n/f_s` sample instants, and code-center voltages; name every axis and unit.
4. Inspect the ADC code and quantization-error view next. Explain why 12 bits change volts per code without
   changing a frequency or sample instant.
5. Move one lever: inspect the sample-rate sweep while the 180 Hz source, analog cutoff, amplitude, and ADC
   settings remain fixed. Explain the positive-to-negative Nyquist margin before discussing MATLAB mechanics.
6. Reset the sample rate to 1 ksample/s. Move the second lever through physical input frequencies and trace
   `[50 180 350 500 350 180 150]` Hz in the apparent-frequency view.
7. Explain the changed views with `f_fold=mod(f_in+f_s/2,f_s)-f_s/2`. Treat exact Nyquist equality as an
   unsafe phase-sensitive boundary even though the plotted magnitude equals `f_s/2`.
8. Open `interactive.m`. Move one control, describe one plot transition, then reset it before moving another.
   Lowering the analog cutoff changes pre-sampling gain and phase; changing ADC bits does not move the fold.
9. Select the bypassed 820 Hz alias. Compare it with the 180 Hz case: the dense analog traces differ but the
   1 kHz sample sequence and ADC codes match. More bits or faster SPI/I2C transport cannot disambiguate them.
10. Select Nyquist phase loss, rail clipping, and the fixed acquisition deadline one at a time. Distinguish
    frequency ambiguity, lost phase information, out-of-range voltage, and uncommitted analytical results.
11. Reset to the filtered baseline. State what remains absent: a real source bandwidth and guard band,
    realizable filter order/tolerances, ADC aperture/jitter/settling/noise/linearity, buffering, bus framing,
    driver cancellation, and hardware evidence.
12. Run `run_checks.m`, answer one interpretation question at a time, and give the two-sentence teach-back:
    mechanism first, then prevention, failure distinctions, deadline boundary, and recovery.

The calculations are deterministic and synthetic. They do not provide MATLAB-runtime evidence in an
unexecuted environment or ADC, sensor, filter, bus, bench, HIL, field, RT1/RT2, Unreal, signing, release,
deployment, staging, or production evidence.
