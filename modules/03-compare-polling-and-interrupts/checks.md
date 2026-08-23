# Checks: Compare Polling and Interrupts

## Observation check

On the baseline timeline, select one detected pulse and one missed pulse. For each, compare its half-open
interval with the neighboring poll instants before looking at the outcome count.

## Independent calculation

For a request on `[1.2, 1.5)` ms and polls at `1.0` and `1.5` ms, determine whether polling detects it.
Repeat for `[1.5, 1.8)` ms. Then calculate the service-start response when an idle, unmasked interrupt
arrives at `1.2` ms with `L_irq = 0.05` ms. Explain why a longer mask wait can subsume that minimum
eligibility latency in this abstraction.

## Limiting cases

- What happens when there are no input events?
- Why is an arrival exactly at a poll time detected while a pulse ending exactly there is missed?
- Why must a decimal poll mathematically at the observation horizon remain outside that horizon?
- When can a pulse at least as wide as `T_poll` still be missed because handler work stretches the loop?
- What does `Q = 1` retain, and what arrives too late to occupy its only outstanding slot?
- Why does a finish exactly at the next arrival free capacity under the half-open time rule?
- Why must a dispatch candidate exactly at a mask start wait while one exactly at its end may dispatch?

## Timeout, rollback, and recovery

Distinguish an accepted request whose handler finishes after the observation horizon from an overrun that
was never accepted. Resetting the mask and capacity controls to their baseline values rolls back the broken
configuration; it does not recreate lost events. Locate the post-drain 11.5 ms request that proves recovery.
There is no asynchronous cancellation or persistent-data transaction in this module.

## Broken-case check

Name the false assumption that one pending record can preserve an arbitrary masked burst. Account for the
first retained edge, five dropped edges, queue drain, and later recovery without answering only “interrupts
were disabled.”

## Interpretation and transfer

Explain when a sticky device status flag would turn a polling miss into coalescing instead. Then name one
real design where bounded response matters, while keeping this synthetic FIFO distinct from that device's
interrupt controller, priorities, synchronizer, measured latency, and CPU load.
Explain why the displayed CPU totals do not isolate periodic check cost when the two mechanisms service
different numbers of requests.

## Teach-back

In two sentences, answer the guiding question. Sentence one must connect pulse persistence, actual poll
instants, response, and periodic check cost. Sentence two must connect interrupt latency, finite outstanding
capacity, masking, overrun, and recovery without relying on MATLAB syntax.

## Executable check

Run:

```matlab
run_checks
```

All assertions must pass before personal learner completion is recorded.
