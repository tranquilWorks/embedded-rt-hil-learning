# Lesson: Compare SPI and I2C Transactions

## Guiding question

What inputs, observable effects, and failure modes matter when you compare SPI and I2C Transactions?

## Connection to P05

P05 showed that moving eight useful UART bits can require framing overhead from start, parity, stop, and
idle time. It also kept
line truth separate from receiver interpretation. P06 preserves both habits: count every synchronous bus
cell, identify who drives a response, and distinguish offered data, clock completion, protocol-visible
failure, and committed payload.

## One concrete register-read model

The target is expected to return bytes `[0xA3 0x56 0xC9 0x1E]` from register `0x2D`. Both configured clocks
begin at 400 kHz so the first comparison isolates framing rather than rate. The I2C seven-bit address is
`0x48`.

The SPI side uses a declared device convention: active-low chip select remains asserted, mode 0 and
MSB-first are selected, and bit 7 of the register byte requests a read. The controller sends command
`0xAD`, then one dummy byte for every requested return byte. The target's first MISO byte is a dummy, and
the target returns payload during the later dummy MOSI bytes. Both wires shift on the same pulses:

```text
C_spi            = 8(N + 1)
t_spi,clocked     = 10^6 C_spi / f_spi us
eta_spi           = 8N / C_spi = N / (N + 1).
```

The read bit, dummy behavior, mode, bit order, and command layout are fixture choices. SPI itself does not
define a register-read command or a generic ACK.

The I2C side sends a combined-format read:

```text
S, 0x90, ACK_target, 0x2D, ACK_target,
Sr, 0x91, ACK_target,
data_1, ACK_controller, ..., data_N, NACK_controller, P
```

`0x90 = 2*0x48 + 0` carries write direction; after the repeated START, `0x91 = 2*0x48 + 1` carries read
direction. Each byte is eight MSB-first bits plus a ninth response clock. The target owns the three header
responses. Once the target is sending read data, the controller owns each ninth bit: it drives ACK low to
request another byte and NACK high after the last byte before STOP. Therefore this fixture requires
`N >= 1`; a zero-byte request cannot supply the final controller-owned NACK and is rejected.

```text
C_i2c             = 9(N + 3)
t_i2c,clocked      = 10^6 C_i2c / f_i2c us
t_i2c,modeled      = t_i2c,clocked + t_stretch
eta_i2c            = 8N / C_i2c.
```

START, repeated START, and STOP are boundary transitions rather than additional SCL data clocks. The model
retains their positions but omits their physical setup/hold and bus-free intervals, so its time is a
nominal clocked time plus one explicit synthetic stretch—not a total physical transaction measurement.

## One prediction before the baseline

For four returned bytes and equal 400 kHz clocks, predict each transaction's clock pulses, nominal clocked
time, and fraction of pulses that carry the 32 payload bits. Which difference comes only from framing?

## Baseline observation

SPI uses `8(4+1) = 40` pulses: one command byte and four simultaneous dummy/return bytes. At 400 kHz that
is 100 us, and its payload efficiency is `32/40 = 80%`.

I2C uses `9(4+3) = 63` pulses: three header bytes, four data bytes, and a response pulse after every byte.
At 400 kHz that is 157.5 us, and its payload efficiency is `32/63`, about 50.8%. The response row is
`[0 0 0 0 0 0 1]`. The final one is not an error: it is the controller-owned NACK that ends the read.

Equal clock rates do not prove one physical bus is universally faster. They expose only the declared
fixture's pulse counts. Real rates, electrical timing, controller latency, and device behavior remain
separate design inputs.

## Lever 1: returned payload length

Keep clocks, address, register, and faults fixed. Sweep `N` through `[1 2 4 8 16]`. SPI pulse counts become
`[16 24 40 72 136]`; I2C counts become `[36 45 63 99 171]`. Both efficiencies rise because the fixed
headers are amortized, but I2C retains a ninth response pulse for every data byte. As `N` grows, this
fixture approaches efficiency 1 for SPI and `8/9` for I2C.

The payload lever changes transaction length. It does not change configured clock rate, address bits,
response ownership, electrical feasibility, or the meaning of the returned bytes.

## Lever 2: modeled I2C clock stretch

Reset to four bytes and equal 400 kHz clocks. Add a synthetic target-held SCL-low interval after the
register ACK at clock 18. Sweeping stretch through `[0 25 100 250] us` leaves all 63 I2C clocked cells
unchanged while modeled elapsed time becomes `[157.5 182.5 257.5 407.5] us`. Completed-payload goodput
falls because the same 32 payload bits occupy more elapsed time. The SPI structure and 100 us time do not
change.

This lever demonstrates a mechanism, not a device limit. The model does not calculate pull-up resistance,
bus capacitance, rise time, a target's legal stretch locations, or a controller driver's policy.

## Response ownership and the deliberately broken assumption

The broken assumption is that completed clock activity means the payload was both accepted and verified.
Three observations separate the failure modes:

1. A target NACK on the register byte makes the first two target responses `[0 1]`. The controller stops
   after 18 pulses, before repeated START or data. This is a protocol-visible refusal.
2. In a clean I2C read, the final high response is controller-owned normal termination. Calling it a target
   failure reverses who is driving SDA.
3. A returned SPI bit flip changes the second payload byte from `0x56` to `0x57`. All SPI pulses still
   complete, and generic SPI supplies no acknowledgment or checksum. A real device protocol may add status,
   redundancy, or a checksum; this fixture intentionally does not.

I2C ACK does not prove data integrity or application semantics. It reports one receiver's acknowledgment
of one byte. Likewise, SPI clock completion does not prove that a target understood a command.

## Deadline, rollback, recovery, and cancellation

The fixed deadline scenario adds 300 us of I2C stretch. Its modeled I2C result takes 457.5 us, so a 250 us
controller policy rejects it and exposes no committed payload; unchanged SPI takes 100 us and meets the
same policy. The pure calculation constructs the analytical cells and then classifies the result. It does
not claim that a driver stopped the bus at 250 us or generated STOP while SCL was held low.

An exact elapsed-time deadline is accepted; any representably earlier one is rejected. Re-running the model
with no fault and an infinite deadline exactly reproduces the clean baseline. That is state-free rollback
and retry recovery, not reversal of arbitrary device side effects. A later clean call is isolated from a
rejected malformed call.

There is no asynchronous wait, driver request, or partial persisted operation, so cancellation is not
applicable. Bus clear, reset, power cycling, retries, and application commit policy require a particular
controller and target and are outside this calculation.

## Common mistakes

- SPI MOSI and MISO shift simultaneously; adding their bit counts double-counts clock pulses.
- The fixture is MSB-first. Copying P05's UART LSB-first order changes every visible byte.
- A seven-bit I2C address must be shifted before the R/W direction bit is appended.
- Every I2C byte consumes a ninth response clock, but response ownership changes during a read.
- The final controller NACK is normal termination; a target NACK in a header is refusal.
- START, repeated START, and STOP are conditions, not extra SCL data pulses in this model.
- SPI command layout and I2C register addressing are device conventions, not universal protocol fields.
- Neither I2C ACK nor SPI clock completion is an end-to-end checksum.
- Configured clock and modeled stretch do not establish electrical compatibility or worst-case latency.

## Completion standard

Explain both pulse-count equations, identify simultaneous SPI directions and I2C response ownership,
predict both lever effects, distinguish normal final NACK, target NACK, silent SPI corruption, and
deterministic deadline, pass `run_checks.m`, and give the teach-back in `checks.md` without relying on
MATLAB syntax.
