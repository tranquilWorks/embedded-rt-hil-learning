# Checks: Command a DAC and Observe Settling

## Observation check

On the baseline target/response view, identify the requested voltage, quantized initial and command codes,
held target, update event, and analog output. Then use the error view to identify the 10 mV band, analytic
entry time, and first sampled stay. Which observations are digital, which are analog, and which are only
calculated policy results?

## Independent calculations

- Calculate `L=4096`, `LSB=3.3/4096 V`, initial code 621, and command code 3103.
- Calculate the quantized levels 0.5003173828125 V and 2.4999755859375 V and their step magnitude
  1.999658203125 V.
- Compare the natural initial slope `D/tau` with 4000 V/s and derive the 249.91455078125 us slew duration.
- Derive the baseline 1.401207097 ms settling duration after update and 1.501207097 ms after command.
- Explain why the 5 us sample grid first reports an entry-and-remain time of 1.505 ms.

## Limiting cases and compatibility

- Why does a command that quantizes to the initial code settle at the latch event with no analog movement?
- Why does positive infinite slew rate recover the pure exponential `tau*ln(D/E_tol)`?
- At exactly `S=D/tau`, why do the slew-limited and pole-limited formulas meet without a discontinuity?
- Why does requesting exactly `V_ref` produce code `L-1` and `V_ref-LSB` in this convention?
- What changes when the update latency falls between observation samples or beyond the observation horizon?
- Why must supported integer numeric classes and scalar-string fault modes normalize to the same result?

## Positive, negative, malformed, and resource-bound cases

Confirm exact `t_n=n T_s`, bounded codes, held target timing, response continuity, ramp/exponential handoff,
inclusive tolerance, all-future sampled stay, and the exact update-deadline boundary. Reject wrong arity;
nonnumeric, logical, nonfinite, complex, nonscalar, negative, fractional, or out-of-range voltage, reference,
bit-depth, latency, time-constant, slew, tolerance, sample-period/count, deadline, fault-schema, and scenario
inputs. Reject reference/bit-depth combinations whose LSB underflows to zero, and reject sample requests and
derived horizons beyond their explicit bounds before trace allocation. Retain remaining error directly when
testing subnormal tolerances so rounded voltage subtraction cannot invent early settling. A rejected call must
not affect the next valid call.

## Two levers and the deliberately broken assumption

Sweep only time constant while code, latency, slew rate, tolerance, and sample grid remain fixed. Then reset
time constant and sweep only slew rate while code, latency, pole, tolerance, and grid remain fixed. Explain why
neither lever changes the DAC code even though both can change settling time.

Run `update-not-latched`. Require the digital command record to contain code 3103 while the active held code
and output remain at their initial level. The intended error must never satisfy the 10 mV entry-and-remain
condition. Remove the fault and require exact `isequaln` rollback to the baseline. This demonstrates pure-model
recovery and state isolation, not reversal of a register write or voltage on a real device.

## Timeout, cancellation, rollback, and recovery

Accept a deadline exactly at the 100 us update latency. Reject one representable step earlier, 50 us, and
zero; expose no recorded code and do not move the held target or output. Re-invocation with an infinite
deadline must recover the exact baseline.

This finite calculation has no asynchronous wait, driver request, partial external transaction, or
cancellation API, so cancellation is not applicable. A real design must say whether cancellation can prevent
a pending latch, how an already active output reaches a safe value, and which analog observation confirms it.

## Interpretation and transfer

Choose one real actuator or stimulus path. State its code convention and reference range, requested tolerance,
update protocol and latency, load and output-current limits, small- and large-signal settling requirements,
glitch allowance, deadline and retry behavior, safe output, independent measurement bandwidth/sample rate,
and evidence environment. Keep the register-level, active-latch, analog, and observation claims separate.

## Teach-back

In two sentences, answer the guiding question. Sentence one must connect requested voltage, code/LSB,
zero-order hold, update latency, time constant, slew rate, target-centered tolerance, and sampled entry-and-
remain observation. Sentence two must distinguish quantization, a recorded-but-unlatched update, command
timeout, slow settling, cancellation boundary, rollback, clean retry, and the hardware measurement still
required—without relying on MATLAB syntax.

## Executable check

Run:

```matlab
run_checks
```

All assertions must pass before personal learner completion is recorded.
