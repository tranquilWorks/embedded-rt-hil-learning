# P13 walkthrough: Move Samples with DMA

## Learner sequence

### 1. Read the request and service model

Start from P12's separation of arrival, start, and completion. For each sample, identify
`a_i=(i-1)T_s`, `q=A+b/r`, `s_i=max(a_i,f_(i-1))`, and `f_i=s_i+q`. Read `T_s-q` as request slack and
`q/T_s` as offered load for one declared serial DMA engine.

Ask one prediction before showing a plot: if only block size increases, will bus load, interrupt count, or
early-sample block-ready latency change?

### 2. Inspect the baseline request timeline

Run the deterministic baseline with 32 samples, `T_s=50 us`, 2 byte/sample, 0.2 byte/us payload rate, 1 us
arbitration per beat, and eight-sample blocks. On the timing view, identify arrivals `0:50:1550 us`, starts
equal to arrivals, and completions `11:50:1561 us`.

Expected observation: `q=11 us`, slack is 39 us, offered load is 22%, and peak pending requests are one.
Name those as synthetic timing results, not a bus measurement.

### 3. Inspect block ownership and memory separately

Show block completions `[361 761 1161 1561] us`. Within each block, point to ready latencies
`[361 311 261 211 161 111 61 11] us`. Ask why sample one finishes its beat at 11 us but is not handed to
the processor until 361 us.

Then show source and destination codes. Expected observation: incrementing destination addresses preserve all
32 codes in order. Completion timing and data integrity are separate checks.

### 4. Compare processor service demand

Read the declared counterfactual processor-copy demand, `32*4=128 us`, beside DMA setup plus completion
handlers, `8+4*3=20 us`. Explain that the 108 us difference is fixture service-demand accounting. It is not
measured utilization and not a P12 response-time guarantee.

### 5. Move only block size

Sweep `B=[1 2 4 8 16 32]` samples while every other input remains at baseline.

- Completion interrupts: `[32 16 8 4 2 1]`.
- DMA CPU demand: `[104 56 32 20 14 11] us`.
- Mean block-ready latency: `[11 36 86 186 386 786] us`.
- Maximum block-ready latency: `[11 61 161 361 761 1561] us`.

Expected observation: larger blocks reduce processor notification work and increase ownership latency. Beat
service, 22% offered load, 352 us total bus service, and 1561 us descriptor completion remain unchanged.

### 6. Reset, then move only payload rate

Restore `B=8`. Sweep `r=[0.025 0.04 0.05 0.1 0.2] byte/us`.

- Beat service: `[81 51 41 21 11] us`.
- Offered load: `[162 102 82 42 22]%`.
- Maximum request latency: `[1042 82 41 21 11] us`.
- Peak pending requests: `[13 2 1 1 1]`.
- Descriptor completion: `[2592 1632 1591 1571 1561] us`.

Expected observation: service above the 50 us request budget accumulates wait. Four block interrupts and
20 us DMA CPU demand remain fixed. Backlog is not automatically sample loss because this fixture has no
finite peripheral FIFO.

### 7. Read the mechanism

Block size controls notification aggregation. Payload rate controls serial service time and queueing.
Destination addressing controls placement. Ask the learner to assign each observed metric to exactly one of
those mechanisms before continuing.

### 8. Break destination incrementing

Reset the baseline and change only address mode to fixed. Expected timing is unchanged: 32 beats and four
blocks complete. Expected memory symptom: every beat targets slot one, code 1158 overwrites earlier values,
31 overwrites are counted, and 31 destination slots remain unwritten.

Ask which assumption failed. Correct answer: the descriptor did not advance the destination address; the
completion interrupt never promised intended placement or data integrity.

### 9. Exercise timeout and abort boundaries

First set the full-descriptor timeout to 1561 us. Equality passes. Then use 1161 us:

- `continue-waiting` records a late descriptor and eventually preserves all 32 writes and four blocks;
- `abort-transfer` retains 24 beats and three full blocks because completion at the boundary wins, and it
  cancels the last eight beats.

Move the abort boundary to 1160 us. Only 23 writes and two complete blocks remain; the partial third block is
not processor-ready. Emphasize that abort does not undo committed memory.

### 10. Roll back, recover, check, and teach back

Restore incrementing addresses, infinite timeout, continued waiting, eight-sample blocks, and the baseline
payload rate. Re-run and require exact baseline identity after the overloaded, broken, continued-timeout,
aborted, and malformed cases. This is state-free computational rollback and recovery, not peripheral reset or
physical recovery.

Run `run_module_checks('P13')`. Ask the interpretation questions one at a time, then request the two-sentence
teach-back from `checks.md`.

## Transfer boundary

Carry the completed-block and ownership vocabulary into P14. P14, not this lesson, adds finite ring-buffer
capacity, a consumer rate, and overwrite/drop/backpressure policy.

## Evidence reminder

The exact vectors are deterministic synthetic references. Do not describe source inspection or Python
reference arithmetic as MATLAB execution, rendered UI evidence, DMA hardware timing, processor utilization,
bench, HIL, field, or production validation.
