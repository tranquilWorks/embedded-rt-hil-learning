# Lesson: Measure Jitter and Worst-Case Response Time

## Guiding question

What inputs, observable effects, and failure modes matter when you measure Jitter and Worst-Case Response Time?

## Connection to P11

P11 showed that a high-priority reader can wait for real mutex-held work even after priority inheritance
removes unrelated inversion. That bounded wait is not the whole response, but it is one term. P12 names it
`B`, adds other interference `I` and own execution `C`, and asks which timestamp subtraction actually measures
each timing property.

For periodic job `k`, keep four events separate:

```text
n_k = nominal release configured by the period
a_k = actual release after arrival variation
s_k = first start after blocking and interference
f_k = completion after own execution.
```

The three derived quantities answer different questions:

```text
j_k = a_k - n_k                         release offset
R_k = f_k - a_k = B_k + I_k + C_k       response time
L_k = f_k - n_k = j_k + R_k             nominal completion latency.
```

Own release offset belongs in `L`, not in `R=f-a`. A different system may declare deadlines from a sensor
edge or nominal phase instead of actual software release; then it must name that origin rather than silently
reuse the word response.

This lesson defines release and response jitter as peak-to-peak ranges:

```text
J_release,pp  = max(j_k) - min(j_k)
J_response,pp = max(R_k) - min(R_k).
```

One retained sample has zero peak-to-peak jitter. Zero retained samples have unavailable jitter (`NaN`).
Neither result establishes that the task is timely.

## One prediction before the baseline

Suppose every `B`, `I`, and `C` value stays fixed, but one job releases 2 ms later relative to its nominal
grid. Does its response `f-a` grow by 2 ms, or does only nominal latency `f-n` grow? Name the subtraction you
would inspect before looking at the plots.

## Baseline observations

The eight-job fixture uses:

| Input | Value | Meaning |
| --- | ---: | --- |
| Nominal period | 20 ms | spacing of `n_k` |
| Release offset | `[0 1 -1 0 1 -1 0 1] ms` | `a_k-n_k` |
| Own execution | 2 ms each | `C_k` |
| Bounded blocking | `[0 1 0 1 0 1 0 1] ms` | `B_k`, connected to P11 |
| Interference | `[0 0 1 0 2 0 1 3] ms` | `I_k` before first start |
| Relative deadline | 7 ms | limit from actual release |
| Timestamp tick | 1 ms | completed-tick capture resolution |

The nominal releases are `[0 20 40 60 80 100 120 140] ms`; actual releases are
`[0 21 39 60 81 99 120 141] ms`; starts are `[0 22 40 61 83 100 121 145] ms`; completions are
`[2 24 42 63 85 102 123 147] ms`.

Read the release-offset view first. Its signed values range from -1 to +1 ms, so release jitter is
`1-(-1)=2 ms` peak-to-peak. Then read the response decomposition:

```text
R = [2 3 3 3 4 3 3 6] ms
J_response,pp = 6 - 2 = 4 ms
max_observed(R) = 6 ms
max(B)+max(I)+max(C) = 1+3+2 = 6 ms.
```

Every response is at most the 7 ms deadline, so no job misses. Equality would also pass; this lesson uses the
strict miss predicate `R>D`.

The 6 ms maximum is exact for these eight declared component records. Calling it a guaranteed target WCRT
would require a coverage argument or a sound analytical model for every relevant input and phasing. A larger
campaign can preserve or increase its observed maximum; it cannot make an earlier observed maximum disappear.

## Lever 1: release-offset amplitude

Hold `B`, `I`, `C`, period, deadline, clock, timeout, and policy fixed. Sweep release-offset amplitude through
`[0 1 2 3] ms`:

```text
Amplitude                         0  1  2  3 ms
Release jitter p-p                0  2  4  6 ms
Observed worst response           6  6  6  6 ms
Response jitter p-p               4  4  4  4 ms
Worst nominal completion latency  6  7  8  9 ms.
```

The actual release and completion both translate by the same job-specific offset, so `f-a` preserves `R`.
The nominal release does not translate, so `f-n=j+R` moves. This is why arrival jitter cannot simply be added
to a response measurement whose origin is already the actual release.

## Lever 2: bounded blocking

Reset release amplitude to 1 ms. Keep the release vector, `I`, `C`, period, deadline, clock, timeout, and
policy fixed. Sweep the blocking budget through `[0 1 2 3] ms`:

```text
Blocking budget                  0  1  2  3 ms
Observed worst response          5  6  7  8 ms
Response jitter p-p              3  4  5  6 ms
Release jitter p-p               2  2  2  2 ms
Deadline misses                  0  0  0  1.
```

Selected jobs receive the declared blocking term directly, so `R=B+I+C` grows. At a 2 ms budget the worst
job has `R=D=7 ms` and passes. At 3 ms it has `R=8 ms` and misses once. P11 explained where a defensible `B`
can come from; P12 does not turn an arbitrary observed mutex delay into a universal bound.

## Deliberately broken assumption: completion spacing is release jitter

Set every release offset to zero while retaining the same response workload. True release jitter is exactly
zero. Now compute the tempting proxy

```text
q_k = (f_k - f_{k-1}) - period.
```

It yields `[1 0 0 1 -1 0 3] ms`, a 4 ms peak-to-peak range. The identity is

```text
q_k = (j_k-j_{k-1}) + (R_k-R_{k-1}).
```

Completion spacing contains response variation, so labeling it release jitter invents arrival variation that
did not occur. Capture or reconstruct `a_k` and subtract `n_k` for release offset; subtract `a_k` from `f_k`
for response. Restoring the baseline input reproduces the exact baseline output because the model has no
persistent state.

## Timestamp resolution is part of the measurement

P04 showed that a completed-tick counter floors event times. P12 applies the same visible operation to release,
start, and completion timestamps. One tolerance derived from that job's three endpoints normalizes values
indistinguishably close to an exact tick; sharing it prevents exponent-boundary disagreement without letting
a distant job alter another job's decision. With a 4 ms timestamp tick and zero release offset, the true
response vector

```text
[2 3 3 3 4 3 3 6] ms
```

is timestamped as

```text
[0 4 0 4 4 4 0 8] ms.
```

Sub-tick responses can collapse to zero and endpoint phases can inflate another interval. The interval error
has magnitude less than one tick in this ideal quantizer, but timestamp resolution is not oscillator accuracy,
clock synchronization, capture latency, interrupt latency, or a target measurement result.

## Timeout, censoring, and an optimistic maximum

The observation timeout compares the fixture response with a configured cutoff. `R=timeout` is retained;
only `R>timeout` times out.

At a 5 ms cutoff, the 6 ms tail job times out. `continue-observing` retains all eight response samples and the
6 ms observed maximum. `cancel-observation` retains seven samples, writes `NaN` for the tail completion
capture and response, and would leave a naive maximum of 4 ms. P12 marks that maximum incomplete and retains
a 5 ms lower bound on the true fixture maximum. It does not claim 4 ms as WCRT.

In general, an uncensored timestamped maximum can be quantized upward. Its safe contribution to a lower bound
on the true fixture maximum is therefore `max(0, measured maximum - timestamp tick)`, combined with the
timeout threshold. A coarse-clock cancellation regression retains this distinction.

Observation cancellation changes no actual release, start, or completion timestamp. It is not asynchronous
RTOS task deletion, mutex cleanup, peripheral rollback, data repair, or plant recovery. Re-running the clean,
state-free input is computational recovery only.

## Limiting cases and resource bounds

- One job has zero peak-to-peak release and response jitter.
- Zero `B`, `I`, and `C` produces zero response without inventing negative duration.
- `R=D` passes; the smallest positive excess misses.
- A response exactly at the timeout passes; a positive excess times out.
- If all observations are censored, the measured maximum, mean, and jitter are `NaN`.
- Row and column vectors normalize to the same per-job record; scalar inputs expand to every job.
- Character and scalar-string policies, integer numeric classes, and empty timeout/action defaults are
  compatible.
- Releases must remain nonnegative and strictly ordered by job ID.
- The model accepts at most 10,000 jobs and derived timestamps at most `1e12` timestamp ticks; caps are checked
  before large per-job outputs are allocated.
- Relative response is formed before absolute timestamps. A nonzero release offset, positive component, or
  positive event advance that disappears at the absolute time's IEEE-double spacing is rejected instead of
  being reported as zero; rescale the time origin and try again.
- Finite large responses use a scaled mean that cannot overflow merely by summing them. If a derived range,
  completion-spacing diagnostic, capture, or aggregate itself is outside finite double range, the record is
  rejected rather than exporting an accidental `Inf` or `NaN`.

## Common mistakes

- Jitter needs a named event and statistic; “the jitter” is not a complete metric.
- Response starts at actual release, while nominal latency starts at the configured phase.
- A constant 9 ms response has zero response jitter but misses an 8 ms deadline every time.
- A small observed maximum is not a guaranteed WCRT without coverage or analysis.
- Dropping timed-out jobs makes a maximum optimistic unless censoring stays visible.
- Completion-interval variation mixes changes in release offset and response.
- A coarse timestamp clock can hide or inflate intervals even when the synthetic event times are exact.
- P11 bounded blocking, P09 scheduling interference, P04 timer quantization, and measured target WCET are
  different evidence inputs.

## Completion standard

Explain `n`, `a`, `s`, `f`, release offset, response, nominal latency, peak-to-peak release and response jitter,
`B+I+C`, deadline equality, observed maximum versus WCRT guarantee, completion-spacing contamination,
timestamp quantization, timeout censoring, rollback, and recovery. Connect bounded blocking back to P11 and
the measurement record forward to P13. Pass `run_checks.m` and answer the teach-back in `checks.md` without
relying on MATLAB syntax.
