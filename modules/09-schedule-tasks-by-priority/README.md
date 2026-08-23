# P09 — Schedule Tasks by Priority

**Track:** Embedded, Real-Time, and Hardware-in-the-Loop Systems  
**Phase 3:** RTOS behavior  
**Status:** implemented

## Guiding question

What inputs, observable effects, and failure modes matter when you schedule Tasks by Priority?

## Computational mental model

P08 treated software scheduling as part of the latency outside its DAC command model. P09 opens that boundary.
Periodic control, telemetry, and logging tasks release distinct jobs onto one CPU. At each 1 ms boundary, the
ready job with the largest fixed priority owns the next half-open interval. A higher-priority release preempts
unfinished lower-priority work; the displaced job keeps its remaining work and later resumes.

For task `i` and job `k`, the fixture declares

```text
r_i,k = phase_i + k T_i
d_i,k = r_i,k + D_i
R_i,k = f_i,k - r_i,k
```

where `T` is period, `D` is relative deadline, `r` is release, `d` is absolute deadline, and `f` is completion.
Completion at `f=d` is on time. An unfinished job at `d` times out once; policy then either lets it continue or
cancels its remaining modeled work. Utilization `U=sum(C_i/T_i)` measures average demand, but it does not say
which job receives service first.

## What the learner controls

- **Worst-case execution time, WCET (ms):** work demanded by each released job.
- **Relative deadline (ms):** release-to-completion allowance for each task.
- **Priority order:** fixed comparison used whenever more than one job is ready; larger numeric priority wins.
- **Deadline action:** continue late or cancel the remaining modeled work exactly at timeout.
- **Observation horizon (ms):** bounded interval whose releases, service, completions, and misses are retained.
- **Scenario:** selects an editable baseline, bad priority map, deadline cancellation, or heavy logger.

Periods `[5 10 20] ms`, phases `[0 0 0] ms`, the 1 ms tick, and the three task identities stay fixed in the
interactive panel so one visible mechanism changes at a time.

## Complete learning flow

1. Connect P08's omitted scheduling latency to three periodic tasks sharing one core, then predict what happens
   when control releases while logger is running.
2. Inspect the deterministic 40 ms CPU-owner timeline and per-job response/deadline view.
3. Sweep only priority order through three safe assignments; explain why response time moves between tasks even
   though periods, work, deadlines, releases, horizon, and utilization are unchanged.
4. Reset priorities to `[3 2 1]`, then sweep only logger WCET through `[2 5 8] ms`; explain why logger response
   grows while higher-priority response remains `[1 3] ms`.
5. Explain dispatch and interference from ready jobs and the fixed-priority response recurrence.
6. Break the priority map by promoting logger. Demand remains `U=0.65`, but control now misses two deadlines.
7. Compare exact-deadline completion, continue-late timeout, cancel-at-deadline, clean rollback, and recovery.
8. Run checks and teach back the inputs, observations, failure modes, and evidence boundary.

## Boundaries and dependencies

This is a deterministic, discrete-time, fixed-priority preemptive single-core calculation written with base
MATLAB arithmetic and UI primitives. Every time must align to the declared tick; values are rejected rather
than silently rounded. Releases at the horizon are excluded. Simultaneous equal-priority jobs use earliest
release, then task ID, then job sequence/FIFO. Dispatch and context-switch overhead are declared zero.
The scenario helper also derives its release count and refuses to return a fixture above the model's 10,000-job
ceiling, so every accepted built-in scenario remains runnable by its paired model.

The model retains a separate record for every job, including queued overlap, deadline outcome, cancellation,
remaining work, service, response, and preemption. It includes no locks, critical sections, resource blocking,
priority inheritance, priority ceiling, multicore migration, cache effects, interrupts, tickless operation,
dynamic priority, sporadic-server policy, or measured WCET. Locks and resource-induced priority inversion are
reserved for P10.

`cancel-at-deadline` is a synchronous calculation policy. It is not proof that an RTOS can safely abort an
arbitrary task, unwind a driver, roll back a peripheral side effect, release a mutex, or restore plant state.
Removing the policy or repairing priorities and invoking the pure function again is computational rollback and
recovery only.

The outputs are a synthetic calculation, not MATLAB-runtime evidence. They are not an RTOS trace, a processor
trace, a worst-case execution-time measurement, a response-time guarantee for hardware, bench evidence, HIL
evidence, field evidence, or production evidence.

## Files

- `p09_scenario.m` owns bounded deterministic task fixtures.
- `model.m` owns validation, releases, per-task FIFO queues, fixed-priority dispatch, deadline policy, and metrics.
- `experiment.m` owns the baseline, five labeled figures, two isolated sweeps, and deliberately broken case.
- `interactive.m` owns immediate controls and complementary CPU-owner and response/deadline views.
- `lesson.m`, `lesson.md`, and `walkthrough.md` own the mechanism-first learner sequence.
- `checks.md` and `run_checks.m` own interpretation prompts and executable invariants.
