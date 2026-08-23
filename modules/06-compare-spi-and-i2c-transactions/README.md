# P06 — Compare SPI and I2C Transactions

**Track:** Embedded, Real-Time, and Hardware-in-the-Loop Systems  
**Phase 2:** Buses and acquisition  
**Status:** implemented

## Guiding question

What inputs, observable effects, and failure modes matter when you compare SPI and I2C Transactions?

## Computational mental model

P05 separated UART payload from start, parity, and stop overhead. P06 applies the same accounting discipline
to one concrete operation: read `N >= 1` bytes from an eight-bit device register. The expected bytes are fixed,
both configured clocks begin at 400 kHz, and every transmitted or response bit is constructed explicitly.

The SPI fixture is one device convention, not universal SPI grammar. It uses active-low chip select, mode 0,
MSB-first transfer, one read-command byte `0x80 | register`, and `N` dummy MOSI bytes while the target returns
one dummy byte followed by `N` payload bytes on MISO. MOSI and MISO shift simultaneously:

```text
C_spi = 8(N + 1) pulses
t_spi,clocked = 10^6 C_spi / f_spi microseconds
eta_spi = 8N / C_spi = N / (N + 1).
```

The I2C fixture uses a seven-bit address and a common combined-format register read:

```text
START, address+W, ACK_target, register, ACK_target,
repeated START, address+R, ACK_target,
data_1, ACK_controller, ..., data_N, NACK_controller, STOP

C_i2c = 9(N + 3) pulses
t_i2c,modeled = 10^6 C_i2c / f_i2c + t_stretch microseconds
eta_i2c = 8N / C_i2c.
```

Every byte is MSB-first and has a ninth response clock. ACK is SDA low and NACK is SDA high. The target owns
the first three responses; the controller owns the responses after read data and intentionally NACKs the
last byte before STOP. That final controller NACK is successful termination. START, repeated START, and STOP
are SDA/SCL boundary conditions and are not counted as extra data clocks.

## What the learner controls

- **Payload length (1–64 bytes):** changes variable data work while fixed command/address overhead stays
  present. At least one byte is required so the I2C controller can NACK the final returned byte before STOP.
- **SPI clock (kHz):** scales only the SPI clocked time in this configured fixture.
- **I2C clock (kHz):** scales only I2C clocked time; it does not remove ninth response pulses.
- **Modeled I2C stretch (us):** adds a target-held SCL-low interval without adding clock pulses.
- **I2C seven-bit address and register:** change the visible header bits without changing their count.
- **Scenario:** selects a clean read, target NACK, silently corrupted SPI return, or fixed stretch deadline.

## Complete learning flow

1. Connect P05 framing overhead to synchronous transaction-cell accounting.
2. Predict the pulse counts for a four-byte read at equal configured clocks.
3. Inspect SPI MOSI/MISO cells, then I2C SDA cells and ninth-clock ownership.
4. Sweep only payload length; observe fixed-overhead amortization and elapsed time.
5. Reset payload length, then sweep only modeled I2C clock stretch; observe unchanged cells but lower goodput.
6. Explain both changed views from the pulse-count and elapsed-time equations.
7. NACK the I2C register byte, distinguish it from the normal final controller NACK, and retry cleanly.
8. Flip one returned SPI data bit and explain why generic SPI reports completed clocks but no generic ACK.
9. Apply a deterministic deadline to a stretched I2C result, reset, run checks, and give the teach-back.

## Boundaries and dependencies

The fixture compares clock-cell accounting and protocol-visible outcomes, not every topology or device. SPI
does not standardize this command bit, register convention, mode, word width, dummy latency, chip-select
timing, status response, or checksum. The I2C register byte is also a device convention. I2C ACK means the
responsible receiver acknowledged a byte; it is not a checksum or proof of application semantics. Neither
generic protocol guarantees end-to-end data integrity.

Clock stretch is a bounded modeled delay. The deterministic deadline classifies a completed analytical
result against a controller policy; it does not sleep, cancel a driver, clear a stuck bus, or undo target
side effects. Re-invoking the pure model with clean inputs is computational rollback and retry recovery.
Asynchronous cancellation is not applicable because there is no wait or external operation.

Only base MATLAB arithmetic, structs, plots, and UI controls are used. No Instrument Control Toolbox,
`spi`, `i2cdev`, Simulink, support package, operating-system driver, protocol analyzer, pull-up/rise-time
model, arbitration model, cable, device register, or electrical threshold is required. Clocked time omits
chip-select setup/hold, START/STOP setup/hold, bus-free time, driver latency, and physical signal integrity.
The outputs are not a hardware measurement, interoperability test, standards-conformance result, bench
result, or HIL result.

## Files

- `p06_scenario.m` owns bounded seedless payload and fault fixtures.
- `model.m` owns validation, explicit MSB-first cells, response ownership, timing, deadline, and metrics.
- `experiment.m` owns the deterministic baseline, labeled views, two isolated sweeps, and broken case.
- `interactive.m` owns immediate controls and complementary SPI/I2C cell views.
- `lesson.m`, `lesson.md`, and `walkthrough.md` own the mechanism-first learner sequence.
- `checks.md` and `run_checks.m` own interpretation prompts and executable invariants.
