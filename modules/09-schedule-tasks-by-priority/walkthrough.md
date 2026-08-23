# Walkthrough: Schedule Tasks by Priority

1. Read the guiding question and connect P08's omitted software-scheduling latency to CPU service before a
   peripheral command can even be offered.
2. Make one prediction only: decide who owns `[5,6) ms` when control releases while logger is unfinished.
3. Run `experiment.m`. Inspect only the baseline CPU-owner timeline. Name releases, ready work, the selected
   task, the two preemptions, resumes, completions, idle slots, and time units.
4. Inspect the response/deadline view next. Identify job IDs, response time in milliseconds, relative deadline,
   releases `[8 4 2]`, service `[8 8 10] ms`, and the zero-miss result.
5. Move one lever through the priority-order sweep while all timing, releases, horizon, and utilization stay
   fixed. Explain why interference moves between tasks before discussing MATLAB mechanics.
6. Reset priority to `[3 2 1]`. Move the second lever through logger WCET `[2 5 8] ms` while periods,
   deadlines, phases, tick, horizon, and higher-priority work stay fixed.
7. Explain both changed views from highest-ready dispatch and
   `R_i(next)=C_i+sum ceil(R_i/T_h)C_h` over higher-priority tasks.
8. Open `interactive.m`. Move one control, describe one plot transition, then reset it before moving another.
9. Select `Bad priority map (fixed)`. Verify that utilization remains 0.65 while logger promotion produces two
   control deadline misses. State the exact violated assumption.
10. Select `Deadline cancellation (fixed)`. Distinguish timeout, continued late work, cancellation of modeled
    remainder, unfinished work beyond the horizon, and clean computational rollback.
11. Check equal-priority ordering, zero-WCET completion, exact-deadline completion, overlapping job queues,
    final-boundary accounting, and strict time-grid rejection.
12. State what remains absent: measured WCET, dispatch/context overhead, interrupts, locks, blocking,
    inheritance, multicore behavior, RTOS semantics, processor traces, and physical timing evidence.
13. Run `run_checks.m`, answer one interpretation question at a time, and give the two-sentence teach-back:
    mechanism first, then failure, cancellation, recovery, and validation boundaries.

The calculations are deterministic and synthetic. They do not provide MATLAB-runtime evidence, an RTOS or
processor trace, bench, HIL, field, RT1/RT2, Unreal, signing, release, deployment, staging, or production
evidence.
