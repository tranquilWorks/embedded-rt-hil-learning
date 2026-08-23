# P14 lesson: Prevent Ring-Buffer Overrun

## Guiding question

What inputs, observable effects, and failure modes matter when you prevent Ring-Buffer Overrun?

## Compounds on

P13 — Move Samples with DMA.

P13 separated request, movement, and block ownership. Begin P14 only after a record is ready for downstream
processing. The new questions are finite storage, consumer service, survivor identity, and what happens at
full. Do not treat DMA completion as proof that the downstream ring can keep up.

## Read: occupancy gives wrapped pointers meaning

A ring reuses physical slots. Let `head` name the oldest unread slot, `tail` name the next write slot, and
`q` count unread records. With `C` allocated slots:

```text
empty             iff q = 0
full              iff q = C
next slot         = 1 + mod(current slot, C)
q_after_consumer  = q_before - min(B, q_before)
q_after_event     = q_after_consumer + written - evicted.
```

Every transition must retain `0<=q<=C`. Because all `C` slots are usable, `head==tail` occurs both when the
ring is empty and when it is full. A separate count or full flag is therefore part of correctness, not extra
telemetry.

Record `i` becomes producer-ready at `a_i=(i-1)T_p`. The consumer visits every `T_c` microseconds and removes
up to `B` oldest records. This lesson declares consumer-before-producer ordering at an equal timestamp. A
consumer at `t=200 us` drains records that were already present; a producer write at the same `t` happens
afterward and waits for the next service. Producer timestamps remain anchored to `(i-1)T_p` plus accumulated
backpressure stall, so repeated floating-point addition cannot manufacture a different ordering for a
commensurate fractional-time tie.

The unthrottled long-run load is

```text
rho = (1/T_p) / (B/T_c) = T_c/(B T_p).
```

`rho<=1` means service capacity is at least average input rate. It does not eliminate phase accumulation or
say how large this finite ring must be. `rho>1` means an infinite campaign has positive backlog drift, even
if a large ring survives the finite lesson trace.

## Prediction before the baseline

The baseline producer and consumer capacities are both `20,000 sample/s`. Before seeing a plot, predict
whether this phase-aligned finite trace needs one slot, four slots, or unbounded storage.

Ask for one answer, then show the baseline. Do not add another prediction before the plots.

## Baseline: read occupancy before residence time

The seedless input reuses P13's 32 source codes `mod(37(i-1)+11,4096)`. Producer attempts occur every
`50 us`; the consumer starts at `200 us`, visits every `200 us`, and removes up to four records. The ring has
eight usable slots and uses drop-newest if full.

Read the occupancy view first. Four records accumulate at `0, 50, 100, 150 us`. At `200 us`, the consumer
removes them before record five arrives. Occupancy after producer actions is therefore `[1 2 3 4]` repeated
eight times. Peak occupancy and independently calculated required capacity are four. The head and tail wrap
repeatedly; their final equality means empty only because final `q=0`.

Now inspect source identity and residence time. The consumer receives IDs `1:32` in order. Ages repeat
`[200 150 100 50] us`, so minimum/mean/maximum residence is `50/125/200 us`. The last producer action is at
`1550 us` and final drain is at `1600 us`. No full write or loss occurs.

### Observation question 1

Why does `rho=1` coexist with a four-record peak instead of zero occupancy?

Pause here. Equal average rates do not align individual events; four records arrive before each consumer
visit.

### Observation question 2

Which observation proves record identity was preserved, and which only proves storage stayed bounded?

Consumed IDs and values prove survivor ordering. `q<=C` proves only the storage bound.

## Lever 1: change finite capacity

Hold source IDs, producer and consumer timing, quota, start phase, policy, and timeout fixed. Sweep only
`C=[1 2 3 4 6 8]` usable samples:

| Capacity (sample) | Peak occupancy (sample) | Lost records (count) | Consumed records (count) |
| ---: | ---: | ---: | ---: |
| 1 | 1 | 24 | 8 |
| 2 | 2 | 16 | 16 |
| 3 | 3 | 8 | 24 |
| 4 | 4 | 0 | 32 |
| 6 | 4 | 0 | 32 |
| 8 | 4 | 0 | 32 |

The offered load remains 100%, the producer timeline remains `0:50:1550 us`, and the final consumer visit
remains `1600 us`. Capacity below four cannot absorb the phase burst. Capacity above four adds unused
headroom in this fixture; it does not create service capacity.

### Observation question 3

Why does increasing `C` from four to eight change neither drain time nor delivered IDs?

The four-slot trace already has no full encounter. Extra storage never participates.

## Reset, then lever 2: change consumer service quota

Reset `C=8` and every baseline input, then sweep only `B=[1 2 3 4 5 8]` samples per service:

| Quota (sample/service) | Offered load (%) | Required C (sample) | Peak (sample) | Lost (count) | Drain (us) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 400 | 25 | 8 | 17 | 3000 |
| 2 | 200 | 18 | 8 | 10 | 2200 |
| 3 | 133.333... | 11 | 8 | 3 | 2000 |
| 4 | 100 | 4 | 4 | 0 | 1600 |
| 5 | 80 | 4 | 4 | 0 | 1600 |
| 8 | 50 | 4 | 4 | 0 | 1600 |

Quota changes downstream capacity. At `B<4`, `rho>1`; occupancy reaches eight and drop-newest rejects later
records. Required capacity reports what an unbounded finite-trace reference would need, while peak occupancy
cannot exceed the configured eight. At `B>=4`, this trace is loss-free.

### Observation question 4

Why can required capacity be 25 while observed occupancy never exceeds eight?

The finite ring clips occupancy through a full policy. Required capacity is a separate no-loss reference;
the missing 17 records explain the difference.

## Read the mechanism after both changes

Capacity and service are independent levers:

- `C` bounds how much temporary accumulation can wait;
- `B/T_c` sets consumer service capacity;
- source IDs reveal which records survive;
- full policy chooses what happens after capacity and service are insufficient.

A capacity increase can absorb a finite burst but cannot repair sustained positive drift. A faster or larger
consumer visit reduces drift but does not retroactively restore records already lost.

## Deliberately broken case: bounded occupancy masquerades as health

Reset timing, set `C=4`, set `B=1`, and choose overwrite-oldest. All incoming writes report accepted,
occupancy stays between zero and four, and the final ring drains. A naive dashboard using only “write
accepted” plus “occupancy bounded” looks healthy.

It is not. The consumer receives `[1 5 9 13 17 21 25 29 30 31 32]`; 21 older IDs are evicted before their
turn. The violated assumption is “bounded occupancy or accepted incoming writes prove loss-free delivery.”
Overwrite keeps the newest data by sacrificing unread history.

### Observation question 5

Why is overwrite-oldest a loss policy even though it never rejects the incoming write?

Acceptance describes the new record only. The operation makes room by removing an older unread record.

## Drop, overwrite, and backpressure

Under `C=4`, `B=1` overload:

- drop-newest preserves the oldest queued records and loses 21 incoming IDs;
- overwrite-oldest accepts each incoming write and loses 21 queued IDs;
- backpressure delivers all 32 IDs but delays 27 producer actions by `150 us` each, for `4050 us` total
  producer stall; the final producer decision moves from `1550` to `5600 us`, and drain moves to `6400 us`.

Backpressure is prevention only for a producer with a real throttle contract. Applying this result to a
free-running ADC or DMA source without that contract would merely rename an upstream overflow.

## Drain timeout and cancellation

Timeout is measured after the final producer decision. Consumer and producer events at the deadline happen
before timeout evaluation. Baseline drain is `50 us` after the last producer action, so `50 us` passes.
At `49 us`, continue-waiting records lateness and drains normally. Cancel-consumer stops future service at
`1599 us`: IDs `1:28` were consumed and IDs `29:32` remain queued. Pending is not classified as loss.

Cancellation is not rollback. It does not undo earlier reads, restore overwritten records, flush a device,
stop a converter, release an OS object, or repair downstream state. A clean pure-model rerun is computational
reset and recovery only.

## Misconceptions to correct directly

- **“Average rates match, so no buffer is needed.”** Phase accumulation still needs four slots here.
- **“Occupancy never exceeded capacity, so no data were lost.”** Drop and overwrite enforce that bound by
  choosing victims.
- **“Head equals tail means empty.”** It also occurs at full when all `C` slots are usable; occupancy gives
  the equality meaning.
- **“A larger ring fixes an overloaded infinite stream.”** It delays the inevitable when `rho>1`.
- **“Overwrite is safe because the newest sample arrived.”** It destroys unread history.
- **“Backpressure always prevents ADC loss.”** Only a genuinely throttleable producer can honor it.
- **“Canceling the consumer rolls the system back.”** It leaves already consumed, lost, and pending state.

## Interpretation checks

1. Which two baseline facts establish both rate balance and enough finite capacity?
2. Why is `C=4` safe while `C=3` loses eight records?
3. What does required capacity show that clipped occupancy cannot?
4. Which IDs survive under overwrite-oldest, and why?
5. When is backpressure a valid prevention mechanism?
6. Why are pending records after cancellation not counted as lost?

## Teach-back

In two sentences, answer the guiding question. Sentence one must connect producer timing, consumer timing and
quota, usable capacity, and event ordering to occupancy. Sentence two must explain how sequence identity and
full policy distinguish true prevention from drop, overwrite, backpressure, timeout, and cancellation.

## Forward boundary and evidence boundary

P15 will align clocks with PPS and timestamps. P14 has one declared synthetic time base and proves no clock
alignment, atomic pointer update, ISR/task synchronization, cache coherence, DMA flow control, or physical
timing. The retained results are static structure and independent simulated arithmetic, not MATLAB-runtime,
rendered-UI, numerical-fidelity, bench, HIL, field, RT1/RT2, Unreal, signing, deployment, staging, or
production validation.
