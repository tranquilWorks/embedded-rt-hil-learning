# Walkthrough: Protect Shared Data Without Excess Blocking

1. Read the guiding question and connect P10's direct blocking to the new design lever: which work is placed
   inside the mutex, not merely which task inherits priority.
2. Make one prediction only: decide whether inheritance can erase private preparation held by a coarse mutex,
   and separate preparation from shared-word commit.
3. Run `experiment.m`. Inspect only the baseline CPU-owner and mutex-owner views. Identify private preparation,
   writer acquire, reader request/block, inherited writer service, unlock, reader copy, local processing, and
   milliseconds.
4. Inspect the record-progress view next. Find the mixed live interval after word one changes and explain why
   the protected reader cannot observe it. Confirm copied generation `[1 1]`.
5. Move one lever through writer private preparation `[2 3 4 5] ms` with reader release fixed at 1 ms. Compare
   short and coarse wait, response, scope-excess time, and observed generation.
6. State the tradeoff directly: short scope returns coherent generation 0 without waiting; coarse scope waits
   for generation 1. Coherence is not a hidden freshness promise.
7. Reset preparation to 2 ms and reader release to 3 ms. Move the second lever through protected record sizes
   `[2 3 4 5]` words. Explain one-for-one commit wait and the additional one-for-one copy cost.
8. Explain both changed views with `H_coarse=C_prepare+C_commit`, `H_short=C_commit`,
   `B_reader=B_commit+B_scope-excess`, and `R_reader=B_reader+C_copy+C_process`.
9. Open `interactive.m`. Move one control, describe one plot transition, then reset before moving another.
10. Select `Unprotected torn read (fixed)`. Verify unchanged numeric work and final record, then identify
    observed values `[101 2]`, generations `[1 0]`, zero wait, and the failed coherence invariant.
11. Select both timeout diagnostics. Distinguish exact handoff from timeout, continued waiting from reader
    cancellation, cancellation from unlock, and computational recovery from data or physical rollback.
12. Check early-reader, zero-preparation, zero-processing, exact timeout, release-at-horizon, short-horizon,
    malformed-input, callback-lifetime, compatibility, and resource-bound cases.
13. State what remains absent: multiple participants, nested locks, lock-free publication, compiler/cache/
    barrier behavior, multicore ordering, measured WCET, kernel traces, hardware behavior, and safe cleanup.
14. Connect bounded lock hold to P12 response-time and jitter inputs, run `run_checks.m`, answer one
    interpretation question at a time, and give the two-sentence teach-back.

The calculations are deterministic and synthetic. They do not provide MATLAB-runtime evidence, an RTOS,
processor, mutex, or memory-ordering implementation test, bench, HIL, field, RT1/RT2, Unreal, signing,
release, deployment, staging, or production evidence.
