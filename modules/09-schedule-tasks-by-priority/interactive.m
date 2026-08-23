function interactive
%INTERACTIVE Explore P09 priorities, execution demand, and deadlines.

% launch_lesson removes this folder after the function returns. Bind P09's
% generic model and unique fixture helper now so retained callbacks cannot
% resolve P01 or another module's model.m after a later module switch.
modelFcn = @model;
scenarioFcn = @p09_scenario;

fig = uifigure('Name', 'P09 Schedule Tasks by Priority', ...
    'Position', [20 30 1740 860]);
gridLayout = uigridlayout(fig, [5 10]);
gridLayout.RowHeight = {'1x', '1x', 130, 22, 40};
gridLayout.ColumnWidth = {'1x', '1x', '1x', '1x', '1x', ...
    '1x', '1x', '1.35x', '1.35x', '1.45x'};

scheduleAxes = uiaxes(gridLayout);
scheduleAxes.Layout.Row = 1;
scheduleAxes.Layout.Column = [1 10];
responseAxes = uiaxes(gridLayout);
responseAxes.Layout.Row = 2;
responseAxes.Layout.Column = [1 10];
summary = uilabel(gridLayout, 'WordWrap', 'on');
summary.Layout.Row = 3;
summary.Layout.Column = [1 10];

makeLabel(gridLayout, 'Control WCET (ms)', 1);
makeLabel(gridLayout, 'Telemetry WCET (ms)', 2);
makeLabel(gridLayout, 'Logger WCET (ms)', 3);
makeLabel(gridLayout, 'Control deadline (ms)', 4);
makeLabel(gridLayout, 'Telemetry deadline (ms)', 5);
makeLabel(gridLayout, 'Logger deadline (ms)', 6);
makeLabel(gridLayout, 'Horizon (ms)', 7);
makeLabel(gridLayout, 'Priority order', 8);
makeLabel(gridLayout, 'Deadline action', 9);
makeLabel(gridLayout, 'Scenario', 10);

controlExecution = integerSpinner(gridLayout, [0 20], 1, 1);
telemetryExecution = integerSpinner(gridLayout, [0 30], 2, 2);
loggerExecution = integerSpinner(gridLayout, [0 40], 5, 3);
controlDeadline = integerSpinner(gridLayout, [1 40], 5, 4);
telemetryDeadline = integerSpinner(gridLayout, [1 80], 10, 5);
loggerDeadline = integerSpinner(gridLayout, [1 120], 20, 6);
horizonControl = integerSpinner(gridLayout, [1 500], 40, 7);
priorityControl = uidropdown(gridLayout, ...
    'Items', {'Control > Telemetry > Logger', ...
    'Telemetry > Control > Logger', ...
    'Control > Logger > Telemetry', ...
    'Logger > Control > Telemetry'}, ...
    'Value', 'Control > Telemetry > Logger');
priorityControl.Layout.Row = 5;
priorityControl.Layout.Column = 8;
deadlineActionControl = uidropdown(gridLayout, ...
    'Items', {'Continue late', 'Cancel at deadline'}, ...
    'Value', 'Continue late');
deadlineActionControl.Layout.Row = 5;
deadlineActionControl.Layout.Column = 9;
scenarioControl = uidropdown(gridLayout, ...
    'Items', {'Editable baseline', 'Bad priority map (fixed)', ...
    'Deadline cancellation (fixed)', 'Heavy logger (fixed)'}, ...
    'Value', 'Editable baseline');
scenarioControl.Layout.Row = 5;
scenarioControl.Layout.Column = 10;

controls = {controlExecution, telemetryExecution, loggerExecution, ...
    controlDeadline, telemetryDeadline, loggerDeadline, horizonControl, ...
    priorityControl, deadlineActionControl};
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
        fixedInput = scenarioFcn(scenarioName, 40);
        controlExecution.Value = fixedInput.execution_ms(1);
        telemetryExecution.Value = fixedInput.execution_ms(2);
        loggerExecution.Value = fixedInput.execution_ms(3);
        controlDeadline.Value = fixedInput.relative_deadline_ms(1);
        telemetryDeadline.Value = fixedInput.relative_deadline_ms(2);
        loggerDeadline.Value = fixedInput.relative_deadline_ms(3);
        horizonControl.Value = fixedInput.horizon_ms;
        priorityControl.Value = priorityLabel(fixedInput.priority);
        deadlineActionControl.Value = ...
            deadlineActionLabel(fixedInput.deadline_action);
        if ~strcmp(scenarioControl.Value, 'Editable baseline')
            for controlIndex = 1:numel(controls)
                controls{controlIndex}.Enable = 'off';
            end
        end
        updateViews();
    end

    function updateViews
        scenarioName = mapScenarioName(scenarioControl.Value);
        input = scenarioFcn(scenarioName, horizonControl.Value);
        if strcmp(scenarioName, 'baseline')
            input.execution_ms = [controlExecution.Value ...
                telemetryExecution.Value loggerExecution.Value];
            input.relative_deadline_ms = [controlDeadline.Value ...
                telemetryDeadline.Value loggerDeadline.Value];
            input.priority = priorityFromLabel(priorityControl.Value);
            input.horizon_ms = horizonControl.Value;
            input.deadline_action = ...
                deadlineActionFromLabel(deadlineActionControl.Value);
        end
        out = modelFcn(input.period_ms, input.execution_ms, ...
            input.relative_deadline_ms, input.priority, input.phase_ms, ...
            input.tick_ms, input.horizon_ms, input.deadline_action);

        cla(scheduleAxes);
        stairs(scheduleAxes, out.schedule.time_edges_ms, ...
            [out.schedule.owner_task_id out.schedule.owner_task_id(end)], ...
            'LineWidth', 1.4);
        grid(scheduleAxes, 'on');
        xlabel(scheduleAxes, 'Time (ms)');
        ylabel(scheduleAxes, 'Processor owner (task ID)');
        yticks(scheduleAxes, 0:3);
        yticklabels(scheduleAxes, ...
            {'Idle', 'Control', 'Telemetry', 'Logger'});
        ylim(scheduleAxes, [-0.25 3.25]);
        title(scheduleAxes, sprintf([ ...
            'Priority [%d %d %d], U=%.2f, preemptions=%d'], ...
            out.input.priority, out.metrics.nominal_utilization, ...
            out.metrics.preemption_count));

        cla(responseAxes);
        jobDeadlineMs = out.input.relative_deadline_ms(out.jobs.task_id);
        bar(responseAxes, out.jobs.id, out.jobs.response_ms, 0.72, ...
            'FaceColor', [0.25 0.55 0.85]);
        hold(responseAxes, 'on');
        plot(responseAxes, out.jobs.id, jobDeadlineMs, 'k.', ...
            'MarkerSize', 10);
        missedJobs = find(out.jobs.deadline_missed);
        if ~isempty(missedJobs)
            plot(responseAxes, missedJobs, jobDeadlineMs(missedJobs), ...
                'rx', 'MarkerSize', 9, 'LineWidth', 1.5);
        end
        hold(responseAxes, 'off');
        grid(responseAxes, 'on');
        xlabel(responseAxes, 'Released job ID (count)');
        ylabel(responseAxes, 'Response time and relative deadline (ms)');
        title(responseAxes, ...
            'Completed response bars; dots are deadlines and red x marks timeout');

        summary.Text = sprintf([ ...
            'Periods [%g %g %g] ms, WCET [%g %g %g] ms, deadlines ' ...
            '[%g %g %g] ms, priorities [%d %d %d]. Releases [%d %d %d], ' ...
            'worst completed responses [%g %g %g] ms, misses [%d %d %d], ' ...
            'deadline cancellations [%d %d %d], unfinished [%d %d %d], ' ...
            'busy %.1f%%, idle %.1f%%. Policy: %s. Synthetic fixed-priority ' ...
            'calculation; not an RTOS, processor, MATLAB-runtime, or ' ...
            'hardware timing measurement.'], ...
            out.input.period_ms, out.input.execution_ms, ...
            out.input.relative_deadline_ms, out.input.priority, ...
            out.metrics.release_count_by_task, ...
            out.metrics.worst_response_ms_by_task, ...
            out.metrics.deadline_miss_count_by_task, ...
            out.metrics.deadline_cancel_count_by_task, ...
            out.metrics.unfinished_count_by_task, ...
            100 .* out.metrics.busy_fraction, ...
            100 .* out.metrics.idle_fraction, ...
            out.policy.deadline_action);
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
    case 'Editable baseline'
        name = 'baseline';
    case 'Bad priority map (fixed)'
        name = 'priority-misassigned';
    case 'Deadline cancellation (fixed)'
        name = 'deadline-cancel';
    case 'Heavy logger (fixed)'
        name = 'heavy-logger';
    otherwise
        error('P09:interactive:Scenario', ...
            'Unknown interactive scenario.');
end
end

function priority = priorityFromLabel(label)
switch label
    case 'Control > Telemetry > Logger'
        priority = [3 2 1];
    case 'Telemetry > Control > Logger'
        priority = [2 3 1];
    case 'Control > Logger > Telemetry'
        priority = [3 1 2];
    case 'Logger > Control > Telemetry'
        priority = [2 1 3];
    otherwise
        error('P09:interactive:Priority', ...
            'Unknown priority ordering.');
end
end

function label = priorityLabel(priority)
if isequal(priority, [3 2 1])
    label = 'Control > Telemetry > Logger';
elseif isequal(priority, [2 3 1])
    label = 'Telemetry > Control > Logger';
elseif isequal(priority, [3 1 2])
    label = 'Control > Logger > Telemetry';
elseif isequal(priority, [2 1 3])
    label = 'Logger > Control > Telemetry';
else
    error('P09:interactive:Priority', ...
        'Scenario priority vector has no UI label.');
end
end

function action = deadlineActionFromLabel(label)
if strcmp(label, 'Continue late')
    action = 'continue-late';
elseif strcmp(label, 'Cancel at deadline')
    action = 'cancel-at-deadline';
else
    error('P09:interactive:DeadlineAction', ...
        'Unknown deadline action.');
end
end

function label = deadlineActionLabel(action)
if strcmp(action, 'continue-late')
    label = 'Continue late';
elseif strcmp(action, 'cancel-at-deadline')
    label = 'Cancel at deadline';
else
    error('P09:interactive:DeadlineAction', ...
        'Scenario deadline action has no UI label.');
end
end
