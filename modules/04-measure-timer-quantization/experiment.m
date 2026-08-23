%% P04 - Measure Timer Quantization
% Read: P03 produced ideal event times. A finite timer can report only the
% completed tick count at each edge. Here q = prescaler / source-clock rate,
% so changing q changes both resolution and wrap range at fixed counter bits.
close all;

%% Baseline - repeat one true interval at different tick phases
input = p04_scenario('baseline', 37);
tickPeriodUs = 10;
timerPhaseUs = 0;
counterBits = 8;

baseline = model(input.start_time_us, input.true_interval_us, ...
    tickPeriodUs, timerPhaseUs, counterBits);
baselineRepeat = model(input.start_time_us, input.true_interval_us, ...
    tickPeriodUs, timerPhaseUs, counterBits);
assert(isequaln(baseline, baselineRepeat), ...
    'The deterministic baseline changed between identical runs.');
expectedElapsedTicks = [3 4 4 3 4 4 3 4 4 4 3 4];
expectedErrorUs = expectedElapsedTicks .* tickPeriodUs - 37;
assert(isequal(baseline.measurement.full_elapsed_ticks, expectedElapsedTicks), ...
    'Baseline completed-tick counts must match the independent floor calculation.');
assert(isequal(baseline.measurement.error_us, expectedErrorUs), ...
    'Baseline interval errors must be the difference of two endpoint errors.');
assert(all(baseline.measurement.valid) && ...
    all(abs(baseline.measurement.error_us) < tickPeriodUs), ...
    'Every valid baseline interval must satisfy the strict one-tick error bound.');

observationIndex = 1:baseline.input.count;
figure('Name', 'P04 baseline timer quantization');
subplot(2, 1, 1);
plot(observationIndex, baseline.input.true_interval_us, 'k--', ...
    'LineWidth', 1.2);
hold on;
stairs(observationIndex, baseline.measurement.interval_us, 'o-', ...
    'LineWidth', 1.3);
hold off;
grid on;
xlabel('Capture-pair index');
ylabel('Interval (us)');
legend({'True interval', 'Timer measurement'}, 'Location', 'eastoutside');
title('One 37 us interval becomes either 30 us or 40 us');

subplot(2, 1, 2);
stem(observationIndex, baseline.measurement.error_us, 'filled', ...
    'LineWidth', 1.1);
hold on;
plot(observationIndex, tickPeriodUs .* ones(size(observationIndex)), ...
    'r--', 'LineWidth', 1);
plot(observationIndex, -tickPeriodUs .* ones(size(observationIndex)), ...
    'r--', 'LineWidth', 1);
hold off;
grid on;
xlabel('Capture-pair index');
ylabel('Measurement error (us)');
title('Interval error has either sign but remains strictly inside one tick');

fprintf(['Baseline metrics: %d intervals, %d measured levels, worst absolute ' ...
    'error %.1f us, q %.1f us, wrap period %.1f us.\n'], ...
    baseline.metrics.total_count, baseline.metrics.measured_level_count, ...
    baseline.metrics.worst_abs_error_us, baseline.timer.tick_period_us, ...
    baseline.timer.wrap_period_us);

%% Sweep 1 - tick period, with event times, phase, and counter bits fixed
tickPeriodSweepUs = [1 2 5 10 20];
worstAbsErrorUs = zeros(size(tickPeriodSweepUs));
measuredLevelCounts = zeros(size(tickPeriodSweepUs));
wrapPeriodUs = zeros(size(tickPeriodSweepUs));
rangeAmbiguityCountsDuringTickSweep = zeros(size(tickPeriodSweepUs));
for sweepIndex = 1:numel(tickPeriodSweepUs)
    swept = model(input.start_time_us, input.true_interval_us, ...
        tickPeriodSweepUs(sweepIndex), timerPhaseUs, counterBits);
    worstAbsErrorUs(sweepIndex) = swept.metrics.worst_abs_error_us;
    measuredLevelCounts(sweepIndex) = swept.metrics.measured_level_count;
    wrapPeriodUs(sweepIndex) = swept.timer.wrap_period_us;
    rangeAmbiguityCountsDuringTickSweep(sweepIndex) = ...
        swept.metrics.range_ambiguity_count;
end
assert(isequal(worstAbsErrorUs, [0 1 3 7 17]), ...
    'Tick-period sweep errors must match independent endpoint quantization.');
assert(isequal(measuredLevelCounts, [1 2 2 2 2]), ...
    'Only the one-microsecond tick resolves every 37 us fixture exactly.');
assert(all(rangeAmbiguityCountsDuringTickSweep == 0), ...
    'The tick-period lever must keep this fixture inside captured-tick range.');

figure('Name', 'P04 tick-period sweep');
subplot(2, 1, 1);
plot(tickPeriodSweepUs, worstAbsErrorUs, 'o-', 'LineWidth', 1.3);
grid on;
xlabel('Timer tick period q (us)');
ylabel('Worst absolute interval error (us)');
title('Lever 1 changed view: coarser ticks enlarge the error staircase');
subplot(2, 1, 2);
plot(tickPeriodSweepUs, wrapPeriodUs, 's-', 'LineWidth', 1.3);
grid on;
xlabel('Timer tick period q (us)');
ylabel('Eight-bit wrap period (us)');
title('At fixed width, coarser resolution extends captured-tick range');
fprintf(['Mechanism for sweep 1: each endpoint is floored to a completed tick; ' ...
    'the interval error is their difference, while 2^B q sets wrap range.\n']);

%% Sweep 2 - timer phase, after resetting the tick period
phaseSweepUs = 0:1:9;
phaseMeasuredUs = zeros(size(phaseSweepUs));
phaseErrorUs = zeros(size(phaseSweepUs));
phaseStartUs = 100;
phaseTrueIntervalUs = 37;
for sweepIndex = 1:numel(phaseSweepUs)
    swept = model(phaseStartUs, phaseTrueIntervalUs, tickPeriodUs, ...
        phaseSweepUs(sweepIndex), counterBits);
    phaseMeasuredUs(sweepIndex) = swept.measurement.interval_us;
    phaseErrorUs(sweepIndex) = swept.measurement.error_us;
end
assert(isequal(phaseMeasuredUs, [30 30 30 40 40 40 40 40 40 40]), ...
    'Phase sweep must expose the independently calculated 30/40 us transition.');
assert(isequal(phaseErrorUs, [-7 -7 -7 3 3 3 3 3 3 3]), ...
    'Phase changes endpoint alignment without changing the true interval.');

figure('Name', 'P04 timer-phase sweep');
subplot(2, 1, 1);
stairs(phaseSweepUs, phaseMeasuredUs, 'o-', 'LineWidth', 1.3);
hold on;
plot(phaseSweepUs, phaseTrueIntervalUs .* ones(size(phaseSweepUs)), ...
    'k--', 'LineWidth', 1.1);
hold off;
grid on;
xlabel('Timer phase phi (us)');
ylabel('Measured interval (us)');
legend({'Timer measurement', 'True interval'}, 'Location', 'eastoutside');
title('Lever 2 changed view: fixed duration crosses one endpoint boundary');
subplot(2, 1, 2);
stem(phaseSweepUs, phaseErrorUs, 'filled', 'LineWidth', 1.1);
grid on;
xlabel('Timer phase phi (us)');
ylabel('Measurement error (us)');
title('Phase is deterministic alignment, not random clock jitter');
fprintf(['Mechanism for sweep 2: moving both edges relative to the tick grid ' ...
    'changes whether the stop capture gains one completed tick.\n']);

%% Broken case - subtract wrapped register values as ordinary signed numbers
brokenInput = p04_scenario('wrap-recovery', 37);
broken = model(brokenInput.start_time_us, brokenInput.true_interval_us, ...
    tickPeriodUs, timerPhaseUs, counterBits);
assert(isequal(broken.capture.crossed_wrap, [true false]), ...
    'The fixture must cross wrap once, then provide a non-wrapping recovery pair.');
assert(isequal(broken.measurement.interval_us, [30 30]), ...
    'Modular subtraction must retain both valid three-tick measurements.');
assert(isequal(broken.diagnostic.naive_interval_us, [-2530 30]), ...
    'Naive signed subtraction must expose a recognizable negative rollover symptom.');
assert(broken.diagnostic.naive_negative(1) && ...
    ~broken.diagnostic.naive_negative(2), ...
    'The later non-wrapping pair must prove diagnostic recovery.');
rolledBack = model(input.start_time_us, input.true_interval_us, ...
    tickPeriodUs, timerPhaseUs, counterBits);
assert(isequaln(rolledBack, baseline), ...
    'Returning to modular baseline inputs must roll back the broken view.');

figure('Name', 'P04 broken naive rollover subtraction');
subplot(2, 1, 1);
bar([broken.capture.start_count; broken.capture.end_count]');
grid on;
xlabel('Capture-pair index');
ylabel('Eight-bit timer count (ticks)');
legend({'Start capture', 'Stop capture'}, 'Location', 'eastoutside');
title('First stop count wrapped from 255 back to 0');
subplot(2, 1, 2);
bar([broken.input.true_interval_us; broken.measurement.interval_us; ...
    broken.diagnostic.naive_interval_us]');
grid on;
xlabel('Capture-pair index');
ylabel('Interval (us)');
legend({'True', 'Modular', 'Naive signed'}, 'Location', 'eastoutside');
title('Broken assumption: raw stop minus start survives rollover');

fprintf(['Broken-case explanation: the first raw subtraction reports -2530 us, ' ...
    'modular subtraction reports 30 us, and the next pair recovers after wrap. ' ...
    'This is a synthetic timer abstraction, not hardware evidence.\n']);
