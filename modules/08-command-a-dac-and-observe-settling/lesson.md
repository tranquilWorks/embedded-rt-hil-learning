# Lesson: Command a DAC and Observe Settling

## Guiding question

What inputs, observable effects, and failure modes matter when you command a DAC and Observe Settling?

## Connection to P07

P07 separated an analog input, sample instants, ADC codes, and bus payload. P08 makes the inverse code to voltage
direction explicit and reverses that chain without
reversing its lessons. Software offers a DAC command, a digital record may accept it, an output latch selects
a quantized voltage, and a physical output stage moves. An ADC or oscilloscope can observe that motion only
with its own bandwidth, rails, sampling, and quantization understood. Neither a matching DAC register readback
nor one plausible ADC sample proves the output entered and remained inside a settling band.

## One declared DAC transfer

The baseline requests 2.5 V from an initial request of 0.5 V using a 12-bit unipolar DAC with a 3.3 V
reference. This lesson makes its transfer convention explicit:

```text
L        = 2^B
q        = V_ref/L
k_raw    = round(V_request/q)
k        = min(max(k_raw, 0), L-1)
V_code   = k q.
```

Equivalently for the declared names, `V_target = code LSB`.

With `B=12`, `L=4096` and `q=3.3/4096 V`, about 0.806 mV. The initial request becomes code 621 and
0.5003173828125 V. The command becomes code 3103 and 2.4999755859375 V, so its quantization error is about
-0.0244 mV. The maximum code is 4095 and produces `3.3-q V`; a unipolar code does not reach an invented
4096th level at exactly 3.3 V.

Other DACs may use offset-binary or signed codes, gain/offset calibration, internal references, segmented
architectures, multiple registers, or device-specific rounding. The declared convention is a transparent
fixture, not a universal data-sheet transfer function.

## Command record, active latch, and zero-order hold

The command is offered at `t=0`. A normal update becomes active after the declared latency `t_u=100 us`.
Before `t_u`, the held code and target stay at their initial values. At and after `t_u`, the active code is
3103 and the target is held at its quantized voltage:

```text
k_hold(t) = k_initial,  t < t_u
k_hold(t) = k_command,  t >= t_u.
```

The analog voltage is continuous at `t_u`; changing a target is not the same as teleporting the output. The
model distinguishes the digital command record, the active output code, and the analog voltage. This matters
for DACs with input and update registers, triggered multi-channel updates, or a failed latch path.

P05 and P06 showed that framing and bus behavior have their own timing and failure modes. This fixture does
not model those transactions: `t_u` is the already-declared latency from offered command to output-latch
event. A real timing budget must add serialization, arbitration, software scheduling, chip-select or update
signals, and device timing from the relevant data sheet.

## One prediction before the baseline

For the 0.5 V to 2.5 V request, predict which happens first: the code update at 100 us or entry into the
10 mV settling tolerance. Which event could a register readback observe, and which requires analog evidence?

## First-order settling with a slew cap

Let `D=|V_target-V_initial|`, `u=max(t-t_u,0)`, `tau` be the small-signal time constant, and `S` the maximum
large-signal slope. Without a binding slew limit, the remaining error is

```text
e(u) = D exp(-u/tau).
```

With update-relative time named `t`, this is the familiar `exp(-t/tau)` first-order tail.

Its initial slope magnitude would be `D/tau`. When `S < D/tau`, the fixture first ramps at `S` until the
remaining error reaches `S tau`. The transition time and piecewise error are

```text
u_s  = D/S - tau
e(u) = D - S u,                         0 <= u <= u_s
e(u) = S tau exp(-(u-u_s)/tau),         u > u_s.
```

Both value and slope are continuous at `u_s`; the slew threshold is the remaining error `S tau`. The baseline
quantized step is 1.999658203125 V. Its natural
initial slope is about 7998.63 V/s, above the declared 4000 V/s cap, so it slews for about 249.915 us and then
follows the exponential tail.

This monotonic, single-pole fixture intentionally has no overshoot or ringing. A real output can enter a band,
leave it, and re-enter; that is why a settling specification says enter and remain, and why the sampled check
retains an all-future condition rather than accepting the first isolated hit.

## Tolerance and observed settling

The 10 mV tolerance is centered on the quantized target, not the unattainable requested value. For an error
band `E_tol`, the analytic time after the latch is

```text
t_settle = 0,                                      D <= E_tol
t_settle = tau ln(D/E_tol),                        S >= D/tau
t_settle = (D-E_tol)/S,                            slew limited and E_tol >= S tau
t_settle = u_s + tau ln(S tau/E_tol),              otherwise.
```

For the baseline, analytic settling is about 1.401207 ms after the update, or 1.501207 ms after the command.
The observation grid is every 5 us, so the first retained sample that enters and stays is 1.505 ms after the
command. Analytic event time and sampled detection time answer different questions. A short trace can end
before either event without making the underlying response infinite.

## Lever 1: output time constant

Hold the requested voltages, reference, bit depth, 100 us latency, 4000 V/s slew limit, 10 mV tolerance,
sample grid, and fault/deadline policy fixed. Sweep `tau=[100 250 500 1000 2000] us`. A larger `tau` slows
the exponential tail and increases the analytic settling time. At small `tau`, the natural initial slope is
larger, so the same large-signal slew cap can dominate more of the early response. Only `tau` changes; the
command code, quantized target, latency, and tolerance do not.

## Lever 2: slew rate

Reset `tau` to 250 us, then sweep `S=[Inf 8000 4000 2000 1000] V/s`. Infinite and sufficiently high `S`
recover the pure exponential. Lower `S` lengthens the initial ramp before the same pole controls the tail.
Only the slope limit changes; the digital codes, held target, latency, pole, and tolerance remain fixed.

## Deliberately broken assumption: a recorded command reached the output

The `update-not-latched` diagnostic represents a command code recorded in a digital-facing register while the
active output latch remains at code 621. The digital command is complete and code 3103 is inspectable, but the
held target and analog voltage remain at about 0.5003 V. The intended error therefore never enters the 10 mV
band. This does not claim a universal DAC register architecture; it isolates the broader failure: digital
success and readback are not physical output evidence.

Recovery removes the fault and calls the pure model again. The result exactly matches the baseline because
the calculation owns no persistent state. A real recovery may require an update pulse, peripheral reset,
power cycle, fault clear, safe-state decision, and independent analog observation.

## Deadline, rollback, and cancellation boundary

The deterministic command deadline compares update latency with caller policy. Equality passes. One
representable step before the 100 us latency, 50 us, and zero all reject the update, expose no recorded code,
and keep the active code and physical output at their initial values. The offered target remains visible for
diagnosis, but it is not mislabeled as applied.

Removing the deadline exactly restores the clean result. This is computational rollback and retry, not an
undo of bus traffic or an already changed voltage. There is no asynchronous wait, device request, partial
external write, or cancellation API in this bounded calculation, so cancellation is not applicable. A real
driver must define whether cancellation can stop a not-yet-latched command and what happens after the latch.

## Common mistakes

- A correct code or successful bus write proves neither output-latch activity nor analog settling.
- `V_ref/2^B` is the declared LSB; the maximum ideal code voltage is `V_ref-LSB` in this convention.
- Quantization error is measured against the request; settling error is measured against the quantized target.
- Bit depth changes target resolution but not the modeled latch latency, time constant, or slew rate.
- A small-signal time constant alone does not describe a large step when slew rate binds.
- A first sample inside tolerance is not enough for a response that can ring or glitch.
- Analytic settling time and sample-grid detection are related but not identical.
- A command deadline is not proof of bus-driver cancellation or hardware rollback.
- This ideal monotonic response does not establish load stability, converter fidelity, or physical timing.

## Completion standard

Explain the transfer convention, zero-order hold, update latency, hybrid settling equations, target-centered
tolerance, and sampled stay rule; predict both lever effects; distinguish quantization, timeout, a recorded-
but-unlatched update, and a slow response; state the cancellation and evidence boundaries; pass
`run_checks.m`; and answer the teach-back in `checks.md` without relying on MATLAB syntax.
