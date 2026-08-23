# Lesson: Trigger Priority Inversion

## Guiding question

What inputs, observable effects, and failure modes matter when you trigger Priority Inversion?

## Connection to P09

P09 ran the highest-priority ready job. Its lower-priority Logger could never delay ready Control work, because
the jobs were independent. It explicitly reserved locks, resource blocking, and priority inheritance for P10.
P10 preserves the same single-core fixed-priority rule but adds one owned mutex. High can now be not ready for
a reason unrelated to its own CPU demand: it needs a resource held by Low.

This distinction is the heart of priority inversion. Ordinary priority interference says a ready higher task
delays a ready lower task. Inversion says High is blocked on Low while an unrelated Medium task, whose base
priority lies between them, runs ahead of the resource owner and indirectly delays High.

## One declared mutex experiment

The deterministic fixture has one one-shot job per task:

| Task | Release (ms) | Pre-critical (ms) | Critical (ms) | Post-critical (ms) | Deadline (ms) | Base priority |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Low owner | 0 | 0 | 4 | 2 | 20 | 1 |
| Medium worker | 1 | 5 | 0 | 0 | 20 | 2 |
| High control | 2 | 0 | 1 | 1 | 6 | 3 |

All times align to a 1 ms tick and the half-open horizon is 16 ms. A task with zero critical work never requests
the mutex. Otherwise it requests only when selected after its pre-critical service. A blocked task leaves the
ready set, but the owner retains the mutex even while preempted.

Larger effective priority runs. Equal effective priorities use earlier release, then smaller task ID. With a
plain mutex, effective priority always equals base priority. With direct priority inheritance,

```text
P_effective,owner = max(P_base,owner, P_base of every current waiter).
```

The base-priority input never mutates. Donation begins as soon as High blocks and disappears when Low unlocks
or when the waiter is canceled.

## One prediction before the baseline

Low owns the mutex after `[0,1) ms`. Medium runs in `[1,2) ms`. At 2 ms High releases, is selected, requests
the Low-owned mutex, and blocks without consuming CPU service. With priority inheritance enabled, predict who
owns `[2,3) ms`, what Low's effective priority is, and whether Medium is ready, blocked, or running.

## Baseline observations

The inherited CPU-owner sequence is

```text
1 2 1 1 1 3 3 2 2 2 2 1 1 0 0 0
```

while mutex ownership is

```text
1 1 1 1 1 3 0 0 0 0 0 0 0 0 0 0.
```

At 2 ms High blocks. Low has already completed one of its four critical ticks, so three mutex-held ticks remain.
Low's effective priority becomes 3 for intervals starting at 2, 3, and 4 ms. Medium remains ready but cannot
preempt the donated priority. Low unlocks at 5 ms; High acquires immediately, executes one critical and one
post-critical tick, and completes at 7 ms. Its response is `7-2=5 ms`, so it meets the absolute deadline at
`2+6=8 ms`.

Low later finishes at 13 ms and Medium at 11 ms. The 13 ms of released work equals 13 ms of served work. Busy
and idle time are 13 and 3 ms. CPU ownership, mutex ownership, readiness, blocking, and effective priority are
separate outputs because conflating them hides the mechanism.

## Direct blocking versus inversion delay

High requests the mutex at `t_request,H` and acquires at `t_acquire,H`:

```text
W_H = t_acquire,H - t_request,H
W_H = B_direct + I_third-party
R_H = W_H + C_H.
```

`B_direct` counts Low service while High waits; that service is necessary to reach unlock. `I_third-party`
counts service by a task that neither waits for nor owns this mutex. In the baseline,

```text
B_direct = 3 ms
I_third-party = 0 ms
W_H = 3 ms
C_H = 2 ms
R_H = 5 ms.
```

Priority inheritance does not make the critical section faster. It prevents Medium from taking CPU time while
High depends on Low.

## Lever 1: Medium CPU work

Hold releases, Low and High work, deadlines, base priorities, tick, horizon, timeout, and critical-section
placement fixed. Sweep Medium work through `[1 3 5 7] ms` and compare both protocols.

```text
Medium work                 1  3  5  7 ms
High wait, plain mutex      3  5  7  9 ms
High response, plain        5  7  9 11 ms
Third-party delay, plain    0  2  4  6 ms
High response, inheritance  5  5  5  5 ms
```

Medium runs for one tick before High releases when it has work. Under a plain mutex, all remaining Medium work
runs while High is blocked. Under inheritance, Low outranks Medium for exactly the donation interval. Direct
blocking remains 3 ms in both cases.

## Lever 2: Low mutex-held share

Reset Medium to 5 ms and keep priority inheritance. Low always has 6 ms total work, but move its critical share
through `[1 2 3 4 5] ms` while post-critical work changes to `[5 4 3 2 1] ms`.

```text
Low critical work  1  2  3  4  5 ms
High direct wait   0  1  2  3  4 ms
High response      2  3  4  5  6 ms
```

With one critical tick, Low unlocks before High releases, so there is no conflict. Each additional held tick
adds one direct waiting tick. The 5 ms case completes High exactly at its absolute deadline and therefore
passes. This lever shows why correct inheritance is not permission to make critical sections arbitrarily long.

## Deliberately broken assumption: a mutex alone preserves priority timing

Disable inheritance and change nothing else. At 2 ms High blocks, but Low stays at priority 1. Medium retains
four ticks and runs through 6 ms. Low then completes its remaining three critical ticks and unlocks at 9 ms.
High waits 7 ms:

```text
W_H = 3 ms direct Low service + 4 ms Medium interference = 7 ms
R_H = 7 + 2 = 9 ms.
```

High is still incomplete at its absolute deadline of 8 ms and misses once. Because these jobs are one-shot, this
model does not define periodic utilization. Released demand, task releases, base priorities, total service, and
the 16 ms observation horizon did not change. The violated assumption is that mutual exclusion by itself
preserves fixed-priority response. Restore inheritance and the state-free calculation reproduces the baseline
exactly.

Trigger order also matters. If High releases at 0 ms, it acquires first and never blocks. Priority numbers alone
do not create inversion; Low must own the needed mutex before High requests it.

## Wait timeout, cancellation, and ownership

Wait time starts when a selected task first finds the mutex owned, not at job release. Prior-slot unlock is
applied before timeout at the same boundary. Therefore a 3 ms timeout lets the baseline High acquire at 5 ms
without timing out. A 2 ms timeout expires at 4 ms.

With `continue-waiting`, the timeout is recorded once, High remains blocked, donation remains active, and the
baseline schedule still completes. With `cancel-waiter`, High's two unserved ticks become canceled work at
4 ms and donation is withdrawn. Medium then preempts Low. Low remains the mutex owner until its own service
reaches unlock at 9 ms. A waiter cannot release a mutex it never owned.

Deadline expiration is checked before wait timeout at the same boundary. Completion or unlock from the prior
interval is already effective. These are deterministic analytical rules, not claims about a particular kernel.
Waiter cancellation is not asynchronous task deletion, stack unwinding, driver cleanup, shared-data repair,
peripheral rollback, or plant recovery.

## Limiting cases and resource bounds

- Zero Medium work makes plain and inherited outcomes identical because there is no third-party interference.
- One Low critical tick unlocks before High requests, producing zero blocking.
- High acquisition before Low proves the owner-before-waiter trigger condition is necessary.
- Completion exactly at an absolute deadline passes; one unfinished tick at that boundary misses once.
- A short horizon conserves released work as served plus canceled plus remaining work.
- A release exactly at the final horizon is excluded from the half-open observation.
- Non-grid-aligned timing is malformed input and is rejected rather than rounded.
- The model accepts at most 16 tasks and 100,000 ticks, and checks bounds before timeline allocation.

## Common mistakes

- A low-priority owner is not running merely because it owns the mutex; CPU owner and mutex owner differ.
- High is blocked, not ready, while it waits. The scheduler cannot dispatch it until ownership changes.
- Medium's ordinary service before High requests is not inversion delay.
- Donation changes effective priority temporarily; it must not overwrite configured base priority.
- Inheritance bounds third-party delay but does not remove the owner's remaining critical work.
- A timeout does not imply safe cancellation, and canceling a waiter must not unlock another task's mutex.
- A finite synthetic schedule cannot prove a target's WCET, mutex implementation, or worst-case response.

## Completion standard

Explain ownership, request, blocking, readiness, base and effective priority, direct blocking, third-party
inversion delay, inheritance, unlock, deadline, timeout, waiter cancellation, rollback, and recovery. Connect
the lesson to P09 and the P11 boundary, pass `run_checks.m`, and answer the teach-back in `checks.md` without
relying on MATLAB syntax.
