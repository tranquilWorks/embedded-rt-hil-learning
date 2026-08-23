# P13 — Move Samples with DMA

**Track:** Embedded, Real-Time, and Hardware-in-the-Loop Systems  
**Phase 4:** Data movement and timing  
**Status:** implemented

## Guiding question

What inputs, observable effects, and failure modes matter when you move Samples with DMA?

## Computational mental model

P12 kept release, start, and completion timestamps separate. P13 applies the same discipline to a peripheral
request and its DMA beat. Once a descriptor is armed, sample `i` arrives every `T_s` microseconds. One serial
DMA engine cannot start a beat before its request arrives or before the previous beat completes:

```text
a_i = (i-1) T_s
q   = A + b/r
s_i = max(a_i, f_(i-1))
f_i = s_i + q
```

`b` is bytes per sample, `r` is payload rate in bytes per microsecond, `A` is fixed arbitration service per
beat, and `q` is one beat's service time. The configured request budget has slack `T_s-q` and offered load
`rho=q/T_s`. Equality at `q=T_s` is sustainable in this declared fixture because completion at a boundary is
processed before the request arriving at that boundary. When `q>T_s`, pending requests accumulate. The
fixture retains a finite request list, so backlog is visible without silently calling it data loss.

The DMA engine writes each completed sample to a configured destination address. The processor is notified
only after each `B`-sample block, so block `j` becomes available at the completion of its last beat. A sample
near the front of a large block waits longer for that ownership transition even though its own beat finished:

```text
e_j                    = min(jB, N)
F_j                    = f_(e_j)
block-ready latency_i  = F_j - a_i
CPU copy demand        = N C_copy
DMA CPU demand         = C_setup + n_blocks C_isr.
```

The `min` makes the ownership rule explicit for a final short block when `N` is not divisible by `B`.

These are service-demand and availability calculations. Less processor copying does not prove a P12 response-
time bound. After abort, observed savings compares only committed processor-copy work against setup and
handlers actually observed; the full-transfer reference remains separate. A completion interrupt does not
prove that destination addressing or sample contents are correct.

## Deterministic baseline

The baseline arms one 32-sample descriptor at `t=0` with `T_s=50 us`, `b=2 byte/sample`, `r=0.2 byte/us`,
`A=1 us`, `B=8 samples`, `C_setup=8 us`, `C_isr=3 us/block`, and `C_copy=4 us/sample`. Its deterministic
source codes are `x_i=mod(37(i-1)+11,4096)`, which here run from 11 through 1158 without wrapping.

- One beat takes `q=1+2/0.2=11 us`; offered load is 22%, request slack is 39 us, and peak pending requests
  are one.
- Arrivals are `0:50:1550 us`, starts equal arrivals, and completions are `11:50:1561 us`.
- The four block-completion times are `[361 761 1161 1561] us`.
- Within each block, processing-ready latency is `[361 311 261 211 161 111 61 11] us`; its mean is 186 us
  and its maximum is 361 us.
- DMA beat service totals `32*11=352 us`. The counterfactual processor-copy demand is `32*4=128 us`; DMA
  setup plus four completion handlers demand `8+4*3=20 us`, a reduction of 108 us for this fixture.
- Incrementing destination addresses preserve every source code in order.

## What the learner controls

- **Sample period `T_s` (us):** request spacing and the per-request service budget.
- **Block size `B` (sample):** how many completed beats share one processor notification.
- **Bytes per sample `b` (byte/sample):** payload moved by each request.
- **DMA payload rate `r` (byte/us):** payload service capacity, separate from arbitration.
- **Arbitration service `A` (us/beat):** fixed non-payload service charged to every beat.
- **DMA setup and completion-ISR demand (us):** processor work at descriptor arm and block handoff.
- **Processor-copy demand (us/sample):** a declared counterfactual service cost, not a measured CPU time.
- **Descriptor wait timeout (us):** a synthetic software observation boundary; zero in the UI disables it.
- **Timeout action:** continue waiting for completion or abort only the modeled unfinished transfer.
- **Scenario/address mode:** incrementing baseline, fixed-destination fault, overloaded bus, continued timeout,
  or aborted transfer.

## Complete learning flow

1. Connect P12's `a`, `s`, and `f` timestamps to a DMA request, then make one prediction about what a larger
   block changes.
2. Inspect the request/start/completion timeline before looking at processor service or buffer contents.
3. Inspect source and destination codes separately; a timing-complete descriptor must also pass an integrity
   check.
4. Sweep only block size through `[1 2 4 8 16 32]` samples. Completion-interrupt counts become
   `[32 16 8 4 2 1]`, DMA CPU demand becomes `[104 56 32 20 14 11] us`, and maximum processing-ready
   latency becomes `[11 61 161 361 761 1561] us`. Bus load and descriptor completion stay fixed.
5. Reset `B=8`, then sweep only payload rate through `[0.025 0.04 0.05 0.1 0.2] byte/us`. Beat service is
   `[81 51 41 21 11] us`, offered load is `[162 102 82 42 22]%`, and maximum request latency is
   `[1042 82 41 21 11] us`. Processor setup, block count, and completion-ISR demand stay fixed.
6. Explain the two transitions from transaction aggregation and serial service capacity, not from MATLAB
   syntax.
7. Break only destination incrementing. Timing still reports 32 completed beats and four block interrupts,
   but all beats target slot one: code 1158 remains there, 31 overwrites occur, and 31 slots are unwritten.
8. Compare exact timeout boundaries, continued waiting, partial abort, state-free rollback, and clean recovery.
9. Run independent checks and give the two-sentence teach-back.

## Timeout, abort, rollback, and recovery boundaries

A finite wait timeout classifies the full descriptor as late only when its reference completion is strictly
greater than the boundary. Completion at 1561 us therefore passes. `continue-waiting` records a late wait and
retains every eventual beat. `abort-transfer` retains only beats with `f_i<=timeout`, never invents a full
descriptor completion, and exposes unfinished destination slots.

At an abort boundary of 1161 us, the beat completing exactly at the boundary is retained: 24 samples and
three complete blocks remain, while the final eight samples are canceled. At 1160 us, only 23 samples and two
complete blocks remain; a partly written third block is not ready for processing. Aborting does not undo
already committed memory writes, reset a real peripheral, release an operating-system object, repair
downstream state, or recover a plant. Re-running the pure model with clean input is computational rollback and
recovery only.

## Boundaries and dependencies

The fixture models one finite descriptor chain, one serial DMA service resource, deterministic request times,
fixed service per beat, preconfigured block handoffs, and a synthetic destination memory initialized to an
unwritten sentinel. Setup occurs before the `t=0` request timeline. The source request list is retained even
when service falls behind, so `rho>1`, pending requests, or request-budget excess do not by themselves prove
peripheral FIFO overflow or lost samples.

P12 supplies timestamp and response-time vocabulary. P13 reports processor service demand that could become
one input to a wider scheduling analysis, but it does not schedule that work or prove WCRT. P07 supplies the
idea that ADC codes have meaning before transport. P14 will add finite ring-buffer capacity, a consumer, and
overrun policy; those are intentionally absent here.

The implementation uses base MATLAB arithmetic, plots, and UI controls. It does not use Simulink, a DMA or
Data Acquisition Toolbox, device support packages, asynchronous timers, operating-system DMA APIs, cache or
memory-barrier primitives, or a physical peripheral. It omits burst coalescing, multiple DMA channels,
arbitrating masters, peripheral FIFO depth, bus faults, cache coherency, descriptor alignment, scatter/gather,
memory protection, interrupt dispatch latency, downstream processing, and finite ring-buffer consumption.

The accepted fixture is bounded before trace and memory allocation. Integer-class source codes are accepted
through `flintmax`; larger values are rejected before normalization can silently alias their identity.
Rejected or aborted calls cannot contaminate a later clean call. Results are deterministic synthetic
calculations, not MATLAB-runtime or
rendered-UI evidence, measured bus timing, processor utilization, cache-coherency evidence, hardware or bench
validation, HIL validation, field evidence, or production evidence. RT1/RT2, Unreal, signing, release,
deployment, and staging validation are not performed by this lesson.

## Files

- `p13_scenario.m` owns bounded deterministic transfer and diagnostic fixtures.
- `model.m` owns validation, serialized beat timing, backlog, block readiness, CPU-service accounting,
  destination writes, timeout, abort, and integrity metrics.
- `experiment.m` owns the baseline, labeled complementary views, two isolated sweeps, deliberately broken
  address case, and recovery diagnostics.
- `interactive.m` owns immediate transfer controls and complementary timing and buffer/CPU views.
- `lesson.m`, `lesson.md`, and `walkthrough.md` own the mechanism-first learner sequence.
- `checks.md` and `run_checks.m` own interpretation prompts and executable invariants.
