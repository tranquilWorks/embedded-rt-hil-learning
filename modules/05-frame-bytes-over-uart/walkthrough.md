# Walkthrough: Frame Bytes over UART

1. Read the guiding question and connect P04's finite clock representation to transmitter and receiver
   bit periods.
2. Make one prediction only: calculate the line-bit count, frame time, and payload efficiency for one
   115200 bit/s 8-N-1 byte.
3. Run `experiment.m`. Inspect only the first baseline logic view. Identify idle/start/data/stop levels,
   confirm the non-palindromic byte 163 is LSB-first, and name the time and logic-level axes.
4. Inspect the byte-value view next. Confirm that each matched-clock decoded value equals its transmitter.
5. Move one lever: inspect the transmitter-baud sweep while byte bits, format, gap, and relative receiver
   error remain fixed. Explain inverse line time and `8/10` goodput.
6. Reset transmitter baud to 115200 bit/s. Move the second lever: inspect receiver error while the
   transmitter waveform stays fixed. Follow center-sample margin before interpreting byte errors.
7. Read the mechanism before opening the next view: `T = 10^6/B` and
   `t_sample(j) = t_start + (j + 1/2)T_rx`, re-anchored at every qualified start.
8. Open `interactive.m`. Move one control, describe one plot transition, then reset it before moving
   another. Toggle parity in the single-data-bit fault and distinguish detected from undetected corruption.
9. Select the fixed forced-low stop scenario. Confirm that controls which could change the named fixture
   reset first. Observe frame 2's framing error, frame 3's missing falling edge, and frame 4's recovery.
10. Select the fixed deadline. Explain why two receive attempts complete by 170 us and later frames are
    cut off, and why this pure absolute cutoff is not a device wait or packet timeout.
11. State what remains absent: packet boundaries, checksum, retry, asynchronous cancellation, physical
    voltage behavior, and device-specific start qualification.
12. Run `run_checks.m`, answer one interpretation question at a time, and give a two-sentence teach-back:
    mechanism first, then failure distinctions and recovery boundary.

The calculations are deterministic and synthetic. They do not provide MATLAB-runtime evidence in an
unexecuted environment or serial peripheral, cable, voltage, bench, HIL, field, RT1/RT2, Unreal, signing,
release, deployment, staging, or production evidence.
