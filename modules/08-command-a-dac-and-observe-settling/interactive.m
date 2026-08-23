function interactive
%INTERACTIVE Explore P08 DAC transfer, latch, and settling controls.

% launch_lesson removes this folder after the function returns. Bind P08's
% generic model and unique fixture helper now so retained callbacks cannot
% resolve another module's model.m after a later module switch.
modelFcn = @model;
scenarioFcn = @p08_scenario;

fig = uifigure('Name', 'P08 Command a DAC and Observe Settling', ...
    'Position', [20 30 1660 850]);
gridLayout = uigridlayout(fig, [5 10]);
gridLayout.RowHeight = {'1x', '1x', 125, 22, 40};
gridLayout.ColumnWidth = {'1x', '1x', '1x', '1x', '1x', ...
    '1x', '1x', '1x', '1x', '1.45x'};

responseAxes = uiaxes(gridLayout);
responseAxes.Layout.Row = 1;
responseAxes.Layout.Column = [1 10];
errorAxes = uiaxes(gridLayout);
errorAxes.Layout.Row = 2;
errorAxes.Layout.Column = [1 10];
summary = uilabel(gridLayout, 'WordWrap', 'on');
summary.Layout.Row = 3;
summary.Layout.Column = [1 10];

makeLabel(gridLayout, 'Command voltage (V)', 1);
makeLabel(gridLayout, 'Initial voltage (V)', 2);
makeLabel(gridLayout, 'Update latency (us)', 3);
makeLabel(gridLayout, 'Time constant (us)', 4);
makeLabel(gridLayout, 'Slew rate (V/ms)', 5);
makeLabel(gridLayout, 'DAC bits', 6);
makeLabel(gridLayout, 'Settling tolerance (mV)', 7);
makeLabel(gridLayout, 'Sample period (us)', 8);
makeLabel(gridLayout, 'Sample count', 9);
makeLabel(gridLayout, 'Scenario', 10);

commandControl = uispinner(gridLayout, ...
    'Limits', [0 3.3], 'Step', 0.05, 'Value', 2.5);
commandControl.Layout.Row = 5;
commandControl.Layout.Column = 1;
initialControl = uispinner(gridLayout, ...
    'Limits', [0 3.3], 'Step', 0.05, 'Value', 0.5);
initialControl.Layout.Row = 5;
initialControl.Layout.Column = 2;
latencyControl = uispinner(gridLayout, ...
    'Limits', [0 10000], 'Step', 10, 'Value', 100);
latencyControl.Layout.Row = 5;
latencyControl.Layout.Column = 3;
timeConstantControl = uispinner(gridLayout, ...
    'Limits', [1 10000], 'Step', 10, 'Value', 250);
timeConstantControl.Layout.Row = 5;
timeConstantControl.Layout.Column = 4;
slewRateControl = uispinner(gridLayout, ...
    'Limits', [0.01 100], 'Step', 0.25, 'Value', 4);
slewRateControl.Layout.Row = 5;
slewRateControl.Layout.Column = 5;
bitsControl = uispinner(gridLayout, ...
    'Limits', [2 16], 'Step', 1, 'Value', 12, ...
    'RoundFractionalValues', 'on');
bitsControl.Layout.Row = 5;
bitsControl.Layout.Column = 6;
toleranceControl = uispinner(gridLayout, ...
    'Limits', [0.01 1000], 'Step', 1, 'Value', 10);
toleranceControl.Layout.Row = 5;
toleranceControl.Layout.Column = 7;
samplePeriodControl = uispinner(gridLayout, ...
    'Limits', [0.1 1000], 'Step', 1, 'Value', 5);
samplePeriodControl.Layout.Row = 5;
samplePeriodControl.Layout.Column = 8;
sampleCountControl = uispinner(gridLayout, ...
    'Limits', [2 5000], 'Step', 1, 'Value', 601, ...
    'RoundFractionalValues', 'on');
sampleCountControl.Layout.Row = 5;
sampleCountControl.Layout.Column = 9;
scenarioControl = uidropdown(gridLayout, ...
    'Items', {'Baseline', 'Recorded code, update-not-latched', ...
    'Command deadline (fixed)', 'Short observation (fixed)', ...
    'Slow output (fixed)'}, 'Value', 'Baseline');
scenarioControl.Layout.Row = 5;
scenarioControl.Layout.Column = 10;

commandControl.ValueChangedFcn = @(~, ~) updateViews();
initialControl.ValueChangedFcn = @(~, ~) updateViews();
latencyControl.ValueChangedFcn = @(~, ~) updateViews();
timeConstantControl.ValueChangedFcn = @(~, ~) updateViews();
slewRateControl.ValueChangedFcn = @(~, ~) updateViews();
bitsControl.ValueChangedFcn = @(~, ~) updateViews();
toleranceControl.ValueChangedFcn = @(~, ~) updateViews();
samplePeriodControl.ValueChangedFcn = @(~, ~) updateViews();
sampleCountControl.ValueChangedFcn = @(~, ~) updateViews();
scenarioControl.ValueChangedFcn = @(~, ~) selectScenario();
selectScenario();

    function selectScenario
        controls = {commandControl, initialControl, latencyControl, ...
            timeConstantControl, slewRateControl, bitsControl, ...
            toleranceControl, samplePeriodControl, sampleCountControl};
        for controlIndex = 1:numel(controls)
            controls{controlIndex}.Enable = 'on';
        end
        scenarioName = mapScenarioName(scenarioControl.Value);
        fixedInput = scenarioFcn(scenarioName, 601);
        commandControl.Value = fixedInput.command_voltage_v;
        initialControl.Value = fixedInput.initial_voltage_v;
        latencyControl.Value = fixedInput.update_latency_us;
        timeConstantControl.Value = fixedInput.time_constant_us;
        slewRateControl.Value = fixedInput.slew_rate_v_per_ms;
        bitsControl.Value = fixedInput.dac_bits;
        toleranceControl.Value = fixedInput.tolerance_mv;
        samplePeriodControl.Value = fixedInput.sample_period_us;
        sampleCountControl.Value = fixedInput.sample_count;
        if ~strcmp(scenarioControl.Value, 'Baseline')
            for controlIndex = 1:numel(controls)
                controls{controlIndex}.Enable = 'off';
            end
        end
        updateViews();
    end

    function updateViews
        scenarioName = mapScenarioName(scenarioControl.Value);
        input = scenarioFcn(scenarioName, sampleCountControl.Value);
        if strcmp(scenarioName, 'baseline')
            input.command_voltage_v = commandControl.Value;
            input.initial_voltage_v = initialControl.Value;
            input.update_latency_s = latencyControl.Value .* 1e-6;
            input.time_constant_s = timeConstantControl.Value .* 1e-6;
            input.slew_rate_v_per_s = slewRateControl.Value .* 1000;
            input.dac_bits = bitsControl.Value;
            input.tolerance_v = toleranceControl.Value .* 1e-3;
            input.sample_period_s = samplePeriodControl.Value .* 1e-6;
            input.sample_count = sampleCountControl.Value;
        end
        out = modelFcn(input.command_voltage_v, input.initial_voltage_v, ...
            input.reference_voltage_v, input.dac_bits, ...
            input.update_latency_s, input.time_constant_s, ...
            input.slew_rate_v_per_s, input.tolerance_v, ...
            input.sample_period_s, input.sample_count, input.fault, ...
            input.command_deadline_s);

        cla(responseAxes);
        stairs(responseAxes, 1000 .* out.response.time_s, ...
            out.response.held_target_v, 'k--', 'LineWidth', 1.2);
        hold(responseAxes, 'on');
        plot(responseAxes, 1000 .* out.response.time_s, ...
            out.response.output_v, 'b-', 'LineWidth', 1.5);
        plot(responseAxes, ...
            1000 .* out.command.scheduled_update_time_s .* [1 1], ...
            [0 out.input.reference_voltage_v], 'r:', 'LineWidth', 1.1);
        hold(responseAxes, 'off');
        grid(responseAxes, 'on');
        xlabel(responseAxes, 'Time (ms)');
        ylabel(responseAxes, 'Voltage (V)');
        legend(responseAxes, {'Active held target', 'Analog output', ...
            'Scheduled update'}, 'Location', 'eastoutside');
        title(responseAxes, sprintf([ ...
            'Codes %d to %d; output update applied %d'], ...
            out.quantizer.initial_code, out.quantizer.command_code, ...
            out.command.output_update_applied));

        cla(errorAxes);
        semilogy(errorAxes, 1000 .* out.response.time_s, ...
            1000 .* max(out.response.intended_error_v, eps), ...
            'b-', 'LineWidth', 1.4);
        hold(errorAxes, 'on');
        plot(errorAxes, 1000 .* out.response.time_s, ...
            1000 .* out.input.tolerance_v .* ...
            ones(size(out.response.time_s)), 'r--', 'LineWidth', 1.1);
        hold(errorAxes, 'off');
        grid(errorAxes, 'on');
        xlabel(errorAxes, 'Time (ms)');
        ylabel(errorAxes, 'Absolute target error (mV)');
        legend(errorAxes, {'Intended-target error', ...
            'Settling tolerance'}, 'Location', 'eastoutside');
        title(errorAxes, sprintf([ ...
            'Slew-limited %d; settled in retained view %d'], ...
            out.settling.slew_limited, ...
            out.settling.settled_within_observation));

        summary.Text = sprintf([ ...
            'Requested %.4f V -> code %d -> %.6f V; LSB %.3f mV and ' ...
            'quantization error %.3f mV. Update %.1f us, digital complete %d, ' ...
            'output applied %d, timeout %d. tau %.1f us, slew %.3f V/ms, ' ...
            'slew-limited %d, analytic settle %.3f ms after update, sampled ' ...
            'stay %.3f ms after command, final error %.3f mV. Synthetic ' ...
            'ideal-DAC fixture; not a hardware measurement.'], ...
            out.input.command_voltage_v, out.quantizer.command_code, ...
            out.quantizer.command_voltage_v, ...
            1000 .* out.quantizer.lsb_v, ...
            1000 .* out.quantizer.command_quantization_error_v, ...
            1e6 .* out.command.scheduled_update_time_s, ...
            out.command.digital_complete, ...
            out.command.output_update_applied, out.command.timed_out, ...
            1e6 .* out.input.time_constant_s, ...
            out.input.slew_rate_v_per_s ./ 1000, ...
            out.settling.slew_limited, ...
            1000 .* out.settling.analytic_after_update_s, ...
            1000 .* out.settling.sampled_first_stay_time_s, ...
            1000 .* out.settling.final_error_v);
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
    case 'Baseline'
        name = 'baseline';
    case 'Recorded code, update-not-latched'
        name = 'update-not-latched';
    case 'Command deadline (fixed)'
        name = 'deadline';
    case 'Short observation (fixed)'
        name = 'short-observation';
    case 'Slow output (fixed)'
        name = 'slow-output';
    otherwise
        error('P08:interactive:Scenario', ...
            'Unknown interactive scenario.');
end
end
