%% P02 - Drive GPIO with a State Machine
% Read: a raw sampled level is an input observation, not yet a command.
% The Moore-style output is high only in ACTIVE and QUALIFY_RELEASE.
close all;

%% Baseline - one bouncy press, qualified before GPIO changes
samplePeriodMs = 1;
debounceMs = 5;
maxOnMs = 80;
baselineInput = p02_scenario('normal', samplePeriodMs, 120, 6);
baseline = model(baselineInput.raw_button, samplePeriodMs, debounceMs, ...
    maxOnMs, baselineInput.cancel);
baselineRepeat = model(baselineInput.raw_button, samplePeriodMs, debounceMs, ...
    maxOnMs, baselineInput.cancel);

assert(isequal(baseline.state_code, baselineRepeat.state_code), ...
    'The deterministic baseline changed between identical runs.');
assert(isequal(baseline.gpio, baselineRepeat.gpio), ...
    'The deterministic GPIO output changed between identical runs.');

figure('Name', 'P02 baseline transitions');
subplot(3, 1, 1);
stairs(baseline.time_ms, double(baseline.raw_button), 'LineWidth', 1.2);
hold on;
stairs(baseline.time_ms, double(baseline.cancel), '--', 'LineWidth', 1.1);
hold off;
grid on;
ylim([-0.1 1.1]);
yticks([0 1]);
yticklabels({'low', 'high'});
xlabel('Time (ms)');
ylabel('Input logic');
legend({'Raw button', 'Cancel'}, 'Location', 'eastoutside');
title('Read the sampled inputs before interpreting the output');

subplot(3, 1, 2);
stairs(baseline.time_ms, double(baseline.state_code), 'LineWidth', 1.2);
grid on;
ylim([-0.2 4.2]);
yticks(0:4);
yticklabels(baseline.state_names);
xlabel('Time (ms)');
ylabel('State code');
title('The controller exposes qualification and safety states');

subplot(3, 1, 3);
stairs(baseline.time_ms, double(baseline.gpio), 'LineWidth', 1.4);
grid on;
ylim([-0.1 1.1]);
yticks([0 1]);
yticklabels({'safe low', 'command high'});
xlabel('Time (ms)');
ylabel('GPIO logic');
title('Observable simulated GPIO command');

figure('Name', 'P02 baseline metrics');
baselineCounts = [baseline.metrics.accepted_presses, ...
    baseline.metrics.gpio_rising_edges, baseline.metrics.timeout_count, ...
    baseline.metrics.cancel_count];
bar(baselineCounts);
grid on;
xticks(1:4);
xticklabels({'Accepted presses', 'GPIO rises', 'Timeouts', 'Cancels'});
ylabel('Event count');
title(sprintf('Baseline: N_d = %d samples, max high run = %.1f ms', ...
    baseline.debounce_samples, baseline.metrics.max_high_run_ms));

fprintf(['Baseline metrics: sample period %.1f ms, qualified debounce %.1f ms, ' ...
    'GPIO high %.1f ms, maximum high run %.1f ms, rising edges %d.\n'], ...
    baseline.sample_period_ms, baseline.quantized_debounce_ms, ...
    baseline.metrics.gpio_high_time_ms, baseline.metrics.max_high_run_ms, ...
    baseline.metrics.gpio_rising_edges);

%% Sweep 1 - debounce time, with input trace and maximum-on time fixed
debounceSweepMs = [0 3 7];
debounceRises = zeros(size(debounceSweepMs));
firstHighMs = nan(size(debounceSweepMs));
for sweepIndex = 1:numel(debounceSweepMs)
    swept = model(baselineInput.raw_button, samplePeriodMs, ...
        debounceSweepMs(sweepIndex), maxOnMs, baselineInput.cancel);
    debounceRises(sweepIndex) = swept.metrics.gpio_rising_edges;
    firstHighIndex = find(swept.gpio, 1, 'first');
    if ~isempty(firstHighIndex)
        firstHighMs(sweepIndex) = swept.time_ms(firstHighIndex);
    end
end

figure('Name', 'P02 debounce sweep');
subplot(2, 1, 1);
plot(debounceSweepMs, debounceRises, 'o-', 'LineWidth', 1.2);
grid on;
xlabel('Requested debounce time (ms)');
ylabel('GPIO rising edges (count)');
title('Lever 1 changed view: qualification rejects bounce-driven edges');
subplot(2, 1, 2);
plot(debounceSweepMs, firstHighMs, 'o-', 'LineWidth', 1.2);
grid on;
xlabel('Requested debounce time (ms)');
ylabel('First GPIO high time (ms)');
title('Longer qualification also adds a bounded response delay');
fprintf(['Mechanism for sweep 1: N_d = ceil(debounce/sample period); ' ...
    'only N_d consecutive high samples enter ACTIVE.\n']);

%% Sweep 2 - maximum-on time, reset to fixed debounce and stuck input
stuckInput = p02_scenario('stuck-high', samplePeriodMs, 120, 6);
maxOnSweepMs = [15 30 55];
observedHighRunMs = zeros(size(maxOnSweepMs));
timeoutCounts = zeros(size(maxOnSweepMs));
for sweepIndex = 1:numel(maxOnSweepMs)
    swept = model(stuckInput.raw_button, samplePeriodMs, debounceMs, ...
        maxOnSweepMs(sweepIndex), stuckInput.cancel);
    observedHighRunMs(sweepIndex) = swept.metrics.max_high_run_ms;
    timeoutCounts(sweepIndex) = swept.metrics.timeout_count;
end

figure('Name', 'P02 maximum-on sweep');
subplot(2, 1, 1);
plot(maxOnSweepMs, observedHighRunMs, 's-', 'LineWidth', 1.2);
hold on;
plot(maxOnSweepMs, maxOnSweepMs, '--', 'LineWidth', 1.0);
hold off;
grid on;
xlabel('Requested maximum-on time (ms)');
ylabel('Longest GPIO high run (ms)');
legend({'Observed', 'Requested'}, 'Location', 'northwest');
title('Lever 2 changed view: timeout bounds a stuck request');
subplot(2, 1, 2);
bar(maxOnSweepMs, timeoutCounts);
grid on;
xlabel('Requested maximum-on time (ms)');
ylabel('Timeout events (count)');
title('The input remains high, but lockout prevents retrigger');
fprintf(['Mechanism for sweep 2: N_t = floor(maximum-on/sample period); ' ...
    'after N_t high samples the next output sample is safe low.\n']);

%% Broken case - bypass debounce and trust every bouncing sample
brokenInput = p02_scenario('normal', samplePeriodMs, 120, 8);
broken = model(brokenInput.raw_button, samplePeriodMs, 0, 200, brokenInput.cancel);
qualified = model(brokenInput.raw_button, samplePeriodMs, debounceMs, 200, brokenInput.cancel);

figure('Name', 'P02 broken debounce assumption');
subplot(2, 1, 1);
stairs(broken.time_ms, double(broken.raw_button), 'Color', [0.35 0.35 0.35]);
hold on;
stairs(broken.time_ms, double(broken.gpio), 'LineWidth', 1.3);
hold off;
grid on;
ylim([-0.1 1.1]);
yticks([0 1]);
xlabel('Time (ms)');
ylabel('Logic level');
legend({'Raw button', 'Broken GPIO'}, 'Location', 'eastoutside');
title('Broken assumption: every sampled level is a clean command');
subplot(2, 1, 2);
bar([qualified.metrics.gpio_rising_edges broken.metrics.gpio_rising_edges]);
grid on;
xticks([1 2]);
xticklabels({'Qualified', 'Debounce bypassed'});
ylabel('GPIO rising edges (count)');
title('Recognizable symptom: output chatter');

assert(broken.metrics.gpio_rising_edges > qualified.metrics.gpio_rising_edges, ...
    'The broken case must expose extra GPIO transitions from contact bounce.');
fprintf(['Broken-case explanation: debounce = 0 quantizes to one sample, so contact bounce ' ...
    'crosses the state boundary repeatedly. This is simulated logic, not hardware evidence.\n']);
