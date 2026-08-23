# Lesson: Compare Polling and Interrupts

## Guiding question

What inputs, observable effects, and failure modes matter when you compare Polling and Interrupts?

## Connection to P02

P02 turned sampled input evidence into a qualified state transition. P03 starts after that semantic
decision: each synthetic pulse means “a request occurred.” The question now is how software observes
and services that request. Holding the request fixture fixed separates observation mechanics from the
state-machine behavior learned in P02.

## Mental model

Request `i` is high on the half-open interval

```text
[a_i, a_i + w_i) milliseconds.
```

Polling creates actual check times `p_k`. A request is detected only if

```text
a_i <= p_k < a_i + w_i.
```

After each check, the next poll cannot occur before either its requested period or the current work
finishes:

```text
p_(k+1) = max(p_k + T_poll, f_k).
```

This exposes both failure directions. A long poll period can leave a short pulse entirely between
checks. A very short period performs more checks and consumes more modeled foreground CPU time.
“Missed” is specific to this transient-level model; a sticky peripheral status flag can retain or
coalesce events and therefore has a different contract.

The interrupt path treats each rising edge as a record offered to finite capacity `Q`. Capacity includes
the request being serviced plus requests waiting in FIFO order. For each accepted request, dispatch is
eligible only after earlier accepted work and a fixed minimum latency, then moves to the end of a mask
window if its candidate falls inside one:

```text
ready_j = max(a_j, last_accepted_finish)
candidate_j = ready_j + L_irq
start_j = next_unmasked(candidate_j)
finish_j = start_j + C_handler
```

Here `j` indexes accepted requests. A longer mask wait can subsume the minimum eligibility latency; the
model does not add that latency again after the mask ends. Masking does not cancel a handler that already
started. If `Q` outstanding records already exist when a new edge arrives, that edge is marked as an
overrun rather than silently called handled.

Positive durations must advance at the current floating-point scale. A small comparison tolerance snaps
derived times to the nearer interval boundary so repeated binary time-step roundoff cannot reverse
arrival-inclusive/end-exclusive pulse or mask rules, exact capacity release, or horizon accounting.

## One prediction before the baseline

For 0.3 ms pulses and a 0.5 ms poll period, which mechanism can miss an isolated pulse that begins and
ends between adjacent poll instants?

## Baseline observation

Read the request/poll timeline before the response plot. The fixed fixture produces ten pulses. Some
contain a poll instant and some do not. The unmasked interrupt path has enough capacity to retain every
baseline edge, but its response is still later than arrival by dispatch latency and any FIFO wait.

The CPU bars are modeled event-handling fractions. Both paths pay the same handler cost per serviced
request, while polling additionally pays a check cost every time it looks. Because the paths may service
different request counts, each total combines handler and observation work; the bars do not isolate check
cost. Interrupt capture, architectural entry/exit, priority, and cache effects are omitted. These values
are not measured utilization, WCET, or hardware timing.

## Lever 1: poll period

Increasing `T_poll` reduces the number of checks but creates larger gaps in which short requests can
appear and disappear. Reducing it creates more observation opportunities and more periodic check work.
The input fixture, pulse width, interrupt latency, handler cost, queue capacity, and mask state remain
fixed during this sweep.

## Lever 2: interrupt mask duration

Reset poll period, keep `Q = 3`, and lengthen the mask beginning at 6 ms. The first burst requests occupy
the available records while dispatch waits. Once all three records are outstanding, later arrivals overrun.
Polling is unchanged because this lever belongs only to the interrupt mechanism.

## Deliberately broken assumption and recovery

The broken case sets `Q = 1`, masks dispatch from 6 to 10 ms, and assumes one pending indication can
remember every burst edge. It cannot: the first edge occupies the only slot and five later burst edges
are dropped. After the retained work drains, the request at 11.5 ms is captured and finishes before the
horizon. That later success is recovery; it does not restore the lost events.

## Common mistakes

- Polling is not inherently slow; its behavior depends on actual check times, pulse persistence, and work.
- Interrupts are not instantaneous and do not imply an unbounded queue.
- A mask delays new dispatch in this model; it is not a cancellation input and does not abort active work.
- A dropped edge and a handler finishing after the observation horizon are different failure modes.
- These equations do not model MCU pending-bit semantics, priorities, nesting, caches, DMA, an RTOS, or
  electrical input capture.

## Completion standard

Explain the input contract, predict each lever's changed view, account for every handled or lost event,
diagnose the broken assumption, pass `run_checks.m`, and give the teach-back in `checks.md`.
