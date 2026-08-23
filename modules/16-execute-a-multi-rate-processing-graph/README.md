# P16 — Execute a Multi-Rate Processing Graph

**Track:** Embedded, Real-Time, and Hardware-in-the-Loop Systems  
**Phase 4:** Data movement and timing  
**Status:** implemented

## Guiding question

What inputs, observable effects, and failure modes matter when you execute a Multi-Rate Processing Graph?

## Computational mental model

P15 produced ordered samples whose timestamps share a reference coordinate. P16 starts at that handoff. A
timestamp does not say when every downstream node should fire, which version of an upstream value it may
consume, or whether the available processor time can finish the work.

The deterministic graph has two rates and two serial workers:

```text
timestamped source --every sample--> two-sample fast filter
                                        |
                                        +--every D samples--> frame mean --> output
```

For an input period `T_s`, decimation factor `D`, and slow-node cost `C_slow`,

```text
T_slow = D T_s
f_slow = f_s / D
U_slow = C_slow / (D T_s)
```

The fast node makes its current result visible before a producer-first frame dispatch. Each frame then
consumes exactly `D` consecutive fast results. The slow worker starts a frame after both its inputs and the
worker are available. A frame is late only when its scheduled completion is strictly after
`release + timeout`; completion at equality is emitted first.

## Deterministic baseline

- **Source:** 32 ramp samples, `0:31` engineering units, at exact `1000 us` timestamp spacing.
- **Fast node:** transparent two-sample average, `y[0]=x[0]` and `y[n]=(x[n-1]+x[n])/2`, costing `100 us/sample`.
- **Slow node:** `D=4`, costing `1200 us/frame`, with a `2000 us` output timeout.
- **Rates:** `1000 Hz` input and `250 Hz` nominal output.
- **Demand:** slow utilization is `0.30`; inclusive outstanding depth (the arriving frame plus prior work still
  waiting or in service) stays at one frame.
- **Outputs:** `[1.125 5 9 13 17 21 25 29]` engineering units.
- **Timing:** every output latency is `1300 us`, leaving `700 us` deadline slack.

Two complementary views keep value correctness separate from timing correctness. The value view shows source,
fast-filter, and frame outputs against aligned reference time. The timing view shows output latency, timeout,
and slow-node outstanding depth.

## Lever 1 — decimation factor

Sweep only `D=[1 2 4 8]` while holding sample period and both execution costs fixed. Nominal output rate becomes
`[1000 500 250 125] Hz`, and slow utilization becomes `[1.2 0.6 0.3 0.15]`. At `D=1`, demand exceeds service
capacity: maximum outstanding depth reaches seven frames, maximum latency reaches `7500 us`, and 28 of 32 frames cross
the timeout. The calculation did not become numerically wrong; its requested rate became unsustainable.

## Lever 2 — slow-node execution cost

Reset every baseline input, then sweep only `C_slow=[200 800 1200 1800 4200] us/frame`. The corresponding slow
utilization is `[0.05 0.20 0.30 0.45 1.05]`, while maximum latency is
`[300 900 1300 1900 5700] us`. Cost consumes deadline slack without changing frame membership or nominal rate.
At `4200 us`, cost also exceeds the `4000 us` frame period, so work carries across releases.

## Deliberately broken case — consumer first

The broken graph dispatches the slow consumer at the frame timestamp before publishing the current fast result.
Frame zero asks for a prehistory value and is rejected before slow-worker admission; an underflow does not consume
phantom service or enter timeout handling. Later frames emit `[4 8 12 16 20 24 28]` instead of
`[5 9 13 17 21 25 29]`, and their consumed timestamp is one `1000 us` sample behind the expected frame timestamp.
The violated assumption is topological visibility: an edge does not make a value current until its producer has
published that firing's result. That one-sample lag is the baseline symptom, not a hard-coded rule: if the fast
worker is overloaded, consumer-first reads the latest complete visible window and can lag by multiple samples.

## Timeout, cancellation, rollback, and recovery

With `D=1`, `C_slow=1200 us`, and a `2000 us` timeout, continuing emits all 32 computed frames but marks 28 late
and lets outstanding work grow. `cancel-frame` emits the first four, cancels 28 late frames at their simulated deadlines,
and limits maximum outstanding depth to two. Cancellation does not rewrite samples or computed values. Returning every
input to baseline reproduces the baseline bit for bit; this is stateless computational recovery, not rollback of
a real processor, task, DMA engine, or plant.

## Controls

`interactive.m` exposes:

- **Samples/frame `D`:** integer rate relationship and frame size.
- **Fast cost (us/sample):** input-stage service demand.
- **Slow cost (us/frame):** frame-stage service demand and slack consumption.
- **Output timeout (us):** allowed release-to-completion latency; zero permits only exact same-time completion.
- **Timeout action:** continue processing or cancel a late frame.
- **Execution order:** producer first or the deliberately broken consumer first.
- **Reset editable:** restores the baseline directly without requiring a scenario-toggle workaround.
- **Fixed diagnostics:** unity-rate, zero-cost, broken-order, timeout-continue, and timeout-cancel cases.

Fixed diagnostics replace all editable values. Press **Reset editable** to restore baseline directly, then move one lever.

## Run

From the repository root, start the tutor-facing entry point:

```bash
./bin/learn start P16
```

In MATLAB:

```matlab
launch_lesson("P16")
run_module_checks("P16")
```

`lesson.m` runs the sectioned experiment and opens one interactive session. `experiment.m` can be run alone for
the deterministic plots. `model.m` and `p16_scenario.m` contain the presentation-free reference calculation and
fixtures. The implementation uses base MATLAB operations; no optional toolbox, Simulink graph, hardware driver,
real scheduler, or network service is required.

## Completion and forward boundary

Complete the numerical checks, answer the interpretation questions in `checks.md`, and give the two-sentence
teach-back in `walkthrough.md`. P17 owns watchdog liveness and reset/recovery behavior. P16 stops at bounded
synthetic graph execution, frame deadlines, and cancellation; it does not turn a missed frame into a hardware
watchdog claim.

The retained results are deterministic simulated references and static contracts. They are not MATLAB-runtime,
rendered-UI, numerical-fidelity, real-concurrency, processor, DMA, bench, HIL, field, RT1/RT2, Unreal, signing,
release, deployment, staging, or production evidence unless separately executed and retained on a named system.
