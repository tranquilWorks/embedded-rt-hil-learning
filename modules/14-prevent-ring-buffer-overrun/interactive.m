function fig = interactive()
%INTERACTIVE Explore P14 finite capacity, service, and overrun policy.
modelFcn = @model;
scenarioFcn = @p14_scenario;

fig = uifigure('Name', 'P14 - Prevent Ring-Buffer Overrun', ...
    'Position', [80 80 1260 760]);
layout = uigridlayout(fig, [5 8]);
layout.RowHeight = {24, 32, '1x', '1x', 88};
layout.ColumnWidth = {'1x', '1x', '1x', '1x', ...
    '1x', '1x', '1x', '1.5x'};

makeLabel(layout, 'Capacity (sample)', 1);
makeLabel(layout, 'Producer period (us)', 2);
makeLabel(layout, 'Consumer period (us)', 3);
makeLabel(layout, 'Quota (sample/service)', 4);
makeLabel(layout, 'Full policy', 5);
makeLabel(layout, 'Drain timeout (us; 0=off)', 6);
makeLabel(layout, 'Timeout action', 7);
makeLabel(layout, 'Scenario', 8);

capacityControl = numericSpinner(layout, [1 64], 8, 1, 1);
producerControl = numericSpinner(layout, [1 1e6], 50, 1, 2);
consumerControl = numericSpinner(layout, [1 1e6], 200, 1, 3);
quotaControl = numericSpinner(layout, [1 32], 4, 1, 4);
policyControl = uidropdown(layout, 'Items', ...
    {'Drop newest', 'Overwrite oldest', 'Backpressure'}, ...
    'Value', 'Drop newest');
policyControl.Layout.Row = 2;
policyControl.Layout.Column = 5;
timeoutControl = numericSpinner(layout, [0 1e6], 0, 1, 6);
timeoutActionControl = uidropdown(layout, 'Items', ...
    {'Continue waiting', 'Cancel consumer'}, ...
    'Value', 'Continue waiting');
timeoutActionControl.Layout.Row = 2;
timeoutActionControl.Layout.Column = 7;
scenarioControl = uidropdown(layout, 'Items', ...
    {'Editable baseline', 'Undersized buffer (fixed)', ...
    'Slow consumer (fixed)', 'Overwrite oldest (fixed)', ...
    'Backpressure (fixed)', 'Timeout continues (fixed)', ...
    'Timeout cancels (fixed)'}, 'Value', 'Editable baseline');
scenarioControl.Layout.Row = 2;
scenarioControl.Layout.Column = 8;

occupancyAxes = uiaxes(layout);
occupancyAxes.Layout.Row = 3;
occupancyAxes.Layout.Column = [1 8];
outcomeAxes = uiaxes(layout);
outcomeAxes.Layout.Row = 4;
outcomeAxes.Layout.Column = [1 8];
summaryLabel = uilabel(layout, 'Text', '', ...
    'HorizontalAlignment', 'left', 'WordWrap', 'on');
summaryLabel.Layout.Row = 5;
summaryLabel.Layout.Column = [1 8];

controls = {capacityControl, producerControl, consumerControl, ...
    quotaControl, policyControl, timeoutControl, timeoutActionControl};
for controlIndex = 1:numel(controls)
    controls{controlIndex}.ValueChangedFcn = @(~, ~) updateViews();
end
scenarioControl.ValueChangedFcn = @(~, ~) scenarioChanged();
scenarioChanged();

    function scenarioChanged
        scenarioName = scenarioFromLabel(scenarioControl.Value);
        fixedScenario = ~strcmp(scenarioName, 'baseline');
        for controlIndex = 1:numel(controls)
            controls{controlIndex}.Enable = onOff(~fixedScenario);
        end
        if fixedScenario
            fixedInput = scenarioFcn(scenarioName);
        else
            fixedInput = scenarioFcn('baseline');
        end
        capacityControl.Value = fixedInput.capacity_samples;
        producerControl.Value = fixedInput.producer_period_us;
        consumerControl.Value = fixedInput.consumer_period_us;
        quotaControl.Value = fixedInput.consumer_quota_samples;
        policyControl.Value = policyLabel(fixedInput.overrun_policy);
        timeoutControl.Value = timeoutControlValue( ...
            fixedInput.drain_timeout_us);
        timeoutActionControl.Value = ...
            timeoutActionLabel(fixedInput.timeout_action);
        updateViews();
    end

    function updateViews
        scenarioName = scenarioFromLabel(scenarioControl.Value);
        if strcmp(scenarioName, 'baseline')
            input = scenarioFcn('baseline', capacityControl.Value, ...
                quotaControl.Value, producerControl.Value, ...
                consumerControl.Value, ...
                timeoutFromControl(timeoutControl.Value));
            input.overrun_policy = policyFromLabel(policyControl.Value);
            input.timeout_action = ...
                timeoutActionFromLabel(timeoutActionControl.Value);
        else
            input = scenarioFcn(scenarioName);
        end
        out = modelFcn(input.source_samples, input.producer_period_us, ...
            input.consumer_period_us, input.consumer_quota_samples, ...
            input.consumer_start_us, input.capacity_samples, ...
            input.overrun_policy, input.drain_timeout_us, ...
            input.timeout_action);

        cla(occupancyAxes);
        stairs(occupancyAxes, out.ring.event_time_us, ...
            out.ring.occupancy_after, 'LineWidth', 1.5);
        hold(occupancyAxes, 'on');
        if isempty(out.ring.event_time_us)
            capacityExtent = [0 1];
        else
            capacityExtent = [out.ring.event_time_us(1) ...
                out.ring.event_time_us(end)];
        end
        plot(occupancyAxes, capacityExtent, ...
            out.input.capacity_samples .* [1 1], '--', 'LineWidth', 1.2);
        hold(occupancyAxes, 'off');
        grid(occupancyAxes, 'on');
        xlabel(occupancyAxes, 'Time from first ready record (us)');
        ylabel(occupancyAxes, 'Ring occupancy (sample)');
        title(occupancyAxes, sprintf( ...
            ['Peak %d/%d sample; unthrottled required C=%d; ' ...
            'unthrottled rho=%.2f'], ...
            out.metrics.peak_occupancy_samples, ...
            out.input.capacity_samples, ...
            out.metrics.finite_trace_required_capacity_samples, ...
            out.metrics.offered_load_ratio));
        legend(occupancyAxes, 'Occupancy after event', ...
            'Usable capacity', 'Location', 'best');

        cla(outcomeAxes);
        hold(outcomeAxes, 'on');
        plotOutcome(outcomeAxes, out.consumer.consumed_source_id, 1, ...
            'o', 'Consumed');
        plotOutcome(outcomeAxes, find(out.producer.dropped_newest), 2, ...
            'x', 'Dropped newest');
        plotOutcome(outcomeAxes, find(out.producer.overwritten_oldest), 3, ...
            's', 'Overwritten oldest');
        plotOutcome(outcomeAxes, out.ring.pending_source_id, 4, ...
            '^', 'Pending after cancellation');
        hold(outcomeAxes, 'off');
        grid(outcomeAxes, 'on');
        xlabel(outcomeAxes, 'Source record (index)');
        ylabel(outcomeAxes, 'Outcome category (unitless code)');
        yticks(outcomeAxes, 1:4);
        yticklabels(outcomeAxes, ...
            {'consumed', 'dropped', 'overwritten', 'pending'});
        ylim(outcomeAxes, [0.5 4.5]);
        title(outcomeAxes, ...
            'Sequence identity exposes gaps that bounded occupancy can hide');
        if ~isempty(outcomeAxes.Children)
            legend(outcomeAxes, 'Location', 'best');
        end

        summaryLabel.Text = sprintf([ ...
            'Policy=%s. Consumed=%d, pending=%d, dropped=%d, ' ...
            'overwritten=%d, full encounters=%d, producer stall=%g us. ' ...
            'Timed out=%d, consumer cancelled=%d. Pointer equality ' ...
            'needs occupancy to distinguish full from empty. ' ...
            'Synthetic calculation only: not MATLAB-runtime, UI, ' ...
            'atomicity, DMA, hardware, bench, HIL, field, or production ' ...
            'evidence.'], out.input.overrun_policy, ...
            out.metrics.consumed_count, out.metrics.pending_count, ...
            out.metrics.dropped_newest_count, ...
            out.metrics.overwritten_oldest_count, ...
            out.metrics.full_write_encounter_count, ...
            out.metrics.total_producer_stall_us, ...
            out.observation.wait_timed_out, ...
            out.observation.consumer_cancelled);
    end
end

function makeLabel(layout, labelText, column)
label = uilabel(layout, 'Text', labelText, ...
    'HorizontalAlignment', 'center');
label.Layout.Row = 1;
label.Layout.Column = column;
end

function control = numericSpinner(layout, limits, value, step, column)
control = uispinner(layout, 'Limits', limits, 'Value', value, ...
    'Step', step, 'RoundFractionalValues', 'on');
control.Layout.Row = 2;
control.Layout.Column = column;
end

function plotOutcome(axesHandle, sourceIds, level, marker, label)
if isempty(sourceIds)
    return;
end
plot(axesHandle, sourceIds, level .* ones(size(sourceIds)), marker, ...
    'LineStyle', 'none', 'MarkerSize', 7, 'DisplayName', label);
end

function value = onOff(enabled)
if enabled
    value = 'on';
else
    value = 'off';
end
end

function name = scenarioFromLabel(label)
switch char(label)
    case 'Editable baseline'
        name = 'baseline';
    case 'Undersized buffer (fixed)'
        name = 'undersized-buffer';
    case 'Slow consumer (fixed)'
        name = 'slow-consumer';
    case 'Overwrite oldest (fixed)'
        name = 'overwrite-oldest';
    case 'Backpressure (fixed)'
        name = 'backpressure';
    case 'Timeout continues (fixed)'
        name = 'timeout-continue';
    case 'Timeout cancels (fixed)'
        name = 'timeout-cancel';
    otherwise
        error('P14:interactive:Scenario', 'Unexpected scenario label.');
end
end

function policy = policyFromLabel(label)
switch char(label)
    case 'Drop newest'
        policy = 'drop-newest';
    case 'Overwrite oldest'
        policy = 'overwrite-oldest';
    case 'Backpressure'
        policy = 'backpressure';
    otherwise
        error('P14:interactive:Policy', 'Unexpected policy label.');
end
end

function label = policyLabel(policy)
switch policy
    case 'drop-newest'
        label = 'Drop newest';
    case 'overwrite-oldest'
        label = 'Overwrite oldest';
    case 'backpressure'
        label = 'Backpressure';
    otherwise
        error('P14:interactive:Policy', 'Unexpected policy.');
end
end

function timeoutUs = timeoutFromControl(value)
if value == 0
    timeoutUs = Inf;
else
    timeoutUs = value;
end
end

function value = timeoutControlValue(timeoutUs)
if isinf(timeoutUs)
    value = 0;
else
    value = timeoutUs;
end
end

function action = timeoutActionFromLabel(label)
if strcmp(char(label), 'Continue waiting')
    action = 'continue-waiting';
else
    action = 'cancel-consumer';
end
end

function label = timeoutActionLabel(action)
if strcmp(action, 'continue-waiting')
    label = 'Continue waiting';
else
    label = 'Cancel consumer';
end
end
