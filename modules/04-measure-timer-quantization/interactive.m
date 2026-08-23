function interactive
%INTERACTIVE Explore P04 timer resolution, phase, and wrap range.

% launch_lesson removes this folder after the function returns. Bind P04's
% generic model and unique fixture helper now so retained callbacks cannot
% resolve another module's model.m after a later module switch.
modelFcn = @model;
scenarioFcn = @p04_scenario;

fig = uifigure('Name', 'P04 Timer Quantization', ...
    'Position', [80 80 1240 800]);
gridLayout = uigridlayout(fig, [5 5]);
gridLayout.RowHeight = {'1x', '1x', 92, 22, 40};
gridLayout.ColumnWidth = {'1x', '1x', '1x', '1x', '1x'};

intervalAxes = uiaxes(gridLayout);
intervalAxes.Layout.Row = 1;
intervalAxes.Layout.Column = [1 5];
errorAxes = uiaxes(gridLayout);
errorAxes.Layout.Row = 2;
errorAxes.Layout.Column = [1 5];
summary = uilabel(gridLayout, 'WordWrap', 'on');
summary.Layout.Row = 3;
summary.Layout.Column = [1 5];

makeLabel(gridLayout, 'Timer tick q (us)', 1);
makeLabel(gridLayout, 'True interval (us)', 2);
makeLabel(gridLayout, 'Phase (tick fraction)', 3);
makeLabel(gridLayout, 'Counter width (bits)', 4);
makeLabel(gridLayout, 'Capture scenario', 5);

tickControl = uispinner(gridLayout, ...
    'Limits', [1 50], 'Step', 1, 'Value', 10);
tickControl.Layout.Row = 5;
tickControl.Layout.Column = 1;
intervalControl = uispinner(gridLayout, ...
    'Limits', [0 200], 'Step', 1, 'Value', 37);
intervalControl.Layout.Row = 5;
intervalControl.Layout.Column = 2;
phaseFractionControl = uispinner(gridLayout, ...
    'Limits', [0 0.9], 'Step', 0.1, 'Value', 0);
phaseFractionControl.Layout.Row = 5;
phaseFractionControl.Layout.Column = 3;
counterBitsControl = uispinner(gridLayout, ...
    'Limits', [3 16], 'Step', 1, 'Value', 8, ...
    'RoundFractionalValues', 'on');
counterBitsControl.Layout.Row = 5;
counterBitsControl.Layout.Column = 4;
scenarioControl = uidropdown(gridLayout, ...
    'Items', {'Repeated interval', ...
    'Wrap and recovery (fixed q=10, B=8, phase=0)', ...
    'Full-range ambiguity and recovery (fixed q=10, B=8, phase=0)'}, ...
    'Value', 'Repeated interval');
scenarioControl.Layout.Row = 5;
scenarioControl.Layout.Column = 5;

tickControl.ValueChangedFcn = @(~, ~) updateViews();
intervalControl.ValueChangedFcn = @(~, ~) updateViews();
phaseFractionControl.ValueChangedFcn = @(~, ~) updateViews();
counterBitsControl.ValueChangedFcn = @(~, ~) updateViews();
scenarioControl.ValueChangedFcn = @(~, ~) selectScenario();
selectScenario();

    function selectScenario
        if strcmp(scenarioControl.Value, 'Repeated interval')
            tickControl.Enable = 'on';
            intervalControl.Enable = 'on';
            phaseFractionControl.Enable = 'on';
            counterBitsControl.Enable = 'on';
        else
            % Keep named diagnostic fixtures invariant under exposed controls.
            tickControl.Value = 10;
            intervalControl.Value = 37;
            phaseFractionControl.Value = 0;
            counterBitsControl.Value = 8;
            tickControl.Enable = 'off';
            intervalControl.Enable = 'off';
            phaseFractionControl.Enable = 'off';
            counterBitsControl.Enable = 'off';
        end
        updateViews();
    end

    function updateViews
        scenarioName = mapScenarioName(scenarioControl.Value);
        input = scenarioFcn(scenarioName, intervalControl.Value);
        tickPeriodUs = tickControl.Value;
        timerPhaseUs = phaseFractionControl.Value .* tickPeriodUs;
        out = modelFcn(input.start_time_us, input.true_interval_us, ...
            tickPeriodUs, timerPhaseUs, counterBitsControl.Value);
        captureIndex = 1:out.input.count;

        cla(intervalAxes);
        plot(intervalAxes, captureIndex, out.input.true_interval_us, ...
            'k--', 'LineWidth', 1.2);
        hold(intervalAxes, 'on');
        stairs(intervalAxes, captureIndex, out.measurement.interval_us, ...
            'o-', 'LineWidth', 1.3);
        plot(intervalAxes, captureIndex(out.measurement.range_ambiguous), ...
            out.input.true_interval_us(out.measurement.range_ambiguous), ...
            'rx', 'LineWidth', 1.5, 'MarkerSize', 9);
        hold(intervalAxes, 'off');
        grid(intervalAxes, 'on');
        xlabel(intervalAxes, 'Capture-pair index');
        ylabel(intervalAxes, 'Interval (us)');
        title(intervalAxes, ...
            'True interval, valid timer measurement, or range-ambiguity marker');
        legend(intervalAxes, {'True interval', 'Timer measurement', ...
            'Ambiguous after full wrap'}, 'Location', 'eastoutside');

        cla(errorAxes);
        stem(errorAxes, captureIndex, out.measurement.error_us, ...
            'filled', 'LineWidth', 1.1);
        hold(errorAxes, 'on');
        plot(errorAxes, captureIndex, ...
            tickPeriodUs .* ones(size(captureIndex)), 'r--', 'LineWidth', 1);
        plot(errorAxes, captureIndex, ...
            -tickPeriodUs .* ones(size(captureIndex)), 'r--', 'LineWidth', 1);
        plot(errorAxes, captureIndex(out.measurement.range_ambiguous), ...
            zeros(1, sum(out.measurement.range_ambiguous)), ...
            'rx', 'LineWidth', 1.5, 'MarkerSize', 9);
        hold(errorAxes, 'off');
        grid(errorAxes, 'on');
        xlabel(errorAxes, 'Capture-pair index');
        ylabel(errorAxes, 'Measurement error (us)');
        title(errorAxes, 'Valid interval error is bounded by one timer tick');

        summary.Text = sprintf([ ...
            '%d/%d valid; range ambiguities %d; wrap crossings %d; ' ...
            'worst error %s.  ' ...
            'Naive signed rollover subtraction is negative for %d pair(s). ' ...
            'Phase is %.2f us; wrap period is %.1f us. These deterministic ' ...
            'synthetic captures are not a hardware measurement.'], ...
            out.metrics.valid_count, out.metrics.total_count, ...
            out.metrics.range_ambiguity_count, ...
            out.metrics.wrap_crossing_count, ...
            formatMetric(out.metrics.worst_abs_error_us), ...
            out.metrics.naive_negative_count, out.timer.timer_phase_us, ...
            out.timer.wrap_period_us);
    end
end

function makeLabel(gridLayout, labelText, column)
label = uilabel(gridLayout, 'Text', labelText, ...
    'HorizontalAlignment', 'center');
label.Layout.Row = 4;
label.Layout.Column = column;
end

function name = mapScenarioName(displayName)
switch displayName
    case 'Repeated interval'
        name = 'baseline';
    case 'Wrap and recovery (fixed q=10, B=8, phase=0)'
        name = 'wrap-recovery';
    case 'Full-range ambiguity and recovery (fixed q=10, B=8, phase=0)'
        name = 'range-recovery';
    otherwise
        error('P04:interactive:Scenario', ...
            'Unknown interactive scenario.');
end
end

function text = formatMetric(valueUs)
if isnan(valueUs)
    text = 'N/A (no valid interval)';
else
    text = sprintf('%.2f us', valueUs);
end
end
