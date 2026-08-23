# Checks: Schedule Tasks by Priority

## Observation check

On the baseline owner view, identify the releases at 0 and 5 ms, the ready set, selected priorities, logger
preemption and resume, completion boundaries, and idle intervals. Then use the job view to distinguish release,
response time, relative deadline, absolute deadline, timeout, cancellation, and unfinished-at-horizon state.

## Independent calculations

- Calculate `U=1/5+2/10+5/20=0.65`, 26 ms busy, and 14 ms idle in the 40 ms baseline.
- Reconstruct the first 20 owner slots as `1 2 2 3 3 1 3 3 3 0 1 2 2 0 0 1 0 0 0 0`.
- Count releases `[8 4 2]`, service `[8 8 10] ms`, and two logger-to-control preemptions.
- Iterate `R_i(next)=C_i+sum ceil(R_i/T_h)C_h` to obtain `[1 3 9] ms` for the clean priority order.
- Explain why completion at `f=d` passes, but one remaining tick at `d` times out.

## Limiting cases and compatibility

- Why does a zero-WCET job complete at release while the CPU remains idle?
- Why is a task phased at the horizon never released into the half-open observation?
- How do equal-priority simultaneous jobs use task ID, and why does an older equal-priority job remain FIFO?
- Why is a deadline beyond the horizon unobserved rather than passed or missed?
- Why must row, column, integer-class, and scalar-string inputs normalize to the same result?
- Why are times rejected when they do not align to `tickMs` rather than rounded silently?

## Two independent levers

Sweep only priority assignment through `[3 2 1]`, `[2 3 1]`, and `[3 1 2]`. Require unchanged timing,
releases, work, horizon, utilization, and zero misses while worst response changes to `[1 3 9]`, `[3 2 9]`,
and `[1 9 7] ms`.

Reset priorities, then sweep only logger WCET through `[2 5 8] ms`. Require utilization
`[0.50 0.65 0.80]`, logger response `[5 9 15] ms`, unchanged releases and deadlines, unchanged priority, and
unchanged higher-priority responses `[1 3] ms`.

## Deliberately broken priority assignment

Promote logger with priorities `[2 1 3]`. Require the same periods, WCET, deadlines, phases, releases, horizon,
and `U=0.65`, but worst responses `[6 9 5] ms` and miss counts `[2 0 0]`. The symptom disproves the named
assumption that utilization below one makes every priority map safe. Restore `[3 2 1]` and require exact
`isequaln` rollback and recovery.

## Timeout, cancellation, rollback, and recovery

For `T=5`, `C=D=5 ms`, require completion exactly at the deadline with no timeout. Increase only `C` to 6 ms:
`continue-late` must mark one miss at 5 ms and finish at 6 ms. `cancel-at-deadline` must retain 5 ms service,
cancel exactly one remaining millisecond before dispatch, and leave no invented completion. A later job whose
deadline lies beyond the 7 ms horizon remains unfinished, not missed.

Reset to `continue-late` and require the exact late result. Re-run the clean baseline after broken, canceled,
and malformed calls and require exact recovery. This is pure computational rollback; it is not an RTOS task
abort, mutex cleanup, peripheral undo, or physical safe-state transition.

## Positive, negative, malformed, isolation, and resource cases

Confirm exact release-before-dispatch behavior, per-job FIFO queues, no lower-priority execution while higher
priority is ready, completion/deadline equality, one-shot miss accounting, service/demand conservation, and
bounded owner IDs. Reject wrong arity; unequal vector lengths; matrices; text, logical, complex, nonfinite,
negative, zero where prohibited, fractional-priority, non-grid-aligned, unsupported deadline-action, excessive
task-count, tick-count, and derived job-count inputs before schedule allocation. A rejected call must not alter
the next valid result. Require the largest accepted built-in scenario horizon, 28,570 ms, to produce exactly
10,000 jobs and run through `model`; reject 28,571 ms before returning an incompatible fixture.

## Interpretation and transfer

Choose one real control application. State each task's release source, measured or justified WCET evidence,
relative deadline, fixed-priority rationale, equal-priority rule, preemption and cancellation safety, dispatch
and interrupt overhead, shared-resource policy, overload behavior, observation horizon, clock resolution, and
named processor/RTOS validation environment. Keep modeled demand, simulated schedule, runtime trace, and
physical outcome claims separate.

## Teach-back

In two sentences, answer the guiding question. Sentence one must connect period, phase, WCET, deadline,
priority, ready jobs, deterministic tie-breaking, preemption/resume, response time, utilization, and the two
lever effects. Sentence two must distinguish bad priority assignment, timeout, continue-late, modeled
cancellation, queued backlog, rollback/recovery, the P10 resource-blocking boundary, and the RTOS/processor
evidence still required—without relying on MATLAB syntax.

## Executable check

Run:

```matlab
run_checks
```

All assertions must pass before personal learner completion is recorded.
