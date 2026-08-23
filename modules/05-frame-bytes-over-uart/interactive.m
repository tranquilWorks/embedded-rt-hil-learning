function interactive
%INTERACTIVE Explore P05 UART timing and framing levers one at a time.

% launch_lesson removes this folder after the function returns. Bind P05's
% generic model and unique fixture helper now so retained callbacks cannot
% resolve another module's model.m after a later module switch.
modelFcn = @model;
scenarioFcn = @p05_scenario;

fig = uifigure('Name', 'P05 Frame Bytes over UART', ...
    'Position', [60 60 1320 820]);
gridLayout = uigridlayout(fig, [5 6]);
gridLayout.RowHeight = {'1x', '1x', 105, 22, 40};
gridLayout.ColumnWidth = {'1x', '1x', '1x', '1x', '1x', '1.25x'};

logicAxes = uiaxes(gridLayout);
logicAxes.Layout.Row = 1;
logicAxes.Layout.Column = [1 6];
byteAxes = uiaxes(gridLayout);
byteAxes.Layout.Row = 2;
byteAxes.Layout.Column = [1 6];
summary = uilabel(gridLayout, 'WordWrap', 'on');
summary.Layout.Row = 3;
summary.Layout.Column = [1 6];

makeLabel(gridLayout, 'Transmit baud (bit/s)', 1);
makeLabel(gridLayout, 'Receiver error (%)', 2);
makeLabel(gridLayout, 'Parity', 3);
makeLabel(gridLayout, 'Stop bits', 4);
makeLabel(gridLayout, 'Idle gap (bit times)', 5);
makeLabel(gridLayout, 'Scenario', 6);

baudControl = uispinner(gridLayout, ...
    'Limits', [1200 1000000], 'Step', 1200, 'Value', 115200, ...
    'RoundFractionalValues', 'on');
baudControl.Layout.Row = 5;
baudControl.Layout.Column = 1;
receiverErrorControl = uispinner(gridLayout, ...
    'Limits', [-12 12], 'Step', 1, 'Value', 0);
receiverErrorControl.Layout.Row = 5;
receiverErrorControl.Layout.Column = 2;
parityControl = uidropdown(gridLayout, ...
    'Items', {'none', 'even', 'odd'}, 'Value', 'none');
parityControl.Layout.Row = 5;
parityControl.Layout.Column = 3;
stopBitsControl = uispinner(gridLayout, ...
    'Limits', [1 2], 'Step', 1, 'Value', 1, ...
    'RoundFractionalValues', 'on');
stopBitsControl.Layout.Row = 5;
stopBitsControl.Layout.Column = 4;
gapControl = uispinner(gridLayout, ...
    'Limits', [0 5], 'Step', 0.5, 'Value', 0);
gapControl.Layout.Row = 5;
gapControl.Layout.Column = 5;
scenarioControl = uidropdown(gridLayout, ...
    'Items', {'Matched byte frames', ...
    'Single data-bit fault (toggle parity)', ...
    'Forced-low stop and recovery', ...
    'Fixed receive deadline'}, ...
    'Value', 'Matched byte frames');
scenarioControl.Layout.Row = 5;
scenarioControl.Layout.Column = 6;

baudControl.ValueChangedFcn = @(~, ~) updateViews();
receiverErrorControl.ValueChangedFcn = @(~, ~) updateViews();
parityControl.ValueChangedFcn = @(~, ~) updateViews();
stopBitsControl.ValueChangedFcn = @(~, ~) updateViews();
gapControl.ValueChangedFcn = @(~, ~) updateViews();
scenarioControl.ValueChangedFcn = @(~, ~) selectScenario();
selectScenario();

    function selectScenario
        baudControl.Enable = 'on';
        receiverErrorControl.Enable = 'on';
        parityControl.Enable = 'on';
        stopBitsControl.Enable = 'on';
        gapControl.Enable = 'on';
        switch scenarioControl.Value
            case 'Matched byte frames'
                % Retain current lever values for free exploration.
            case 'Single data-bit fault (toggle parity)'
                receiverErrorControl.Value = 0;
                parityControl.Value = 'even';
                stopBitsControl.Value = 1;
                gapControl.Value = 0;
                receiverErrorControl.Enable = 'off';
                stopBitsControl.Enable = 'off';
                gapControl.Enable = 'off';
            case 'Forced-low stop and recovery'
                receiverErrorControl.Value = 0;
                parityControl.Value = 'none';
                stopBitsControl.Value = 1;
                gapControl.Value = 0;
                receiverErrorControl.Enable = 'off';
                parityControl.Enable = 'off';
                stopBitsControl.Enable = 'off';
                gapControl.Enable = 'off';
            case 'Fixed receive deadline'
                baudControl.Value = 115200;
                receiverErrorControl.Value = 0;
                parityControl.Value = 'none';
                stopBitsControl.Value = 1;
                gapControl.Value = 0;
                baudControl.Enable = 'off';
                receiverErrorControl.Enable = 'off';
                parityControl.Enable = 'off';
                stopBitsControl.Enable = 'off';
                gapControl.Enable = 'off';
        end
        updateViews();
    end

    function updateViews
        scenarioName = mapScenarioName(scenarioControl.Value);
        input = scenarioFcn(scenarioName);
        out = modelFcn(input.payload_bytes, baudControl.Value, ...
            receiverErrorControl.Value, parityControl.Value, ...
            stopBitsControl.Value, gapControl.Value, input.fault, ...
            input.receive_timeout_us);

        if strcmp(input.fault.mode, 'none')
            displayFrame = 1;
        else
            displayFrame = input.fault.frame_index;
        end
        frameBits = out.tx.actual_frame_bits(displayFrame, :);
        bitEdgesUs = (0:out.config.bits_per_frame) .* ...
            out.config.tx_bit_period_us;
        localSampleTimeUs = out.rx.sample_time_us(displayFrame, :) - ...
            out.tx.frame_start_us(displayFrame);

        cla(logicAxes);
        stairs(logicAxes, bitEdgesUs, [frameBits frameBits(end)], ...
            'LineWidth', 1.4);
        hold(logicAxes, 'on');
        plot(logicAxes, localSampleTimeUs, ...
            out.rx.sample_level(displayFrame, :), 'ko', ...
            'MarkerFaceColor', 'w', 'LineWidth', 1.1);
        hold(logicAxes, 'off');
        grid(logicAxes, 'on');
        xlabel(logicAxes, 'Time from selected frame start (us)');
        ylabel(logicAxes, 'Logic level (0 or 1)');
        ylim(logicAxes, [-0.2 1.2]);
        title(logicAxes, sprintf([ ...
            'Frame %d: transmitter slots and receiver samples'], displayFrame));
        legend(logicAxes, {'Transmitter slots', 'Receiver samples'}, ...
            'Location', 'eastoutside');

        frameIndex = 1:out.input.frame_count;
        cla(byteAxes);
        plot(byteAxes, frameIndex, out.input.payload_bytes, ...
            'ks--', 'LineWidth', 1.2);
        hold(byteAxes, 'on');
        plot(byteAxes, frameIndex, out.rx.decoded_bytes, ...
            'bo-', 'LineWidth', 1.3);
        plot(byteAxes, frameIndex(out.rx.parity_error), ...
            out.input.payload_bytes(out.rx.parity_error), ...
            'mx', 'LineWidth', 1.7, 'MarkerSize', 9);
        plot(byteAxes, frameIndex(out.rx.framing_error), ...
            out.input.payload_bytes(out.rx.framing_error), ...
            'rx', 'LineWidth', 1.7, 'MarkerSize', 9);
        unavailable = out.rx.missed_start | out.rx.timed_out;
        plot(byteAxes, frameIndex(unavailable), ...
            out.input.payload_bytes(unavailable), ...
            'kv', 'LineWidth', 1.4, 'MarkerSize', 8);
        hold(byteAxes, 'off');
        grid(byteAxes, 'on');
        xlabel(byteAxes, 'Frame index');
        ylabel(byteAxes, 'Byte value (decimal)');
        title(byteAxes, ...
            'Transmitted bytes, decoded bytes, and explicit error outcomes');
        legend(byteAxes, {'Transmitted', 'Decoded', 'Parity error', ...
            'Framing error', 'Missed or timed out'}, ...
            'Location', 'eastoutside');

        summary.Text = sprintf([ ...
            '%d/%d correct; parity errors %d; framing errors %d; ' ...
            'missed starts %d; deadline cutoffs %d; undetected corruptions %d. ' ...
            'Minimum center-sample margin %s TX-bit times; line time %.2f us; ' ...
            'payload goodput %s. UART character frames do not supply packet ' ...
            'boundaries. These synthetic logic levels are not a hardware measurement.'], ...
            out.metrics.correct_count, out.input.frame_count, ...
            out.metrics.parity_error_count, ...
            out.metrics.framing_error_count, ...
            out.metrics.missed_start_count, ...
            out.metrics.timed_out_count, ...
            out.metrics.undetected_corruption_count, ...
            formatMetric(out.metrics.minimum_sampling_margin_bits, 'bits'), ...
            out.tx.line_time_us, ...
            formatMetric(out.metrics.payload_goodput_bps, 'bit/s'));
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
    case 'Matched byte frames'
        name = 'baseline';
    case 'Single data-bit fault (toggle parity)'
        name = 'parity-fault';
    case 'Forced-low stop and recovery'
        name = 'stop-fault-recovery';
    case 'Fixed receive deadline'
        name = 'deadline';
    otherwise
        error('P05:interactive:Scenario', ...
            'Unknown interactive scenario.');
end
end

function text = formatMetric(value, unit)
if isnan(value)
    text = ['N/A (no received frame) ' unit];
else
    text = sprintf('%.3f %s', value, unit);
end
end
