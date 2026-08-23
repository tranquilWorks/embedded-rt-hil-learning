# Checks: Measure Timer Quantization

## Observation check

On the baseline interval view, choose one 30 us result and one 40 us result. For each pair, divide both
edge times by `q = 10 us`, floor the completed-tick positions, and explain the measured tick difference
before looking at the error plot.

## Independent calculation

For a start at 100 us and a true interval of 37 us with `q = 10 us`, calculate captures and interval at
`phi = 0 us`, then repeat at `phi = 3 us`. Confirm results of 30 us and 40 us and errors of -7 us and
+3 us. Explain why subtracting the two endpoint errors permits a positive interval error.

For an eight-bit timer with `q = 10 us`, calculate the modulus (256 counts), maximum raw count (255),
and wrap period (2560 us). Starting at count 255 and stopping at count 2, compare ordinary signed and
modular subtraction.

## Limiting cases

- What should an empty fixture and a zero-length interval return?
- Why does an interval equal to an integer number of ticks measure exactly at every phase?
- How can a positive sub-tick interval capture zero elapsed ticks at one phase and one tick at another?
- Why is the valid interval-error bound one tick rather than half a tick?
- Why do more counter bits extend range without improving resolution?
- Why is a mathematically exact decimal tick boundary normalized before flooring?
- What information is missing when the captured unwrapped delta reaches one complete modulus?

## Range ambiguity, timeout, cancellation, rollback, and recovery

An eight-bit, 10 us timer presented with 256 captured ticks has exceeded the unambiguous captured-tick
range. The model marks that pair range-ambiguous and withholds the primary interval instead of calling its
modular zero residue a valid result. The next short pair can still be valid and proves recovery because the
model has no persistent state. Returning to the repeated baseline inputs rolls back the broken diagnostic
view and must reproduce the original structure exactly.

There is no asynchronous timeout, cancellation, transaction, wait loop, or external resource in this
bounded pure calculation. Timeout and cancellation are therefore not applicable; range ambiguity must not
be mislabeled as either one.

## Broken-case check

Name the false assumption that `stop_count - start_count` works across a rollover. Explain why modular
subtraction repairs the three-tick wrapped pair but cannot identify a full unseen counter cycle without an
overflow count or range deadline.

## Interpretation and transfer

Choose a real input-capture design. State its required interval range and desired resolution, then select
a tick and width while keeping oscillator accuracy, synchronizer/capture latency, overflow handling, and
register access as separate requirements. Do not infer measured device behavior from this synthetic model.

## Teach-back

In two sentences, answer the guiding question. Sentence one must connect edge times, tick period, phase,
integer captures, signed interval error, and the one-tick bound. Sentence two must connect counter width,
modular subtraction, naive rollover failure, full-wrap range ambiguity, recovery, and the distinction between
resolution and clock accuracy without relying on MATLAB syntax.

## Executable check

Run:

```matlab
run_checks
```

All assertions must pass before personal learner completion is recorded.
