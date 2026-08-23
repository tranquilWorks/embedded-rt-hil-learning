# P03 — Compare Polling and Interrupts

**Track:** Embedded, Real-Time, and Hardware-in-the-Loop Systems  
**Phase 1:** Microcontroller execution  
**Status:** implemented

## Guiding question

What inputs, observable effects, and failure modes matter when you compare Polling and Interrupts?

## Computational mental model

The same transient request pulses are offered to two observation mechanisms. A polling loop checks
the request level at generated poll instants. It detects pulse `i` only when a poll time `p_k` lies
inside the half-open interval `[a_i, a_i + w_i)`. Short pulses between checks can be missed, while
more frequent checks consume more modeled foreground work.

The interrupt path captures each rising edge into finite outstanding capacity. That capacity includes
both queued and in-service requests. Masking delays dispatch; if the retained work fills the capacity,
later arrivals are explicitly dropped. A captured request still pays dispatch latency and handler time.
Here dispatch latency defines the earliest eligible start; a longer mask wait can subsume it. The same
handler cost is charged per serviced request after either polling or interrupt observation. Because the
mechanisms can service different event counts, each CPU total combines that handler work with its own
observation work; it is not an isolated check-cost comparison. Interrupt capture, architectural
entry/exit, and other MCU overhead are omitted.

These are deterministic synthetic request and CPU-work abstractions, not measurements of an MCU,
interrupt controller, synchronizer, processor utilization, or physical hardware. This is not a hardware measurement.
A peripheral with a sticky status flag would change the polling failure mode because multiple requests
could coalesce.

Floating-point interval comparisons use a small scale-aware tolerance to snap derived times to the nearer
boundary. This preserves half-open pulse and mask behavior, exact capacity release, and horizon accounting
when repeated binary additions drift slightly; a positive duration must still advance representably.

## What the learner controls

- **Poll period (ms):** trades opportunities to observe short pulses against periodic check cost.
- **Pulse width (ms):** changes how long each transient request is visible to polling.
- **Interrupt mask duration (ms):** delays dispatch and can build a finite backlog.
- **Outstanding capacity (event records):** integer-rounded control that bounds queued plus in-service work.
- **Request scenario:** switches among deterministic mixed, sparse, and burst/recovery arrivals.

## Complete learning flow

1. Connect P02's qualified state transition to the request events used here.
2. Read the fixed event fixture and inspect the baseline polling timeline first.
3. Compare per-event response and outcome metrics for polling and interrupts.
4. Sweep poll period while the pulses and interrupt configuration remain fixed.
5. Reset, then sweep interrupt-mask duration while polling and queue capacity remain fixed.
6. Explain both changed views from sampling, finite capacity, and service-time mechanisms.
7. Break the unlimited-pending assumption with one outstanding slot, then observe drain and recovery.
8. Run the independent checks and give the requested teach-back.

## Files and dependencies

- `p03_scenario.m` owns bounded, seedless synthetic request fixtures.
- `model.m` owns validation, polling instants, FIFO dispatch, accounting, and metrics.
- `experiment.m` owns the deterministic baseline, labeled plots, two sweeps, and broken case.
- `interactive.m` owns immediate controls and complementary timeline/response views.
- `lesson.m`, `lesson.md`, and `walkthrough.md` own the mechanism-first learner sequence.
- `checks.md` and `run_checks.m` own interpretation prompts and executable invariants.

Only base MATLAB operations are used. No toolbox, Simulink, support package, asynchronous timer,
operating-system interrupt, or hardware API is required.
