function interactive
%INTERACTIVE Explore P02 one deterministic lever at a time.

% launch_lesson removes the module folder from the search path after this
% function returns. Bind P02's dependencies now so later UI callbacks do
% not resolve another module's generic model.m after a module switch.
modelFcn = @model;
scenarioFcn = @p02_scenario;

fig = uifigure('Name', 'P02 GPIO State Machine', 'Position', [100 100 1120 760]);
gridLayout = uigridlayout(fig, [5 4]);
gridLayout.RowHeight = {'1x', '1x', 78, 22, 40};
gridLayout.ColumnWidth = {'1x', '1x', '1x', '1x'};

signalAxes = uiaxes(gridLayout);
signalAxes.Layout.Row = 1;
signalAxes.Layout.Column = [1 4];
stateAxes = uiaxes(gridLayout);
stateAxes.Layout.Row = 2;
stateAxes.Layout.Column = [1 4];
summary = uilabel(gridLayout, 'WordWrap', 'on');
summary.Layout.Row = 3;
summary.Layout.Column = [1 4];

makeLabel(gridLayout, 'Debounce (ms)', 1);
makeLabel(gridLayout, 'Maximum on (ms)', 2);
makeLabel(gridLayout, 'Contact bounce (ms)', 3);
makeLabel(gridLayout, 'Input scenario', 4);

debounceControl = uispinner(gridLayout, 'Limits', [0 15], 'Step', 1, 'Value', 5);
debounceControl.Layout.Row = 5;
debounceControl.Layout.Column = 1;
maxOnControl = uispinner(gridLayout, 'Limits', [5 100], 'Step', 5, 'Value', 80);
maxOnControl.Layout.Row = 5;
maxOnControl.Layout.Column = 2;
bounceControl = uispinner(gridLayout, 'Limits', [0 12], 'Step', 1, 'Value', 6);
bounceControl.Layout.Row = 5;
bounceControl.Layout.Column = 3;
scenarioControl = uidropdown(gridLayout, ...
    'Items', {'Normal press', 'Stuck high', 'Cancel and recovery'}, ...
    'Value', 'Normal press');
scenarioControl.Layout.Row = 5;
scenarioControl.Layout.Column = 4;

debounceControl.ValueChangedFcn = @(~, ~) updateViews();
maxOnControl.ValueChangedFcn = @(~, ~) updateViews();
bounceControl.ValueChangedFcn = @(~, ~) updateViews();
scenarioControl.ValueChangedFcn = @(~, ~) updateViews();
updateViews();

    function updateViews
        scenarioName = mapScenarioName(scenarioControl.Value);
        input = scenarioFcn(scenarioName, 1, 120, bounceControl.Value);
        out = modelFcn(input.raw_button, input.sample_period_ms, ...
            debounceControl.Value, maxOnControl.Value, input.cancel);

        cla(signalAxes);
        stairs(signalAxes, out.time_ms, double(out.raw_button), ...
            'Color', [0.45 0.45 0.45], 'LineWidth', 1.0);
        hold(signalAxes, 'on');
        stairs(signalAxes, out.time_ms, double(out.gpio), 'LineWidth', 1.5);
        stairs(signalAxes, out.time_ms, double(out.cancel), '--', 'LineWidth', 1.1);
        hold(signalAxes, 'off');
        grid(signalAxes, 'on');
        ylim(signalAxes, [-0.1 1.1]);
        yticks(signalAxes, [0 1]);
        yticklabels(signalAxes, {'low', 'high'});
        xlabel(signalAxes, 'Time (ms)');
        ylabel(signalAxes, 'Logic level');
        title(signalAxes, 'Input observations and simulated GPIO command');
        legend(signalAxes, {'Raw button', 'GPIO', 'Cancel'}, 'Location', 'eastoutside');

        cla(stateAxes);
        stairs(stateAxes, out.time_ms, double(out.state_code), 'LineWidth', 1.2);
        grid(stateAxes, 'on');
        ylim(stateAxes, [-0.2 4.2]);
        yticks(stateAxes, 0:4);
        yticklabels(stateAxes, out.state_names);
        xlabel(stateAxes, 'Time (ms)');
        ylabel(stateAxes, 'State code');
        title(stateAxes, 'Mechanism view: qualification, active output, and lockout');

        summary.Text = sprintf([ ...
            'N_d = %d samples (%.1f ms); N_t = %d samples (%.1f ms).  ' ...
            'GPIO rises: %d; longest high run: %.1f ms; timeouts: %d; cancels: %d.  ' ...
            'GPIO changes because state changed; the plot is not a hardware measurement.'], ...
            out.debounce_samples, out.quantized_debounce_ms, ...
            out.timeout_samples, out.quantized_max_on_ms, ...
            out.metrics.gpio_rising_edges, out.metrics.max_high_run_ms, ...
            out.metrics.timeout_count, out.metrics.cancel_count);
    end
end

function makeLabel(gridLayout, labelText, column)
label = uilabel(gridLayout, 'Text', labelText, 'HorizontalAlignment', 'center');
label.Layout.Row = 4;
label.Layout.Column = column;
end

function name = mapScenarioName(displayName)
switch displayName
    case 'Normal press'
        name = 'normal';
    case 'Stuck high'
        name = 'stuck-high';
    case 'Cancel and recovery'
        name = 'cancel-recovery';
    otherwise
        error('P02:interactive:Scenario', 'Unknown interactive scenario.');
end
end
