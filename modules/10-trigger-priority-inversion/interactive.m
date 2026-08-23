function interactive
%INTERACTIVE Explore P10 mutex ownership, inversion, and inheritance.

% launch_lesson removes this folder after the function returns. Bind P10's
% generic model and unique fixture helper now so retained callbacks cannot
% resolve another module's model.m after a later module switch.
modelFcn = @model;
scenarioFcn = @p10_scenario;

fig = uifigure('Name', 'P10 Trigger Priority Inversion', ...
    'Position', [20 30 1740 860]);
gridLayout = uigridlayout(fig, [5 8]);
gridLayout.RowHeight = {'1x', '1x', 130, 22, 40};
gridLayout.ColumnWidth = {'1x', '1x', '1x', '1x', ...
    '1.2x', '1.2x', '1.35x', '1.6x'};

ownershipAxes = uiaxes(gridLayout);
ownershipAxes.Layout.Row = 1;
ownershipAxes.Layout.Column = [1 8];
priorityAxes = uiaxes(gridLayout);
priorityAxes.Layout.Row = 2;
priorityAxes.Layout.Column = [1 8];
summary = uilabel(gridLayout, 'WordWrap', 'on');
summary.Layout.Row = 3;
summary.Layout.Column = [1 8];

makeLabel(gridLayout, 'Medium work (ms)', 1);
makeLabel(gridLayout, 'Low mutex work (ms)', 2);
makeLabel(gridLayout, 'High deadline (ms)', 3);
makeLabel(gridLayout, 'Horizon (ms)', 4);
makeLabel(gridLayout, 'Mutex protocol', 5);
makeLabel(gridLayout, 'High wait timeout (ms; 0=off)', 6);
makeLabel(gridLayout, 'Timeout action', 7);
makeLabel(gridLayout, 'Scenario', 8);

mediumWorkControl = integerSpinner(gridLayout, [0 15], 5, 1);
lowCriticalControl = integerSpinner(gridLayout, [1 6], 4, 2);
highDeadlineControl = integerSpinner(gridLayout, [1 20], 6, 3);
horizonControl = integerSpinner(gridLayout, [1 100], 16, 4);
protocolControl = uidropdown(gridLayout, ...
    'Items', {'Priority inheritance', 'Plain mutex'}, ...
    'Value', 'Priority inheritance');
protocolControl.Layout.Row = 5;
protocolControl.Layout.Column = 5;
waitTimeoutControl = integerSpinner(gridLayout, [0 20], 0, 6);
timeoutActionControl = uidropdown(gridLayout, ...
    'Items', {'Continue waiting', 'Cancel waiter'}, ...
    'Value', 'Continue waiting');
timeoutActionControl.Layout.Row = 5;
timeoutActionControl.Layout.Column = 7;
scenarioControl = uidropdown(gridLayout, ...
    'Items', {'Editable protected baseline', ...
    'Plain mutex inversion (fixed)', ...
    'Wait timeout continues (fixed)', ...
    'Cancel blocked waiter (fixed)', ...
    'High acquires first (fixed)'}, ...
    'Value', 'Editable protected baseline');
scenarioControl.Layout.Row = 5;
scenarioControl.Layout.Column = 8;

controls = {mediumWorkControl, lowCriticalControl, ...
    highDeadlineControl, horizonControl, protocolControl, ...
    waitTimeoutControl, timeoutActionControl};
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
        fixedInput = scenarioFcn(scenarioName, 5, 4, 16);
        mediumWorkControl.Value = fixedInput.pre_critical_ms(2);
        lowCriticalControl.Value = fixedInput.critical_ms(1);
        highDeadlineControl.Value = fixedInput.relative_deadline_ms(3);
        horizonControl.Value = fixedInput.horizon_ms;
        protocolControl.Value = protocolLabel(fixedInput.protocol);
        waitTimeoutControl.Value = ...
            timeoutControlValue(fixedInput.wait_timeout_ms(3));
        timeoutActionControl.Value = ...
            timeoutActionLabel(fixedInput.timeout_action);
        if ~strcmp(scenarioControl.Value, ...
                'Editable protected baseline')
            for controlIndex = 1:numel(controls)
                controls{controlIndex}.Enable = 'off';
            end
        end
        updateViews();
    end

    function updateViews
        scenarioName = mapScenarioName(scenarioControl.Value);
        input = scenarioFcn(scenarioName, mediumWorkControl.Value, ...
            lowCriticalControl.Value, horizonControl.Value);
        if strcmp(scenarioName, 'baseline')
            input.relative_deadline_ms(3) = highDeadlineControl.Value;
            input.protocol = protocolFromLabel(protocolControl.Value);
            input.wait_timeout_ms(3) = ...
                timeoutFromControl(waitTimeoutControl.Value);
            input.timeout_action = ...
                timeoutActionFromLabel(timeoutActionControl.Value);
        end
        out = modelFcn(input.release_ms, input.pre_critical_ms, ...
            input.critical_ms, input.post_critical_ms, ...
            input.relative_deadline_ms, input.base_priority, ...
            input.protocol, input.tick_ms, input.horizon_ms, ...
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
        yticks(ownershipAxes, 0:3);
        yticklabels(ownershipAxes, ...
            {'Idle/free', 'Low', 'Medium', 'High'});
        ylim(ownershipAxes, [-0.25 3.25]);
        legend(ownershipAxes, {'CPU owner', 'Mutex owner'}, ...
            'Location', 'eastoutside');
        title(ownershipAxes, sprintf([ ...
            'CPU and mutex ownership; protocol=%s'], ...
            out.policy.mutex_protocol));

        cla(priorityAxes);
        yyaxis(priorityAxes, 'left');
        stairs(priorityAxes, out.timeline.time_edges_ms, ...
            [out.timeline.effective_priority_by_task(1, :) ...
            out.timeline.effective_priority_by_task(1, end)], ...
            'LineWidth', 1.4);
        ylabel(priorityAxes, 'Low effective priority (integer)');
        ylim(priorityAxes, [0.5 3.5]);
        yyaxis(priorityAxes, 'right');
        stairs(priorityAxes, out.timeline.time_edges_ms, ...
            [double(out.timeline.blocked_by_task(3, :)) ...
            double(out.timeline.blocked_by_task(3, end))], ...
            'LineWidth', 1.4);
        ylabel(priorityAxes, 'High blocked (logical)');
        yticks(priorityAxes, [0 1]);
        yticklabels(priorityAxes, {'No', 'Yes'});
        ylim(priorityAxes, [-0.1 1.1]);
        grid(priorityAxes, 'on');
        xlabel(priorityAxes, 'Time (ms)');
        title(priorityAxes, ...
            'Donation and blocking share a boundary but remain distinct states');

        summary.Text = sprintf([ ...
            'Release [%.0f %.0f %.0f] ms; work [%.0f %.0f %.0f] ms; ' ...
            'base priority [%d %d %d]. High response %.1f ms, mutex wait ' ...
            '%.1f ms = direct %.1f + third-party %.1f ms; deadline %.1f ' ...
            'ms, missed=%d, wait timeout=%d, waiter cancelled=%d. Low ' ...
            'boost %.1f ms and releases mutex at %.1f ms. Served %.1f, ' ...
            'cancelled %.1f, remaining %.1f ms. Synthetic one-mutex ' ...
            'calculation; not an RTOS, processor, MATLAB-runtime, or ' ...
            'hardware timing measurement.'], ...
            out.input.release_ms, out.input.total_execution_ms, ...
            out.input.base_priority, out.tasks.response_ms(3), ...
            out.tasks.blocked_time_ms(3), ...
            out.tasks.direct_blocking_ms(3), ...
            out.tasks.third_party_interference_ms(3), ...
            out.input.relative_deadline_ms(3), ...
            out.tasks.deadline_missed(3), ...
            out.tasks.wait_timed_out(3), ...
            out.tasks.cancelled_while_waiting(3), ...
            out.tasks.boost_time_ms(1), ...
            out.tasks.resource_release_ms(1), ...
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
    case 'Editable protected baseline'
        name = 'baseline';
    case 'Plain mutex inversion (fixed)'
        name = 'plain-mutex';
    case 'Wait timeout continues (fixed)'
        name = 'wait-continue';
    case 'Cancel blocked waiter (fixed)'
        name = 'wait-cancel';
    case 'High acquires first (fixed)'
        name = 'high-first';
    otherwise
        error('P10:interactive:Scenario', ...
            'Unknown interactive scenario.');
end
end

function protocol = protocolFromLabel(label)
if strcmp(label, 'Priority inheritance')
    protocol = 'priority-inheritance';
elseif strcmp(label, 'Plain mutex')
    protocol = 'none';
else
    error('P10:interactive:Protocol', 'Unknown mutex protocol.');
end
end

function label = protocolLabel(protocol)
if strcmp(protocol, 'priority-inheritance')
    label = 'Priority inheritance';
elseif strcmp(protocol, 'none')
    label = 'Plain mutex';
else
    error('P10:interactive:Protocol', ...
        'Scenario mutex protocol has no UI label.');
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
elseif strcmp(label, 'Cancel waiter')
    action = 'cancel-waiter';
else
    error('P10:interactive:TimeoutAction', ...
        'Unknown timeout action.');
end
end

function label = timeoutActionLabel(action)
if strcmp(action, 'continue-waiting')
    label = 'Continue waiting';
elseif strcmp(action, 'cancel-waiter')
    label = 'Cancel waiter';
else
    error('P10:interactive:TimeoutAction', ...
        'Scenario timeout action has no UI label.');
end
end
