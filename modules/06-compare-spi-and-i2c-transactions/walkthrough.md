# Walkthrough: Compare SPI and I2C Transactions

1. Read the guiding question and connect P05's payload-versus-frame accounting to synchronous clock cells.
2. Make one prediction only: for four returned bytes at equal 400 kHz clocks, calculate SPI and I2C pulse
   counts, nominal clocked times, and payload efficiencies.
3. Run `experiment.m`. Inspect only the first SPI cell view. Identify the `0xAD` command, dummy MOSI bytes,
   simultaneous MISO return, MSB-first order, and clock-pulse axis.
4. Inspect the I2C cell view next. Find `0x90`, `0x2D`, repeated START after pulse 18, `0x91`, and each ninth
   response. Name which side owns the three header ACKs and four data responses.
5. Open the baseline metric view. Explain why equal configured clocks produce 40 versus 63 pulses without
   claiming a universal physical speed ranking.
6. Move one lever: inspect the payload-length sweep while clocks, address, register, and faults stay fixed.
   Explain rising efficiency from `8(N+1)` and `9(N+3)` before discussing MATLAB mechanics.
7. Reset payload length to four bytes. Move the second lever: inspect the clock-stretch sweep while every
   clocked SDA cell and the SPI transaction remain fixed. Explain `t = C/f + t_stretch` mechanism first.
8. Open `interactive.m`. Move one control, describe one plot transition, then reset it before moving another.
   Changing address or register should alter header bits without altering their pulse count.
9. Select the target-NACK scenario. Confirm the fixed controls reset first, then observe the register response
   high at pulse 18 and the absence of repeated START or payload.
10. Return to the clean scenario and identify the last controller response high. Explain why that final NACK
    is successful termination rather than the target failure in step 9.
11. Select SPI returned-bit corruption, then the fixed stretch deadline. Distinguish completed-but-unverified
    SPI data, protocol-visible I2C NACK, and a controller-policy deadline with no committed payload.
12. State what remains absent: universal SPI commands, device status/checksum, I2C semantic validation,
    physical setup/hold or rise time, arbitration, driver cancellation, bus clear, hardware interoperability,
    and target side effects. Run `run_checks.m`, answer one interpretation question at a time, and give the
    two-sentence teach-back: mechanism first, then failure distinctions and recovery boundary.

The calculations are deterministic and synthetic. They do not provide MATLAB-runtime evidence in an
unexecuted environment or protocol-analyzer, device, pull-up network, bench, HIL, field, RT1/RT2, Unreal,
signing, release, deployment, staging, or production evidence.
