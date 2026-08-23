# P14 — Prevent Ring-Buffer Overrun

**Track:** Embedded, Real-Time, and Hardware-in-the-Loop Systems  
**Phase 4:** Data movement and timing  
**Status:** implemented

## Guiding question

What inputs, observable effects, and failure modes matter when you prevent Ring-Buffer Overrun?

## Computational mental model

P13 ended when a completed synthetic record became processor-visible. P14 starts at that handoff and asks
whether finite storage and an independent consumer can preserve every record. Record `i` becomes ready at

```text
a_i = (i-1) T_p.
```

The producer writes at the tail. A consumer visits every `T_c` microseconds and removes up to `B` oldest
records. The ring owns `C` usable slots, a wrapped head, a wrapped tail, and a separate occupancy count `q`:

```text
empty                    iff q = 0
full                     iff q = C
next slot                = 1 + mod(current slot, C)
q_after_consumer         = q_before - min(B, q_before)
q_after_event            = q_after_consumer + written - evicted
0 <= q <= C.
```

At the same timestamp, the consumer drains existing records first, the producer acts second, and a drain
timeout is evaluated last. A record produced at that timestamp cannot be consumed by the service that ran
just before it. Wrapped `head == tail` can mean empty or full; `q` disambiguates the two states and lets all
`C` allocated slots carry data. Nominal producer times use the origin-anchored expression `(i-1)T_p`, plus
only accumulated backpressure stall. They are not advanced by repeated addition, which could otherwise turn
a commensurate fractional-time tie into a false producer-first event through recurrence roundoff.

The unthrottled offered-load ratio is

```text
rho = producer rate / consumer capacity = T_c / (B T_p).
```

`rho <= 1` is a long-run rate condition. It does not say how much capacity a finite startup phase needs.
Conversely, a large ring can survive a finite trace with `rho > 1`, but no finite ring absorbs a positive
drift forever.

## Full-buffer policies

- **Drop newest:** reject the incoming record and preserve the older queued records.
- **Overwrite oldest:** accept the incoming record by evicting the current head record.
- **Backpressure:** retain the current record until a consumer frees a slot, then generate the next record
  one producer period later.

Drop and overwrite are data-loss policies, not overrun prevention. Backpressure prevents loss only when the
upstream producer can actually be throttled. A free-running converter or DMA request stream needs real flow
control or enough service and capacity; this model does not invent that capability.

Every record carries a source ID independently of its value. At the end of an observation, the disjoint
classification is

```text
generated = consumed + pending + dropped_newest + overwritten_oldest.
```

Pending records after cancellation are retained state, not loss. Gaps between consumed IDs reveal missing
interior records, while the full classification also catches a lost prefix or suffix.

## Deterministic baseline

The seedless baseline reuses P13's 32 codes `x_i=mod(37(i-1)+11,4096)` and declares:

- producer period `T_p=50 us`, so record attempts are `0:50:1550 us`;
- consumer start and period `T_c=200 us`;
- quota `B=4 sample/service`;
- capacity `C=8 usable sample`;
- `drop-newest`, no finite drain timeout, and continued waiting.

Consumer service at `200:200:1600 us` removes four records before the equal-time producer action. Occupancy
after producer attempts is `[1 2 3 4]` repeated eight times. Peak occupancy and the independently calculated
finite-trace requirement are both four samples. All 32 IDs are consumed in order, no full write occurs, and
residence ages repeat `[200 150 100 50] us`, giving minimum/mean/maximum `50/125/200 us`. The final drain is
at `1600 us`. Producer and consumer capacities both equal `20,000 sample/s`, so `rho=1`.

## What the learner controls

- **Capacity `C` (sample):** finite records that can remain unread at once.
- **Producer period `T_p` (us):** spacing between P13-ready records in the synthetic fixture.
- **Consumer period `T_c` (us):** spacing between consumer service opportunities.
- **Consumer quota `B` (sample/service):** oldest records removed per visit.
- **Full policy:** drop newest, overwrite oldest, or throttleable backpressure.
- **Drain timeout (us):** software observation duration after the final producer decision.
- **Timeout action:** continue waiting or cancel future consumer service while retaining queued records.
- **Scenario:** editable baseline or a fixed capacity, service, policy, or timeout diagnostic.

## Complete learning flow

1. Connect P13 record completion to a ring write and make one prediction about required finite capacity.
2. Read baseline occupancy before the residence-time view.
3. Sweep only `C=[1 2 3 4 6 8]` samples. Lost counts are `[24 16 8 0 0 0]`, peak occupancy is
   `[1 2 3 4 4 4]`, and consumed counts are `[8 16 24 32 32 32]`.
4. Reset `C=8`, then sweep only `B=[1 2 3 4 5 8]` sample/service. Offered load is
   `[400 200 133.333... 100 80 50]%`; finite-trace required capacity is `[25 18 11 4 4 4]`; loss is
   `[17 10 3 0 0 0]`; and drain time is `[3000 2200 2000 1600 1600 1600] us`.
5. Explain capacity as finite accumulation headroom and quota as service capacity, not as MATLAB settings.
6. Deliberately use overwrite-oldest with `C=4` and `B=1`. All 32 incoming writes are accepted and
   occupancy remains bounded, yet 21 old IDs disappear.
7. Compare drop, overwrite, and backpressure; then inspect timeout equality, continued wait, cancellation,
   state-free rollback, and clean recovery.
8. Run independent checks and give the two-sentence teach-back.

## Deliberately broken health criterion

The broken case asserts that “occupancy never exceeded capacity and no incoming write was rejected” proves
healthy delivery. With `C=4`, `B=1`, and overwrite-oldest, that criterion passes. The consumer receives

```text
[1 5 9 13 17 21 25 29 30 31 32]
```

while IDs

```text
[2 3 4 6 7 8 10 11 12 14 15 16 18 19 20 22 23 24 26 27 28]
```

were overwritten before consumption. The ring stayed bounded because overwrite makes room by destroying
the oldest unread record. Prevention needs zero full encounters, sufficient service/capacity, or proven
flow control—not just a bounded graph.

## Timeout, cancellation, rollback, and recovery

Drain timeout begins after the final producer decision at `1550 us`. Events at the deadline execute before
timeout evaluation. The baseline drains at `1600 us`, so a `50 us` timeout passes by equality. At `49 us`,
continue-waiting records lateness and still delivers all records. Cancel-consumer stops service at `1599 us`
after 28 records have been consumed; IDs `29:32` remain pending and loss stays zero.

Cancellation does not undo earlier consumption, discard queued entries, restore overwritten records, stop a
real converter, release a driver object, reset DMA, repair cache visibility, or recover a plant. Calling the
state-free model again with clean baseline input is computational rollback and recovery only.

## Boundaries and dependencies

The model owns one finite record list, one producer, one consumer, one counted FIFO ring, instantaneous
serialized event transitions, and named full policies. It validates source count, capacity, timing horizon,
event count, numeric identity, and timestamp precision before large allocation. It accepts row/column and
integer numeric sources through `flintmax`, character/scalar-string policies, duplicate values, and empty
defaults for policy, timeout, and action.

P13 supplies the idea of records becoming ready after data movement; P14 does not re-model bus service,
descriptor ownership, or address programming. P15 will add independent clocks and timestamps; P14 uses one
declared synthetic clock and makes no synchronization claim.

The source uses base MATLAB arrays, loops, `mod`, plots, and UI controls. It does not use a queue toolbox,
Simulink, asynchronous timers, parallel workers, device support packages, a real ISR/task pair, atomic
operations, memory barriers, cache maintenance, a physical DMA engine, or hardware flow control. Results are
deterministic simulated calculations, not MATLAB-runtime or rendered-UI evidence, numerical-fidelity
evidence from MATLAB, hardware or bench validation, HIL validation, field evidence, or production evidence.
RT1/RT2, Unreal, signing, release, deployment, staging, and production validation are not performed.

## Files

- `p14_scenario.m` owns bounded seedless baseline and diagnostic fixtures.
- `model.m` owns validation, event ordering, ring state, full policies, timeout, cancellation, and accounting.
- `experiment.m` owns the deterministic baseline, labeled complementary views, two isolated sweeps, broken
  criterion, and recovery diagnostics.
- `interactive.m` owns immediate capacity, timing, quota, policy, timeout, and scenario controls.
- `lesson.m`, `lesson.md`, and `walkthrough.md` own the mechanism-first learner sequence.
- `checks.md` and `run_checks.m` own interpretation prompts and executable invariants.
