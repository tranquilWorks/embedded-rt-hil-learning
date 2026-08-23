# P14 walkthrough: Prevent Ring-Buffer Overrun

## Learner sequence

1. Read the guiding question: What inputs, observable effects, and failure modes matter when you prevent
   Ring-Buffer Overrun?
2. Connect P13's completed synthetic record to one producer-ready event. Do not re-open DMA timing.
3. Read the counted-ring rules: `q=0` is empty, `q=C` is full, all `C` slots are usable, and
   `next=1+mod(current,C)` wraps a pointer.
4. Make one prediction: with equal average producer and consumer capacity, will the baseline need one slot,
   four slots, or unbounded capacity?
5. Run `experiment` and inspect only the baseline occupancy view. Expected producer-side occupancy is
   `[1 2 3 4]` repeated eight times; peak and required capacity are four samples.
6. Inspect the residence view next. Expected IDs are `1:32`, ages repeat `[200 150 100 50] us`, and final
   drain is `1600 us`.
7. Explain why `rho=1` still permits four records to accumulate before each consumer visit.
8. Sweep only capacity through `[1 2 3 4 6 8]` samples. Expect loss `[24 16 8 0 0 0]`, peak occupancy
   `[1 2 3 4 4 4]`, and consumed counts `[8 16 24 32 32 32]`.
9. Read the first mechanism: capacity changes finite headroom while timing and offered load remain fixed.
10. Reset every input to baseline. Sweep only consumer quota through `[1 2 3 4 5 8]` samples/service.
11. Expect loss `[17 10 3 0 0 0]`, required capacity `[25 18 11 4 4 4]`, and drain time
    `[3000 2200 2000 1600 1600 1600] us`.
12. Read the second mechanism: quota changes service capacity and `rho=T_c/(B T_p)`.
13. Run the deliberately broken overwrite-oldest case. Observe bounded occupancy and 32 accepted incoming
    writes beside 21 overwritten old IDs. Name the failed “bounded means loss-free” assumption.
14. Compare overload policies. Drop preserves older queued data, overwrite preserves newer data, and
    throttleable backpressure preserves all IDs by adding `4050 us` of producer stall.
15. Inspect drain timeout. `50 us` passes by equality; `49 us` with continued waiting completes; `49 us`
    with cancellation leaves IDs `29:32` pending without calling them lost.
16. Reset and rerun the baseline. Exact equality with the first result is computational rollback and recovery,
    not a hardware or plant reset.
17. Run `interactive` and move one editable control at a time. Fixed diagnostics reset and lock their controls
    before rendering.
18. Run `run_module_checks('P14')` in MATLAB when a named runtime is available.
19. Answer the interpretation questions in `checks.md`, then give the two-sentence teach-back.

## Expected interpretation

- Long-run service balance and finite accumulation are separate requirements.
- Full is a state, not yet a loss; the policy applied to a full write determines loss or stall.
- Wrapped pointers need occupancy or a full flag to distinguish empty from full.
- A bounded occupancy trace cannot reveal dropped or overwritten identities by itself.
- Backpressure protects data only across a real throttleable producer boundary.
- Cancellation retains queued records and cannot undo earlier consumption or loss.

## Forward boundary

P15 adds clock alignment and timestamps. This P14 trace uses one synthetic clock and establishes no MATLAB
runtime, UI, atomicity, DMA, physical hardware, bench, HIL, field, or production behavior.
