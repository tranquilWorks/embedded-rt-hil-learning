# Checks: Measure Jitter and Worst-Case Response Time

## Observation check

On the release view, identify nominal release `n`, actual release `a`, and signed release offset `j=a-n` in
milliseconds. On the separate response view, identify first start `s`, completion `f`, bounded blocking `B`,
interference `I`, execution `C`, response `R=f-a`, nominal latency `L=f-n`, and the 7 ms relative deadline.
Explain why release, response, nominal-latency, and completion-spacing variation need different names.

## Independent calculations

- From offsets `[0 1 -1 0 1 -1 0 1] ms`, calculate release jitter `1-(-1)=2 ms` peak-to-peak.
- Add the baseline component vectors and recover response `[2 3 3 3 4 3 3 6] ms`, response jitter
  `6-2=4 ms`, and fixture observed maximum `6 ms`.
- Calculate the component envelope `max(B)+max(I)+max(C)=1+3+2=6 ms` and explain its declared scope.
- Add `j+R` and recover nominal latency `[2 4 2 3 5 2 3 7] ms`.
- Confirm each completion-spacing deviation equals `delta j + delta R`.

## Limiting cases and compatibility

- Why does one retained job have zero peak-to-peak jitter but not prove deterministic future timing?
- Why do zero blocking, interference, and execution produce zero response without producing a deadline miss?
- Why does `R=D` pass and the smallest positive excess miss?
- Why does `R=timeout` remain retained and the smallest positive excess time out?
- Why are maximum, mean, and jitter `NaN` rather than zero when every response is censored?
- Why must prefix observed maximum be nondecreasing as more jobs are examined?
- Why do scalar components, integer-class values, column vectors, scalar strings, and empty timeout/action
  defaults normalize without changing the calculation?
- Why must actual releases remain nonnegative and strictly ordered?

## Two independent levers

Sweep only release-offset amplitude through `[0 1 2 3] ms`. Require release jitter
`[0 2 4 6] ms`, observed worst response `[6 6 6 6] ms`, response jitter `[4 4 4 4] ms`, and worst
nominal latency `[6 7 8 9] ms`. Blocking, interference, execution, period, deadline, timestamp tick,
timeout, and policy remain fixed.

Reset release amplitude to 1 ms. Sweep only bounded blocking through `[0 1 2 3] ms`. Require observed worst
response `[5 6 7 8] ms`, response jitter `[3 4 5 6] ms`, release jitter `[2 2 2 2] ms`, and deadline
misses `[0 0 0 1]`. Release offsets, interference, execution, period, deadline, timestamp tick, timeout, and
policy remain fixed.

## Deliberately broken measurement

Use zero release offset without changing `B`, `I`, or `C`. Require true release jitter 0 ms and completion-
interval deviation `[1 0 0 1 -1 0 3] ms`, whose peak-to-peak range is 4 ms. Reject the assumption that
completion spacing is release jitter because `delta f-period=delta j+delta R`. Restore baseline input and
require exact `isequaln` rollback and recovery.

## Timestamp, timeout, cancellation, rollback, and recovery

With a 4 ms timestamp tick, require true response `[2 3 3 3 4 3 3 6] ms` and timestamped response
`[0 4 0 4 4 4 0 8] ms`. Confirm every retained response-measurement error has magnitude below one tick.
Across a binary exponent boundary, require release/start/completion to share one per-job normalization
tolerance and preserve the same strict interval bound. Add an unrelated far-future job and require that it
cannot change the earlier capture decision.

At a 6 ms timeout with `cancel-observation`, retain every sample because equality passes. At a 5 ms timeout,
`continue-observing` records one timeout and still retains the 6 ms response. `cancel-observation` censors only
that tail response, retains seven jobs, reports a visible incomplete 4 ms maximum and 5 ms lower bound on the
true fixture maximum, and leaves the job's actual completion unchanged. If all responses are censored, require
unavailable measured statistics. Observation cancellation must never be described as RTOS task deletion,
mutex cleanup, data repair, peripheral rollback, or plant recovery.

Also combine a 4 ms clock with censoring so an uncensored 1 ms response measures as 4 ms while the true
fixture maximum is 2 ms. Require the reported lower bound to remain 1.5 ms, not the upward-quantized 4 ms.

After coarse-clock, broken, timeout, cancellation, all-censored, resource-bound, and malformed calls, re-run
the clean fixture and require exact baseline recovery. This proves pure computational isolation, not target
recovery.

Bind the P12 model and scenario handles, remove the P12 folder from the MATLAB search path, place P01's
incompatible generic `model.m` first, clear the generic model name as a later lesson launch does, and require
the retained handles to reproduce the exact P12 baseline. This checks the callback lifetime used after
`launch_lesson` removes its temporary module path.

## Positive, negative, malformed, isolation, and resource cases

Confirm causal timestamp order `a <= s <= f` (`n` only defines `j=a-n`), nonnegative response components,
exact `L=j+R` and `R=B+I+C`,
nonnegative jitter, nondecreasing prefix maximum, finite maximum no larger than its component envelope,
deadline strictness, quantization error bound, visible censored counts, and no fake response for a canceled
observation. Reject wrong arity; empty component vectors; text, logical, complex, NaN, or invalid infinite
numeric input; nonscalar scalar fields; vector-length mismatch; nonpositive period, deadline, or timestamp
tick; nonpositive finite timeout; negative execution, blocking, or interference; noninteger or zero job count;
nonnegative/order-violating actual releases; unsupported action or scenario; more than 10,000 jobs; oversized
per-job vectors; derived timestamps beyond `1e12` timestamp ticks; an overflowing component envelope; and
any nonzero release offset, positive relative component, or positive absolute-time advance erased by
floating-point precision. Retain a finite scaled mean for two `1e308 ms` responses, but reject a completion-
spacing diagnostic that would overflow even though its source timestamps remain finite. Verify exact accepted
job/timestamp bounds and rejection one step beyond each.

## Interpretation questions

1. Which two timestamps define release offset, response, and nominal completion latency?
2. Why can own release jitter change `L=f-n` without changing `R=f-a`?
3. How does P11 bounded blocking enter response, and what evidence would justify a real bound?
4. Why can zero response jitter coexist with every job missing its deadline?
5. Why is a finite observed maximum not automatically a WCRT guarantee?
6. How does completion spacing combine release-offset and response variation?
7. Why can censoring the slowest job make an apparently safe maximum invalid?
8. What clock, scheduler, WCET, processor, and physical evidence would be required before applying this result
   to a real target?

## Teach-back

In two sentences, answer: “What inputs, observable effects, and failure modes matter when you measure Jitter
and Worst-Case Response Time?” Sentence one must connect `n`, `a`, `s`, `f`, `j`, `R`, `L`, peak-to-peak
jitter, `B+I+C`, deadline, and P11. Sentence two must connect finite-trace coverage, completion-spacing
contamination, timestamp quantization, timeout/censoring, rollback/recovery, P13, and why this synthetic
calculation is not MATLAB-runtime, numerical-fidelity, UI, RTOS, processor, measured-WCET/WCRT, hardware,
bench, HIL, field, or production evidence.
