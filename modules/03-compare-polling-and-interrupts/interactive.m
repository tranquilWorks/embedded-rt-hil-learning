function interactive
%INTERACTIVE Explore P03 observation and capacity levers one at a time.

% launch_lesson removes this folder after the function returns. Bind P03's
% generic model and unique scenario helper now so retained callbacks cannot
% resolve another module's model.m after a later module switch.
modelFcn = @model;
scenarioFcn = @p03_scenario;

fig = uifigure('Name', 'P03 Polling and Interrupts', ...
    'Position', [80 80 1240 800]);
gridLayout = uigridlayout(fig, [5 5]);
gridLayout.RowHeight = {'1x', '1x', 92, 22, 40};
gridLayout.ColumnWidth = {'1x', '1x', '1x', '1x', '1x'};

timingAxes = uiaxes(gridLayout);
timingAxes.Layout.Row = 1;
timingAxes.Layout.Column = [1 5];
responseAxes = uiaxes(gridLayout);
responseAxes.Layout.Row = 2;
responseAxes.Layout.Column = [1 5];
summary = uilabel(gridLayout, 'WordWrap', 'on');
summary.Layout.Row = 3;
summary.Layout.Column = [1 5];

makeLabel(gridLayout, 'Poll period (ms)', 1);
makeLabel(gridLayout, 'Pulse width (ms)', 2);
makeLabel(gridLayout, 'Mask duration (ms)', 3);
makeLabel(gridLayout, 'Outstanding capacity', 4);
makeLabel(gridLayout, 'Request scenario', 5);

pollPeriodControl = uispinner(gridLayout, ...
    'Limits', [0.25 2], 'Step', 0.25, 'Value', 0.5);
pollPeriodControl.Layout.Row = 5;
pollPeriodControl.Layout.Column = 1;
pulseWidthControl = uispinner(gridLayout, ...
    'Limits', [0.1 0.5], 'Step', 0.1, 'Value', 0.3);
pulseWidthControl.Layout.Row = 5;
pulseWidthControl.Layout.Column = 2;
maskDurationControl = uispinner(gridLayout, ...
    'Limits', [0 4], 'Step', 0.5, 'Value', 0);
maskDurationControl.Layout.Row = 5;
maskDurationControl.Layout.Column = 3;
capacityControl = uispinner(gridLayout, ...
    'Limits', [1 6], 'Step', 1, 'Value', 3, ...
    'RoundFractionalValues', 'on');
capacityControl.Layout.Row = 5;
capacityControl.Layout.Column = 4;
scenarioControl = uidropdown(gridLayout, ...
    'Items', {'Mixed arrivals', 'Sparse arrivals', 'Burst and recovery'}, ...
    'Value', 'Mixed arrivals');
scenarioControl.Layout.Row = 5;
scenarioControl.Layout.Column = 5;

pollPeriodControl.ValueChangedFcn = @(~, ~) updateViews();
pulseWidthControl.ValueChangedFcn = @(~, ~) updateViews();
maskDurationControl.ValueChangedFcn = @(~, ~) updateViews();
capacityControl.ValueChangedFcn = @(~, ~) updateViews();
scenarioControl.ValueChangedFcn = @(~, ~) updateViews();
updateViews();

    function updateViews
        scenarioName = mapScenarioName(scenarioControl.Value);
        input = scenarioFcn(scenarioName, pulseWidthControl.Value);
        maskWindowsMs = makeMask(input.mask_start_ms, maskDurationControl.Value);
        out = modelFcn(input.event_times_ms, input.pulse_width_ms, ...
            input.horizon_ms, pollPeriodControl.Value, 0.02, 0.05, 0.20, ...
            capacityControl.Value, maskWindowsMs);
        [pulseTimeMs, pulseLevel] = pulseTrace(out.events, out.horizon_ms);

        cla(timingAxes);
        stairs(timingAxes, pulseTimeMs, pulseLevel, 'LineWidth', 1.3);
        hold(timingAxes, 'on');
        stem(timingAxes, out.poll.sample_times_ms, ...
            1.12 * ones(size(out.poll.sample_times_ms)), '.', 'LineWidth', 0.7);
        plot(timingAxes, out.poll.detection_time_ms(out.poll.detected), ...
            0.72 * ones(1, sum(out.poll.detected)), ...
            'go', 'MarkerFaceColor', 'g');
        plot(timingAxes, out.events.arrival_ms(out.poll.missed), ...
            0.45 * ones(1, sum(out.poll.missed)), 'rx', 'LineWidth', 1.4);
        hold(timingAxes, 'off');
        grid(timingAxes, 'on');
        ylim(timingAxes, [-0.1 1.25]);
        xlabel(timingAxes, 'Time (ms)');
        ylabel(timingAxes, 'Request / poll outcome');
        title(timingAxes, 'Polling timeline: level pulses, poll instants, and outcomes');
        legend(timingAxes, {'Request pulse', 'Poll instant', 'Detected', 'Missed'}, ...
            'Location', 'eastoutside');

        eventIndex = 1:out.events.count;
        cla(responseAxes);
        plot(responseAxes, eventIndex, out.poll.response_latency_ms, ...
            'o-', 'LineWidth', 1.2);
        hold(responseAxes, 'on');
        plot(responseAxes, eventIndex, out.interrupt.response_latency_ms, ...
            's-', 'LineWidth', 1.2);
        plot(responseAxes, eventIndex(out.poll.missed), ...
            zeros(1, sum(out.poll.missed)), 'rx', 'LineWidth', 1.4);
        plot(responseAxes, eventIndex(out.interrupt.dropped_overrun), ...
            zeros(1, sum(out.interrupt.dropped_overrun)), ...
            'kx', 'LineWidth', 1.4);
        hold(responseAxes, 'off');
        grid(responseAxes, 'on');
        xlabel(responseAxes, 'Input event index');
        ylabel(responseAxes, 'Service-start response (ms)');
        title(responseAxes, 'Mechanism view: finite response or explicit loss');
        legend(responseAxes, {'Polling response', 'Interrupt response', ...
            'Polling miss', 'Interrupt overrun'}, 'Location', 'eastoutside');

        pollResponseText = formatResponse(out.metrics.poll_detected_count, ...
            out.metrics.poll_worst_response_ms);
        interruptResponseText = formatResponse(out.metrics.interrupt_captured_count, ...
            out.metrics.interrupt_worst_response_ms);
        summary.Text = sprintf([ ...
            'Polling detected %d/%d; worst response %s; modeled CPU %.1f%%.  ' ...
            'Interrupt captured %d/%d; overruns %d; worst response %s; ' ...
            'modeled CPU %.1f%%. Capacity includes queued plus in-service work. ' ...
            'These synthetic results are not a hardware measurement.'], ...
            out.metrics.poll_detected_count, out.metrics.total_events, ...
            pollResponseText, 100 * out.poll.cpu_busy_fraction, ...
            out.metrics.interrupt_captured_count, out.metrics.total_events, ...
            out.metrics.interrupt_dropped_count, ...
            interruptResponseText, ...
            100 * out.interrupt.cpu_busy_fraction);
    end
end

function makeLabel(gridLayout, labelText, column)
label = uilabel(gridLayout, 'Text', labelText, 'HorizontalAlignment', 'center');
label.Layout.Row = 4;
label.Layout.Column = column;
end

function name = mapScenarioName(displayName)
switch displayName
    case 'Mixed arrivals'
        name = 'mixed';
    case 'Sparse arrivals'
        name = 'sparse';
    case 'Burst and recovery'
        name = 'burst-recovery';
    otherwise
        error('P03:interactive:Scenario', 'Unknown interactive scenario.');
end
end

function maskWindowsMs = makeMask(maskStartMs, durationMs)
if durationMs == 0
    maskWindowsMs = zeros(0, 2);
else
    maskWindowsMs = [maskStartMs maskStartMs + durationMs];
end
end

function [timeMs, level] = pulseTrace(events, horizonMs)
timeMs = [0 reshape([events.arrival_ms; events.end_ms], 1, []) horizonMs];
level = [0 reshape([ones(1, events.count); zeros(1, events.count)], 1, []) 0];
end

function text = formatResponse(servicedCount, responseMs)
if servicedCount == 0
    text = 'N/A (no serviced event)';
else
    text = sprintf('%.2f ms', responseMs);
end
end
