# Checks: Protect Shared Data Without Excess Blocking

## Observation check

On the baseline views, identify private preparation in `[0,2) ms`, writer lock acquisition at 2 ms, reader
request and block at 3 ms, inherited writer completion and unlock at 4 ms, reader copy in `[4,6) ms`, local
processing in `[6,8) ms`, and coherent generation 1. Explain why CPU owner, mutex owner, live record version,
reader blocked state, and copied generation must be read as separate signals.

## Independent calculations

- Calculate baseline `B_reader=1 ms commit+0 ms scope excess` and `R_reader=1+2+2=5 ms`.
- For coarse scope with 2 ms preparation and a 1 ms reader request, calculate `H_writer=2+2=4 ms`, the
  three remaining owner ticks, and reader response `3+2+2=7 ms`.
- Decode `[101 102]` as generation `[1 1]` and `[101 2]` as `[1 0]` using `(word-index)/100`.
- Account for 8 ms baseline demand as 8 served, and the four-word cancellation case as 6 served plus 6
  canceled milliseconds.

## Limiting cases and compatibility

- Why does an early short-scope reader return coherent generation 0 without blocking?
- Why is that result coherent but not the newest eventual generation?
- Why does unlock at the exact 1 ms timeout boundary pass, while a four-word commit times out at 4 ms?
- Why is a reader release at the horizon excluded, and why must a short horizon retain remaining work?
- Why do commit, copy, and generation traces change at a completion edge rather than at the start of service?
- Why do integer-class scalars, scalar strings, omitted timeout, and empty defaults normalize identically?
- Why are non-grid times rejected rather than silently rounded?

## Two independent levers

Sweep only writer private preparation through `[2 3 4 5] ms`, with two words, release at 1 ms, and 2 ms local
processing. Require short wait `[0 0 0 0] ms`, response `[4 4 4 4] ms`, and coherent generation 0. Require
coarse wait `[3 4 5 6] ms`, response `[7 8 9 10] ms`, scope excess `[1 2 3 4] ms`, and coherent generation 1.
All numeric inputs outside preparation remain fixed.

Reset preparation to 2 ms, release to 3 ms, and short scope. Sweep record words `[2 3 4 5]`. Require commit
wait `[1 2 3 4] ms`, response `[5 7 9 11] ms`, zero scope excess, and coherent generation 1. Preparation,
release, processing, tick, horizon, timeout, and policy remain fixed.

## Deliberately broken shared protocol

Change only protection to unprotected access. Require identical numeric input, 8 ms released/served work, and
final writer record `[101 102]`. The reader must have zero wait and 4 ms response but copy `[101 2]`, whose
generation vector `[1 0]` produces exactly one torn-read symptom. Restore the short mutex and require exact
`isequaln` rollback and recovery.

## Timeout, cancellation, rollback, and recovery

With the two-word baseline and a 1 ms `cancel-reader` limit, writer unlock at 4 ms wins and the reader does not
time out. With four words and a 1 ms limit, record timeout once at 4 ms. `continue-waiting` must preserve a
coherent completion at 12 ms. `cancel-reader` removes six pending reader ticks, leaves the writer owning until
6 ms, permits generation 1 publication, and conserves 12 ms as 6 served plus 6 canceled.

Re-run the clean baseline after coarse, unprotected, timeout, cancellation, short-horizon, and malformed calls
and require exact recovery. This is pure computational rollback. It is not arbitrary mutex cleanup, record
repair, asynchronous RTOS task deletion, peripheral undo, or a physical safe-state transition.

## Positive, negative, malformed, isolation, and resource cases

Confirm mutual exclusion for protected readers, a blocked reader never executing, writer ownership while
preempted, temporary inheritance, commit/scope wait decomposition, complete-copy consistency, stale-but-
coherent classification, completion-edge alignment of record state, one-shot timeout, cancellation ownership,
bounded task/owner/stage IDs, and work/time conservation. Reject wrong arity; nonscalar, text, logical, complex,
NaN, or invalid infinite numeric inputs;
negative preparation/release/processing; fewer than two words; fractional words; zero tick/horizon/timeout;
non-grid timing; unsupported protection/action; more than 64 words; more than 100,000 horizon ticks; and finite
times above one billion ticks. Verify exact accepted word, horizon, and finite-time bounds and rejection one
step beyond each.

## Interpretation questions

1. Which baseline wait is required commit service, and which portion is scope excess?
2. Why does priority inheritance change who runs without changing the amount of protected work?
3. When is coherent generation 0 acceptable, and what separate freshness condition might be required?
4. Why can a correct final record coexist with a torn snapshot that already escaped to a reader?
5. Why must canceling a blocked reader leave the writer's mutex ownership and partial commit untouched?
6. What compiler, cache, barrier, multicore, kernel, measured-time, and failure-recovery evidence would be
   required before applying this result to a real target?

## Teach-back

In two sentences, answer: “What inputs, observable effects, and failure modes matter when you protect Shared
Data Without Excess Blocking?” Sentence one must connect private preparation, protected commit/copy, local
processing, lock scope, priority inheritance, blocking, response, coherence, and freshness. Sentence two must
connect torn reads, timeout/cancellation ownership, rollback/recovery, the P10 and P12 links, and why this
synthetic calculation is not MATLAB-runtime, RTOS, memory-ordering, processor, hardware, bench, HIL, field,
or production evidence.
