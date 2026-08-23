# Walkthrough: Trigger Priority Inversion

1. Read the guiding question and connect P09's highest-ready-job rule to the new reason High can leave the
   ready set: it needs a Low-owned mutex.
2. Make one prediction only: decide who owns `[2,3) ms` after High blocks with inheritance enabled, and name
   Low's base and effective priorities.
3. Run `experiment.m`. Inspect only the baseline CPU-owner and mutex-owner views. Identify acquisition,
   preemption, wait, donation, unlock, High service, later Medium service, and milliseconds.
4. Inspect the priority/blocking view next. Verify that High is blocked only in intervals starting at 2, 3,
   and 4 ms, while Low's effective priority is 3 only in those same intervals.
5. Move one lever through Medium work `[1 3 5 7] ms`. Keep lock work and every other model input fixed. Compare
   direct blocking, third-party interference, High response, and deadline outcomes under both protocols.
6. Reset Medium to 5 ms and inheritance on. Move the second lever through Low critical work `[1 2 3 4 5] ms`
   while Low total work remains 6 ms. Explain why response grows one-for-one and the final completion at the
   deadline still passes.
7. Explain both changed views with `W_H=B_direct+I_third-party` and `R_H=W_H+C_H`, then connect donation to the
   highest-effective-priority dispatch rule.
8. Open `interactive.m`. Move one control, describe one plot transition, then reset it before moving another.
9. Select `Plain mutex inversion (fixed)`. Verify unchanged work, releases, and base priorities, then identify
   the four Medium interference ticks, seven High wait ticks, nine-millisecond response, and deadline miss.
10. Select `High acquires first (fixed)`. Explain why no inversion occurs even with a plain reading of the
    priorities: the required owner-before-waiter contention phasing is absent.
11. Select both timeout diagnostics. Distinguish wait timeout from deadline, continued waiting from waiter
    cancellation, donation withdrawal from mutex unlock, and computational recovery from physical rollback.
12. Check no-Medium, one-critical-tick, exact-deadline, short-horizon, release-at-horizon, deterministic tie,
    malformed-input, callback-lifetime, and resource-bound cases.
13. State what remains absent: nested/transitive locking, priority ceiling, deadlock, measured WCET, kernel or
    processor traces, target timing, hardware behavior, and shared-data design choices reserved for P11.
14. Run `run_checks.m`, answer one interpretation question at a time, and give the two-sentence teach-back:
    mechanism first, then failure, timeout/cancellation, recovery, and validation boundaries.

The calculations are deterministic and synthetic. They do not provide MATLAB-runtime evidence, an RTOS or
processor trace, mutex implementation evidence, bench, HIL, field, RT1/RT2, Unreal, signing, release,
deployment, staging, or production evidence.
