# P12 — Measure Jitter and Worst-Case Response Time

**Track:** Embedded, Real-Time, and Hardware-in-the-Loop Systems  
**Phase 3:** RTOS behavior  
**Status:** implemented

## Guiding question

What inputs, observable effects, and failure modes matter when you measure Jitter and Worst-Case Response Time?

## Computational mental model

P11 separated required resource blocking from excess lock scope. P12 uses that bounded blocking as one
response-time input and keeps four timestamps distinct for every periodic job `k`:

```text
n_k = nominal release
a_k = actual release
s_k = first execution start
f_k = completion

j_k = a_k - n_k                         release offset
R_k = f_k - a_k = B_k + I_k + C_k       response time
L_k = f_k - n_k = j_k + R_k             nominal completion latency.
```

`B_k` is P11-style bounded blocking, `I_k` is other scheduler interference before first start, and `C_k` is
the job's own execution. This lesson names peak-to-peak jitter explicitly:

```text
J_release,pp  = max(j_k) - min(j_k)
J_response,pp = max(R_k) - min(R_k).
```

The largest response in a finite campaign is an **observed worst response**. It is exact for this declared
synthetic fixture, but it is not automatically a guaranteed worst-case response time for every phasing,
input, cache state, interrupt sequence, or target. The transparent component envelope
`max(B)+max(I)+max(C)` is a conservative bound for the supplied component vectors only.

The baseline has eight jobs, a 20 ms nominal period, release offsets `[0 1 -1 0 1 -1 0 1] ms`, 2 ms own
execution, alternating 0/1 ms blocking, interference `[0 0 1 0 2 0 1 3] ms`, a 7 ms relative deadline,
and 1 ms timestamp ticks. Its response vector is `[2 3 3 3 4 3 3 6] ms`. Release jitter is 2 ms
peak-to-peak, response jitter is 4 ms peak-to-peak, the fixture's observed worst response is 6 ms, the
component envelope is 6 ms, and no job misses the deadline.

## What the learner controls

- **Release-offset amplitude (ms):** signed arrival displacement around the nominal periodic grid.
- **P11 blocking bound (ms):** mutex or shared-resource delay that enters response, not release jitter.
- **Nominal period (ms):** spacing of the configured job releases.
- **Own execution `C` (ms):** service required by each measured job.
- **Relative deadline `D` (ms):** response limit measured from actual release; `R=D` passes.
- **Timestamp tick (ms):** completed-tick resolution of the synthetic event capture.
- **Response timeout (ms):** observation cutoff; zero in the UI disables it.
- **Timeout action:** continue retaining a late response or censor only its measurement.
- **Scenario:** editable baseline or fixed completion-spacing, coarse-clock, timeout, cancellation, and
  exact-boundary diagnostics.

## Complete learning flow

1. Connect P11 blocking to `R=B+I+C`, then make one prediction about whether moving `a_k` changes `f_k-a_k`.
2. Inspect release offsets first; then inspect response components and the deadline.
3. Sweep only release-offset amplitude through `[0 1 2 3] ms`. Release jitter becomes `[0 2 4 6] ms`,
   observed worst response stays `[6 6 6 6] ms`, and worst nominal latency becomes `[6 7 8 9] ms`.
4. Reset release amplitude to 1 ms. Sweep only bounded blocking through `[0 1 2 3] ms`. Observed worst
   response becomes `[5 6 7 8] ms`, response jitter becomes `[3 4 5 6] ms`, and deadline-miss count becomes
   `[0 0 0 1]`.
5. Explain the two transitions from `R=f-a=B+I+C` and `L=f-n=j+R`.
6. Break the measurement by treating completion-interval variation as release jitter. A fixed zero-release-
   jitter fixture still shows 4 ms peak-to-peak completion variation because `delta f` also contains
   `delta R`.
7. Coarsen the timestamp clock, then compare exact timeout, continued observation, censored observation,
   rollback, and clean recovery.
8. Run independent checks and give the two-sentence teach-back.

## Measurement, timeout, and cancellation boundaries

The synthetic logger floors each event time to the last completed timestamp tick, using the same transparent
normalization rule as P04 near exact tick boundaries. Release, start, and completion use one shared
normalization tolerance per job, so an exponent boundary cannot make paired capture rules disagree and an
unrelated far-future job cannot change an earlier job's capture. With a 4 ms tick, true responses
`[2 3 3 3 4 3 3 6] ms` become `[0 4 0 4 4 4 0 8] ms`; a coarse clock can both hide short responses and
inflate the retained maximum. Timer resolution is not clock accuracy, synchronization, capture latency, or
interrupt latency.

A finite response timeout classifies `R>timeout`; equality is retained. `continue-observing` records the
timeout and later completion. `cancel-observation` replaces that completion capture and response sample with
`NaN`, increments a censored count, and marks the measured maximum as incomplete. It does not change the
synthetic start or completion, cancel an RTOS task, release a mutex, repair data, undo a peripheral action, or
recover a plant.
If every response is censored, the measured maximum and jitter are unavailable (`NaN`), never zero.
When a retained timestamped maximum contributes to the incomplete observed-worst lower bound, one timestamp
tick is subtracted first; an upward-quantized retained interval cannot masquerade as a lower bound on the true
fixture maximum.

Restoring clean input and re-running the state-free model is computational rollback and recovery only. It is
not target rollback or physical recovery.

## Boundaries and dependencies

The model is per-job additive timestamp accounting. It assumes each supplied `B`, `I`, and `C` component is
already classified, nonnegative, and expressed in the same millisecond time base. It does not derive those
components from a priority recurrence, simulate CPU dispatch, reconstruct preemption intervals, model queued
overlapping releases, or prove that a measured campaign covers every phase. P09 supplies the scheduling
vocabulary; P11 supplies the bounded-blocking connection; P04 supplies timestamp-quantization intuition.
P13 will use timing observations when comparing processor-driven and DMA data movement.

The fixture accepts 1–10,000 jobs and derived timestamps up to `1e12` timestamp ticks, with caps checked
before large per-job allocation. Inputs accept scalar expansion, integer numeric classes, row or column
vectors, character or scalar-string policies, and empty timeout/action defaults. The implementation uses base
MATLAB arithmetic; no Simulink, statistics toolbox, operating-system clock, support package, asynchronous
timer, hardware API, or device trace is required.

The calculation forms response from the relative components before it builds absolute timestamps. If IEEE
double precision would erase a nonzero release offset, a positive component, or a positive absolute-time
advance, the model rejects the record with `P12:model:TimingPrecision` and asks for a rescaled time origin;
it never silently turns positive work into zero response. Per-identity residuals remain visible for accepted
rounding that does not collapse an event. Derived diagnostics and aggregates must also remain finite: the mean
uses scaled arithmetic to avoid a finite-value intermediate overflow, while an unrepresentable completion-
spacing diagnostic is rejected with `P12:model:TimingResourceBound`.

These outputs are deterministic synthetic calculations. They are not MATLAB-runtime evidence, a numerical-
fidelity study, rendered-UI evidence, an RTOS scheduler measurement, processor trace, measured WCET/WCRT,
clock characterization, memory-ordering proof, hardware measurement, bench evidence, HIL evidence, field
evidence, or production evidence. RT1/RT2, Unreal, signing, release, deployment, and staging validation were
not performed.

## Files

- `p12_scenario.m` owns bounded deterministic timestamp fixtures.
- `model.m` owns validation, time identities, timestamp quantization, jitter metrics, deadline classification,
  observation timeout/censoring, component envelope, and finite-trace qualification.
- `experiment.m` owns the baseline, labeled figures, two isolated sweeps, deliberately broken measurement,
  and recovery diagnostics.
- `interactive.m` owns immediate timing controls and complementary release/response views.
- `lesson.m`, `lesson.md`, and `walkthrough.md` own the mechanism-first learner sequence.
- `checks.md` and `run_checks.m` own interpretation prompts and executable invariants.
