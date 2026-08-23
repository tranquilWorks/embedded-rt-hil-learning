# P16 walkthrough: Execute a Multi-Rate Processing Graph

## Learner sequence

### 1. Connect aligned timestamps to graph firing

Read the guiding question: What inputs, observable effects, and failure modes matter when you execute a
Multi-Rate Processing Graph?

Carry P15's reference-aligned, ordered timestamps forward. State the new boundary directly: timestamp agreement
does not define node firing rate, upstream value visibility, execution cost, worker availability, or timeout action.

### 2. Make one prediction

The slow node costs `1200 us`. Predict whether changing its firing period from `4000 us` (`D=4`) to `1000 us`
(`D=1`) keeps inclusive outstanding work bounded. Ask no second prediction before showing the baseline.

### 3. Read the baseline value view

Expected observation: the fast two-sample filter begins `[0 0.5 1.5 2.5 ...]`; eight slow frames emit
`[1.125 5 9 13 17 21 25 29]` engineering units. Ask why the first output is not the raw four-sample mean.
Connect the answer to edge ownership: the frame consumes fast outputs, not raw inputs.

### 4. Read the baseline timing view

Expected observation: input/output rates are `1000/250 Hz`, slow utilization is `0.30`, every latency is
`1300 us`, every slack is `700 us`, and inclusive outstanding depth remains one. Clarify that this counts the
arriving frame plus prior work still waiting or in service. Ask which statement comes from the rate ratio
and which comes from execution timing.

### 5. Move lever 1: decimation factor

Sweep only `D=[1 2 4 8]`. Expected output rates are `[1000 500 250 125] Hz`; slow utilization is
`[1.2 0.6 0.3 0.15]`; timeout counts are `[28 0 0 0]`; maximum outstanding depths are `[7 1 1 1]` frames.

Explain after the changed view: `D` changes frame membership, firing count, nominal rate, and the denominator of
`U_slow=C_slow/(D T_s)`. At `D=1`, backlog adds `200 us` per frame.

### 6. Reset, then move lever 2: slow-node cost

Reset every baseline input. Sweep only `[200 800 1200 1800 4200] us/frame`. Expected maximum latencies are
`[300 900 1300 1900 5700] us`, minimum slack values are `[1700 1100 700 100 -3700] us`, and only the final
case has utilization above one.

Explain after the changed view: cost consumes finish-time slack without changing frame values, membership, or
nominal output rate. At `4200 us`, service also extends across the next `4000 us` release interval.

### 7. Break topological visibility

Select **Broken consumer first**. Expected observation: frame zero underflows, later frame outputs are one
engineering unit low, and every consumed timestamp is `1000 us` behind its expected frame timestamp. Correct the
misconception directly: more deadline slack cannot make an unpublished current producer value visible.
Explain that this is the baseline symptom; an overloaded fast worker can leave fewer complete values visible and
produce multiple underflows with a larger sample lag. Confirm that each underflow is rejected before slow-worker
admission, so it consumes no service time and cannot fabricate later backlog or timeout failures.

### 8. Inspect timeout equality, continuation, and cancellation

With baseline `D=4`, a `1900 us` slow cost completes at exactly `2000 us` latency and all eight outputs emit. In
the overloaded `D=1` diagnostic, continue-processing emits all 32 and marks 28 late; cancel-frame emits four,
cancels 28, and lowers maximum outstanding depth from seven to two.

Expected observation: both actions preserve source and computed values. Cancellation changes output availability
and future worker availability. Return to editable baseline and confirm exact clean recovery. Describe it as pure
model rerun, not processor, task, DMA, watchdog, or plant rollback.

### 9. Check and teach back

Run `run_module_checks('P16')`. Then give two sentences: first connect aligned inputs, integer rate relation,
producer visibility, worker costs, and timeout policy to outputs; second explain overload, stale data, underflow,
timeout/cancellation, observed metrics, and the evidence boundary.

## Tutor pacing

Present one value or timing transition at a time. Ask one observation question, wait, then connect it to the rate,
utilization, start/finish, and timeout equations with units. Run checks before requesting the teach-back.
Static and independent simulated results are not MATLAB-runtime, rendered-UI, real-concurrency, processor, DMA,
bench, HIL, field, RT1/RT2, Unreal, signing, release, deployment, staging, or production evidence.
