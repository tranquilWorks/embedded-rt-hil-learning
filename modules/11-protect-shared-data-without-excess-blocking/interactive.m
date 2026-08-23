function interactive
%INTERACTIVE Explore P11 lock scope, coherence, and blocking.

% launch_lesson removes this folder after the function returns. Bind P11's
% generic model and unique fixture helper now so retained callbacks cannot
% resolve another module's model.m after a later module switch.
modelFcn = @model;
scenarioFcn = @p11_scenario;

fig = uifigure('Name', ...
    'P11 Protect Shared Data Without Excess Blocking', ...
    'Position', [10 25 1810 880]);
gridLayout = uigridlayout(fig, [5 9]);
gridLayout.RowHeight = {'1x', '1x', 135, 22, 42};
gridLayout.ColumnWidth = {'1x', '1x', '1x', '1x', ...
    '1.25x', '1.25x', '1.25x', '1x', '1.65x'};

ownershipAxes = uiaxes(gridLayout);
ownershipAxes.Layout.Row = 1;
ownershipAxes.Layout.Column = [1 9];
recordAxes = uiaxes(gridLayout);
recordAxes.Layout.Row = 2;
recordAxes.Layout.Column = [1 9];
summary = uilabel(gridLayout, 'WordWrap', 'on');
summary.Layout.Row = 3;
summary.Layout.Column = [1 9];

makeLabel(gridLayout, 'Writer private prep (ms)', 1);
makeLabel(gridLayout, 'Protected record (words)', 2);
makeLabel(gridLayout, 'Reader release (ms)', 3);
makeLabel(gridLayout, 'Reader local process (ms)', 4);
makeLabel(gridLayout, 'Protection scope', 5);
makeLabel(gridLayout, 'Reader wait timeout (ms; 0=off)', 6);
makeLabel(gridLayout, 'Timeout action', 7);
makeLabel(gridLayout, 'Horizon (ms)', 8);
makeLabel(gridLayout, 'Scenario', 9);

writerPrepareControl = integerSpinner(gridLayout, [0 20], 2, 1);
recordWordsControl = integerSpinner(gridLayout, [2 16], 2, 2);
readerReleaseControl = integerSpinner(gridLayout, [0 30], 3, 3);
readerProcessControl = integerSpinner(gridLayout, [0 20], 2, 4);
protectionControl = uidropdown(gridLayout, ...
    'Items', {'Short mutex', 'Coarse mutex', 'Unprotected'}, ...
    'Value', 'Short mutex');
protectionControl.Layout.Row = 5;
protectionControl.Layout.Column = 5;
waitTimeoutControl = integerSpinner(gridLayout, [0 30], 0, 6);
timeoutActionControl = uidropdown(gridLayout, ...
    'Items', {'Continue waiting', 'Cancel reader'}, ...
    'Value', 'Continue waiting');
timeoutActionControl.Layout.Row = 5;
timeoutActionControl.Layout.Column = 7;
horizonControl = integerSpinner(gridLayout, [1 100], 16, 8);
scenarioControl = uidropdown(gridLayout, ...
    'Items', {'Editable short-mutex baseline', ...
    'Coarse lock (fixed)', ...
    'Unprotected torn read (fixed)', ...
    'Wait timeout continues (fixed)', ...
    'Cancel blocked reader (fixed)', ...
    'Early coherent reader (fixed)'}, ...
    'Value', 'Editable short-mutex baseline');
scenarioControl.Layout.Row = 5;
scenarioControl.Layout.Column = 9;

controls = {writerPrepareControl, recordWordsControl, ...
    readerReleaseControl, readerProcessControl, protectionControl, ...
    waitTimeoutControl, timeoutActionControl, horizonControl};
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
        fixedInput = scenarioFcn(scenarioName, 2, 2, 3, 2, 16);
        writerPrepareControl.Value = fixedInput.writer_prepare_ms;
        recordWordsControl.Value = fixedInput.record_words;
        readerReleaseControl.Value = fixedInput.reader_release_ms;
        readerProcessControl.Value = fixedInput.reader_process_ms;
        protectionControl.Value = ...
            protectionLabel(fixedInput.protection);
        waitTimeoutControl.Value = ...
            timeoutControlValue(fixedInput.wait_timeout_ms);
        timeoutActionControl.Value = ...
            timeoutActionLabel(fixedInput.timeout_action);
        horizonControl.Value = fixedInput.horizon_ms;
        if ~strcmp(scenarioControl.Value, ...
                'Editable short-mutex baseline')
            for controlIndex = 1:numel(controls)
                controls{controlIndex}.Enable = 'off';
            end
        end
        updateViews();
    end

    function updateViews
        scenarioName = mapScenarioName(scenarioControl.Value);
        input = scenarioFcn(scenarioName, ...
            writerPrepareControl.Value, recordWordsControl.Value, ...
            readerReleaseControl.Value, readerProcessControl.Value, ...
            horizonControl.Value);
        if strcmp(scenarioName, 'baseline')
            input.protection = ...
                protectionFromLabel(protectionControl.Value);
            input.wait_timeout_ms = ...
                timeoutFromControl(waitTimeoutControl.Value);
            input.timeout_action = ...
                timeoutActionFromLabel(timeoutActionControl.Value);
        end
        out = modelFcn(input.writer_prepare_ms, input.record_words, ...
            input.reader_release_ms, input.reader_process_ms, ...
            input.protection, input.tick_ms, input.horizon_ms, ...
            input.wait_timeout_ms, input.timeout_action);

        cla(ownershipAxes);
        stairs(ownershipAxes, out.timeline.time_edges_ms, ...
            [out.timeline.cpu_owner_task_id ...
            out.timeline.cpu_owner_task_id(end)], ...
            'LineWidth', 1.4);
        hold(ownershipAxes, 'on');
        stairs(ownershipAxes, out.timeline.time_edges_ms, ...
            [out.timeline.mutex_owner_task_id ...
            out.timeline.mutex_owner_task_id(end)], '--', ...
            'LineWidth', 1.3);
        hold(ownershipAxes, 'off');
        grid(ownershipAxes, 'on');
        xlabel(ownershipAxes, 'Time (ms)');
        ylabel(ownershipAxes, 'Owner (task ID)');
        yticks(ownershipAxes, 0:2);
        yticklabels(ownershipAxes, {'Idle/free', 'Writer', 'Reader'});
        ylim(ownershipAxes, [-0.25 2.25]);
        legend(ownershipAxes, {'CPU owner', 'Mutex owner'}, ...
            'Location', 'eastoutside');
        title(ownershipAxes, sprintf([ ...
            'CPU and mutex ownership; scope=%s'], ...
            out.policy.protection));

        cla(recordAxes);
        yyaxis(recordAxes, 'left');
        stairs(recordAxes, out.timeline.time_edges_ms, ...
            out.timeline.writer_committed_word_count, ...
            'LineWidth', 1.4);
        hold(recordAxes, 'on');
        stairs(recordAxes, out.timeline.time_edges_ms, ...
            out.timeline.reader_copied_word_count, '--', ...
            'LineWidth', 1.4);
        hold(recordAxes, 'off');
        ylabel(recordAxes, 'Completed words (count)');
        yyaxis(recordAxes, 'right');
        stairs(recordAxes, out.timeline.time_edges_ms, ...
            [double(out.timeline.reader_blocked) ...
            double(out.timeline.reader_blocked(end))], ':', ...
            'LineWidth', 1.5);
        ylabel(recordAxes, 'Reader blocked (logical)');
        yticks(recordAxes, [0 1]);
        yticklabels(recordAxes, {'No', 'Yes'});
        ylim(recordAxes, [-0.1 1.1]);
        grid(recordAxes, 'on');
        xlabel(recordAxes, 'Time (ms)');
        title(recordAxes, ...
            'Writer commit, reader copy, and blocking progress');
        legend(recordAxes, {'Writer committed', 'Reader copied', ...
            'Reader blocked'}, 'Location', 'eastoutside');

        summary.Text = sprintf([ ...
            'Prepare %.0f ms; record %.0f words; reader release %.0f ms; ' ...
            'local processing %.0f ms. Reader wait %.1f ms = commit ' ...
            '%.1f + scope excess %.1f ms; response %.1f ms; observed ' ...
            'generation %.0f, coherent=%d, stale=%d, torn=%d; timeout=%d, ' ...
            'cancelled=%d. Writer completes %.1f ms; served %.1f, ' ...
            'cancelled %.1f, remaining %.1f ms. Generation tags are a ' ...
            'synthetic oracle, not MATLAB-runtime, RTOS, processor, ' ...
            'memory-ordering, or hardware evidence.'], ...
            out.input.writer_prepare_ms, out.input.record_words, ...
            out.input.reader_release_ms, ...
            out.input.reader_process_ms, ...
            out.reader.blocked_time_ms, ...
            out.reader.commit_blocking_ms, ...
            out.reader.scope_excess_blocking_ms, ...
            out.reader.response_ms, out.reader.observed_version, ...
            out.reader.snapshot_consistent, ...
            out.reader.stale_but_consistent, ...
            out.reader.torn_read_detected, ...
            out.reader.wait_timed_out, ...
            out.reader.cancelled_while_waiting, ...
            out.writer.completion_ms, ...
            out.metrics.served_work_ms, ...
            out.metrics.cancelled_work_ms, ...
            out.metrics.remaining_work_ms);
    end
end

function control = integerSpinner(gridLayout, limits, value, column)
control = uispinner(gridLayout, 'Limits', limits, 'Step', 1, ...
    'Value', value, 'RoundFractionalValues', 'on');
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
    case 'Editable short-mutex baseline'
        name = 'baseline';
    case 'Coarse lock (fixed)'
        name = 'coarse-lock';
    case 'Unprotected torn read (fixed)'
        name = 'unprotected-torn';
    case 'Wait timeout continues (fixed)'
        name = 'timeout-continue';
    case 'Cancel blocked reader (fixed)'
        name = 'timeout-cancel';
    case 'Early coherent reader (fixed)'
        name = 'early-reader';
    otherwise
        error('P11:interactive:Scenario', ...
            'Unknown interactive scenario.');
end
end

function protection = protectionFromLabel(label)
if strcmp(label, 'Short mutex')
    protection = 'short-mutex';
elseif strcmp(label, 'Coarse mutex')
    protection = 'coarse-mutex';
elseif strcmp(label, 'Unprotected')
    protection = 'unprotected';
else
    error('P11:interactive:Protection', ...
        'Unknown protection scope.');
end
end

function label = protectionLabel(protection)
if strcmp(protection, 'short-mutex')
    label = 'Short mutex';
elseif strcmp(protection, 'coarse-mutex')
    label = 'Coarse mutex';
elseif strcmp(protection, 'unprotected')
    label = 'Unprotected';
else
    error('P11:interactive:Protection', ...
        'Scenario protection has no UI label.');
end
end

function value = timeoutFromControl(value)
if value == 0
    value = Inf;
end
end

function value = timeoutControlValue(timeoutMs)
if isinf(timeoutMs)
    value = 0;
else
    value = timeoutMs;
end
end

function action = timeoutActionFromLabel(label)
if strcmp(label, 'Continue waiting')
    action = 'continue-waiting';
elseif strcmp(label, 'Cancel reader')
    action = 'cancel-reader';
else
    error('P11:interactive:TimeoutAction', ...
        'Unknown timeout action.');
end
end

function label = timeoutActionLabel(action)
if strcmp(action, 'continue-waiting')
    label = 'Continue waiting';
elseif strcmp(action, 'cancel-reader')
    label = 'Cancel reader';
else
    error('P11:interactive:TimeoutAction', ...
        'Scenario timeout action has no UI label.');
end
end
