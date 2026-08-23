function fig = interactive()
%INTERACTIVE Explore local-clock offset, skew, PPS identity, and timeout.
%   Bound function handles keep P15 callbacks isolated from other modules'
%   generic model.m files after the launcher restores the MATLAB path.

modelFcn = @model;
scenarioFcn = @p15_scenario;

fig = uifigure('Name', 'P15 - Align Clocks with PPS and Timestamps', ...
    'Position', [100 100 1180 760]);
layout = uigridlayout(fig, [7 6]);
layout.RowHeight = {28, 28, 28, 28, '1x', '1x', 54};
layout.ColumnWidth = {132, 116, 132, 116, 132, '1x'};
layout.Padding = [12 12 12 12];

makeLabel(layout, 'Scenario', 1, 1);
scenarioControl = uidropdown(layout, ...
    'Items', {'Editable baseline', 'Zero offset and skew', ...
    'Missing ID, correct', 'Broken arrival index', ...
    'Coarse timestamp', 'Timeout, continue', 'Timeout, cancel'}, ...
    'Value', 'Editable baseline');
scenarioControl.Layout.Row = 1;
scenarioControl.Layout.Column = [2 3];

makeLabel(layout, 'Clock offset (us)', 1, 4);
offsetControl = numericSpinner(layout, [0 10000], 2500, 100, 1, 5);
makeLabel(layout, 'Oscillator skew (ppm)', 2, 1);
skewControl = numericSpinner(layout, [-200 200], 40, 10, 2, 2);
makeLabel(layout, 'Timestamp tick (us)', 2, 3);
tickControl = numericSpinner(layout, [1 1000], 1, 1, 2, 4);
makeLabel(layout, 'PPS timeout (us)', 2, 5);
timeoutControl = numericSpinner(layout, [0 5e6], 0, 100000, 2, 6);

makeLabel(layout, 'Timeout action', 3, 1);
timeoutActionControl = uidropdown(layout, ...
    'Items', {'Continue waiting', 'Cancel alignment'}, ...
    'Value', 'Continue waiting');
timeoutActionControl.Layout.Row = 3;
timeoutActionControl.Layout.Column = 2;
makeLabel(layout, 'PPS association', 3, 3);
associationControl = uidropdown(layout, ...
    'Items', {'Sequence ID', 'Arrival index'}, ...
    'Value', 'Sequence ID');
associationControl.Layout.Row = 3;
associationControl.Layout.Column = 4;

instruction = uilabel(layout, ...
    'Text', ['Move one lever, then reset. Zero timeout disables the ' ...
    'synthetic wait deadline.'], ...
    'FontAngle', 'italic');
instruction.Layout.Row = 4;
instruction.Layout.Column = [1 6];

errorAxes = uiaxes(layout);
errorAxes.Layout.Row = 5;
errorAxes.Layout.Column = [1 6];
anchorAxes = uiaxes(layout);
anchorAxes.Layout.Row = 6;
anchorAxes.Layout.Column = [1 6];
statusLabel = uilabel(layout, 'Text', '', 'WordWrap', 'on');
statusLabel.Layout.Row = 7;
statusLabel.Layout.Column = [1 6];

controls = {offsetControl, skewControl, tickControl, timeoutControl, ...
    timeoutActionControl, associationControl};
scenarioControl.ValueChangedFcn = @(~, ~) scenarioChanged();
for controlIndex = 1:numel(controls)
    controls{controlIndex}.ValueChangedFcn = @(~, ~) updateViews();
end

scenarioChanged();

    function scenarioChanged()
        scenarioName = scenarioFromLabel(scenarioControl.Value);
        fixedScenario = ~strcmp(scenarioName, 'baseline');
        if fixedScenario
            fixedInput = scenarioFcn(scenarioName);
        else
            fixedInput = scenarioFcn('baseline');
        end
        offsetControl.Value = fixedInput.clock_offset_us;
        skewControl.Value = fixedInput.clock_skew_ppm;
        tickControl.Value = fixedInput.timestamp_tick_us;
        timeoutControl.Value = ...
            timeoutControlValue(fixedInput.pps_wait_timeout_us);
        timeoutActionControl.Value = ...
            timeoutActionLabel(fixedInput.timeout_action);
        associationControl.Value = ...
            associationLabel(fixedInput.association_mode);
        for controlIndex = 1:numel(controls)
            controls{controlIndex}.Enable = onOff(~fixedScenario);
        end
        updateViews();
    end

    function updateViews()
        scenarioName = scenarioFromLabel(scenarioControl.Value);
        if strcmp(scenarioName, 'baseline')
            input = scenarioFcn('baseline', offsetControl.Value, ...
                skewControl.Value, tickControl.Value, ...
                timeoutFromControl(timeoutControl.Value), ...
                timeoutActionFromLabel(timeoutActionControl.Value), ...
                associationFromLabel(associationControl.Value));
        else
            input = scenarioFcn(scenarioName);
        end
        out = modelFcn(input.event_reference_us, ...
            input.pps_sequence_id, input.pps_period_us, ...
            input.clock_offset_us, input.clock_skew_ppm, ...
            input.timestamp_tick_us, input.pps_wait_timeout_us, ...
            input.timeout_action, input.association_mode);

        cla(errorAxes);
        plot(errorAxes, input.event_reference_us, ...
            out.clock.raw_error_us, '-o', 'LineWidth', 1.4, ...
            'DisplayName', 'Raw local');
        hold(errorAxes, 'on');
        plot(errorAxes, input.event_reference_us, ...
            out.alignment.offset_only_error_us, '-s', 'LineWidth', 1.4, ...
            'DisplayName', 'One-PPS offset only');
        if out.alignment.available
            plot(errorAxes, input.event_reference_us, ...
                out.alignment.corrected_error_us, '-^', ...
                'LineWidth', 1.4, 'DisplayName', 'Affine aligned');
        end
        hold(errorAxes, 'off');
        grid(errorAxes, 'on');
        xlabel(errorAxes, 'Reference event time (us)');
        ylabel(errorAxes, 'Timestamp error (us)');
        title(errorAxes, ...
            sprintf('Event errors; association=%s', input.association_mode));
        legend(errorAxes, 'Location', 'best');

        cla(anchorAxes);
        localMinusTrueUs = out.pps.local_timestamp_us - ...
            out.pps.true_reference_us;
        stem(anchorAxes, input.pps_sequence_id, localMinusTrueUs, ...
            'filled', 'DisplayName', 'Local minus true reference');
        hold(anchorAxes, 'on');
        if out.alignment.available
            plot(anchorAxes, input.pps_sequence_id, ...
                out.pps.fit_residual_us, '-s', 'LineWidth', 1.4, ...
                'DisplayName', 'Fit residual');
        end
        censoredIds = input.pps_sequence_id(out.pps.censored);
        if ~isempty(censoredIds)
            plot(anchorAxes, censoredIds, ...
                localMinusTrueUs(out.pps.censored), 'rx', ...
                'MarkerSize', 10, 'LineWidth', 1.8, ...
                'DisplayName', 'Censored after cancel');
        end
        hold(anchorAxes, 'off');
        grid(anchorAxes, 'on');
        xlabel(anchorAxes, 'PPS sequence ID (count)');
        ylabel(anchorAxes, 'Clock or fit error (us)');
        title(anchorAxes, ...
            'PPS identity exposes missing epochs, quantization, and censoring');
        legend(anchorAxes, 'Location', 'best');

        if out.alignment.available
            estimateText = sprintf( ...
                'estimate offset=%.3f us, skew=%.3f ppm, corrected max=%.3f us', ...
                out.alignment.estimated_offset_us, ...
                out.alignment.estimated_skew_ppm, ...
                out.metrics.corrected_maximum_absolute_error_us);
        else
            estimateText = 'affine estimate unavailable (fewer than two retained PPS anchors)';
        end
        statusLabel.Text = sprintf([ ...
            'Missing=%d, retained=%d, censored=%d, timeout=%s, ' ...
            'cancelled=%s; %s. Deterministic simulated view only: ' ...
            'not MATLAB-runtime, PPS/GNSS hardware, bench, HIL, field, or production evidence.'], ...
            out.metrics.missing_pps_count, ...
            out.observation.retained_pps_count, ...
            out.observation.censored_pps_count, ...
            yesNo(out.observation.wait_timed_out), ...
            yesNo(out.observation.alignment_cancelled), estimateText);
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
    'Step', step);
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
    case 'Zero offset and skew'
        name = 'zero-error';
    case 'Missing ID, correct'
        name = 'missing-id-correct';
    case 'Broken arrival index'
        name = 'broken-arrival-index';
    case 'Coarse timestamp'
        name = 'coarse-timestamp';
    case 'Timeout, continue'
        name = 'timeout-continue';
    case 'Timeout, cancel'
        name = 'timeout-cancel';
    otherwise
        error('P15:interactive:Scenario', 'Unexpected scenario label.');
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
if strcmp(label, 'Continue waiting')
    action = 'continue-waiting';
else
    action = 'cancel-alignment';
end
end

function label = timeoutActionLabel(action)
if strcmp(action, 'continue-waiting')
    label = 'Continue waiting';
else
    label = 'Cancel alignment';
end
end

function mode = associationFromLabel(label)
if strcmp(label, 'Sequence ID')
    mode = 'sequence-id';
else
    mode = 'arrival-index';
end
end

function label = associationLabel(mode)
if strcmp(mode, 'sequence-id')
    label = 'Sequence ID';
else
    label = 'Arrival index';
end
end

function text = yesNo(value)
if value
    text = 'yes';
else
    text = 'no';
end
end
