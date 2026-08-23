# P10 — Trigger Priority Inversion

**Track:** Embedded, Real-Time, and Hardware-in-the-Loop Systems  
**Phase 3:** RTOS behavior  
**Status:** implemented

## Guiding question

What inputs, observable effects, and failure modes matter when you trigger Priority Inversion?

## Computational mental model

P09 selected the highest-priority ready job and deliberately excluded locks. P10 adds one owned mutex. Low
acquires it first, Medium performs unrelated CPU work, and High later requests the same mutex. High is not
ready while blocked. With a plain mutex, Medium can preempt Low even though High is waiting for Low; that
third-party service is priority-inversion delay. With priority inheritance, Low temporarily receives High's
priority until it unlocks, so Medium cannot extend the wait.

For the High task,

```text
W_H = t_acquire,H - t_request,H
W_H = B_direct + I_third-party
R_H = W_H + C_H
```

The baseline leaves 3 ms of Low critical work when High requests the mutex. Medium has 4 ms of work remaining.
A plain mutex therefore gives `W_H=3+4=7 ms` and `R_H=9 ms`; High misses its 6 ms relative deadline. Priority
inheritance retains the legitimate 3 ms direct block, removes the 4 ms third-party delay, and gives
`W_H=3 ms`, `R_H=5 ms`.

## What the learner controls

- **Medium work (ms):** unrelated CPU demand that can amplify inversion under a plain mutex.
- **Low mutex-held work (ms):** the critical share of Low's fixed 6 ms total job work.
- **High relative deadline (ms):** release-to-completion allowance; completion exactly at the boundary passes.
- **Mutex protocol:** plain ownership or direct priority inheritance.
- **High wait timeout (ms):** analytical mutex-wait limit; zero in the UI means disabled.
- **Timeout action:** continue waiting or cancel only the modeled blocked waiter.
- **Horizon (ms):** bounded half-open observation interval.
- **Scenario:** editable baseline or fixed inversion, timeout, cancellation, and no-contention diagnostics.

## Complete learning flow

1. Connect P09's ordinary ready-job interference to a mutex-blocked High task, then make one prediction about
   the interval when High first waits.
2. Inspect separate CPU-owner and mutex-owner timelines, then the Low effective-priority and High-blocked view.
3. Sweep only Medium work through `[1 3 5 7] ms`. Compare plain-mutex response `[5 7 9 11] ms` with the
   inherited `[5 5 5 5] ms` response.
4. Reset Medium to 5 ms and keep inheritance enabled. Move Low's fixed 6 ms total work into critical work
   `[1 2 3 4 5] ms`; High response becomes `[2 3 4 5 6] ms`.
5. Explain why inheritance suppresses unrelated interference but cannot erase resource-owner service.
6. Break the protection by selecting a plain mutex. Work, releases, base priorities, and service stay fixed,
   but Medium runs 4 ms while High waits and High misses once.
7. Compare continued waiting, exact unlock-at-timeout precedence, waiter cancellation, donation withdrawal,
   unchanged mutex ownership, rollback, and clean recovery.
8. Run checks and teach back the inputs, observable effects, failure modes, and evidence boundary.

## Boundaries and dependencies

The model contains one single-core scheduler, one nonrecursive mutex, one one-shot job per task, and at most one
critical section per task. Pre-critical, critical, and post-critical durations are CPU service, not wall time.
A task requests the mutex only when selected after completing its pre-critical work. A blocked task is not
ready; an owner retains the mutex while preempted. Larger effective priority wins, with earlier release and
then task ID as deterministic ties. Dispatch and context-switch overhead are zero.

Priority inheritance is direct: the current owner receives the greatest base priority among current waiters.
Base priorities never change. Donation begins in the same interval that a waiter blocks and ends at unlock or
waiter cancellation. The model has no nested resources, transitive donation, recursive locks, priority ceiling,
deadlock detection, self-suspension, interrupts, multicore migration, dynamic priorities, measured WCET, or
kernel implementation. P11 will use this resource-blocking insight to compare shared-data protection choices
and excess blocking.

A wait timeout is a synchronous classification. `cancel-waiter` removes only the modeled blocked job and its
remaining work. It does not unlock the Low-owned mutex, asynchronously delete an RTOS task, unwind a driver,
repair shared data, or roll back a plant or peripheral. Restoring clean inputs and invoking the state-free
function again is computational rollback and recovery only.

These outputs are synthetic calculations and not MATLAB-runtime evidence. They are not an RTOS trace, mutex
implementation test, processor trace, timing guarantee, hardware measurement, bench evidence, HIL evidence,
field evidence, or production evidence.

## Files

- `p10_scenario.m` owns bounded deterministic lock-contention fixtures.
- `model.m` owns validation, fixed-priority dispatch, mutex ownership, wait state, direct inheritance, timeout,
  cancellation, and conservation metrics.
- `experiment.m` owns the baseline, five labeled figures, two isolated sweeps, and deliberately broken case.
- `interactive.m` owns immediate controls and complementary ownership and priority/blocking views.
- `lesson.m`, `lesson.md`, and `walkthrough.md` own the mechanism-first learner sequence.
- `checks.md` and `run_checks.m` own interpretation prompts and executable invariants.
