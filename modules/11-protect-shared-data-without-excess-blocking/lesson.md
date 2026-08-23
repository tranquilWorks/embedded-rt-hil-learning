# Lesson: Protect Shared Data Without Excess Blocking

## Guiding question

What inputs, observable effects, and failure modes matter when you protect Shared Data Without Excess Blocking?

## Connection to P10

P10 gave a blocked High task priority inheritance so unrelated Medium work could not preempt the Low mutex
owner. It split High's wait into direct owner service and third-party interference. P11 starts at the remaining
limit: inheritance cannot make legitimate critical work disappear. If private preparation is placed inside the
mutex, inheritance may help the owner run, but the high-priority reader still waits for preparation that never
needed shared access.

P11 uses one low-priority writer and one high-priority reader. The writer prepares a new multiword record,
publishes it one word per tick, and the reader copies one word per tick before processing locally. The design
question is not simply “lock or no lock?” It is “which exact operations must share the lock?”

## One versioned-record experiment

The default fixture is:

| Input | Value | Meaning |
| --- | ---: | --- |
| Writer private preparation | 2 ms | work that does not touch the live record |
| Record size | 2 words | protected commit and copy service |
| Reader release | 3 ms | contention begins after the first word changes |
| Reader local processing | 2 ms | work on the copied values after unlock |
| Tick | 1 ms | one preparation, commit, copy, or process unit |
| Horizon | 16 ms | half-open interval `[0,16) ms` |

The initial record is `[1 2]`, generation 0. The target is `[101 102]`, generation 1. Subtract each word's
index and divide by 100 to expose its generation. A coherent snapshot has the same integer generation in every
word. Those tags let the lesson detect tearing; a real design needs its own declared data contract.

The writer has base priority 1 and the reader priority 2. With protected access, direct priority inheritance
raises a blocked reader's writer owner to effective priority 2. There is no Medium task here: the remaining
wait comes from lock scope and actual record work.

## One prediction before the baseline

Suppose the writer holds a coarse mutex during 2 ms of private preparation and 2 ms of publication. The reader
requests at 1 ms. Does priority inheritance erase the three remaining owner ticks, or merely ensure that the
owner runs them? Name which portion of that wait touches the live record.

## Baseline observations

The short-mutex CPU-owner sequence is:

```text
1 1 1 1 2 2 2 2 0 0 0 0 0 0 0 0
```

and mutex ownership is:

```text
0 0 1 1 2 2 0 0 0 0 0 0 0 0 0 0.
```

The writer prepares in `[0,2) ms` without owning the mutex. It acquires at 2 ms and writes word one in
`[2,3) ms`. The reader releases at 3 ms, requests the mutex, and blocks. Inheritance makes the writer's
effective priority 2 while it writes word two in `[3,4) ms`. Unlock at 4 ms makes the reader ready. The reader
copies in `[4,6) ms`, unlocks, processes locally in `[6,8) ms`, and completes with response `8-3=5 ms`.

CPU, mutex, stage, and blocked traces describe the interval that starts at each `time_ms`. Commit, copy, and
generation traces are boundary states: service in `[t,t+1) ms` first changes them at `t+1 ms`.

The live record is mixed during `[3,4) ms`, but the reader cannot execute its copy while the writer owns the
mutex. It observes `[101 102]`, so the generation vector is `[1 1]` and the snapshot is coherent.

## Scope, blocking, and response equations

For the writer:

```text
H_coarse,writer = C_prepare + C_commit
H_short,writer  = C_commit.
```

For a blocked reader:

```text
B_reader = t_acquire - t_request
B_reader = B_commit + B_scope-excess
R_reader = B_reader + C_copy + C_process.
```

In the baseline, `B_commit=1 ms`, `B_scope-excess=0`, `C_copy=2 ms`, and `C_process=2 ms`, so
`R_reader=1+2+2=5 ms`. Priority inheritance controls dispatch while the reader waits; it does not reduce
`C_commit` or `C_copy`.

## Lever 1: writer private preparation

Move the reader release to 1 ms, keep two record words and 2 ms of local processing, then sweep writer private
preparation through `[2 3 4 5] ms`.

```text
Writer preparation             2  3  4  5 ms
Short-mutex reader wait        0  0  0  0 ms
Short-mutex reader response    4  4  4  4 ms
Short observed generation      0  0  0  0
Coarse-mutex reader wait       3  4  5  6 ms
Coarse-mutex reader response   7  8  9 10 ms
Coarse scope-excess wait       1  2  3  4 ms
Coarse observed generation     1  1  1  1
```

The early short-mutex reader preempts private preparation, copies complete generation 0, and finishes before
the writer publishes generation 1. It is coherent but one generation old. The coarse reader waits for the
future update, including remaining private work, and receives generation 1. Moving work outside the lock does
not itself promise freshness. If the reader requires generation 1, add an explicit ready/notification/age
condition rather than silently using mutex wait as a freshness protocol.

## Lever 2: protected record size

Reset preparation to 2 ms, release to 3 ms, and use short scope. Sweep record size through `[2 3 4 5]` words.

```text
Protected words        2  3  4  5
Reader commit wait     1  2  3  4 ms
Reader response        5  7  9 11 ms
Scope-excess wait      0  0  0  0 ms
Observed generation    1  1  1  1
```

At 3 ms the writer has completed the first word. Every extra word adds one remaining commit tick before
unlock and one copy tick after acquisition. Coherence remains true, but legitimate lock service still grows.
For a large record, a design review might consider immutable buffers plus an atomic publication primitive;
that requires a separate memory-ordering contract and is not modeled here.

## Deliberately broken assumption: zero wait means safe data

Change only protection to unprotected access. The writer updates word one in `[2,3) ms`. The reader releases,
preempts the writer, reads new word one in `[3,4) ms`, then old word two in `[4,5) ms`. It observes:

```text
values       [101   2]
generations  [  1   0].
```

Reader wait falls to 0 and response to 4 ms, but the record invariant fails. The final writer result is still
`[101 102]` after it resumes; inspecting only the final record would miss the transient torn snapshot. The
violated assumption is that fast completion or a correct final writer value proves safe concurrent access.
All participants that touch the multiword live record must follow the declared protocol.

Restore short locking and the state-free function reproduces the baseline exactly. This rollback changes the
modeled input and recomputes; it does not repair data in a running target.

## Wait timeout, cancellation, and ownership

Wait begins when the selected reader finds the writer-owned mutex. A prior-slot commit, publication, unlock,
and unblock are already effective before timeout classification at the next boundary. In the two-word baseline,
a 1 ms timeout therefore permits acquisition at 4 ms without timing out.

With four words, the reader has three remaining commit ticks to wait. A 1 ms timeout records once at 4 ms.
`continue-waiting` preserves the reader and the eventual coherent generation-1 snapshot. `cancel-reader`
removes six pending reader ticks at 4 ms, but the writer still owns the mutex, commits the remaining words, and
unlocks at 6 ms. Cancellation cannot grant ownership to a task that never acquired it.

This is synchronous modeled work removal, not asynchronous RTOS deletion, stack unwinding, mutex cleanup,
record repair, peripheral rollback, or plant recovery.

## Limiting cases and resource bounds

- An early short-scope reader returns complete generation 0 with zero blocking.
- A reader release exactly at the half-open horizon is excluded.
- A short horizon conserves released work as served plus canceled plus remaining work.
- Zero private preparation and zero local processing remain well-defined.
- Unlock at the exact wait-timeout boundary wins; one extra protected word makes the timeout observable.
- Non-grid timing is rejected rather than rounded, including tiny positives that collapse to zero ticks.
- The model accepts 2–64 record words and at most 100,000 horizon ticks, with bounds checked before allocation.

## Common mistakes

- Mutex ownership is not CPU ownership; a preempted writer still owns the record lock.
- Priority inheritance makes an owner eligible to run; it does not shorten its critical section.
- Private computation and local processing do not belong inside a mutex merely because they precede or follow
  protected access.
- A coherent snapshot may be the previous generation. Consistency, freshness, and deadline are separate.
- One atomic scalar word does not make a multiword record atomic.
- `volatile`, a checksum observed after the fact, or a passed deadline does not establish coherent access.
- A timeout or cancellation does not imply safe unlock, cleanup, or data rollback.
- Generation tags in this calculation do not prove compiler, cache, barrier, or multicore behavior.

## Completion standard

Explain private preparation, commit, copy, local processing, CPU and mutex ownership, short and coarse scope,
priority inheritance, commit versus scope-excess blocking, coherence versus freshness, torn reads, timeout,
cancellation ownership, rollback, and recovery. Connect the result back to P10 and forward to P12, pass
`run_checks.m`, and answer the teach-back in `checks.md` without relying on MATLAB syntax.
