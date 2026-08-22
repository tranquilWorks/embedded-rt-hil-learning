# Walkthrough: Drive GPIO with a State Machine

1. Read the guiding question and the five state names before running code.
2. Recall P01: sampled work has a timing boundary. Predict only whether more debounce moves the GPIO
   transition earlier or later.
3. Run `experiment.m`. Inspect the raw-button/cancel plot first and name its logic level and time units.
4. Inspect the state plot next. Locate `QUALIFY_PRESS`, then inspect the GPIO plot and explain why it
   stays low during qualification.
5. Read the baseline metrics. Confirm that event counts are counts and high-run duration is milliseconds.
6. Inspect sweep 1. The input and maximum-on time are fixed; only debounce changes. Explain the edge-count
   and first-high-time changes using `N_d`.
7. Reset to the baseline debounce value. Inspect sweep 2, where only maximum-on time changes on a fixed
   stuck-high input. Explain the bounded high run and lockout using `N_t`.
8. Open `interactive.m`. Move one control, describe one plot transition, then reset it before moving another.
9. Select **Cancel and recovery**. Locate same-sample safe-low cancellation, qualified release, re-arm,
   and the later successful press.
10. Return to `experiment.m` and inspect the broken debounce-bypass case. Name the false clean-input
    assumption and the extra-edge symptom.
11. Run `run_checks.m`, answer the interpretation questions, and give a two-sentence teach-back:
    mechanism first, safety consequence second.

All views are deterministic simulated logic. No MATLAB execution in another environment and no physical
GPIO, voltage, current, bench, or HIL behavior should be inferred from the retained repository artifacts.
