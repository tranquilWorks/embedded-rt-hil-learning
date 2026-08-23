# Lesson: Schedule Tasks by Priority

## Guiding question

What inputs, observable effects, and failure modes matter when you schedule Tasks by Priority?

## Connection to P08

P08 separated a requested DAC voltage, recorded command, active latch, and analog settling. It also said that a
real command-latency budget must include software scheduling. P09 now opens that upstream layer. Before a task
can offer the peripheral command, its released job must obtain CPU time. A correct priority schedule therefore
supports a latency budget, but it still does not prove the command latched or the output settled.

P01 first showed that logically correct work can finish late and that average utilization is not a sufficient
schedulability test. P09 advances that observation with configurable priorities, distinct queued jobs, explicit
tie-breaking, preemption/resume events, response time, and an exact deadline policy.

## One declared scheduler

The baseline has one CPU and three independent periodic tasks:

| Task | Period `T` (ms) | WCET `C` (ms) | Deadline `D` (ms) | Priority |
| --- | ---: | ---: | ---: | ---: |
| Control | 5 | 1 | 5 | 3 |
| Telemetry | 10 | 2 | 10 | 2 |
| Logger | 20 | 5 | 20 | 1 |

All phases are zero, the tick is 1 ms, and the observation horizon is 40 ms. Larger numeric priority wins.
The half-open interval `[t,t+1)` belongs to one selected job or is idle. Dispatch and context-switch overhead
are zero, so every busy tick contributes exactly 1 ms of service.

For task `i`, job `k` has

```text
release:            r_i,k = phase_i + k T_i
absolute deadline:  d_i,k = r_i,k + D_i
response:           R_i,k = f_i,k - r_i,k.
```

Every release creates a separate record. A new release never overwrites unfinished work or its deadline. Jobs
from one task remain FIFO. Across ready tasks the model selects the largest priority; equal priority uses the
earliest release, then smaller task ID, then job sequence. This declared tie rule is deterministic, not a claim
about every RTOS.

## One prediction before the baseline

At 3 ms the first logger job begins. It still has work when control releases again at 5 ms. Predict who owns
`[5,6) ms`, what happens to the logger's remaining work, and whether that ownership change is a completion,
preemption, or cancellation.

## Baseline observations

The first 20 ms owner sequence is

```text
1 2 2 3 3 1 3 3 3 0 1 2 2 0 0 1 0 0 0 0
```

and it repeats over the second 20 ms. Control releases at 5 ms while logger is unfinished, so control runs for
`[5,6) ms`. Logger keeps three remaining ticks and resumes at 6 ms. The same event occurs at 25 ms, producing
two logger-to-control preemptions. A switch after a completion, cancellation, or idle interval is not counted
as a preemption.

The 40 ms horizon retains releases `[8 4 2]` and service `[8 8 10] ms`. Nominal utilization is

```text
U = sum(C_i/T_i) = 1/5 + 2/10 + 5/20 = 0.65.
```

Busy time is 26 ms and idle time is 14 ms. Observed worst response is `[1 3 9] ms`, and every job whose
deadline occurs in the horizon meets it. Completion exactly at an absolute deadline is on time.

## Why priority changes response

A lower-priority job is delayed by its own work plus releases from higher-priority tasks. Under the declared
independent preemptive assumptions, a fixed-priority response calculation iterates

```text
R_i(next) = C_i + sum over h with P_h>P_i of ceil(R_i/T_h) C_h.
```

For the baseline this gives `R_control=1 ms`, `R_telemetry=3 ms`, and `R_logger=9 ms`, matching the retained
schedule. The recurrence is an explanatory independent calculation for this task model. It is not valid after
silently adding blocking, interrupts, release jitter, dispatch overhead, self-suspension, multicore migration,
or unmeasured execution demand.

## Lever 1: fixed-priority assignment

Hold periods, WCET, deadlines, phases, tick, horizon, releases, and deadline action fixed. Sweep the priority
vectors

```text
[3 2 1] -> worst response [1 3 9] ms
[2 3 1] -> worst response [3 2 9] ms
[3 1 2] -> worst response [1 9 7] ms.
```

All three safe assignments retain `U=0.65` and zero misses. Priority does not create CPU capacity; it decides
which ready job receives that capacity and therefore who suffers interference.

## Lever 2: logger execution time

Reset priority to `[3 2 1]`. Hold every other input fixed and sweep only logger WCET through `[2 5 8] ms`.
Utilization becomes `[0.50 0.65 0.80]`, and logger worst response becomes `[5 9 15] ms`. Control and telemetry
remain `[1 3] ms` because a ready lower-priority logger cannot delay them in this model. This invariant is also
the boundary to P10: resource blocking and inherited or effective priorities do not exist here.

## Deliberately broken assumption: any priority map is safe below 100 percent

Promote the long logger above the deadline-sensitive tasks with priorities `[2 1 3]`. Periods, work, deadlines,
phases, releases, horizon, and `U=0.65` do not change. Logger now finishes quickly, but observed worst responses
become `[6 9 5] ms`; two control jobs exceed their 5 ms deadlines.

The violated assumption is not merely “the model is wrong.” It is: utilization below one makes every priority
assignment safe. Average capacity is necessary for this periodic task set, but priority determines worst-case
interference. Resetting priorities and invoking the state-free model again exactly restores the baseline.

## Deadline timeout and cancellation policy

At each boundary, completion from the preceding interval is already effective. The model then marks each
unfinished job whose absolute deadline is that boundary exactly once. Under `continue-late`, the job remains
ready and can complete late. Under `cancel-at-deadline`, its unserved work is removed before the next dispatch.
The final horizon boundary is also checked, while releases exactly at the horizon are excluded.

For one task with `T=5 ms`, `C=5 ms`, and `D=5 ms`, completion at 5 ms passes. With `C=6 ms`, timeout occurs
at 5 ms. Continue-late completes at 6 ms; cancel-at-deadline records 5 ms service, one canceled millisecond,
and no completion. A later job whose deadline lies beyond the horizon is unfinished, not falsely missed.

This cancellation is only a synchronous model policy. It does not establish an asynchronous RTOS task-delete
API, safe mutex cleanup, peripheral rollback, or plant recovery. Removing the policy is computational rollback;
a clean repeated call is state-isolated recovery.

## Limiting cases and exact boundaries

- A zero-WCET job completes at its release without consuming a CPU interval.
- If all released work completes, `busy+idle=horizon` and released demand equals served work.
- If work remains or is canceled, released demand equals served plus remaining plus canceled work.
- A phase at or beyond the horizon produces no release in the half-open observation.
- A deadline beyond the horizon is not observed and must not be called a pass or miss.
- Equal-priority simultaneous jobs follow task ID; an older equal-priority job is not time-sliced away.
- Non-grid-aligned timing is malformed input, not silently rounded scheduler behavior.
- Multiple releases of an overloaded task remain separate queued jobs with separate deadlines.

## Common mistakes

- `U<1` does not prove an arbitrary fixed-priority assignment is schedulable.
- Highest priority is not “fastest task”; priority is a dispatch relation, while WCET is demanded work.
- A preempted job is ready and unfinished, not canceled or restarted from zero.
- Completed-only worst response must be read beside miss, cancellation, and unfinished counts.
- Equal numeric priority needs an explicit deterministic tie policy.
- A finite simulated horizon cannot prove a worst case that occurs later.
- A modeled WCET is an input, not a measured upper bound on a processor.
- Priority inversion requires resource blocking; it is not the ordinary delay of lower-priority work modeled here.

## Completion standard

Explain release, ready state, fixed priority, deterministic ties, preemption/resume, completion, response time,
deadline timeout, cancellation policy, utilization, and the two lever effects. Diagnose the bad priority map,
state the P10 and evidence boundaries, pass `run_checks.m`, and answer the teach-back in `checks.md` without
relying on MATLAB syntax.
