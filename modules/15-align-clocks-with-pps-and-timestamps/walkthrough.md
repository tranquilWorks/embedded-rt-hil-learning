# P15 walkthrough: Align Clocks with PPS and Timestamps

## Learner sequence

### 1. Connect preserved records to independent time

Read the guiding question: What inputs, observable effects, and failure modes matter when you align Clocks
with PPS and Timestamps?

Carry P14's record identity and ordering forward. State the new boundary directly: intact ordered records do
not prove that their local timestamps share a reference coordinate.

### 2. Make one prediction

The clock starts `2500 us` ahead and runs `40 ppm` fast. Predict whether removing the first-PPS offset keeps
the next four seconds aligned. Ask no second prediction before showing the baseline.

### 3. Read the baseline event-error view

Expected observation: raw error grows from `2510` to `2650 us`. One-PPS offset-only error grows from `10` to
`150 us`. Correct first/last affine alignment is zero in the ideal governing arithmetic.

Ask why offset-only correction leaves a slope. Connect the `20 us` rise per `500000 us` event interval to
`40 ppm`; do not begin with MATLAB syntax.

### 4. Read the PPS-anchor view

Expected observation: local-minus-reference PPS error rises from `2500` to `2660 us`. Five correctly named
anchors recover `2500 us` offset and `40 ppm` skew with zero ideal residual.

Ask which information comes from the sharp edge and which comes from its sequence/timestamp identity.

### 5. Move lever 1: initial offset

Sweep only `[0 1000 2500 5000 10000] us`. Expected first errors are
`[10 1010 2510 5010 10010] us`; expected final errors are `[150 1150 2650 5150 10150] us`.

Explain after the change: offset translates the curve without changing its `140 us` rise.

### 6. Reset, then move lever 2: oscillator skew

Reset every baseline input, then sweep only `[-80 -40 0 40 80] ppm`. Expected four-second drift is
`[-320 -160 0 160 320] us`; expected offset-only maximum error is `[300 150 0 150 300] us`.

Explain after the change: skew changes slope and sign. Two correctly associated anchors identify ideal rate;
one anchor cannot.

### 7. Break PPS association

Use received IDs `[0 2 3 4]`. First keep sequence-ID association: the missing ID is visible and the ideal fit
remains exact. Then switch to arrival-index association.

Expected observation: the wrong fit reports about `333386.667 ppm`, interior PPS residual reaches about
`666693 us`, and final event error is `-937500 us`. Correct the misconception directly: four captures do not
imply four consecutive seconds.

### 8. Inspect tick resolution

Select the coarse timestamp diagnostic. Expected observation: flooring to a larger tick changes captured
anchors and event errors. More displayed decimal places cannot restore discarded counter resolution.

Keep the numerical boundary explicit: this transparent model supports absolute tick indices through `1e12`
and rejects finer configurations that double precision cannot floor without an ambiguous ULP band.

### 9. Inspect timeout, cancellation, rollback, and recovery

With a missing-ID gap of `2000000 us`, a `2000000 us` timeout passes by equality. At `1500000 us`, continue
waiting records lateness and retains all captures. Cancel alignment retains only ID `0`, censors IDs `2:4`,
and leaves the affine estimate unavailable.

Expected observation: cancellation never changes the raw local event timestamps. Return to editable baseline
and confirm exact clean recovery. Describe that as pure-model reset, not receiver or oscillator rollback.

### 10. Check and teach back

Run `run_module_checks('P15')`. Then give two sentences: first connect offset, skew, tick, PPS edge, and trusted
epoch identity to correction; second explain missing association, residuals, timeout/cancellation, and the
physical evidence boundary.

## Tutor pacing

Present one view or transition at a time. Ask one observation question, wait, then connect it to the affine
clock equation and units. Run checks before requesting the teach-back. Static and independent simulated
results are not MATLAB-runtime, rendered-UI, PPS/GNSS hardware, oscillator, bench, HIL, field, RT1/RT2,
Unreal, signing, deployment, or production validation.
