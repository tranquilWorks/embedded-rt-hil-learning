function interactive
%INTERACTIVE Explore P07 sample-rate, front-end, ADC, and alias controls.

% launch_lesson removes this folder after the function returns. Bind P07's
% generic model and unique fixture helper now so retained callbacks cannot
% resolve another module's model.m after a later module switch.
modelFcn = @model;
scenarioFcn = @p07_scenario;

fig = uifigure('Name', 'P07 Sample an ADC Without Aliasing', ...
    'Position', [35 35 1440 840]);
gridLayout = uigridlayout(fig, [5 8]);
gridLayout.RowHeight = {'1x', '1x', 125, 22, 40};
gridLayout.ColumnWidth = {'1x', '1x', '1x', '1x', ...
    '1x', '1x', '1x', '1.35x'};

timeAxes = uiaxes(gridLayout);
timeAxes.Layout.Row = 1;
timeAxes.Layout.Column = [1 8];
frequencyAxes = uiaxes(gridLayout);
frequencyAxes.Layout.Row = 2;
frequencyAxes.Layout.Column = [1 8];
summary = uilabel(gridLayout, 'WordWrap', 'on');
summary.Layout.Row = 3;
summary.Layout.Column = [1 8];

makeLabel(gridLayout, 'Input frequency (Hz)', 1);
makeLabel(gridLayout, 'Sample rate (Hz)', 2);
makeLabel(gridLayout, 'AA cutoff (Hz)', 3);
makeLabel(gridLayout, 'ADC bits', 4);
makeLabel(gridLayout, 'Amplitude (V)', 5);
makeLabel(gridLayout, 'Offset (V)', 6);
makeLabel(gridLayout, 'Samples', 7);
makeLabel(gridLayout, 'Scenario', 8);

frequencyControl = uispinner(gridLayout, ...
    'Limits', [0 1200], 'Step', 10, 'Value', 180);
frequencyControl.Layout.Row = 5;
frequencyControl.Layout.Column = 1;
sampleRateControl = uispinner(gridLayout, ...
    'Limits', [100 5000], 'Step', 50, 'Value', 1000);
sampleRateControl.Layout.Row = 5;
sampleRateControl.Layout.Column = 2;
cutoffControl = uispinner(gridLayout, ...
    'Limits', [10 2000], 'Step', 10, 'Value', 400);
cutoffControl.Layout.Row = 5;
cutoffControl.Layout.Column = 3;
bitsControl = uispinner(gridLayout, ...
    'Limits', [4 16], 'Step', 1, 'Value', 12, ...
    'RoundFractionalValues', 'on');
bitsControl.Layout.Row = 5;
bitsControl.Layout.Column = 4;
amplitudeControl = uispinner(gridLayout, ...
    'Limits', [0 2], 'Step', 0.1, 'Value', 1);
amplitudeControl.Layout.Row = 5;
amplitudeControl.Layout.Column = 5;
offsetControl = uispinner(gridLayout, ...
    'Limits', [0 3.3], 'Step', 0.05, 'Value', 1.65);
offsetControl.Layout.Row = 5;
offsetControl.Layout.Column = 6;
sampleCountControl = uispinner(gridLayout, ...
    'Limits', [8 256], 'Step', 1, 'Value', 51, ...
    'RoundFractionalValues', 'on');
sampleCountControl.Layout.Row = 5;
sampleCountControl.Layout.Column = 7;
scenarioControl = uidropdown(gridLayout, ...
    'Items', {'Filtered baseline', 'Bypassed 820 Hz alias', ...
    'Nyquist phase loss', 'ADC rail clipping', ...
    'Fixed acquisition deadline'}, ...
    'Value', 'Filtered baseline');
scenarioControl.Layout.Row = 5;
scenarioControl.Layout.Column = 8;

frequencyControl.ValueChangedFcn = @(~, ~) updateViews();
sampleRateControl.ValueChangedFcn = @(~, ~) updateViews();
cutoffControl.ValueChangedFcn = @(~, ~) updateViews();
bitsControl.ValueChangedFcn = @(~, ~) updateViews();
amplitudeControl.ValueChangedFcn = @(~, ~) updateViews();
offsetControl.ValueChangedFcn = @(~, ~) updateViews();
sampleCountControl.ValueChangedFcn = @(~, ~) updateViews();
scenarioControl.ValueChangedFcn = @(~, ~) selectScenario();
selectScenario();

    function selectScenario
        controls = {frequencyControl, sampleRateControl, cutoffControl, ...
            bitsControl, amplitudeControl, offsetControl, ...
            sampleCountControl};
        for controlIndex = 1:numel(controls)
            controls{controlIndex}.Enable = 'on';
        end
        scenarioName = mapScenarioName(scenarioControl.Value);
        fixedInput = scenarioFcn(scenarioName, 51);
        frequencyControl.Value = fixedInput.signal_frequency_hz;
        sampleRateControl.Value = fixedInput.sample_rate_hz;
        cutoffControl.Value = fixedInput.anti_alias_cutoff_hz;
        bitsControl.Value = fixedInput.adc_bits;
        amplitudeControl.Value = fixedInput.amplitude_v;
        offsetControl.Value = fixedInput.offset_v;
        sampleCountControl.Value = fixedInput.sample_count;
        if ~strcmp(scenarioControl.Value, 'Filtered baseline')
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
            input.signal_frequency_hz = frequencyControl.Value;
            input.sample_rate_hz = sampleRateControl.Value;
            input.anti_alias_cutoff_hz = cutoffControl.Value;
            input.adc_bits = bitsControl.Value;
            input.amplitude_v = amplitudeControl.Value;
            input.offset_v = offsetControl.Value;
        end
        out = modelFcn(input.signal_frequency_hz, ...
            input.sample_rate_hz, input.sample_count, input.amplitude_v, ...
            input.offset_v, input.phase_rad, input.anti_alias_cutoff_hz, ...
            input.adc_bits, input.reference_voltage_v, input.fault, ...
            input.acquisition_deadline_s);

        cla(timeAxes);
        plot(timeAxes, 1000 .* out.analog.reference_time_s, ...
            out.analog.source_v, 'Color', [0.65 0.65 0.65], ...
            'LineWidth', 1.1);
        hold(timeAxes, 'on');
        plot(timeAxes, 1000 .* out.analog.reference_time_s, ...
            out.analog.filtered_v, 'b-', 'LineWidth', 1.3);
        plot(timeAxes, 1000 .* out.analog.reference_time_s, ...
            out.analog.apparent_alias_v, 'r--', 'LineWidth', 1.1);
        plot(timeAxes, 1000 .* out.samples.time_s, ...
            out.adc.code_center_v, 'ko', 'MarkerFaceColor', 'w');
        hold(timeAxes, 'off');
        grid(timeAxes, 'on');
        xlabel(timeAxes, 'Time (ms)');
        ylabel(timeAxes, 'Voltage (V)');
        legend(timeAxes, {'Physical input', 'After analog front end', ...
            'Apparent folded sinusoid', 'ADC code centers'}, ...
            'Location', 'eastoutside');
        title(timeAxes, sprintf([ ...
            'Physical %.1f Hz; sampled apparent %.1f Hz'], ...
            out.input.signal_frequency_hz, ...
            out.frequency.alias_frequency_hz));

        cla(frequencyAxes);
        plot(frequencyAxes, [1 2], [out.input.signal_frequency_hz ...
            out.frequency.alias_frequency_hz], 'o-', ...
            'LineWidth', 1.5, 'MarkerSize', 7);
        hold(frequencyAxes, 'on');
        plot(frequencyAxes, [0.75 2.25], ...
            [out.frequency.nyquist_hz out.frequency.nyquist_hz], ...
            'k--', 'LineWidth', 1.1);
        hold(frequencyAxes, 'off');
        grid(frequencyAxes, 'on');
        xlim(frequencyAxes, [0.75 2.25]);
        frequencyAxes.XTick = [1 2];
        frequencyAxes.XTickLabel = {'Physical input', 'Sampled apparent'};
        ylabel(frequencyAxes, 'Frequency (Hz)');
        legend(frequencyAxes, {'Input-to-fold mapping', ...
            'Nyquist boundary'}, 'Location', 'eastoutside');
        title(frequencyAxes, sprintf([ ...
            'Strict margin %.1f Hz; aliasing present %d'], ...
            out.frequency.nyquist_margin_hz, ...
            out.frequency.aliasing_present));

        summary.Text = sprintf([ ...
            'H(f) gain %.3f and phase %.3f rad; front end enabled %d. ' ...
            'f_s %.1f Hz, f_N %.1f Hz, signed fold %.1f Hz, ' ...
            'strictly safe %d. ADC: %d bits, LSB %.3f mV, clipped %d/%d, ' ...
            'committed %d/%d, deadline %d, raw payload %.0f bit/s. ' ...
            'A bus can transport these codes but cannot restore an aliased ' ...
            'analog frequency. Synthetic fixture; not a hardware measurement.'], ...
            out.filter.gain, out.filter.phase_rad, out.filter.enabled, ...
            out.input.sample_rate_hz, out.frequency.nyquist_hz, ...
            out.frequency.signed_fold_hz, ...
            out.frequency.strict_nyquist_safe, out.input.adc_bits, ...
            1000 .* out.adc.lsb_v, out.adc.clipped_count, ...
            out.input.sample_count, numel(out.adc.committed_codes), ...
            out.input.sample_count, out.capture.timed_out, ...
            out.capture.raw_payload_rate_bps);
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
    case 'Filtered baseline'
        name = 'baseline';
    case 'Bypassed 820 Hz alias'
        name = 'alias-trap';
    case 'Nyquist phase loss'
        name = 'nyquist-boundary';
    case 'ADC rail clipping'
        name = 'clipping';
    case 'Fixed acquisition deadline'
        name = 'deadline';
    otherwise
        error('P07:interactive:Scenario', ...
            'Unknown interactive scenario.');
end
end
