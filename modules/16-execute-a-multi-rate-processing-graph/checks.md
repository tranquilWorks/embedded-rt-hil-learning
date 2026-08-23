# P16 checks: Execute a Multi-Rate Processing Graph

Run the module checks in MATLAB only after the baseline, both isolated sweeps, and the deliberately broken
consumer-first case have been observed:

```matlab
run_module_checks("P16")
```

## Numerical invariants

`run_checks.m` independently checks:

- the exact 32-sample timestamp grid, transparent two-sample fast filter, eight `D=4` frames, output values,
  release/readiness/completion times, `1300 us` latency, `700 us` slack, and deterministic repeat;
- conservation of complete frame membership, frame timestamps, output rate, utilization, and bounded inclusive
  outstanding depth;
- an isolated `D=[1 2 4 8]` sweep with exact frame counts, output rates, utilization, timeout counts, latencies,
  and outstanding depths;
- a reset and isolated `C_slow=[200 800 1200 1800 4200] us/frame` sweep with exact latency, slack, overload,
  and outstanding-work results;
- the unity-rate and zero-cost limiting cases, including the same-timestamp producer-first rule;
- the broken consumer-first baseline underflow and one-sample lag, rejection before slow-worker admission, plus
  multi-sample lag when the fast worker is overloaded, stale frame values, and the correct comparator;
- strict timeout equality, one-microsecond lateness, continue-processing, cancellation, rollback, and clean
  stateless recovery;
- row/column, integer, scalar-string, empty-default, callback-lifetime, and conflicting-module compatibility;
- malformed type, shape, order, grid, partition, enum, precision, timeline, and resource-bound rejection.

These are deterministic calculations. The file does not use `timer`, `pause`, random input, a scheduler,
Simulink, hardware, or an opaque graph executor.

## Interpretation questions

Answer without describing MATLAB syntax:

1. What makes one slow frame eligible, data-valid, ready, started, complete, and emitted?
2. Which quantities change when `D` changes, and which change when only slow execution cost changes?
3. Why can utilization above one produce growing latency even when every frame calculation is correct?
4. Why does consumer-first order create stale data that a larger timeout cannot repair?
5. Why does completion at exact timeout equality emit before timeout handling?
6. What does `cancel-frame` preserve, remove, and change for future simulated work?
7. Which conclusions are deterministic simulated references, and which would require MATLAB-runtime, rendered-UI,
   real-concurrency, processor, bench, HIL, or field evidence?

## Teach-back

Give two sentences answering: “What inputs, observable effects, and failure modes matter when you execute a
Multi-Rate Processing Graph?” Include aligned values/timestamps, `D`, order, cost, worker availability, timeout
policy, output value/rate, timestamp error, latency/slack, outstanding depth, underflow, and cancellation. Then state why
these checks are not MATLAB-runtime, rendered-UI, hardware, bench, HIL, field, RT1/RT2, Unreal, signing, release,
deployment, staging, or production validation unless separately run and retained on a named environment.
