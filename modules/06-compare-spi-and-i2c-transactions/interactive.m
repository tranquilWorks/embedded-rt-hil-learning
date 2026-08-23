function interactive
%INTERACTIVE Explore P06 transaction overhead and failure observability.

% launch_lesson removes this folder after the function returns. Bind P06's
% generic model and unique fixture helper now so retained callbacks cannot
% resolve another module's model.m after a later module switch.
modelFcn = @model;
scenarioFcn = @p06_scenario;

fig = uifigure('Name', 'P06 Compare SPI and I2C Transactions', ...
    'Position', [45 45 1380 840]);
gridLayout = uigridlayout(fig, [5 7]);
gridLayout.RowHeight = {'1x', '1x', 115, 22, 40};
gridLayout.ColumnWidth = {'1x', '1x', '1x', '1x', ...
    '1x', '1x', '1.35x'};

spiAxes = uiaxes(gridLayout);
spiAxes.Layout.Row = 1;
spiAxes.Layout.Column = [1 7];
i2cAxes = uiaxes(gridLayout);
i2cAxes.Layout.Row = 2;
i2cAxes.Layout.Column = [1 7];
summary = uilabel(gridLayout, 'WordWrap', 'on');
summary.Layout.Row = 3;
summary.Layout.Column = [1 7];

makeLabel(gridLayout, 'Payload (bytes)', 1);
makeLabel(gridLayout, 'SPI clock (kHz)', 2);
makeLabel(gridLayout, 'I2C clock (kHz)', 3);
makeLabel(gridLayout, 'I2C stretch (us)', 4);
makeLabel(gridLayout, 'I2C 7-bit address', 5);
makeLabel(gridLayout, 'Register', 6);
makeLabel(gridLayout, 'Scenario', 7);

payloadControl = uispinner(gridLayout, ...
    'Limits', [1 64], 'Step', 1, 'Value', 4, ...
    'RoundFractionalValues', 'on');
payloadControl.Layout.Row = 5;
payloadControl.Layout.Column = 1;
spiClockControl = uispinner(gridLayout, ...
    'Limits', [10 5000], 'Step', 50, 'Value', 400);
spiClockControl.Layout.Row = 5;
spiClockControl.Layout.Column = 2;
i2cClockControl = uispinner(gridLayout, ...
    'Limits', [10 1000], 'Step', 25, 'Value', 400);
i2cClockControl.Layout.Row = 5;
i2cClockControl.Layout.Column = 3;
stretchControl = uispinner(gridLayout, ...
    'Limits', [0 500], 'Step', 25, 'Value', 0);
stretchControl.Layout.Row = 5;
stretchControl.Layout.Column = 4;
addressControl = uispinner(gridLayout, ...
    'Limits', [8 119], 'Step', 1, 'Value', 72, ...
    'RoundFractionalValues', 'on');
addressControl.Layout.Row = 5;
addressControl.Layout.Column = 5;
registerControl = uispinner(gridLayout, ...
    'Limits', [0 127], 'Step', 1, 'Value', 45, ...
    'RoundFractionalValues', 'on');
registerControl.Layout.Row = 5;
registerControl.Layout.Column = 6;
scenarioControl = uidropdown(gridLayout, ...
    'Items', {'Clean register read', 'Target NACK on register', ...
    'SPI returned-bit corruption', 'Fixed stretch deadline'}, ...
    'Value', 'Clean register read');
scenarioControl.Layout.Row = 5;
scenarioControl.Layout.Column = 7;

payloadControl.ValueChangedFcn = @(~, ~) updateViews();
spiClockControl.ValueChangedFcn = @(~, ~) updateViews();
i2cClockControl.ValueChangedFcn = @(~, ~) updateViews();
stretchControl.ValueChangedFcn = @(~, ~) updateViews();
addressControl.ValueChangedFcn = @(~, ~) updateViews();
registerControl.ValueChangedFcn = @(~, ~) updateViews();
scenarioControl.ValueChangedFcn = @(~, ~) selectScenario();
selectScenario();

    function selectScenario
        controls = {payloadControl, spiClockControl, i2cClockControl, ...
            stretchControl, addressControl, registerControl};
        for controlIndex = 1:numel(controls)
            controls{controlIndex}.Enable = 'on';
        end
        if ~strcmp(scenarioControl.Value, 'Clean register read')
            payloadControl.Value = 4;
            spiClockControl.Value = 400;
            i2cClockControl.Value = 400;
            stretchControl.Value = 0;
            addressControl.Value = 72;
            registerControl.Value = 45;
            for controlIndex = 1:numel(controls)
                controls{controlIndex}.Enable = 'off';
            end
        end
        updateViews();
    end

    function updateViews
        scenarioName = mapScenarioName(scenarioControl.Value);
        input = scenarioFcn(scenarioName, payloadControl.Value);
        fault = input.fault;
        timeoutUs = input.transaction_timeout_us;
        if strcmp(scenarioName, 'baseline') && stretchControl.Value > 0
            fault = struct('mode', 'i2c-clock-stretch', ...
                'i2c_stretch_us', stretchControl.Value);
        end
        out = modelFcn(input.payload_bytes, ...
            spiClockControl.Value .* 1000, ...
            i2cClockControl.Value .* 1000, addressControl.Value, ...
            registerControl.Value, fault, timeoutUs);

        spiEdges = 0:out.spi.clocked_bit_count;
        cla(spiAxes);
        stairs(spiAxes, spiEdges, ...
            [out.spi.mosi_bits out.spi.mosi_bits(end)] + 1.5, ...
            'b-', 'LineWidth', 1.3);
        hold(spiAxes, 'on');
        stairs(spiAxes, spiEdges, ...
            [out.spi.miso_actual_bits out.spi.miso_actual_bits(end)], ...
            'k-', 'LineWidth', 1.3);
        plot(spiAxes, [out.spi.chip_select_assert_clock_index ...
            out.spi.chip_select_assert_clock_index ...
            out.spi.chip_select_deassert_clock_index ...
            out.spi.chip_select_deassert_clock_index], ...
            [4 3 3 4], 'g-', 'LineWidth', 1.3);
        hold(spiAxes, 'off');
        grid(spiAxes, 'on');
        xlabel(spiAxes, 'SPI clock pulse index');
        ylabel(spiAxes, 'Logic level plus lane offset');
        ylim(spiAxes, [-0.2 4.2]);
        legend(spiAxes, {'MOSI command/dummy (+1.5)', ...
            'MISO dummy/payload', 'Active-low CS (+3)'}, ...
            'Location', 'eastoutside');
        title(spiAxes, sprintf([ ...
            'SPI: %d pulses, complete %d, payload correct %d'], ...
            out.spi.clocked_bit_count, out.spi.transaction_complete, ...
            out.spi.payload_correct));

        i2cEdges = 0:out.i2c.actual_clocked_bit_count;
        cla(i2cAxes);
        stairs(i2cAxes, i2cEdges, ...
            [out.i2c.clocked_sda_bits out.i2c.clocked_sda_bits(end)], ...
            'b-', 'LineWidth', 1.3);
        hold(i2cAxes, 'on');
        plot(i2cAxes, out.i2c.response_clock_indices - 0.5, ...
            out.i2c.response_bits, 'ro', 'MarkerFaceColor', 'w', ...
            'LineWidth', 1.2);
        if out.i2c.repeated_start_present
            plot(i2cAxes, [18 18], [-0.2 1.2], ...
                'k:', 'LineWidth', 1.1);
        end
        hold(i2cAxes, 'off');
        grid(i2cAxes, 'on');
        xlabel(i2cAxes, 'I2C SCL clock pulse index');
        ylabel(i2cAxes, 'SDA logic level (0 or 1)');
        ylim(i2cAxes, [-0.2 1.2]);
        if out.i2c.repeated_start_present
            legend(i2cAxes, {'Clocked SDA cells', 'Ninth-clock responses', ...
                'Repeated START boundary'}, 'Location', 'eastoutside');
        else
            legend(i2cAxes, {'Clocked SDA cells', ...
                'Ninth-clock responses'}, 'Location', 'eastoutside');
        end
        title(i2cAxes, sprintf([ ...
            'I2C: %d pulses, target NACK %d, final controller NACK %d'], ...
            out.i2c.actual_clocked_bit_count, ...
            out.i2c.target_nack_detected, ...
            out.i2c.intentional_final_nack));

        summary.Text = sprintf([ ...
            'SPI: %.2f us modeled elapsed, %.1f%% nominal payload efficiency, ' ...
            '%d/%d correct bytes, undetected corruptions %d, deadline %d. ' ...
            'I2C: %.2f us modeled elapsed (%.2f us clocked + %.2f us stretch), ' ...
            '%.1f%% nominal payload efficiency, %d/%d committed bytes, ' ...
            'target NACK %d, deadline %d. Final read NACK is controller-owned ' ...
            'normal termination. This device-specific synthetic fixture is ' ...
            'not a hardware measurement or conformance result.'], ...
            out.spi.modeled_elapsed_time_us, ...
            100 .* out.metrics.spi_nominal_payload_efficiency, ...
            out.metrics.spi_correct_payload_count, out.input.payload_count, ...
            out.metrics.spi_undetected_corruption_count, out.spi.timed_out, ...
            out.i2c.modeled_elapsed_time_us, out.i2c.clocked_time_us, ...
            out.i2c.clock_stretch_us, ...
            100 .* out.metrics.i2c_nominal_payload_efficiency, ...
            out.metrics.i2c_correct_payload_count, out.input.payload_count, ...
            out.i2c.target_nack_detected, out.i2c.timed_out);
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
    case 'Clean register read'
        name = 'baseline';
    case 'Target NACK on register'
        name = 'target-nack';
    case 'SPI returned-bit corruption'
        name = 'spi-corruption';
    case 'Fixed stretch deadline'
        name = 'stretch-timeout';
    otherwise
        error('P06:interactive:Scenario', ...
            'Unknown interactive scenario.');
end
end
