# P16 lesson: Execute a Multi-Rate Processing Graph

## Guiding question

What inputs, observable effects, and failure modes matter when you execute a Multi-Rate Processing Graph?

## Compounds on

P15 — Align Clocks with PPS and Timestamps.

P15 made timestamp origin, rate, resolution, and event identity explicit. P16 assumes the 32 synthetic input
timestamps are already aligned, ordered, and uniformly spaced. It asks the next question: how do those samples
move through nodes that fire at different rates without consuming stale data or accumulating more work than a
worker can serve?

## Read: rate, data dependency, and execution demand are different contracts

A block diagram is not yet an execution contract. For each node, identify:

1. the input values and timestamps it consumes;
2. the firing rule that says when it becomes eligible;
3. the predecessor result version that must already be visible;
4. the execution cost and serial worker that determine finish time;
5. the output deadline and what happens after it is crossed.

The P16 graph is intentionally small:

```text
x[n], t[n] --> fast two-sample filter --> D-value frame mean --> output
                 every sample              every D samples
```

The transparent fast rule is

```text
y[0] = x[0]
y[n] = (x[n-1] + x[n]) / 2, n > 0.
```

The slow frame period, rate, and utilization are

```text
T_slow = D T_s
f_slow = f_s / D
U_slow = C_slow / (D T_s).
```

`U_slow` is demand divided by capacity on the slow worker. It says whether backlog can grow in this periodic
fixture; it does not by itself prove a particular frame met its timeout. Latency still follows the release,
readiness, worker-availability, start, and finish recurrence:

```text
start[k]  = max(input_ready[k], previous_stop[k])
finish[k] = start[k] + C_slow
late[k]   = finish[k] > release[k] + timeout.
```

Completion at equality is visible before timeout handling. Releases come directly from aligned source indices,
not repeated floating-point addition. Cancellation is a deterministic model action, not a real wait.

## Prediction before the baseline

The baseline slow node costs `1200 us` and fires every `D T_s = 4000 us`. If only `D` changes from four to one,
will inclusive outstanding depth stay at one because the node's code did not change, or grow because jobs arrive
faster than the worker can finish them?

Make this one prediction, then inspect the baseline before changing anything.

## Baseline: read values before timing

The source is the ramp `0:31` at exact `1000 us` intervals. The fast output begins
`[0 0.5 1.5 2.5 ...]`. With `D=4`, each slow firing consumes one disjoint four-value frame and emits

```text
[1.125 5 9 13 17 21 25 29] engineering units.
```

Read the first plot as a data-dependency view. Each stem lies at the mean aligned timestamp of the four expected
samples. An output value can be plausible while its sample membership or timestamp is wrong, so do not infer
timing correctness from the curve shape.

### Observation question 1

Why is the first frame `1.125` rather than the mean of raw inputs `[0 1 2 3]`?

Because the slow node consumes fast-filter outputs `[0 0.5 1.5 2.5]`, not the original source vector. The edge
defines both the producer and the value version.

## Baseline: read timing separately

The final source value for each frame arrives at its release. The fast node completes it `100 us` later, then the
slow node consumes `1200 us`. Every output latency is therefore `1300 us`, every timeout slack is `700 us`, and
inclusive outstanding depth remains one. This depth counts the arriving frame plus prior frames still waiting or
in service; it is not the conventional waiting-only queue length. The nominal rates are `1000 Hz` input and `250 Hz` output; slow utilization is
`1200/4000 = 0.30`.

### Observation question 2

Does outstanding depth one mean all multi-rate graphs with `D=4` are safe?

No. It describes these costs, worker separation, timestamps, and horizon. Larger fast cost can postpone input
readiness; larger slow cost can consume slack or exceed the frame period; different order can consume stale data.

## Lever 1: change decimation factor

Sweep only `D=[1 2 4 8]`, resetting all other inputs for each run.

| `D` (sample/frame) | output rate (Hz) | slow utilization | timed-out frames | max outstanding (frame) |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 1000 | 1.20 | 28 | 7 |
| 2 | 500 | 0.60 | 0 | 1 |
| 4 | 250 | 0.30 | 0 | 1 |
| 8 | 125 | 0.15 | 0 | 1 |

### Observation question 3

At `D=1`, why do later frames time out even though the first four finish within `2000 us` of release?

Each `1200 us` job arrives only `1000 us` after the previous job. The worker inherits `200 us` more backlog per
frame. Latency grows from `1300 us`; by the fifth frame it is `2100 us`, strictly beyond the timeout.

## Reset, then lever 2: change slow-node cost

Return to `D=4`, then sweep only `C_slow=[200 800 1200 1800 4200] us/frame`.

| cost (us/frame) | utilization | maximum latency (us) | minimum slack (us) | max outstanding (frame) |
| ---: | ---: | ---: | ---: | ---: |
| 200 | 0.05 | 300 | 1700 | 1 |
| 800 | 0.20 | 900 | 1100 | 1 |
| 1200 | 0.30 | 1300 | 700 | 1 |
| 1800 | 0.45 | 1900 | 100 | 1 |
| 4200 | 1.05 | 5700 | -3700 | 2 |

### Observation question 4

What stays unchanged while cost rises?

The input timestamps, `D`, frame membership, frame values, and nominal `250 Hz` rate remain fixed. Cost moves
start/finish behavior and slack. At `4200 us`, it also exceeds the `4000 us` service interval, so backlog grows.

## Read the mechanism after both changes

The two levers enter different parts of the same ratio:

```text
U_slow = C_slow / (D T_s).
```

Changing `D` alters the graph's rate relation and frame membership. Changing `C_slow` alters work per firing.
Both can raise utilization, but only the first changes nominal output rate and number of frames. A plot of demand
without units or a block diagram without worker/order semantics hides that distinction.

## Deliberately broken case: consumer runs before its current producer

The correct same-timestamp rule publishes a zero-cost fast result before dispatching its dependent slow firing.
The diagnostic reverses this order. Frame zero has no complete predecessor window and underflows. Each later frame
uses the previous fast result in place of the current one, so its consumed timestamp is `-1000 us` relative to the
expected frame timestamp and its ramp output is one engineering unit low:

```text
correct: [1.125 5 9 13 17 21 25 29]
broken:  [NaN   4 8 12 16 20 24 28].
```

The invalid first firing is rejected before slow-worker admission: it has no data-ready, slow-start, finish,
timeout, or cancellation event and cannot delay a later valid frame. Treating an absent input window as a real
slow job would create phantom service demand and false downstream latency.

That one-sample lag is the baseline diagnostic. The model does not assume it: when the fast worker itself is
overloaded, consumer-first uses the latest complete visible `D`-value window, so underflow and lag can grow.

### Observation question 5

Why is this not fixed by giving the consumer more deadline slack?

Slack changes when a result finishes. It cannot change which upstream version the consumer read. The violated
assumption is topological visibility, not processor capacity.

## Timeout, cancellation, rollback, and recovery

In the overloaded `D=1` case, `continue-processing` emits all 32 numerical results and marks 28 late; maximum
outstanding depth reaches seven. `cancel-frame` terminates a late simulated job at its deadline, emits only the first
four, cancels 28, and limits maximum outstanding depth to two. The computed frame values and source inputs are identical
between actions. Cancellation changes output availability and future worker availability, not history.

A clean rerun of baseline inputs exactly recovers the baseline. Call that stateless computational recovery. It is
not rollback of processor memory, task state, DMA ownership, an actuator, or a plant. P17 introduces watchdog
liveness and reset behavior; P16 does not pre-claim it.

## Misconceptions to correct directly

- **“Different rates just mean different plot spacing.”** No. They change firing counts, frame membership, and
  execution demand.
- **“A correct numerical formula guarantees a timely graph.”** No. Values, readiness, worker capacity, and
  deadline policy are separate contracts.
- **“Utilization below one proves every deadline.”** No. It prevents unbounded periodic backlog in this isolated
  worker model; readiness delay and a tighter timeout can still fail.
- **“More timeout fixes stale data.”** No. A producer/consumer order bug changes data version, not just latency.
- **“Cancellation repairs the missed frame.”** No. It removes that output and changes later worker availability.
- **“This plot proves a real scheduler or HIL target.”** No. It is a deterministic simulated reference.

## Interpretation checks

1. Identify the values, timestamps, rate relation, execution order, costs, and timeout policy needed to reproduce
   one P16 run.
2. Explain why `D=1` has slow utilization `1.2` and why its timeout count is not 32.
3. Distinguish the effect of changing `D` from changing `C_slow`.
4. Explain the initial underflow and one-sample timestamp lag in the broken order case.
5. State why exact-timeout equality emits, while a completion one microsecond later is late.
6. Explain what cancellation changes, what it preserves, and how clean rerun recovery works.

## Teach-back

In two sentences, answer the guiding question. First connect aligned sample values/timestamps, integer rate
relations, topological visibility, execution costs, worker availability, and deadlines to graph outputs. Second
explain how overload, stale consumption, underflow, timeout/cancellation, and the evidence boundary become visible
in values, timestamp error, latency, slack, outstanding depth, and dropped-frame metrics.

## Forward boundary and evidence boundary

P17 owns watchdog heartbeat, timeout, reset, and recovery teaching. P16 stops after deterministic graph dispatch,
deadline/cancellation accounting, and stateless rerun recovery.

Repository tests exercise static source structure and an independent Python reference. Unless a separately named
run is retained, the MATLAB source, executable checks, and UI have not run in MATLAB. No real scheduler,
concurrency, processor, DMA, physical hardware, bench, HIL, field, RT1/RT2, Unreal, signing, release, deployment,
staging, or production validation is implied.
