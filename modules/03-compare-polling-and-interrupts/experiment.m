%% P03 - Compare Polling and Interrupts
% Read: a transient request is observable only through a stated mechanism.
% Polling samples a level at explicit instants. An interrupt path captures
% rising edges into finite outstanding capacity and dispatches them later.
close all;

%% Baseline - identical deterministic requests, two observation mechanisms
input = p03_scenario('mixed', 0.3);
pollPeriodMs = 0.5;
pollCheckCostMs = 0.02;
interruptLatencyMs = 0.05;
handlerCostMs = 0.20;
queueCapacity = 3;
noMask = zeros(0, 2);

baseline = model(input.event_times_ms, input.pulse_width_ms, input.horizon_ms, ...
    pollPeriodMs, pollCheckCostMs, interruptLatencyMs, handlerCostMs, ...
    queueCapacity, noMask);
baselineRepeat = model(input.event_times_ms, input.pulse_width_ms, input.horizon_ms, ...
    pollPeriodMs, pollCheckCostMs, interruptLatencyMs, handlerCostMs, ...
    queueCapacity, noMask);
assert(isequaln(baseline, baselineRepeat), ...
    'The deterministic baseline changed between identical runs.');
assert(baseline.metrics.poll_detected_count + baseline.metrics.poll_missed_count == ...
    baseline.metrics.total_events, 'Polling accounting must conserve every input event.');
assert(baseline.metrics.interrupt_captured_count + ...
    baseline.metrics.interrupt_dropped_count == baseline.metrics.total_events, ...
    'Interrupt accounting must conserve every input event.');

[pulseTimeMs, pulseLevel] = pulseTrace(baseline.events, baseline.horizon_ms);
figure('Name', 'P03 baseline timing');
subplot(2, 1, 1);
stairs(pulseTimeMs, pulseLevel, 'LineWidth', 1.4);
hold on;
stem(baseline.poll.sample_times_ms, 1.12 * ones(size(baseline.poll.sample_times_ms)), ...
    '.', 'LineWidth', 0.8);
plot(baseline.poll.detection_time_ms(baseline.poll.detected), ...
    0.72 * ones(1, sum(baseline.poll.detected)), 'go', 'MarkerFaceColor', 'g');
plot(baseline.events.arrival_ms(baseline.poll.missed), ...
    0.45 * ones(1, sum(baseline.poll.missed)), 'rx', 'LineWidth', 1.4);
hold off;
grid on;
ylim([-0.1 1.25]);
yticks([0 0.45 0.72 1 1.12]);
yticklabels({'low', 'poll miss', 'poll detected', 'request high', 'poll instant'});
xlabel('Time (ms)');
ylabel('Request / observation');
title('Polling sees only pulses containing an actual poll instant');

subplot(2, 1, 2);
eventIndex = 1:baseline.events.count;
plot(eventIndex, baseline.poll.response_latency_ms, 'o-', 'LineWidth', 1.2);
hold on;
plot(eventIndex, baseline.interrupt.response_latency_ms, 's-', 'LineWidth', 1.2);
plot(eventIndex(baseline.poll.missed), zeros(1, sum(baseline.poll.missed)), ...
    'rx', 'LineWidth', 1.4);
hold off;
grid on;
xlabel('Input event index');
ylabel('Service-start response (ms)');
legend({'Polling response', 'Interrupt response', 'Polling miss marker'}, ...
    'Location', 'northwest');
title('The interrupt path captures every baseline edge, but still has finite latency');

figure('Name', 'P03 baseline metrics');
subplot(2, 1, 1);
bar([baseline.metrics.poll_detected_count baseline.metrics.poll_missed_count; ...
    baseline.metrics.interrupt_captured_count baseline.metrics.interrupt_dropped_count]);
grid on;
xticks([1 2]);
xticklabels({'Polling', 'Interrupt'});
ylabel('Event count');
legend({'Handled', 'Missed / dropped'}, 'Location', 'eastoutside');
title('Same requests, mechanism-specific outcomes');
subplot(2, 1, 2);
bar(100 * [baseline.poll.cpu_busy_fraction baseline.interrupt.cpu_busy_fraction]);
grid on;
xticks([1 2]);
xticklabels({'Polling', 'Interrupt'});
ylabel('Modeled event-handling CPU fraction (%)');
title('Modeled work, not measured processor utilization');

fprintf(['Baseline metrics: %d requests; polling detected %d and missed %d; ' ...
    'interrupt captured %d and dropped %d. Poll response worst %.2f ms; ' ...
    'interrupt response worst %.2f ms.\n'], baseline.metrics.total_events, ...
    baseline.metrics.poll_detected_count, baseline.metrics.poll_missed_count, ...
    baseline.metrics.interrupt_captured_count, baseline.metrics.interrupt_dropped_count, ...
    baseline.metrics.poll_worst_response_ms, ...
    baseline.metrics.interrupt_worst_response_ms);

%% Sweep 1 - poll period, with pulses and interrupt configuration fixed
pollPeriodSweepMs = [0.25 0.5 1 2];
pollDetectedCounts = zeros(size(pollPeriodSweepMs));
pollMissedCounts = zeros(size(pollPeriodSweepMs));
pollCpuPercent = zeros(size(pollPeriodSweepMs));
interruptCapturedDuringPollSweep = zeros(size(pollPeriodSweepMs));
for sweepIndex = 1:numel(pollPeriodSweepMs)
    swept = model(input.event_times_ms, input.pulse_width_ms, input.horizon_ms, ...
        pollPeriodSweepMs(sweepIndex), pollCheckCostMs, interruptLatencyMs, ...
        handlerCostMs, queueCapacity, noMask);
    pollDetectedCounts(sweepIndex) = swept.metrics.poll_detected_count;
    pollMissedCounts(sweepIndex) = swept.metrics.poll_missed_count;
    pollCpuPercent(sweepIndex) = 100 * swept.poll.cpu_busy_fraction;
    interruptCapturedDuringPollSweep(sweepIndex) = ...
        swept.metrics.interrupt_captured_count;
end
assert(isequal(pollDetectedCounts, [10 6 2 2]), ...
    'The fixed fixture must expose the expected poll-period detection limit.');
assert(all(interruptCapturedDuringPollSweep == baseline.metrics.interrupt_captured_count), ...
    'The poll-period lever must not mutate the interrupt mechanism.');

figure('Name', 'P03 poll-period sweep');
subplot(2, 1, 1);
plot(pollPeriodSweepMs, pollDetectedCounts, 'o-', 'LineWidth', 1.2);
hold on;
plot(pollPeriodSweepMs, pollMissedCounts, 'x--', 'LineWidth', 1.2);
hold off;
grid on;
xlabel('Poll period (ms)');
ylabel('Event count');
legend({'Detected', 'Missed'}, 'Location', 'eastoutside');
title('Lever 1 changed view: slower sampling misses more short pulses');
subplot(2, 1, 2);
plot(pollPeriodSweepMs, pollCpuPercent, 'd-', 'LineWidth', 1.2);
grid on;
xlabel('Poll period (ms)');
ylabel('Modeled event-handling CPU fraction (%)');
title('Shorter periods add checks and can change serviced-handler work');
fprintf(['Mechanism for sweep 1: each pulse is [arrival, end); a poll detects it only ' ...
    'when a generated poll instant lies inside that half-open interval. The CPU total ' ...
    'combines periodic checks with handlers for requests actually detected.\n']);

%% Sweep 2 - interrupt mask duration, with polling and queue capacity fixed
maskDurationSweepMs = [0 1 2 4];
interruptCapturedCounts = zeros(size(maskDurationSweepMs));
interruptDropCounts = zeros(size(maskDurationSweepMs));
interruptWorstResponseMs = zeros(size(maskDurationSweepMs));
pollDetectedDuringMaskSweep = zeros(size(maskDurationSweepMs));
for sweepIndex = 1:numel(maskDurationSweepMs)
    maskWindowsMs = makeMask(input.mask_start_ms, maskDurationSweepMs(sweepIndex));
    swept = model(input.event_times_ms, input.pulse_width_ms, input.horizon_ms, ...
        pollPeriodMs, pollCheckCostMs, interruptLatencyMs, handlerCostMs, ...
        queueCapacity, maskWindowsMs);
    interruptCapturedCounts(sweepIndex) = swept.metrics.interrupt_captured_count;
    interruptDropCounts(sweepIndex) = swept.metrics.interrupt_dropped_count;
    interruptWorstResponseMs(sweepIndex) = swept.metrics.interrupt_worst_response_ms;
    pollDetectedDuringMaskSweep(sweepIndex) = swept.metrics.poll_detected_count;
end
assert(isequal(interruptCapturedCounts, [10 10 9 7]), ...
    'Finite interrupt capacity must expose the expected masked-burst losses.');
assert(isequal(interruptDropCounts, [0 0 1 3]), ...
    'Interrupt drop counts must complement captured counts.');
assert(all(pollDetectedDuringMaskSweep == baseline.metrics.poll_detected_count), ...
    'The interrupt-mask lever must not mutate the polling mechanism.');

figure('Name', 'P03 interrupt-mask sweep');
subplot(2, 1, 1);
plot(maskDurationSweepMs, interruptDropCounts, 's-', 'LineWidth', 1.2);
grid on;
xlabel('Interrupt mask duration (ms)');
ylabel('Dropped event count');
title('Lever 2 changed view: a finite queue overruns during a masked burst');
subplot(2, 1, 2);
plot(maskDurationSweepMs, interruptWorstResponseMs, 'o-', 'LineWidth', 1.2);
grid on;
xlabel('Interrupt mask duration (ms)');
ylabel('Worst service-start response (ms)');
title('Retained requests wait until dispatch is eligible');
fprintf(['Mechanism for sweep 2: masking delays dispatch while capacity counts both ' ...
    'queued and in-service requests; arrivals beyond that capacity are dropped.\n']);

%% Broken case - assume one outstanding slot preserves an arbitrary masked burst
brokenMaskMs = [6 10];
broken = model(input.event_times_ms, input.pulse_width_ms, input.horizon_ms, ...
    pollPeriodMs, pollCheckCostMs, interruptLatencyMs, handlerCostMs, 1, brokenMaskMs);
recoveryIndex = find(abs(input.event_times_ms - 11.5) < 10 * eps, 1, 'first');
assert(broken.metrics.interrupt_dropped_count == 5, ...
    'The broken one-slot assumption must lose five events in the masked burst.');
assert(broken.interrupt.captured(recoveryIndex) && ...
    broken.interrupt.finish_ms(recoveryIndex) < input.horizon_ms, ...
    'A post-drain event must prove interrupt-path recovery.');

figure('Name', 'P03 broken interrupt-capacity assumption');
subplot(2, 1, 1);
stairs(pulseTimeMs, pulseLevel, 'LineWidth', 1.2);
hold on;
patch([brokenMaskMs(1) brokenMaskMs(2) brokenMaskMs(2) brokenMaskMs(1)], ...
    [0 0 1.15 1.15], [0.85 0.85 0.85], ...
    'FaceAlpha', 0.35, 'EdgeColor', 'none');
plot(input.event_times_ms(broken.interrupt.captured), ...
    0.72 * ones(1, sum(broken.interrupt.captured)), 'go', 'MarkerFaceColor', 'g');
plot(input.event_times_ms(broken.interrupt.dropped_overrun), ...
    0.45 * ones(1, sum(broken.interrupt.dropped_overrun)), 'rx', 'LineWidth', 1.5);
hold off;
grid on;
ylim([-0.1 1.2]);
xlabel('Time (ms)');
ylabel('Request / interrupt outcome');
legend({'Request pulse', 'Mask window', 'Captured', 'Dropped'}, ...
    'Location', 'eastoutside');
title('Broken assumption: one outstanding slot can remember an unlimited burst');
subplot(2, 1, 2);
bar([broken.metrics.interrupt_captured_count broken.metrics.interrupt_dropped_count]);
grid on;
xticks([1 2]);
xticklabels({'Captured', 'Dropped'});
ylabel('Event count');
title('Recognizable symptom: silent event loss before post-drain recovery');

fprintf(['Broken-case explanation: the first masked edge occupies the only outstanding ' ...
    'slot, five later burst edges overrun it, and the 11.5 ms edge succeeds after drain. ' ...
    'This is a synthetic abstraction, not MCU or hardware evidence.\n']);

function [timeMs, level] = pulseTrace(events, horizonMs)
timeMs = [0 reshape([events.arrival_ms; events.end_ms], 1, []) horizonMs];
level = [0 reshape([ones(1, events.count); zeros(1, events.count)], 1, []) 0];
end

function maskWindowsMs = makeMask(maskStartMs, durationMs)
if durationMs == 0
    maskWindowsMs = zeros(0, 2);
else
    maskWindowsMs = [maskStartMs maskStartMs + durationMs];
end
end
