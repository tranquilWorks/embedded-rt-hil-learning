# Lesson: Frame Bytes over UART

## Guiding question

What inputs, observable effects, and failure modes matter when you frame Bytes over UART?

## Connection to P04

P04 converted event times into finite clock/timer counts and separated resolution from oscillator accuracy.
P05 uses the same clock discipline at a communication boundary. A transmitter assigns one duration to
each logic slot; an asynchronous receiver has a different clock and must decide which level occupies its
predicted slot center. The byte can be correct in software and still be sampled incorrectly on the line.

## Mental model

The binary line is idle-high. One eight-data-bit character frame is

```text
[0, d0, d1, d2, d3, d4, d5, d6, d7, parity?, 1, ...]
```

The first zero is the start bit, data are least-significant bit first, optional parity follows the data,
and one or two high slots stop the frame. Therefore

```text
N_frame = 1 + 8 + N_parity + N_stop
T_tx    = 10^6 / B_tx us
T_frame = N_frame * T_tx.
```

Binary non-return-to-zero UART carries one bit per symbol, so its baud and bit rate are numerically equal
in this lesson. That does not make baud a synonym for bytes per second: 8-N-1 spends ten symbols to move
eight payload bits before any inter-frame idle time.

Let receiver error `e` be a percentage of transmitter baud:

```text
B_rx = B_tx * (1 + e/100)
T_rx = 10^6 / B_rx.
```

After a qualified start edge at `t_start`, the model schedules the center of slot `j`, starting with
`j = 0` for the start slot:

```text
t_sample(j) = t_start + (j + 1/2) * T_rx.
```

It measures each sample's signed distance to the intended transmitter slot boundaries. The smaller
distance is the sampling margin. A strictly positive minimum means all centers remain inside their
intended slots for every data pattern in this abstraction. At zero or below, the transmitter-truth oracle
knows that some center reached or crossed a boundary; a receiver would not directly observe the margin,
and a forgiving data pattern can still appear correct.

Each accepted start edge re-anchors the equation. Baud error accumulates within a character frame, not
across the entire byte stream. The model uses exact start-edge qualification and half-open logic slots;
it does not claim a particular MCU's oversampling, start filter, metastability behavior, or boundary
decision. Consequently, the observed mismatch threshold is a fixture result, not a universal tolerance.

## One prediction before the baseline

At 115200 binary symbols/s, how many line bits and how much time does one 8-N-1 byte require, and what
fraction of those bits carry the eight-bit value?

## Baseline observation

The first view shows byte 163. Its data bits are `1,1,0,0,0,1,0,1` because UART sends `d0` first. With
start and stop, the complete row is `[0 1 1 0 0 0 1 0 1 1]`. Reversing those data bits would encode a
different value, so this non-palindromic byte makes the least-significant-bit-first order visible rather
than merely labeling it. Matched receiver samples sit half a
transmitter-bit from both boundaries. The second view confirms that all four decoded byte values equal
the transmitted values.

At 115200 bit/s, one bit is about 8.681 us, one 8-N-1 frame is about 86.806 us, and four continuous frames
occupy about 347.222 us. The nominal character-framing efficiency is `8/10 = 80%`.

## Lever 1: transmitter baud

Keep the byte sequence, 8-N-1 format, zero gap, and zero receiver error fixed. Sweeping transmitter baud
through `[9600 19200 57600 115200] bit/s` does not alter a single frame bit. It scales `T_tx`, total line
time, and matched-clock goodput. With no gap, correct payload goodput is `8/10` of the binary line rate.
Faster baud is a shorter synthetic symbol period, not evidence that a cable or peripheral supports it.

## Lever 2: receiver baud error

Reset the transmitter to 115200 bit/s, then sweep receiver error while the transmitter waveform remains
unchanged. Early slots move a little; later slots move farther because `(j + 1/2)T_rx` grows with `j`.
The retained fixture is correct through its positive-margin core. Larger errors cross a start, data, or
stop boundary, producing wrong data, a framing error, or a receiver that remains busy past a later start.
The exact transitions depend on this format, zero phase abstraction, byte pattern, and edge qualifier.

## Parity diagnostic

Even parity chooses one bit so the data-plus-parity count of ones is even; odd parity chooses the opposite.
Flipping one data bit after parity was formed makes the parity comparison fail. With parity disabled, the
same altered byte can remain a valid UART character and become undetected corruption. Two changed data
bits can also preserve parity, so parity is not a checksum, packet boundary, or general integrity proof.

## Deliberately broken stop assumption and recovery

The broken fixture forces frame 2's stop slot low while keeping the inter-frame gap at zero. The receiver
samples a low stop and reports a framing error. Because low stop is followed immediately by low start,
frame 3 has no high-to-low start edge in the transmitter truth and is missed. Frame 3 still ends with its
own normal high stop; frame 4 then provides a falling edge and proves bounded recovery. Resetting the
fault reproduces the clean baseline exactly.

This idealized receiver only considers true frame-start transitions. A physical receiver that becomes
idle inside frame 3 might falsely acquire a falling data edge; that device-specific behavior is outside
the model. Recovery means a later frame is independently accepted, not that either lost byte was restored.

## Deadline, cancellation, and stream boundaries

The optional deadline accepts a frame only when its final configured sample is no later than an absolute
microsecond cutoff. It deterministically classifies later frames as timed out; it does not sleep, poll a
device, or model an inter-byte packet timeout. An exact final-sample boundary is accepted. A slightly
earlier deadline rejects that frame and all later ones. Calling the pure model again with `Inf` recovers
the full clean result without persisted state.

There is no asynchronous wait or external transaction, so cancellation is not applicable. A low stop is
a framing error, a missing edge is a missed start, and an incomplete application message would need a
separate protocol parser. UART character framing alone supplies no delimiter, length, checksum,
acknowledgment, retry, or message boundary.

## Common mistakes

- UART sends the least-significant data bit first; plotting the byte MSB-first changes the waveform.
- Baud controls symbol time, while start/parity/stop/gap overhead controls payload efficiency.
- Parity detects some bit changes; it neither corrects them nor replaces a checksum.
- A high stop is both a sampled validity condition and the idle level needed before a new falling start.
- Re-anchoring at each start prevents baud drift from accumulating across the whole stream.
- A nonpositive oracle margin is risk, not proof that every byte pattern visibly fails.
- Logic zero/one is not a claim about TTL, CMOS, or inverted RS-232 voltage levels.

## Completion standard

Explain the frame bits and sample equation, predict both lever effects, distinguish parity, framing,
missed-start, timeout, and packet-boundary concerns, pass `run_checks.m`, and give the teach-back in
`checks.md` without relying on MATLAB syntax.
