# Checks: Frame Bytes over UART

## Observation check

On the baseline logic view, read byte 163 from the sampled slots without using the decimal plot. Name the
idle, start, data, and stop levels, and explain why the first data slot is `d0` rather than `d7`.

## Independent calculations

- At 115200 bit/s, calculate `T_bit`, the ten-bit 8-N-1 frame time, four-frame line time, framing
  efficiency, and continuous matched-clock payload goodput.
- For byte 163, divide by powers of two or use repeated integer division to derive `d0` through `d7`.
- At receiver errors of -6%, 0%, and +6%, calculate the last 8-N-1 sample position as
  `9.5/(1 + e/100)` transmitter-bit times and compare it with the intended stop interval `[9, 10)`.

## Limiting cases and compatibility

- What should an empty byte vector report for frame counts, line time, and minimum observed margin?
- Why do bytes 0 and 255 still require start and stop slots?
- Why does a column byte vector or a `uint8` vector produce the same row-oriented frame truth?
- How do parity and a second stop bit change `N_frame` and payload efficiency?
- Why can a nonpositive pattern-independent margin coexist with an apparently correct byte pattern?

## Positive, negative, malformed, and resource-bound cases

Confirm exact 8-N-1 rows for bytes 0, 85, 163, and 255. Then reject nonnumeric, nonvector, nonfinite,
fractional, negative, and greater-than-255 byte inputs; invalid baud/error/parity/stop/gap/deadline values;
malformed fault structs; out-of-range fault frames/bits; and requests exceeding the bounded frame, sample,
or transmitter-cell budgets. A rejected call must not affect the next valid call.

## Parity, broken stop, rollback, and recovery

Flip one data bit after even parity is formed. Explain why parity rejects the altered byte, why the same
fault under 8-N-1 is an undetected valid character, and why two flipped data bits can preserve even parity.
Then force frame 2's stop low with no gap: distinguish its framing error from frame 3's absent start edge,
and point to frame 4 as later recovery. Reset all inputs and require exact `isequaln` rollback to baseline.

## Timeout and cancellation

The fixed 170 us deadline accepts the first two receiver sample sequences and cuts off the later two.
Move the deadline exactly to a frame's final sample, then just below it, and explain the inclusive boundary.
This is a deterministic absolute cutoff, not a wall-clock wait or an inter-byte application timeout.

There is no asynchronous operation, wait loop, external resource, or partial persisted transaction in this
pure calculation, so cancellation is not applicable. Do not relabel low stop as timeout or missing start as
cancellation. Re-invocation with an infinite deadline is rollback; a later independently decoded frame is
recovery.

## Interpretation and transfer

Choose a real UART link. State its format, rate, oscillator budget, start qualification, voltage standard,
cable environment, packet-boundary rule, integrity check, timeout, retry policy, and required recovery.
Keep those physical and protocol requirements separate from what this synthetic character model proves.

## Teach-back

In two sentences, answer the guiding question. Sentence one must connect idle/start, LSB-first data,
optional parity, stop bits, transmitter bit period, receiver center samples, and sampling margin. Sentence
two must distinguish corrupted data, parity error, framing error, missing start, deterministic deadline,
packet boundaries, rollback, and later recovery without relying on MATLAB syntax.

## Executable check

Run:

```matlab
run_checks
```

All assertions must pass before personal learner completion is recorded.
