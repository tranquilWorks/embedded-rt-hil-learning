# Checks: Compare SPI and I2C Transactions

## Observation check

On the baseline views, identify the SPI command and first returned payload byte without using the decimal
metrics. Then identify the three I2C header bytes, the repeated START boundary, all ninth responses, and
the side that owns each response. Why is the last high response not a target failure?

## Independent calculations

- For `N=4`, calculate `C_spi = 8(N+1) = 40` pulses and `C_i2c = 9(N+3) = 63` pulses.
- At equal 400 kHz clocks, calculate 100 us SPI clocked time and 157.5 us I2C clocked time.
- Calculate payload efficiencies `32/40 = 80%` and `32/63`, about 50.8%.
- Derive SPI command `0x80 | 0x2D = 0xAD` and I2C headers `2*0x48 + [0, 1] = [0x90, 0x91]`.
- Add 25, 100, and 250 us of stretch to 157.5 us without changing the 63-pulse count.

## Limiting cases and compatibility

- Why is a zero-byte request rejected instead of labeled a completed I2C read? Identify the returned byte
  whose controller-owned NACK must precede STOP.
- For one returned byte, why are the pulse counts 16 for SPI and 36 for I2C?
- As payload length grows, why do the fixture efficiencies approach 1 for SPI and `8/9` for I2C?
- Why must a column payload or `uint8` payload preserve the same row-oriented clock truth?
- Which conclusions would change if a device used LSB-first SPI, command latency, a different mode, or status?

## Positive, negative, malformed, and resource-bound cases

Confirm one active-low chip select spans every SPI clock and exact MSB-first cells encode command `0xAD`,
headers `0x90`, `0x2D`, `0x91`, and payload bytes. Then
reject nonnumeric, nonvector, nonfinite, complex, fractional, negative, and greater-than-255 payloads;
invalid SPI/I2C clocks, reserved or out-of-range fixture addresses, register values, deadlines, fault modes,
fault fields, NACK owners, flip positions, stretch values, and requests exceeding the payload or derived
clock-cell budgets. A rejected call must not affect the next valid call.

## Response ownership, broken case, rollback, and recovery

NACK target response 1, 2, and 3 independently. Require the transaction to stop after 9, 18, and 27 pulses,
respectively; a register-byte NACK must prevent repeated START and data. In a clean read, require the final
controller response to be NACK while the transaction still succeeds. Do not claim that ACK checks payload
integrity or application meaning.

Flip bit 0 of returned SPI payload byte 2. Confirm `0x56` becomes `0x57`, all clocks complete, and no generic
SPI acknowledgment detects it. Remove every fault and deadline and require exact `isequaln` rollback to the
baseline. A clean retry is recovery; it does not undo arbitrary device side effects.

## Timeout and cancellation

Set the common deterministic deadline exactly to the clean I2C modeled elapsed time, then one representable
step below it. The exact boundary passes; the earlier boundary rejects I2C while the shorter SPI fixture still
passes.
Add 300 us of synthetic stretch and apply the retained 250 us deadline: I2C exposes no committed payload.
Re-invocation with no stretch and an infinite deadline recovers the exact baseline.

This bounded calculation has no asynchronous operation, driver wait, external resource, or persisted partial
transaction, so cancellation is not applicable. The deadline classifies an analytical result; it does not
prove that a controller aborted clocks, generated STOP while SCL was low, or cleared a bus.

## Interpretation and transfer

Choose one real register-read requirement. State the device's SPI command/mode/bit order/chip-select timing
or I2C address/combined-format/clock-stretch policy, plus required rate, setup/hold and rise-time limits,
integrity check, timeout, retry, bus recovery, and application commit rule. Keep those device, electrical,
and operational requirements separate from what this synthetic clock-cell model proves.

## Teach-back

In two sentences, answer the guiding question. Sentence one must connect SPI simultaneous MOSI/MISO and
device-select framing with I2C in-band addressing, repeated START, ninth responses, response ownership,
pulse counts, clocks, stretch, elapsed time, and payload efficiency. Sentence two must distinguish final
controller NACK, target NACK, silent SPI corruption, deterministic deadline, cancellation boundary,
rollback, and clean retry without relying on MATLAB syntax.

## Executable check

Run:

```matlab
run_checks
```

All assertions must pass before personal learner completion is recorded.
