# Checks: Move Samples with DMA

## Observation check

On the transfer-timing view, identify request arrival `a_i`, DMA start `s_i`, beat completion `f_i`, request
wait `s_i-a_i`, and block-completion time `F_j` in microseconds. On the complementary processor/buffer view,
identify setup demand, completion-handler demand, source code, destination slot, unwritten memory, and block
ownership. Explain why a completed beat, a completed block, low CPU service demand, and correct destination
contents are four different claims.

## Independent baseline calculations

For `N=32`, `T_s=50 us`, `b=2 byte/sample`, `r=0.2 byte/us`, `A=1 us`, and `B=8`:

- calculate `q=A+b/r=11 us`, slack `T_s-q=39 us`, and offered load `100q/T_s=22%`;
- derive arrival `0:50:1550 us`, start equal to arrival, and completion `11:50:1561 us`;
- require `s_i=max(a_i,f_(i-1))`, `f_i=s_i+q`, causal order `a_i<=s_i<=f_i`, and no overlapping service;
- calculate total beat service `Nq=352 us`, descriptor completion 1561 us, zero request wait, and peak pending
  count one when boundary completion precedes boundary arrival;
- derive block completions `[361 761 1161 1561] us` and the repeated ready-latency pattern
  `[361 311 261 211 161 111 61 11] us`, with mean 186 us and maximum 361 us;
- calculate processor-copy demand `32*4=128 us`, DMA demand `8+4*3=20 us`, and savings 108 us;
- generate `x_i=mod(37(i-1)+11,4096)` and require incrementing destination memory to equal the source exactly.

## Limiting cases and compatibility

- Why does `q=T_s` have zero slack without growing backlog under the declared completion-before-arrival
  boundary order? Check the exact boundary and one slower representable case.
- Why does one sample in one block have one beat of request and block-ready latency rather than zero?
- Why does `B=1` minimize ready latency while retaining one completion interrupt per sample?
- Why does `B=N` produce one interrupt but make the first sample wait until full descriptor completion?
- Why can zero setup/ISR demand produce zero modeled DMA CPU demand without proving the processor is idle?
- Construct a small transfer whose setup and block-handler demand exceed the declared processor-copy demand;
  DMA savings must be negative rather than clamped to zero.
- Verify the declared final-short-block policy for a sample count not divisible by `B`. A partial tail must not
  be silently called a full `B`-sample block or processor-owned before its declared completion.
- Require integer numeric classes through the exact `flintmax` boundary, row or column source codes,
  character or scalar-string policies, and empty timeout/action/address defaults to normalize without
  changing the calculation. Reject the next integer value rather than silently rounding its identity.

## Two independent levers

Sweep only block size through `[1 2 4 8 16 32]` while source codes, request period, bytes per sample, payload
rate, arbitration, CPU costs, timeout, action, and address mode remain fixed. Require:

- completion-interrupt count `[32 16 8 4 2 1]`;
- DMA CPU demand `[104 56 32 20 14 11] us`;
- mean ready latency `[11 36 86 186 386 786] us`;
- maximum ready latency `[11 61 161 361 761 1561] us`;
- invariant descriptor completion 1561 us, total beat service 352 us, offered load 22%, and exact destination
  data.

Reset `B=8`. Sweep only payload rate through `[0.025 0.04 0.05 0.1 0.2] byte/us` while all other baseline
inputs remain fixed. Require:

- beat service `[81 51 41 21 11] us`;
- offered load `[162 102 82 42 22]%`;
- maximum request latency `[1042 82 41 21 11] us`;
- peak pending count `[13 2 1 1 1]`;
- descriptor completion `[2592 1632 1591 1571 1561] us`;
- request-budget-exceeded count `[32 32 0 0 0]`;
- invariant four completion interrupts and 20 us DMA CPU demand.

The first two rates prove deterministic backlog in this finite retained request list. They do not prove
sample loss because no finite peripheral FIFO is modeled.

## Deliberately broken destination configuration

Change only address mode from incrementing to fixed. Require identical arrival, start, completion,
descriptor-completion, beat-count, block-count, bus-load, and CPU-demand results. Every completed beat must
target slot one. The last source code, 1158, remains in that slot; exactly 31 earlier writes are overwritten;
31 destination slots remain unwritten; and data integrity is false.

Restore incrementing addresses and require exact `isequaln` rollback to the baseline. A second fixed-address
call must reproduce the same corruption without leaking state into another call.

## Timeout, cancellation, rollback, and recovery

Require full descriptor completion exactly at a 1561 us timeout to pass. At 1161 us, both actions classify
the full descriptor as late:

- `continue-waiting` records one timeout and retains all 32 eventual writes, four block completions, and the
  exact baseline destination;
- `abort-transfer` retains every beat with `f_i<=1161 us`, including equality, leaving 24 committed samples,
  three complete blocks, and eight canceled tail beats. It must expose no full-descriptor completion and no
  fabricated values in unwritten tail slots.

At an abort boundary of 1160 us, require 23 committed beats and only two processor-ready complete blocks. The
partly written third block remains invalid even though seven of its eight destination writes occurred.
Already committed writes must remain visible after abort; cancellation is not transactional rollback.
At 1161 us, equal-work observed CPU savings is `24*4 - (8+3*3) = 79 us`. The 128 us full-transfer copy
counterfactual remains reference-only and must not be called observed savings after only 24 samples commit.

After continued timeout, abort at both boundaries, fixed addressing, overloaded service, resource rejection,
and malformed calls, re-run the clean fixture and require exact baseline recovery. This proves state-free
computational isolation only. It does not reset a DMA controller, stop a converter, flush caches, undo memory
writes, cancel an operating-system driver, repair downstream state, or recover a plant.

Bind the P13 model and scenario handles, remove the P13 folder from the MATLAB search path, place P01's
incompatible generic `model.m` first, clear the generic model name as a later lesson launch does, and require
the retained handles to reproduce the exact P13 baseline. This checks callback lifetime after
`launch_lesson` removes its temporary module path.

## Positive, negative, malformed, and resource-bound cases

Confirm deterministic source generation; finite and ordered arrival/start/completion times; nonnegative wait,
service, request latency, and ready latency; serial non-overlap; exact service and slack identities; pending-
request conservation; completion-before-arrival equality; block-end ownership; CPU-demand accounting;
bounded destination indices; explicit unwritten values; overwrite conservation; integrity status; timeout
strictness; completion masks; and no full-completion claim after abort.

Reject wrong arity; empty sample vectors; text, logical, complex, NaN, or infinite sample data; nonscalar
scalar fields; zero or negative sample period, bytes per sample, payload rate, or block size; fractional bytes
or block size; negative arbitration or CPU costs; zero, negative, NaN, or nonscalar finite timeout; unsupported
timeout action or address mode; and any incompatible input length or shape. Rejection must occur before
large trace or destination allocation.

Accept the documented maximum of 10,000 samples and reject 10,001 samples or any oversized source vector.
Accept bytes-per-sample values 1 through 16 and reject 17; accept the declared 1,000,000-sample block bound
without allocating a million-sample trace and reject 1,000,001.
Accept a derived finite timeline at the declared `1e12 us` bound and reject the next value beyond it. Reject
nonfinite service, CPU-demand, address, readiness, queue, or descriptor diagnostics and any record where
floating-point precision erases a positive sample interval or beat service. Accept exact integer source codes
through `flintmax` and reject larger integer-class codes before double normalization can alias them. Verify
those exact accepted bounds rather than allocating an unbounded trace.

## Interpretation questions

Ask one at a time:

1. Which terms determine one beat's payload time, arbitration service, and request slack?
2. Why can a larger block reduce processor demand while increasing an early sample's availability latency?
3. Which metric shows a service-capacity problem, and why does it not prove data loss without a finite FIFO?
4. Why can all completion interrupts occur while destination integrity is false?
5. At abort, which writes remain committed and which blocks are safe for a consumer?
6. How does P12 timing vocabulary help without turning this service accounting into a WCRT proof?
7. Which finite buffer and consumer rules are intentionally deferred to P14?
8. What DMA controller, bus arbitration, cache, barrier, interrupt, scheduler, peripheral FIFO, and target
   measurements are still required for a real design?

## Teach-back

In two sentences, answer: “What inputs, observable effects, and failure modes matter when you move Samples
with DMA?” Sentence one must connect `T_s`, bytes per sample, payload rate, arbitration, serialized beat
timing, block size, processor service demand, and block-ready latency. Sentence two must distinguish backlog
from proved loss, completion from destination integrity, continued timeout from abort, computational rollback
from hardware recovery, and the P12/P14 boundaries without relying on MATLAB syntax.

## Evidence boundary

Passing repository source and reference-arithmetic checks establishes static contracts only. Passing
`run_checks.m` in a retained named MATLAB environment would add MATLAB-runtime numerical evidence, but would
still not establish rendered-UI behavior, physical DMA timing, CPU utilization, cache coherency, bench, HIL,
field, or production evidence.

## Executable check

Run:

```matlab
run_checks
```

All assertions and the learner's teach-back must pass before personal completion is recorded.
