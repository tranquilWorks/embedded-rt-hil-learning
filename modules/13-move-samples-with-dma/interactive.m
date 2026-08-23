function interactive
%INTERACTIVE Explore P13 DMA service, block ownership, and memory integrity.

% launch_lesson removes this folder after this function returns. Bind P13's
% generic model and unique fixture helper now so retained callbacks cannot
% resolve another module's model.m after a later module switch.
modelFcn = @model;
scenarioFcn = @p13_scenario;

fig = uifigure('Name', 'P13 Move Samples with DMA', ...
    'Position', [5 20 1900 930]);
gridLayout = uigridlayout(fig, [5 11]);
gridLayout.RowHeight = {'1x', '1x', 115, 22, 42};
gridLayout.ColumnWidth = repmat({'1x'}, 1, 11);

timingAxes = uiaxes(gridLayout);
timingAxes.Layout.Row = 1;
timingAxes.Layout.Column = [1 6];
readyAxes = uiaxes(gridLayout);
readyAxes.Layout.Row = 1;
readyAxes.Layout.Column = [7 11];
cpuAxes = uiaxes(gridLayout);
cpuAxes.Layout.Row = 2;
cpuAxes.Layout.Column = [1 6];
memoryAxes = uiaxes(gridLayout);
memoryAxes.Layout.Row = 2;
memoryAxes.Layout.Column = [7 11];
summary = uilabel(gridLayout, 'WordWrap', 'on');
summary.Layout.Row = 3;
summary.Layout.Column = [1 11];

makeLabel(gridLayout, 'Sample period (us)', 1);
makeLabel(gridLayout, 'Block size (sample)', 2);
makeLabel(gridLayout, 'Bytes/sample', 3);
makeLabel(gridLayout, 'Bus rate (byte/us)', 4);
makeLabel(gridLayout, 'Arbitration (us/beat)', 5);
makeLabel(gridLayout, 'DMA setup CPU (us)', 6);
makeLabel(gridLayout, 'Completion ISR CPU (us)', 7);
makeLabel(gridLayout, 'Processor copy (us/sample)', 8);
makeLabel(gridLayout, 'Timeout (us; 0=off)', 9);
makeLabel(gridLayout, 'Timeout action', 10);
makeLabel(gridLayout, 'Scenario', 11);

samplePeriodControl = numericSpinner(gridLayout, [1 1e6], 50, 1, 1);
blockControl = uidropdown(gridLayout, ...
    'Items', {'1', '2', '4', '8', '16', '32'}, 'Value', '8');
blockControl.Layout.Row = 5;
blockControl.Layout.Column = 2;
bytesControl = uidropdown(gridLayout, ...
    'Items', arrayfun(@num2str, 1:16, 'UniformOutput', false), ...
    'Value', '2');
bytesControl.Layout.Row = 5;
bytesControl.Layout.Column = 3;
busRateControl = numericSpinner(gridLayout, [0.001 10], 0.2, ...
    0.025, 4);
arbitrationControl = numericSpinner(gridLayout, [0 1000], 1, ...
    0.25, 5);
setupControl = numericSpinner(gridLayout, [0 1000], 8, 1, 6);
isrControl = numericSpinner(gridLayout, [0 1000], 3, 1, 7);
copyControl = numericSpinner(gridLayout, [0 1000], 4, 1, 8);
timeoutControl = numericSpinner(gridLayout, [0 1e6], 0, 1, 9);
timeoutActionControl = uidropdown(gridLayout, ...
    'Items', {'Continue waiting', 'Abort transfer'}, ...
    'Value', 'Continue waiting');
timeoutActionControl.Layout.Row = 5;
timeoutActionControl.Layout.Column = 10;
scenarioControl = uidropdown(gridLayout, ...
    'Items', {'Editable baseline', 'Fixed destination (fixed)', ...
    'Overloaded bus (fixed)', 'Timeout continues (fixed)', ...
    'Timeout aborts (fixed)'}, ...
    'Value', 'Editable baseline');
scenarioControl.Layout.Row = 5;
scenarioControl.Layout.Column = 11;

controls = {samplePeriodControl, blockControl, bytesControl, ...
    busRateControl, arbitrationControl, setupControl, isrControl, ...
    copyControl, timeoutControl, timeoutActionControl};
for controlIndex = 1:numel(controls)
    controls{controlIndex}.ValueChangedFcn = @(~, ~) updateViews();
end
scenarioControl.ValueChangedFcn = @(~, ~) selectScenario();
selectScenario();

    function selectScenario
        for controlIndex = 1:numel(controls)
            controls{controlIndex}.Enable = 'on';
        end
        scenarioName = mapScenarioName(scenarioControl.Value);
        fixedInput = scenarioFcn(scenarioName);
        samplePeriodControl.Value = fixedInput.sample_period_us;
        blockControl.Value = num2str(fixedInput.block_samples);
        bytesControl.Value = num2str(fixedInput.bytes_per_sample);
        busRateControl.Value = fixedInput.bus_rate_bytes_per_us;
        arbitrationControl.Value = fixedInput.arbitration_us;
        setupControl.Value = fixedInput.dma_setup_cpu_us;
        isrControl.Value = fixedInput.completion_isr_cpu_us;
        copyControl.Value = ...
            fixedInput.processor_copy_cpu_us_per_sample;
        timeoutControl.Value = ...
            timeoutControlValue(fixedInput.descriptor_timeout_us);
        timeoutActionControl.Value = ...
            timeoutActionLabel(fixedInput.timeout_action);
        if ~strcmp(scenarioName, 'baseline')
            for controlIndex = 1:numel(controls)
                controls{controlIndex}.Enable = 'off';
            end
        end
        updateViews();
    end

    function updateViews
        scenarioName = mapScenarioName(scenarioControl.Value);
        input = scenarioFcn(scenarioName, ...
            str2double(blockControl.Value), busRateControl.Value, ...
            samplePeriodControl.Value, arbitrationControl.Value, ...
            isrControl.Value, copyControl.Value);
        if strcmp(scenarioName, 'baseline')
            input.bytes_per_sample = str2double(bytesControl.Value);
            input.dma_setup_cpu_us = setupControl.Value;
            input.descriptor_timeout_us = ...
                timeoutFromControl(timeoutControl.Value);
            input.timeout_action = ...
                timeoutActionFromLabel(timeoutActionControl.Value);
        end
        out = modelFcn(input.source_samples, input.sample_period_us, ...
            input.bytes_per_sample, input.bus_rate_bytes_per_us, ...
            input.arbitration_us, input.block_samples, ...
            input.dma_setup_cpu_us, input.completion_isr_cpu_us, ...
            input.processor_copy_cpu_us_per_sample, ...
            input.descriptor_timeout_us, input.timeout_action, ...
            input.destination_mode);

        cla(timingAxes);
        observedStartUs = out.timeline.start_us;
        observedCompletionUs = out.timeline.completion_us;
        if out.observation.abort_issued
            startedBeforeAbort = out.timeline.start_us < ...
                input.descriptor_timeout_us;
            observedStartUs(~startedBeforeAbort) = NaN;
            observedCompletionUs(~out.memory.committed) = NaN;
        end
        plot(timingAxes, out.timeline.sample_index, ...
            out.timeline.request_us, 'ko-', 'LineWidth', 1.1);
        hold(timingAxes, 'on');
        plot(timingAxes, out.timeline.sample_index, ...
            observedStartUs, 'bs--', 'LineWidth', 1.1);
        plot(timingAxes, out.timeline.sample_index, ...
            observedCompletionUs, 'r.-', ...
            'LineWidth', 1.1, 'MarkerSize', 11);
        hold(timingAxes, 'off');
        grid(timingAxes, 'on');
        xlabel(timingAxes, 'Sample request (index)');
        ylabel(timingAxes, 'Time from descriptor arm (us)');
        legend(timingAxes, {'Reference request', 'Observed DMA start', ...
            'Committed DMA finish'}, ...
            'Location', 'northwest');
        title(timingAxes, sprintf( ...
            'Serialized beats: q=%.3g us, peak pending=%d', ...
            out.metrics.beat_service_us, ...
            out.metrics.peak_pending_requests));

        cla(readyAxes);
        bar(readyAxes, out.timeline.sample_index, ...
            out.block.observed_ready_latency_us);
        grid(readyAxes, 'on');
        xlabel(readyAxes, 'Sample (index)');
        ylabel(readyAxes, 'Observed block-ready latency (us)');
        title(readyAxes, sprintf( ...
            '%d of %d completion blocks are processor-owned', ...
            out.observation.completed_block_count, ...
            out.metrics.block_count));

        cla(cpuAxes);
        stairs(cpuAxes, out.timeline.sample_index, ...
            out.cpu.processor_copy_cumulative_us, ...
            'LineWidth', 1.4);
        hold(cpuAxes, 'on');
        stairs(cpuAxes, out.timeline.sample_index, ...
            out.cpu.observed_dma_cumulative_us, ...
            'LineWidth', 1.4);
        hold(cpuAxes, 'off');
        grid(cpuAxes, 'on');
        xlabel(cpuAxes, 'Samples requested (count)');
        ylabel(cpuAxes, 'Cumulative processor service demand (us)');
        legend(cpuAxes, {'Reference full processor copy', ...
            'Observed DMA control'}, ...
            'Location', 'northwest');
        title(cpuAxes, 'Declared service demand, not measured utilization');

        cla(memoryAxes);
        stem(memoryAxes, out.timeline.sample_index, ...
            out.memory.source_samples, 'filled', 'LineWidth', 1.0);
        hold(memoryAxes, 'on');
        plot(memoryAxes, out.timeline.sample_index, ...
            out.memory.destination_samples, 'rx', ...
            'LineWidth', 1.4, 'MarkerSize', 7);
        hold(memoryAxes, 'off');
        grid(memoryAxes, 'on');
        xlabel(memoryAxes, 'Source or destination slot (index)');
        ylabel(memoryAxes, 'Synthetic sample code (count)');
        legend(memoryAxes, {'Source', 'Destination'}, ...
            'Location', 'northwest');
        title(memoryAxes, sprintf( ...
            'Integrity=%d; written=%d; unwritten=%d; overwrites=%d', ...
            out.metrics.data_integrity, ...
            out.metrics.written_slot_count, ...
            out.metrics.unwritten_slot_count, ...
            out.metrics.overwrite_count));

        summary.Text = sprintf([ ...
            'q=A+b/r=%.3g us; slack %.3g us; offered load %.3g%%; ' ...
            'observed descriptor finish %.3g us; ' ...
            'reference no-abort finish %.3g us; ' ...
            'request-budget excesses %d. ' ...
            'CPU demand: reference full copy %.3g us, ' ...
            'DMA observed %.3g us. ' ...
            'Timeout=%d, abort=%d, committed=%d/%d, completed ' ...
            'blocks=%d. Backlog is not proved loss; completion is not ' ...
            'destination integrity; abort is not rollback. Synthetic ' ...
            'view only: not MATLAB-runtime or hardware evidence.'], ...
            out.metrics.beat_service_us, ...
            out.metrics.request_slack_us, ...
            out.metrics.offered_bus_load_pct, ...
            out.observation.descriptor_completion_us, ...
            out.metrics.descriptor_completion_us, ...
            out.metrics.request_budget_exceed_count, ...
            out.cpu.processor_copy_demand_us, ...
            out.cpu.observed_dma_demand_us, ...
            out.observation.wait_timed_out, ...
            out.observation.abort_issued, ...
            out.observation.committed_sample_count, ...
            out.metrics.sample_count, ...
            out.observation.completed_block_count);
    end
end

function control = numericSpinner(gridLayout, limits, value, step, column)
control = uispinner(gridLayout, 'Limits', limits, 'Value', value, ...
    'Step', step);
control.Layout.Row = 5;
control.Layout.Column = column;
end

function makeLabel(gridLayout, labelText, column)
label = uilabel(gridLayout, 'Text', labelText, ...
    'HorizontalAlignment', 'center');
label.Layout.Row = 4;
label.Layout.Column = column;
end

function name = mapScenarioName(displayName)
switch displayName
    case 'Editable baseline'
        name = 'baseline';
    case 'Fixed destination (fixed)'
        name = 'fixed-destination';
    case 'Overloaded bus (fixed)'
        name = 'overloaded-bus';
    case 'Timeout continues (fixed)'
        name = 'timeout-continue';
    case 'Timeout aborts (fixed)'
        name = 'timeout-abort';
    otherwise
        error('P13:interactive:Scenario', ...
            'Unknown interactive scenario label.');
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
    action = 'abort-transfer';
end
end

function label = timeoutActionLabel(action)
if strcmp(action, 'continue-waiting')
    label = 'Continue waiting';
else
    label = 'Abort transfer';
end
end
