function fig = interactive()
%INTERACTIVE Explore rates, work, order, timeout, and frame visibility.
%   Bound function handles keep P16 callbacks isolated from other modules'
%   generic model.m files after the launcher restores the MATLAB path.

modelFcn = @model;
scenarioFcn = @p16_scenario;

fig = uifigure('Name', 'P16 - Execute a Multi-Rate Processing Graph', ...
    'Position', [100 100 1180 780]);
layout = uigridlayout(fig, [7 6]);
layout.RowHeight = {28, 28, 28, 28, '1x', '1x', 58};
layout.ColumnWidth = {140, 118, 140, 118, 140, '1x'};
layout.Padding = [12 12 12 12];

makeLabel(layout, 'Scenario', 1, 1);
scenarioControl = uidropdown(layout, ...
    'Items', {'Editable baseline', 'Unity-rate limit', ...
    'Zero-cost limit', 'Broken consumer first', ...
    'Timeout, continue', 'Timeout, cancel'}, ...
    'Value', 'Editable baseline');
scenarioControl.Layout.Row = 1;
scenarioControl.Layout.Column = [2 3];

makeLabel(layout, 'Samples/frame D', 1, 4);
decimationControl = uidropdown(layout, ...
    'Items', {'1', '2', '4', '8', '16', '32'}, 'Value', '4');
decimationControl.Layout.Row = 1;
decimationControl.Layout.Column = 5;
resetControl = uibutton(layout, 'push', 'Text', 'Reset editable');
resetControl.Layout.Row = 1;
resetControl.Layout.Column = 6;

makeLabel(layout, 'Fast cost (us)', 2, 1);
fastCostControl = numericSpinner(layout, [0 2000], 100, 100, 2, 2);
makeLabel(layout, 'Slow cost (us)', 2, 3);
slowCostControl = numericSpinner(layout, [0 6000], 1200, 100, 2, 4);
makeLabel(layout, 'Output timeout (us)', 2, 5);
timeoutControl = numericSpinner(layout, [0 10000], 2000, 100, 2, 6);

makeLabel(layout, 'Timeout action', 3, 1);
timeoutActionControl = uidropdown(layout, ...
    'Items', {'Continue processing', 'Cancel frame'}, ...
    'Value', 'Continue processing');
timeoutActionControl.Layout.Row = 3;
timeoutActionControl.Layout.Column = 2;
makeLabel(layout, 'Execution order', 3, 3);
executionOrderControl = uidropdown(layout, ...
    'Items', {'Producer first', 'Consumer first'}, ...
    'Value', 'Producer first');
executionOrderControl.Layout.Row = 3;
executionOrderControl.Layout.Column = 4;

instruction = uilabel(layout, ...
    'Text', ['Move one lever, then reset. Timeout zero means exact ' ...
    'same-timestamp completion only.'], ...
    'FontAngle', 'italic');
instruction.Layout.Row = 4;
instruction.Layout.Column = [1 6];

valueAxes = uiaxes(layout);
valueAxes.Layout.Row = 5;
valueAxes.Layout.Column = [1 6];
timingAxes = uiaxes(layout);
timingAxes.Layout.Row = 6;
timingAxes.Layout.Column = [1 6];
statusLabel = uilabel(layout, 'Text', '', 'WordWrap', 'on');
statusLabel.Layout.Row = 7;
statusLabel.Layout.Column = [1 6];

controls = {decimationControl, fastCostControl, slowCostControl, ...
    timeoutControl, timeoutActionControl, executionOrderControl};
scenarioControl.ValueChangedFcn = @(~, ~) scenarioChanged();
resetControl.ButtonPushedFcn = @(~, ~) resetEditable();
for controlIndex = 1:numel(controls)
    controls{controlIndex}.ValueChangedFcn = @(~, ~) updateViews();
end

scenarioChanged();

    function resetEditable()
        scenarioControl.Value = 'Editable baseline';
        scenarioChanged();
    end

    function scenarioChanged()
        scenarioName = scenarioFromLabel(scenarioControl.Value);
        fixedScenario = ~strcmp(scenarioName, 'baseline');
        if fixedScenario
            fixedInput = scenarioFcn(scenarioName);
        else
            fixedInput = scenarioFcn('baseline');
        end
        decimationControl.Value = ...
            sprintf('%d', fixedInput.decimation_factor);
        fastCostControl.Value = fixedInput.fast_cost_us;
        slowCostControl.Value = fixedInput.slow_cost_us;
        timeoutControl.Value = fixedInput.output_timeout_us;
        timeoutActionControl.Value = ...
            timeoutActionLabel(fixedInput.timeout_action);
        executionOrderControl.Value = ...
            executionOrderLabel(fixedInput.execution_order);
        for controlIndex = 1:numel(controls)
            controls{controlIndex}.Enable = onOff(~fixedScenario);
        end
        updateViews();
    end

    function updateViews()
        scenarioName = scenarioFromLabel(scenarioControl.Value);
        if strcmp(scenarioName, 'baseline')
            input = scenarioFcn('baseline', ...
                str2double(decimationControl.Value), ...
                fastCostControl.Value, slowCostControl.Value, ...
                timeoutControl.Value, ...
                timeoutActionFromLabel(timeoutActionControl.Value), ...
                executionOrderFromLabel(executionOrderControl.Value));
        else
            input = scenarioFcn(scenarioName);
        end
        out = modelFcn(input.sample_value, input.sample_time_us, ...
            input.decimation_factor, input.fast_cost_us, ...
            input.slow_cost_us, input.output_timeout_us, ...
            input.timeout_action, input.execution_order);

        cla(valueAxes);
        plot(valueAxes, input.sample_time_us, ...
            out.fast.filtered_value, '-', 'LineWidth', 1.2, ...
            'DisplayName', 'Fast filtered value');
        hold(valueAxes, 'on');
        emittedMask = out.frame.emitted;
        if any(emittedMask)
            stem(valueAxes, ...
                out.frame.expected_timestamp_us(emittedMask), ...
                out.frame.output_value(emittedMask), 'filled', ...
                'DisplayName', 'Emitted slow frame');
        end
        droppedMask = ~out.frame.emitted;
        if any(droppedMask)
            plot(valueAxes, out.frame.expected_timestamp_us(droppedMask), ...
                zeros(1, sum(droppedMask)), 'rx', 'MarkerSize', 10, ...
                'LineWidth', 1.8, 'DisplayName', 'Dropped/invalid frame');
        end
        hold(valueAxes, 'off');
        grid(valueAxes, 'on');
        xlabel(valueAxes, 'Aligned reference time (us)');
        ylabel(valueAxes, 'Signal value (engineering unit)');
        title(valueAxes, sprintf( ...
            'Fast and slow values; D=%d, order=%s', ...
            input.decimation_factor, input.execution_order));
        legend(valueAxes, 'Location', 'best');

        cla(timingAxes);
        scheduledLatencyUs = out.frame.scheduled_finish_us - ...
            out.frame.release_us;
        plot(timingAxes, out.frame.release_us, scheduledLatencyUs, ...
            '-o', 'LineWidth', 1.4, ...
            'DisplayName', 'Scheduled latency');
        hold(timingAxes, 'on');
        yline(timingAxes, input.output_timeout_us, '--', ...
            'Timeout', 'DisplayName', 'Timeout boundary');
        if any(out.frame.cancelled)
            plot(timingAxes, ...
                out.frame.release_us(out.frame.cancelled), ...
                scheduledLatencyUs(out.frame.cancelled), 'rx', ...
                'MarkerSize', 10, 'LineWidth', 1.8, ...
                'DisplayName', 'Cancelled frame');
        end
        hold(timingAxes, 'off');
        grid(timingAxes, 'on');
        xlabel(timingAxes, 'Frame release time (us)');
        ylabel(timingAxes, 'Scheduled output latency (us)');
        title(timingAxes, sprintf( ...
            ['Slow utilization %.2f; maximum outstanding depth ' ...
            '%d frame(s)'], ...
            out.metrics.slow_utilization_ratio, ...
            out.metrics.maximum_outstanding_depth));
        legend(timingAxes, 'Location', 'best');

        statusLabel.Text = sprintf([ ...
            'Frames=%d, emitted=%d, timeout=%d, cancelled=%d, ' ...
            'underflow=%d, timestamp error max=%g us. Deterministic ' ...
            'simulated view only: not MATLAB-runtime, rendered-UI, real ' ...
            'processor/task hardware, bench, HIL, field, or production evidence.'], ...
            out.metrics.frame_count, out.metrics.emitted_count, ...
            out.metrics.timeout_count, out.metrics.cancelled_count, ...
            out.metrics.underflow_count, ...
            out.metrics.maximum_absolute_timestamp_error_us);
    end
end

function makeLabel(layout, labelText, row, column)
label = uilabel(layout, 'Text', labelText, ...
    'HorizontalAlignment', 'right');
label.Layout.Row = row;
label.Layout.Column = column;
end

function control = numericSpinner(layout, limits, value, step, row, column)
control = uispinner(layout, 'Limits', limits, 'Value', value, ...
    'Step', step, 'RoundFractionalValues', 'on');
control.Layout.Row = row;
control.Layout.Column = column;
end

function value = onOff(enabled)
if enabled
    value = 'on';
else
    value = 'off';
end
end

function name = scenarioFromLabel(label)
switch label
    case 'Editable baseline'
        name = 'baseline';
    case 'Unity-rate limit'
        name = 'unity-rate';
    case 'Zero-cost limit'
        name = 'zero-cost';
    case 'Broken consumer first'
        name = 'broken-consumer-first';
    case 'Timeout, continue'
        name = 'timeout-continue';
    case 'Timeout, cancel'
        name = 'timeout-cancel';
    otherwise
        error('P16:interactive:Scenario', 'Unexpected scenario label.');
end
end

function action = timeoutActionFromLabel(label)
if strcmp(label, 'Continue processing')
    action = 'continue-processing';
else
    action = 'cancel-frame';
end
end

function label = timeoutActionLabel(action)
if strcmp(action, 'continue-processing')
    label = 'Continue processing';
else
    label = 'Cancel frame';
end
end

function order = executionOrderFromLabel(label)
if strcmp(label, 'Producer first')
    order = 'producer-first';
else
    order = 'consumer-first';
end
end

function label = executionOrderLabel(order)
if strcmp(order, 'producer-first')
    label = 'Producer first';
else
    label = 'Consumer first';
end
end
