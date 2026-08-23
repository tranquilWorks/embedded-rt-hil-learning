# Walkthrough: Compare Polling and Interrupts

1. Read the guiding question and connect each request edge to P02's qualified input transition.
2. Make one prediction only: decide which mechanism can miss a 0.3 ms pulse between 0.5 ms checks.
3. Run `experiment.m`. Inspect only the request/poll timeline first; identify half-open pulses, poll
   instants, detections, and misses in milliseconds.
4. Inspect the per-event response view next. Distinguish a finite service-start response from an explicit
   miss or overrun marker.
5. Read the baseline event-count plot, then the modeled CPU-fraction plot. Separate periodic check work
   from the changed number of serviced requests, and do not call either view a hardware measurement.
6. Inspect sweep 1. The request fixture and interrupt configuration stay fixed while only poll period
   changes. Explain both event loss and check cost from generated poll instants.
7. Reset poll period. Inspect sweep 2, where only interrupt-mask duration changes with capacity fixed.
   Explain wait and overrun from queued plus in-service work.
8. Open `interactive.m`. Move one control, describe one plot transition, then reset it before moving another.
9. Return to the broken one-slot case. Name the unlimited-pending assumption, the five dropped burst edges,
   the retained work draining, and the successful 11.5 ms recovery event.
10. Run `run_checks.m`, answer the interpretation questions, and give a two-sentence teach-back:
    mechanism first, tradeoff and failure boundary second.

The model is deterministic synthetic event handling. It does not provide MATLAB-runtime evidence in an
unexecuted environment or measured MCU, bench, HIL, field, RT1/RT2, Unreal, or production behavior.
