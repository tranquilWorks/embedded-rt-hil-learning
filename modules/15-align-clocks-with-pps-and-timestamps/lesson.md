# P15 lesson: Align Clocks with PPS and Timestamps

## Guiding question

What inputs, observable effects, and failure modes matter when you align Clocks with PPS and Timestamps?

## Compounds on

P14 — Prevent Ring-Buffer Overrun.

P14 used source IDs to prove which records survived finite storage. Begin P15 with those records intact.
Their order and content can be correct while their local timestamps still use an offset, fast, slow, or
quantized clock. Preserved data is necessary, but it does not establish a shared time coordinate.

## Read: a pulse edge and its epoch are different information

Let reference time be `t` microseconds. This lesson's local timestamp counter is

```text
C(t) = b + r t
r    = 1 + s * 10^-6,
```

where `b` is the initial offset in microseconds and `s` is oscillator skew in parts per million. Positive
skew means the local clock accumulates more microseconds than the reference. A timestamp register with tick
`q` reports

```text
c(t) = q floor(C(t)/q).
```

PPS supplies a repeatable phase event. A received pulse still needs an identity or trusted timestamp label:

```text
t_pps(k) = k T_pps.
```

The edge says “a second boundary occurred.” Sequence ID `k` says which boundary. With retained first and last
anchor pairs `(t_1,c_1)` and `(t_N,c_N)`, estimate

```text
r_hat = (c_N-c_1)/(t_N-t_1)
b_hat = c_1-r_hat t_1
t_hat = (c_event-b_hat)/r_hat.
```

One anchor gives `b_hat` only if rate is assumed. Two distinct anchors make rate observable. More anchors can
reveal non-affine behavior through residuals, but this lesson deliberately keeps the estimator transparent
instead of hiding it behind a fitting toolbox.

## Prediction before the baseline

The baseline local clock starts `2500 us` ahead and runs `40 ppm` fast. If the first PPS removes the initial
offset, predict whether event error stays zero or grows during the next four seconds.

Ask for one answer, then show the baseline. Do not add another prediction before the plots.

## Baseline: read event error before anchor residuals

Eight events occur from `250000` through `3750000 us`. PPS IDs `0:4` arrive every `1000000 us`. The local
timestamp tick is `1 us`, so all ideal baseline captures land exactly on a tick.

First read the event-error view:

- raw local error is `[2510 2530 2550 2570 2590 2610 2630 2650] us`;
- one-PPS offset-only error is `[10 30 50 70 90 110 130 150] us`;
- the correctly associated affine correction has zero error in the governing arithmetic.

Offset-only error grows because removing a translation does not change slope. At `40 ppm`, every
`500000 us` between events adds `20 us` of local clock lead.

Now read the PPS-anchor view. Local captures are

```text
[2500 1002540 2002580 3002620 4002660] us.
```

The first-to-last local span is `4000160 us` across a `4000000 us` reference span. That ratio recovers
`r_hat=1.00004`, so `s_hat=40 ppm`; the first anchor recovers `b_hat=2500 us`. Intermediate residuals are
zero because the fixture is an ideal affine clock.

### Observation question 1

Why does one-PPS correction start near zero yet end at `150 us`?

The first edge removes offset at one instant. It supplies no independent rate estimate, so skew keeps
accumulating.

### Observation question 2

What does a zero fit residual prove here, and what does it not prove physically?

It proves the synthetic retained points lie on this affine relation. It does not prove trusted epoch labels,
hardware capture latency, oscillator stability, receiver health, MATLAB execution, or physical accuracy.

## Lever 1: change initial clock offset

Hold event times, PPS identities and period, skew, timestamp tick, association, and timeout fixed. Sweep only
`b=[0 1000 2500 5000 10000] us`:

| Offset (us) | First raw error (us) | Final raw error (us) | Estimated offset (us) |
| ---: | ---: | ---: | ---: |
| 0 | 10 | 150 | 0 |
| 1000 | 1010 | 1150 | 1000 |
| 2500 | 2510 | 2650 | 2500 |
| 5000 | 5010 | 5150 | 5000 |
| 10000 | 10010 | 10150 | 10000 |

Every curve translates by the offset change. Its `140 us` rise across the event window remains because skew
did not move. Correct affine alignment remains zero in the governing ideal arithmetic.

### Observation question 3

Why does changing offset move the first and final errors equally?

Offset is an additive coordinate translation. It does not change how much error accumulates per second.

## Reset, then lever 2: change oscillator skew

Reset `b=2500 us` and every baseline input, then sweep only
`s=[-80 -40 0 40 80] ppm`:

| Skew (ppm) | Four-second PPS drift (us) | Final raw error (us) | Offset-only max (us) |
| ---: | ---: | ---: | ---: |
| -80 | -320 | 2200 | 300 |
| -40 | -160 | 2350 | 150 |
| 0 | 0 | 2500 | 0 |
| 40 | 160 | 2650 | 150 |
| 80 | 320 | 2800 | 300 |

The sign selects fast or slow; magnitude selects the slope. The limiting equation is

```text
drift_us = s_ppm * duration_us / 10^6.
```

Correctly associated ideal first/last anchors recover every swept affine slope.

### Observation question 4

Why is the offset-only maximum the same for `-40` and `+40 ppm`?

Their errors grow in opposite directions with equal magnitude. Maximum absolute error discards the sign.

## Read the mechanism after both changes

Offset and skew are independent clock properties:

- offset says where the local coordinate starts;
- skew says how its distance changes relative to reference time;
- timestamp tick limits capture resolution;
- PPS phase marks a sharp boundary;
- PPS identity or a trusted timestamp label names that boundary's epoch.

An edge without epoch is ambiguous. An epoch message without a precisely captured edge has transport-delay
uncertainty. Alignment needs the correct association between the two.

## Deliberately broken case: received position masquerades as identity

Drop PPS ID `1`, leaving received IDs `[0 2 3 4]`. Sequence-aware association uses true reference anchors
`[0 2000000 3000000 4000000] us` and still recovers `2500 us`, `40 ppm`, and zero ideal event error.

Now ignore the IDs and pair the same four captures with received positions `[0 1000000 2000000 3000000] us`.
The endpoint calculation still returns a line and both endpoint residuals are zero. That does not make the
association correct. It estimates `333386.666... ppm`, interior residuals reach about `666693 us`, and event
errors become

```text
[-62500 -187500 -312500 -437500 -562500 -687500 -812500 -937500] us.
```

The violated assumption is “array position still identifies the second after a missing pulse.” The missing
sequence number is evidence, not an inconvenience to renumber away.

### Observation question 5

Why do zero endpoint residuals fail to protect this broken alignment?

Any two distinct points define a line. The wrong reference coordinates can force a wrong line through both
endpoints; sequence identity and interior residuals expose the mistake.

## Timestamp resolution

Changing `q` floors both event and PPS captures to a coarser local tick. Quantization can make nearby true
events share a timestamp and can bias the endpoint slope. It cannot manufacture more timing information than
the counter resolved. A precise-looking floating-point estimate derived from coarse integer ticks is not a
more precise physical clock.

The transparent double-precision model accepts absolute tick indices only through `1e12`. At larger
quotients, eight ULPs can cover enough of one tick to snap a genuinely below-boundary timestamp upward, which
would contradict `floor`. The model rejects that unresolved configuration instead of silently changing the
quantization rule.

## PPS timeout and cancellation

Timeout applies to each observed PPS gap. The declared order is capture first, timeout second at equality.
The gap from ID `0` to ID `2` is `2000000 us`, so a `2000000 us` deadline passes. At `1500000 us`:

- continue-waiting records a late gap, retains IDs `0,2,3,4`, and still performs the correct ID-aware fit;
- cancel-alignment retains only ID `0`, censors the later captures, and cannot estimate affine rate.

Cancellation leaves raw event timestamps unchanged. It does not stop or steer a hardware oscillator, undo a
capture, reset a counter, release a receiver, repair an epoch source, or restore external state. A clean
state-free model call is computational recovery only.

## Misconceptions to correct directly

- **“PPS gives absolute time.”** The edge gives phase; identity or a trusted message supplies epoch.
- **“One PPS edge calibrates the clock.”** One anchor cannot separate offset from rate.
- **“Record order means timestamps are aligned.”** P14 ordering and P15 clock coordinates are different
  properties.
- **“Zero endpoint residuals prove the association.”** Any two points define a line, including wrongly paired
  points.
- **“A missing pulse can be removed from the index.”** Renumbering destroys the elapsed-time meaning carried
  by sequence identity.
- **“A finer printed result beats timestamp resolution.”** Calculations cannot recover information discarded
  by the tick.
- **“Canceling alignment rolls the clock back.”** It only censors this synthetic observation prefix.

## Interpretation checks

1. Which baseline observations distinguish offset from skew?
2. Why are two distinct PPS anchors the minimum for affine rate estimation?
3. What information comes from the edge, and what comes from sequence/timestamp identity?
4. Why does correct ID association tolerate the missing ID `1`?
5. How can the broken endpoint residuals be zero while aligned event error is large?
6. What does timestamp tick change that adding more decimal places cannot repair?
7. Why does equality pass the PPS timeout while a strict larger gap times out?
8. Which conclusions require MATLAB runtime, a real PPS/GNSS source, bench, HIL, or field evidence?

## Teach-back

In two sentences, answer the guiding question. Sentence one must connect offset, skew, timestamp tick, PPS
phase, and trusted sequence/timestamp identity to the affine correction. Sentence two must explain how a
missing or wrongly associated pulse, timeout, cancellation, and fit residuals reveal failure without claiming
that this synthetic model validates physical synchronization.

## Forward boundary and evidence boundary

P16 will execute a multi-rate processing graph in a declared common time coordinate. P15 does not schedule,
buffer, interpolate, or retime that graph. It also does not prove receiver timestamp provenance, leap-second
handling, UTC/TAI conversion, PTP/NTP behavior, oscillator temperature response, interrupt capture latency,
counter rollover, or hardware discipline.

The retained results are static structure and independent simulated arithmetic, not MATLAB-runtime,
rendered-UI, MATLAB numerical-fidelity, PPS/GNSS receiver, physical oscillator, bench, HIL, field, RT1/RT2,
Unreal, signing, release, deployment, staging, or production validation.
