# Walkthrough: Measure Jitter and Worst-Case Response Time

1. Read the guiding question and connect P11's bounded mutex delay to the `B` term in `R=B+I+C`.
2. Make one prediction only: if actual release moves while `B`, `I`, and `C` stay fixed, decide whether
   `R=f-a`, `L=f-n`, or both must move.
3. Run `experiment.m`. Inspect only the baseline release-offset view. Identify nominal release `n`, actual
   release `a`, signed offset `j=a-n`, milliseconds, and the 2 ms peak-to-peak range.
4. Inspect the response-component view next. For each job, add blocking, interference, and execution. Confirm
   response `[2 3 3 3 4 3 3 6] ms`, 4 ms response jitter, 6 ms observed maximum, and no 7 ms deadline miss.
5. Move one lever through release-offset amplitudes `[0 1 2 3] ms`. Observe release jitter
   `[0 2 4 6] ms`, unchanged response maximum `[6 6 6 6] ms`, and nominal-latency maximum
   `[6 7 8 9] ms`.
6. Explain the first changed view with `L=j+R`: actual release and completion translate together, so `f-a`
   stays fixed while `f-n` changes.
7. Reset release amplitude to 1 ms. Move the P11 blocking bound through `[0 1 2 3] ms`. Observe worst
   response `[5 6 7 8] ms`, response jitter `[3 4 5 6] ms`, fixed release jitter, and misses
   `[0 0 0 1]`.
8. Explain the second changed view with `R=B+I+C`, including why `R=D` passes and `R>D` misses.
9. Select `Completion spacing trap (fixed)`. Confirm true release jitter is zero while
   `diff(completion)-period` has a 4 ms range. Name the contaminating `delta R` term.
10. Select `Coarse timestamp clock (fixed)`. Compare true responses with `[0 4 0 4 4 4 0 8] ms` and explain
    why completed-tick resolution can hide or inflate an interval.
11. Select both timeout diagnostics. Distinguish exact-boundary retention, continued observation, censored
    `NaN`, incomplete maximum, and a retained lower bound. State that observation cancellation does not
    actuate or cancel a task.
12. Open `interactive.m`. Move one control, describe one plot transition, then reset before moving another.
13. Check single-job, zero-response, deadline/timeout equality, all-censored, coarse-clock censoring,
    exponent-boundary normalization, floating-point collapse rejection, prefix maximum, malformed-input,
    compatibility, callback-lifetime, timestamp-order, and resource-bound cases.
14. Restore baseline and require exact `isequaln` recovery. Distinguish computational recovery from target,
    peripheral, plant, or data rollback.
15. State what remains absent: a complete phasing campaign, analytical scheduler proof, measured WCET/WCRT,
    clock accuracy, RTOS or processor traces, rendered UI evidence, hardware, bench, HIL, and field evidence.
16. Connect the timestamp record forward to P13, run `run_checks.m`, answer one interpretation question at a
    time, and give the two-sentence teach-back.

The calculations are deterministic and synthetic. They do not provide MATLAB-runtime, numerical-fidelity,
UI, RTOS, processor, memory-ordering, hardware, bench, HIL, field, RT1/RT2, Unreal, signing, release,
deployment, staging, or production evidence. A finite trace is not a WCRT guarantee.
