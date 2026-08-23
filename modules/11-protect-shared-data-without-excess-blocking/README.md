# P11 — Protect Shared Data Without Excess Blocking

**Track:** Embedded, Real-Time, and Hardware-in-the-Loop Systems  
**Phase 3:** RTOS behavior  
**Status:** implemented

## Guiding question

What inputs, observable effects, and failure modes matter when you protect Shared Data Without Excess Blocking?

## Computational mental model

P10 separated mutex ownership from CPU ownership and showed that priority inheritance removes unrelated
third-party delay, not the resource owner's real work. P11 keeps that rule and changes the lock boundary. A
low-priority writer prepares a new record privately, then commits one word per millisecond. A high-priority
reader copies the record one word per millisecond, then processes its local copy.

With a short mutex, only writer commit and reader copy are protected. With a coarse mutex, private writer
preparation and local reader processing are protected too. Both can preserve a coherent record, but only the
short scope excludes unrelated work:

```text
H_coarse,writer = C_prepare + C_commit
H_short,writer  = C_commit
B_reader = t_acquire - t_request
B_reader = B_commit + B_scope-excess
R_reader = B_reader + C_copy + C_process.
```

The two-word baseline uses 2 ms of private preparation, a reader release at 3 ms, 2 ms of local processing,
a 1 ms tick, and a half-open 16 ms horizon. The reader arrives after word one has changed. It waits 1 ms while
the writer finishes word two, copies `[101 102]`, observes generation 1 coherently, and responds in 5 ms.

## What the learner controls

- **Writer private preparation (ms):** computation that creates the next record without touching live data.
- **Protected record size (words):** one-tick word commits and copies that determine legitimate lock work.
- **Reader release (ms):** contention phase relative to preparation and commit.
- **Reader local processing (ms):** work on the copied snapshot that does not require the mutex.
- **Protection scope:** short mutex, coarse mutex, or deliberately unprotected access.
- **Reader wait timeout (ms):** analytical lock-wait limit; zero in the UI disables it.
- **Timeout action:** continue waiting or cancel only the modeled blocked reader.
- **Horizon (ms):** bounded half-open observation interval.
- **Scenario:** editable baseline or fixed coarse, torn-read, timeout, cancellation, and early-reader diagnostics.

## Complete learning flow

1. Connect P10's direct blocking to lock scope, then make one prediction about whether inheritance can erase
   private work held inside a coarse mutex.
2. Inspect CPU owner and mutex owner separately, then inspect record-generation and copy progress.
3. Sweep only writer preparation through `[2 3 4 5] ms` with an early reader. Short scope returns coherent
   generation 0 without waiting; coarse scope waits `[3 4 5 6] ms` for generation 1.
4. Reset preparation and release. Sweep only protected words through `[2 3 4 5]`; reader wait becomes
   `[1 2 3 4] ms` and response becomes `[5 7 9 11] ms`.
5. Explain why coherence and freshness are separate contracts, and why inheritance cannot shorten commit or
   copy service.
6. Break the shared protocol by letting both tasks access the live record without exclusion. The reader looks
   fast but captures `[101 2]`, whose per-word generations are `[1 0]`.
7. Compare exact unlock-at-timeout precedence, continued waiting, blocked-reader cancellation, unchanged
   writer ownership, pure rollback, and clean recovery.
8. Run checks and teach back the inputs, observable effects, failure modes, and evidence boundary.

## Boundaries and dependencies

The model has one low-priority writer, one high-priority reader, one nonrecursive mutex, direct priority
inheritance, one publication, and one read. Larger priority runs first. Each preparation, commit, copy, and
processing duration is CPU service on an integer tick grid. The initial record is generation 0 (`[1 2 ...]`),
and generation 1 is `[101 102 ...]`; the 100-count tags are a simulation oracle, not an implementation recipe.
Every protected participant follows the same mutex. A coherent reader may intentionally receive the previous
complete generation when it arrives before publication; requiring generation 1 would need a separate ready,
notification, or age contract.

CPU owner, mutex owner, task stage, and blocked traces describe half-open service intervals beginning at
`time_ms`. Committed-word, copied-word, and live-generation traces describe state at `time_edges_ms`; a word
served in `[t,t+1) ms` changes those state traces at `t+1 ms`, never at dispatch time.

The model assumes sequential visibility, atomic scalar word service at the declared tick, zero dispatch and
context-switch cost, no cache or barrier cost, and no writer failure inside the critical section. It omits
nested locks, multiple readers or writers, recursive locks, deadlock, lock-free algorithms, sequence counters,
atomic pointer publication, interrupt access, multicore memory ordering, measured WCET, and kernel cleanup.
P12 will treat bounded blocking as one input to response-time and jitter analysis.

Wait timeout begins when the selected reader finds the mutex owned. Prior-slot unlock and unblock occur before
timeout classification at the same boundary. `cancel-reader` removes only remaining modeled reader work; it
does not unlock the writer, repair a record, undo a publication, delete an RTOS task, unwind a driver, roll
back a peripheral, or restore a plant. Re-running the state-free function with clean input is computational
rollback and recovery only.

These outputs are synthetic calculations and not MATLAB-runtime evidence. They are not an RTOS or mutex
implementation test, memory-ordering proof, processor trace, timing guarantee, hardware measurement, bench
evidence, HIL evidence, field evidence, or production evidence.

## Files

- `p11_scenario.m` owns bounded deterministic shared-record fixtures.
- `model.m` owns validation, fixed-priority execution, lock scope, word generations, timeout/cancellation,
  and work accounting.
- `experiment.m` owns the baseline, five labeled figures, two isolated sweeps, and deliberately broken case.
- `interactive.m` owns immediate controls and complementary ownership and record-progress views.
- `lesson.m`, `lesson.md`, and `walkthrough.md` own the mechanism-first learner sequence.
- `checks.md` and `run_checks.m` own interpretation prompts and executable invariants.
