# P13 lesson: Move Samples with DMA

## Guiding question

What inputs, observable effects, and failure modes matter when you move Samples with DMA?

## Compounds on

P12 — Measure Jitter and Worst-Case Response Time.

P12 kept actual release, first start, and completion distinct. Keep the same three observations here: a
sample request can exist before its DMA beat starts, and a beat can finish before the processor owns a whole
block. DMA changes who performs the copy and how often the processor is notified; it does not erase time,
bandwidth, address configuration, or data-validity requirements.

## Read: one serial engine moves one beat at a time

After setup, the first sample request is at `t=0` and later requests are `T_s` microseconds apart:

```text
a_i = (i-1) T_s
q   = A + b/r
s_i = max(a_i, f_(i-1))
f_i = s_i + q.
```

Here `b/r` is payload time and `A` is fixed arbitration service. The recurrence says exactly two things:
service cannot start before the sample exists, and a serial engine cannot serve two beats at once. The
request budget has slack `T_s-q`; the offered load is `rho=q/T_s`. If `q<=T_s`, each baseline request can
finish no later than the next request boundary. If `q>T_s`, the waiting term `s_i-a_i` grows. This model keeps
the finite request list while it waits, so backlog is a warning about required queue capacity, not evidence
that a sample was physically lost.

The descriptor groups completed beats into `B`-sample blocks. The processor owns a block only at its final
beat completion `F_j`. Earlier samples in that block therefore have larger processing-ready latency:

```text
ready latency_i = F_j - a_i.
```

For a declared per-sample processor copy demand `C_copy`, setup demand `C_setup`, and completion-handler
demand `C_isr`, compare:

```text
processor-copy demand = N C_copy
DMA CPU demand        = C_setup + n_complete_blocks C_isr.
```

For a completed descriptor, both terms describe the same `N` delivered samples. After abort, an observed
savings comparison instead uses only the committed sample count on the processor-copy side; subtracting
observed DMA work from a full-transfer copy cost would compare unequal work. This is accounting, not a CPU
schedule or a measured utilization. P12 would still require releases, interference, blocking, deadlines, and
an appropriate observation campaign before making a response-time statement.

## Prediction before the baseline

If only block size grows, which should change first: DMA bus load, the number of completion interrupts, or
the time an early sample waits for block ownership?

Ask for one answer, then show the baseline. Do not add a second prediction before the plots.

## Baseline: read timing before summary metrics

The seedless baseline uses:

- 32 source codes `x_i=mod(37(i-1)+11,4096)`;
- `T_s=50 us` and `b=2 byte/sample`;
- `r=0.2 byte/us` and `A=1 us/beat`;
- `B=8 sample/block`;
- `C_setup=8 us`, `C_isr=3 us/block`, and `C_copy=4 us/sample`;
- no finite timeout, continued waiting, and incrementing destination addresses.

Read the timing view first. One beat costs `q=11 us`, so the 39 us slack prevents request waiting. Arrivals
are `0:50:1550 us`; starts equal arrivals; completions are `11:50:1561 us`. Offered load is 22%, total beat
service is 352 us, and peak pending count is one. Those facts describe the declared engine, not a measured
bus.

Now read block ownership. The block-completion times are `[361 761 1161 1561] us`. In each eight-sample
block, ready latency is `[361 311 261 211 161 111 61 11] us`; the fixture mean is 186 us and maximum is
361 us. The first code waits for seven later arrivals plus its block's last 11 us beat even though its own
beat finished at 11 us.

Finally read processor demand and memory separately. Processor copying would demand `32*4=128 us`. DMA
setup and four completion handlers demand `8+4*3=20 us`, 108 us less in this fixture. Incrementing
destination addresses make the destination vector exactly equal the source vector. Neither the timing result
nor the CPU-demand result substitutes for that integrity comparison.

### Observation question 1

Why does the first sample finish its own beat at 11 us but wait until 361 us for block ownership?

Pause after this question. The mechanism is notification granularity: the block is handed over only after
sample eight completes.

### Observation question 2

Which baseline numbers support “no request backlog,” and which separate observation supports “correct data”?

The timing evidence is `q=11 us<T_s=50 us`, zero request wait, and peak pending one. Correctness comes from
the independent source/destination comparison.

## Lever 1: aggregate more samples per notification

Hold request timing, bytes, payload rate, arbitration, source codes, CPU costs, timeout, and address mode at
baseline. Sweep only `B=[1 2 4 8 16 32]` samples:

| Block size (sample) | Completion interrupts | DMA CPU demand (us) | Mean ready latency (us) | Maximum ready latency (us) |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 32 | 104 | 11 | 11 |
| 2 | 16 | 56 | 36 | 61 |
| 4 | 8 | 32 | 86 | 161 |
| 8 | 4 | 20 | 186 | 361 |
| 16 | 2 | 14 | 386 | 761 |
| 32 | 1 | 11 | 786 | 1561 |

The descriptor still completes at 1561 us, total beat service stays 352 us, and offered load stays 22%.
Block size aggregates processor notification; it does not make a beat faster. Fewer interrupts cost an early
sample more time before the block becomes available.

### Observation question 3

Why can DMA CPU demand fall while descriptor completion time remains exactly fixed?

Only the notification count changes. The same 32 beats still follow the same arrival and service recurrence.

## Lever 2: change the payload service capacity

Reset `B=8` and every other input, then sweep only
`r=[0.025 0.04 0.05 0.1 0.2] byte/us`:

| Payload rate (byte/us) | Beat service (us) | Offered load (%) | Maximum request latency (us) | Peak pending | Descriptor completion (us) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.025 | 81 | 162 | 1042 | 13 | 2592 |
| 0.04 | 51 | 102 | 82 | 2 | 1632 |
| 0.05 | 41 | 82 | 41 | 1 | 1591 |
| 0.1 | 21 | 42 | 21 | 1 | 1571 |
| 0.2 | 11 | 22 | 11 | 1 | 1561 |

The number of block-completion interrupts stays four and DMA CPU demand stays 20 us. At 0.04 byte/us,
`q=51 us` is only 1 us above the 50 us budget, but serial waiting accumulates. At 0.025 byte/us the finite
campaign reaches 13 pending requests. The model intentionally has no finite peripheral FIFO, so those
pending counts do not state how many samples real hardware would lose.

### Observation question 4

What changes at `q=T_s`, and why does equality pass in this fixture?

There is zero slack but no growing wait. A beat completing at a request boundary releases the engine before
the new request is admitted. A target with different boundary ordering would need a different contract.

## Read the mechanism after both changes

The two levers act on different mechanisms:

- `B` changes how often completed movement becomes processor-visible and how often the completion handler
  runs;
- `r` changes `q`, request slack, backlog, and completion time;
- neither lever changes destination address semantics;
- neither completion timing nor notification count validates stored values.

DMA is therefore not “free copying.” The engine performs serialized service on behalf of the processor. The
processor exchanges per-sample copy work for setup and block-handoff work, while block availability and bus
capacity remain explicit timing constraints.

## Deliberately broken case: a completion that hides corrupt placement

Reset the baseline and change only destination mode from incrementing to fixed. Every completed beat targets
slot one. The DMA timing remains `[11 61 ... 1561] us`, all 32 beats complete, and all four completion events
still occur. Yet later writes replace earlier ones: slot one ends with the last code, 1158; 31 overwrites are
counted; slots 2 through 32 remain unwritten; and integrity is false.

The violated assumption is “the destination address advances once per sample.” The recognizable symptom is
a healthy-looking completion timeline beside a buffer with one changing slot and 31 holes. A completion flag
means the programmed transfers finished. It cannot certify that the program described the intended memory
layout.

### Observation question 5

Why is retrying the same fixed-address descriptor not recovery?

The configuration error is deterministic, so a retry repeats the overwrite. Recovery requires restoring the
address mode, rearming clean input, and validating the resulting memory. In a device, already overwritten
memory and any downstream use would need their own recovery policy.

## Timeout, continued waiting, and abort

The finite descriptor wait is late only when full completion is strictly greater than its timeout. The
baseline completion at exactly 1561 us passes.

At a 1161 us boundary, `continue-waiting` records a timeout but eventually retains all 32 writes and four
block completions. `abort-transfer` retains a beat whose completion equals the boundary, so 24 samples and
three complete blocks remain while eight later beats are canceled. At 1160 us, only 23 writes remain and only
two complete blocks are ready; the partial third block must not masquerade as processor-owned data.

Abort changes only the modeled unfinished transfer. It does not undo committed writes, reset a DMA
controller, flush a cache, stop a converter, release a driver resource, repair a consumer, or restore a
plant. Calling the state-free model again with the clean baseline is deterministic computational rollback and
recovery, not physical rollback.

## Misconceptions to correct directly

- **“DMA makes the transfer instantaneous.”** No. `q`, serialization, request wait, and block-ready latency
  remain visible.
- **“Larger blocks increase bandwidth.”** Not here. They reduce notification count and increase ownership
  latency while beat timing stays fixed.
- **“Under 100% offered load means the data are correct.”** It only bounds the declared service queue;
  addressing and source/destination integrity are separate.
- **“Over 100% means this model proved sample loss.”** It proved backlog in a finite retained request list.
  A loss claim needs a finite peripheral queue and overflow policy.
- **“The DMA interrupt validates the buffer.”** It reports a programmed count boundary, not intended address
  configuration, coherency, or contents.
- **“Abort rolls everything back.”** Already completed memory writes remain committed in the model and may
  have observable consequences on a target.

## Connection forward to P14

P13 stops at DMA request service, destination placement, and block handoff. It deliberately does not give the
producer a finite software ring, schedule a consumer, or choose overwrite/drop/backpressure behavior. P14
adds those finite-capacity decisions and asks when a correct DMA producer can still overrun a ring buffer.

## Interpretation questions

Ask one at a time:

1. Which timestamps identify request wait, beat service, request latency, and block-ready latency?
2. Why does block size change processor demand without changing offered bus load?
3. What evidence distinguishes queue capacity from address correctness?
4. Why can a descriptor be timing-complete while its destination buffer is unusable?
5. Which already committed effects survive an abort?
6. What FIFO, arbitration, cache, barrier, interrupt, scheduler, and target measurements would be needed
   before applying this fixture to hardware?

## Teach-back

In two sentences, answer the guiding question. Sentence one must connect sample period, bytes per sample,
payload rate, arbitration, serialized beat timing, block size, processor service demand, and block-ready
latency. Sentence two must distinguish backlog from proved loss, completion from destination integrity,
timeout from abort, and computational recovery from hardware recovery without relying on MATLAB syntax.

## Evidence boundary

The module is a deterministic synthetic model implemented with base MATLAB source. Repository checks can
validate identity, structure, equations, reference arithmetic, and the presence of executable checks.
Unless separately retained from a named environment, they do not establish MATLAB numerical execution,
figure rendering, UI behavior, peripheral timing, processor load, memory ordering or cache coherency,
hardware or bench behavior, HIL behavior, field behavior, or production behavior. RT1/RT2, Unreal, signing,
release, deployment, staging, and production validation are outside this lesson.
