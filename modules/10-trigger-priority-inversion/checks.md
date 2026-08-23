# Checks: Trigger Priority Inversion

## Observation check

On the baseline views, identify the Low mutex acquisition at 0 ms, Medium service at 1 ms, High request and
block at 2 ms, Low's donation interval, unlock at 5 ms, High completion at 7 ms, and later Low and Medium
completion. Explain why CPU owner, mutex owner, ready state, blocked state, base priority, and effective priority
must be read as separate signals.

## Independent calculations

- At the High request, calculate the three remaining Low critical ticks and four remaining Medium ticks.
- Calculate plain-mutex `W_H=3+4=7 ms` and `R_H=7+2=9 ms`.
- Calculate inherited `W_H=3+0=3 ms` and `R_H=3+2=5 ms`.
- Confirm that High's absolute deadline is `2+6=8 ms`, so completion at 7 passes and completion at 11 misses.
- Account for 13 ms released work as 13 served in the baseline and as 11 served plus 2 canceled in the waiter-
  cancellation diagnostic.

## Limiting cases and compatibility

- Why do plain and inherited protocols agree when Medium work is zero?
- Why does one Low critical tick unlock before High releases and produce no mutex wait?
- Why does High acquiring first eliminate the trigger even though the priority order is unchanged?
- Why does completion exactly at an absolute deadline pass while one unfinished tick misses?
- Why is a release at the horizon excluded, and why must a short horizon retain remaining work?
- Why must row, column, integer-class, scalar-string, omitted-timeout, and empty-default inputs normalize to the
  same result?
- Why are non-grid times rejected rather than silently rounded?

## Two independent levers

Sweep only Medium work through `[1 3 5 7] ms`. Require plain High wait `[3 5 7 9] ms`, response
`[5 7 9 11] ms`, and third-party delay `[0 2 4 6] ms`; inherited wait and response remain 3 and 5 ms. Direct
blocking remains 3 ms. Releases, lock work, deadlines, base priorities, tick, horizon, and timeout stay fixed.

Reset Medium to 5 ms and inheritance on. Sweep Low critical work `[1 2 3 4 5] ms` while Low total work stays
6 ms. Require High direct wait `[0 1 2 3 4] ms`, response `[2 3 4 5 6] ms`, no third-party delay, and no miss.

## Deliberately broken mutex policy

Change only the protocol to plain mutex. Require identical numeric input, service `[6 5 2] ms`, released
demand 13 ms, and base priorities `[1 2 3]`. High must wait 7 ms: 3 ms owner service plus 4 ms Medium service.
Its response becomes 9 ms and it misses once. The symptom disproves the assumption that mutual exclusion alone
preserves fixed-priority response. Restore inheritance and require exact `isequaln` rollback and recovery.

## Timeout, cancellation, rollback, and recovery

With a 3 ms High wait limit and `cancel-waiter`, Low's unlock at 5 ms occurs at the timeout boundary and wins;
High acquires without timeout. With a 2 ms limit and `continue-waiting`, record timeout at 4 ms but preserve
donation and completion. With `cancel-waiter`, cancel High at 4 ms, withdraw Low's donation, retain Low mutex
ownership until 9 ms, and conserve 11 served plus 2 canceled milliseconds.

Re-run the clean baseline after plain-mutex, timeout, cancellation, short-horizon, and malformed calls and
require exact recovery. This is pure computational rollback. It is not asynchronous task deletion, arbitrary
mutex cleanup, shared-data repair, peripheral undo, or a physical safe-state transition.

## Positive, negative, malformed, isolation, and resource cases

Confirm mutual exclusion, blocked tasks never executing, owner retention while preempted, base-priority
immutability, same-interval donation, immediate deboost at unlock/cancel, one-shot timeout/miss accounting,
bounded owner IDs, task-state exclusivity, and work/time conservation. Reject wrong arity; unequal vectors;
matrices; text, logical, complex, nonfinite finite-time inputs; negative work or release; zero deadline/tick/
horizon/timeout; fractional priority; non-grid timing; unsupported protocol or timeout action; more than 16
tasks; more than 100,000 horizon ticks; and finite task time above one billion ticks. Verify the exact accepted
task and horizon bounds and rejection immediately beyond each.

## Interpretation questions

1. Which portion of High's wait is necessary owner service, and which portion is priority inversion?
2. Why is Medium's first tick at 1 ms ordinary service rather than inversion delay?
3. Why does inheritance change Low's effective priority without changing its base priority or critical work?
4. Why must canceling High withdraw donation but leave Low's mutex ownership untouched?
5. What additional lock topology, scheduler overhead, measured timing, and target behavior would be required
   before applying this result to a real RTOS?

## Teach-back

In two sentences, answer: “What inputs, observable effects, and failure modes matter when you trigger Priority
Inversion?” Sentence one must connect contention phasing, ownership, blocked High, Medium interference, direct
blocking, and effective-priority inheritance. Sentence two must connect deadline failure, critical-section
length, timeout/cancellation ownership, recovery, the P11 design boundary, and why this synthetic calculation
is not MATLAB-runtime, RTOS, processor, hardware, bench, HIL, field, or production evidence.
