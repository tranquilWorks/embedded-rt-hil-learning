function out = model(periodMs, executionMs, relativeDeadlineMs, ...
    priority, phaseMs, tickMs, horizonMs, deadlineAction)
%MODEL Simulate bounded fixed-priority preemptive dispatch on one CPU.
%   Jobs release on a declared time grid. The ready job with the largest
%   numeric priority runs for one tick; equal priorities use earliest
%   release, then task ID, then job sequence. Completion at an absolute
%   deadline is on time. An incomplete job is marked missed at its deadline
%   and either continues late or is cancelled by the declared analytical
%   policy. Dispatch and context-switch overhead are zero.

if nargin < 7 || nargin > 8
    error('P09:model:Arity', ...
        ['Expected period, execution, relative deadline, priority, phase, ' ...
        'tick, horizon, and an optional deadline action.']);
end
if nargin < 8 || isempty(deadlineAction)
    deadlineAction = 'continue-late';
end

maxTasks = 16;
maxTicks = 100000;
maxJobs = 10000;
maxInputTicks = 1e9;

periodMs = validateNumericVector(periodMs, 'P09:model:Period', 'periodMs');
taskCount = numel(periodMs);
if taskCount > maxTasks
    error('P09:model:ResourceBound', ...
        'At most sixteen periodic tasks are allowed.');
end
executionMs = validateNumericVector(executionMs, ...
    'P09:model:Execution', 'executionMs');
relativeDeadlineMs = validateNumericVector(relativeDeadlineMs, ...
    'P09:model:Deadline', 'relativeDeadlineMs');
priority = validateNumericVector(priority, ...
    'P09:model:Priority', 'priority');
phaseMs = validateNumericVector(phaseMs, ...
    'P09:model:Phase', 'phaseMs');
if any([numel(executionMs), numel(relativeDeadlineMs), ...
        numel(priority), numel(phaseMs)] ~= taskCount)
    error('P09:model:VectorLength', ...
        'Every task vector must contain the same number of elements.');
end
if any(periodMs <= 0)
    error('P09:model:Period', 'Every period must be positive.');
end
if any(executionMs < 0)
    error('P09:model:Execution', ...
        'Every execution time must be nonnegative.');
end
if any(relativeDeadlineMs <= 0)
    error('P09:model:Deadline', ...
        'Every relative deadline must be positive.');
end
if any(priority ~= round(priority)) || any(abs(priority) > 1e6)
    error('P09:model:Priority', ...
        'Priorities must be integer values with magnitude at most 1e6.');
end
if any(phaseMs < 0)
    error('P09:model:Phase', 'Every release phase must be nonnegative.');
end
tickMs = validatePositiveScalar(tickMs, ...
    'P09:model:Tick', 'tickMs');
horizonMs = validatePositiveScalar(horizonMs, ...
    'P09:model:Horizon', 'horizonMs');
deadlineAction = validateDeadlineAction(deadlineAction);

scaledHorizon = horizonMs ./ tickMs;
if ~isfinite(scaledHorizon) || scaledHorizon > maxTicks
    error('P09:model:TimingResourceBound', ...
        'The observation horizon may contain at most 100000 ticks.');
end
allScaledTimes = [periodMs, executionMs, relativeDeadlineMs, ...
    phaseMs, horizonMs] ./ tickMs;
nearestTicks = round(allScaledTimes);
alignmentTolerance = 32 .* eps(max(abs(allScaledTimes), 1));
positiveCollapsedToZero = allScaledTimes > 0 & nearestTicks == 0;
if any(~isfinite(allScaledTimes)) || ...
        any(abs(allScaledTimes - nearestTicks) > alignmentTolerance) || ...
        any(positiveCollapsedToZero)
    error('P09:model:GridAlignment', ...
        ['Every task time and the horizon must align to tickMs; a ' ...
        'positive time cannot collapse to zero ticks.']);
end
if any(allScaledTimes > maxInputTicks)
    error('P09:model:TimingResourceBound', ...
        'Each declared task time may span at most 1e9 ticks.');
end

periodTicks = round(periodMs ./ tickMs);
executionTicks = round(executionMs ./ tickMs);
deadlineTicks = round(relativeDeadlineMs ./ tickMs);
phaseTicks = round(phaseMs ./ tickMs);
horizonTicks = round(scaledHorizon);
if horizonTicks < 1
    error('P09:model:Horizon', ...
        'The horizon must contain at least one scheduler tick.');
end

releaseCountByTask = zeros(1, taskCount);
for taskId = 1:taskCount
    if phaseTicks(taskId) < horizonTicks
        releaseCountByTask(taskId) = floor( ...
            (horizonTicks - 1 - phaseTicks(taskId)) ./ ...
            periodTicks(taskId)) + 1;
    end
end
totalJobCount = sum(releaseCountByTask);
if totalJobCount > maxJobs
    error('P09:model:JobResourceBound', ...
        'The bounded horizon may release at most 10000 jobs.');
end

ownerTask = zeros(1, horizonTicks);
ownerJob = zeros(1, horizonTicks);
readyJobDepth = zeros(1, horizonTicks);
readyTaskDepth = zeros(1, horizonTicks);
selectedPriority = NaN(1, horizonTicks);
deadlineBuckets = cell(1, horizonTicks + 1);
readyQueues = cell(1, taskCount);
queueHead = ones(1, taskCount);
taskSequence = zeros(1, taskCount);

jobTask = zeros(1, totalJobCount);
jobSequence = zeros(1, totalJobCount);
jobReleaseTick = zeros(1, totalJobCount);
jobDeadlineTick = zeros(1, totalJobCount);
jobExecutionTicks = zeros(1, totalJobCount);
jobRemainingTicks = zeros(1, totalJobCount);
jobServiceTicks = zeros(1, totalJobCount);
jobCancelledWorkTicks = zeros(1, totalJobCount);
jobStartTick = NaN(1, totalJobCount);
jobCompletionTick = NaN(1, totalJobCount);
jobMissTick = NaN(1, totalJobCount);
jobCancellationTick = NaN(1, totalJobCount);
jobDeadlineMissed = false(1, totalJobCount);
jobCancelled = false(1, totalJobCount);
jobDispatchCount = zeros(1, totalJobCount);
jobPreemptionCount = zeros(1, totalJobCount);

jobCount = 0;
readyJobCount = 0;
lastOwnerJob = 0;

% Boundaries are processed in this order: prior completion, deadline
% expiration, release, then dispatch for [boundary, boundary + one tick).
% The final boundary is visited for deadline accounting but has no release.
for boundaryTick = 0:horizonTicks
    dueJobs = deadlineBuckets{boundaryTick + 1};
    for dueIndex = 1:numel(dueJobs)
        dueJob = dueJobs(dueIndex);
        unfinished = isnan(jobCompletionTick(dueJob)) && ...
            ~jobCancelled(dueJob) && jobRemainingTicks(dueJob) > 0;
        if unfinished
            jobDeadlineMissed(dueJob) = true;
            jobMissTick(dueJob) = boundaryTick;
            if strcmp(deadlineAction, 'cancel-at-deadline')
                jobCancelled(dueJob) = true;
                jobCancellationTick(dueJob) = boundaryTick;
                jobCancelledWorkTicks(dueJob) = ...
                    jobRemainingTicks(dueJob);
                jobRemainingTicks(dueJob) = 0;
                readyJobCount = readyJobCount - 1;
            end
        end
    end

    if boundaryTick == horizonTicks
        break;
    end

    for taskId = 1:taskCount
        releasesNow = boundaryTick >= phaseTicks(taskId) && ...
            mod(boundaryTick - phaseTicks(taskId), ...
            periodTicks(taskId)) == 0;
        if releasesNow
            jobCount = jobCount + 1;
            taskSequence(taskId) = taskSequence(taskId) + 1;
            jobTask(jobCount) = taskId;
            jobSequence(jobCount) = taskSequence(taskId);
            jobReleaseTick(jobCount) = boundaryTick;
            jobDeadlineTick(jobCount) = boundaryTick + ...
                deadlineTicks(taskId);
            jobExecutionTicks(jobCount) = executionTicks(taskId);
            jobRemainingTicks(jobCount) = executionTicks(taskId);
            if jobDeadlineTick(jobCount) <= horizonTicks
                deadlineBucketIndex = jobDeadlineTick(jobCount) + 1;
                deadlineBuckets{deadlineBucketIndex}(end + 1) = jobCount;
            end
            if executionTicks(taskId) == 0
                jobStartTick(jobCount) = boundaryTick;
                jobCompletionTick(jobCount) = boundaryTick;
            else
                readyQueues{taskId}(end + 1) = jobCount;
                readyJobCount = readyJobCount + 1;
            end
        end
    end

    candidateJob = zeros(1, taskCount);
    for taskId = 1:taskCount
        queue = readyQueues{taskId};
        head = queueHead(taskId);
        for boundedSkip = 1:numel(queue)
            if head > numel(queue)
                break;
            end
            queuedJob = queue(head);
            terminal = jobCancelled(queuedJob) || ...
                ~isnan(jobCompletionTick(queuedJob)) || ...
                jobRemainingTicks(queuedJob) == 0;
            if ~terminal
                break;
            end
            head = head + 1;
        end
        queueHead(taskId) = head;
        if head <= numel(queue)
            candidateJob(taskId) = queue(head);
        end
    end

    selectedJob = 0;
    selectedTask = 0;
    for taskId = 1:taskCount
        proposedJob = candidateJob(taskId);
        if proposedJob == 0
            continue;
        end
        if selectedJob == 0
            chooseProposed = true;
        else
            chooseProposed = priority(taskId) > priority(selectedTask) || ...
                (priority(taskId) == priority(selectedTask) && ...
                (jobReleaseTick(proposedJob) < ...
                jobReleaseTick(selectedJob) || ...
                (jobReleaseTick(proposedJob) == ...
                jobReleaseTick(selectedJob) && ...
                (taskId < selectedTask || ...
                (taskId == selectedTask && ...
                jobSequence(proposedJob) < ...
                jobSequence(selectedJob))))));
        end
        if chooseProposed
            selectedJob = proposedJob;
            selectedTask = taskId;
        end
    end

    slotIndex = boundaryTick + 1;
    readyJobDepth(slotIndex) = readyJobCount;
    readyTaskDepth(slotIndex) = sum(candidateJob > 0);
    if selectedJob > 0
        selectedPriority(slotIndex) = priority(selectedTask);
    end
    if lastOwnerJob > 0 && selectedJob ~= lastOwnerJob && ...
            jobRemainingTicks(lastOwnerJob) > 0 && ...
            ~jobCancelled(lastOwnerJob)
        lastTask = jobTask(lastOwnerJob);
        if selectedJob == 0 || priority(selectedTask) <= priority(lastTask)
            error('P09:model:InternalDispatch', ...
                'Only a strictly higher-priority ready job may preempt.');
        end
        jobPreemptionCount(lastOwnerJob) = ...
            jobPreemptionCount(lastOwnerJob) + 1;
    end

    ownerTask(slotIndex) = selectedTask;
    ownerJob(slotIndex) = selectedJob;
    if selectedJob > 0
        if selectedJob ~= lastOwnerJob
            jobDispatchCount(selectedJob) = ...
                jobDispatchCount(selectedJob) + 1;
        end
        if isnan(jobStartTick(selectedJob))
            jobStartTick(selectedJob) = boundaryTick;
        end
        jobRemainingTicks(selectedJob) = ...
            jobRemainingTicks(selectedJob) - 1;
        jobServiceTicks(selectedJob) = jobServiceTicks(selectedJob) + 1;
        if jobRemainingTicks(selectedJob) == 0
            jobCompletionTick(selectedJob) = boundaryTick + 1;
            readyJobCount = readyJobCount - 1;
        end
    end
    lastOwnerJob = selectedJob;
end

if jobCount ~= totalJobCount || readyJobCount < 0
    error('P09:model:InternalAccounting', ...
        'Bounded scheduler accounting did not conserve jobs.');
end

jobCompleted = ~isnan(jobCompletionTick);
jobUnfinished = ~jobCompleted & ~jobCancelled;
jobResponseTicks = NaN(1, totalJobCount);
jobResponseTicks(jobCompleted) = ...
    jobCompletionTick(jobCompleted) - jobReleaseTick(jobCompleted);
completionCountByTask = zeros(1, taskCount);
missCountByTask = zeros(1, taskCount);
cancelCountByTask = zeros(1, taskCount);
unfinishedCountByTask = zeros(1, taskCount);
serviceTicksByTask = zeros(1, taskCount);
worstResponseTicksByTask = NaN(1, taskCount);
for taskId = 1:taskCount
    taskMask = jobTask == taskId;
    completedMask = taskMask & jobCompleted;
    completionCountByTask(taskId) = sum(completedMask);
    missCountByTask(taskId) = sum(taskMask & jobDeadlineMissed);
    cancelCountByTask(taskId) = sum(taskMask & jobCancelled);
    unfinishedCountByTask(taskId) = sum(taskMask & jobUnfinished);
    serviceTicksByTask(taskId) = sum(jobServiceTicks(taskMask));
    completedResponses = jobResponseTicks(completedMask);
    if ~isempty(completedResponses)
        worstResponseTicksByTask(taskId) = max(completedResponses);
    end
end

busyTicks = sum(ownerTask > 0);
idleTicks = horizonTicks - busyTicks;
releasedDemandTicks = sum(jobExecutionTicks);
servedTicks = sum(jobServiceTicks);
cancelledTicks = sum(jobCancelledWorkTicks);
remainingTicks = sum(jobRemainingTicks);

out = struct();
out.input = struct( ...
    'period_ms', periodTicks .* tickMs, ...
    'execution_ms', executionTicks .* tickMs, ...
    'relative_deadline_ms', deadlineTicks .* tickMs, ...
    'priority', priority, ...
    'phase_ms', phaseTicks .* tickMs, ...
    'tick_ms', tickMs, ...
    'horizon_ms', horizonTicks .* tickMs);
out.policy = struct( ...
    'scheduler', 'fixed-priority-preemptive-single-core', ...
    'larger_priority_runs_first', true, ...
    'tie_break', ['earliest release, then task ID, then job sequence/' ...
    'FIFO'], ...
    'deadline_action', deadlineAction, ...
    'dispatch_overhead_ms', 0, ...
    'context_switch_overhead_ms', 0, ...
    'release_at_horizon_included', false);
out.schedule = struct( ...
    'time_ms', (0:(horizonTicks - 1)) .* tickMs, ...
    'time_edges_ms', (0:horizonTicks) .* tickMs, ...
    'owner_task_id', ownerTask, ...
    'owner_job_id', ownerJob, ...
    'ready_job_count', readyJobDepth, ...
    'ready_task_count', readyTaskDepth, ...
    'selected_priority', selectedPriority);
out.jobs = struct( ...
    'id', 1:totalJobCount, ...
    'task_id', jobTask, ...
    'sequence', jobSequence, ...
    'release_ms', jobReleaseTick .* tickMs, ...
    'absolute_deadline_ms', jobDeadlineTick .* tickMs, ...
    'execution_ms', jobExecutionTicks .* tickMs, ...
    'start_ms', jobStartTick .* tickMs, ...
    'completion_ms', jobCompletionTick .* tickMs, ...
    'response_ms', jobResponseTicks .* tickMs, ...
    'service_ms', jobServiceTicks .* tickMs, ...
    'remaining_ms', jobRemainingTicks .* tickMs, ...
    'cancelled_work_ms', jobCancelledWorkTicks .* tickMs, ...
    'miss_time_ms', jobMissTick .* tickMs, ...
    'cancellation_time_ms', jobCancellationTick .* tickMs, ...
    'completed', jobCompleted, ...
    'deadline_missed', jobDeadlineMissed, ...
    'cancelled_at_deadline', jobCancelled, ...
    'unfinished_at_horizon', jobUnfinished, ...
    'dispatch_count', jobDispatchCount, ...
    'preemption_count', jobPreemptionCount);
out.metrics = struct( ...
    'nominal_utilization', sum(executionTicks ./ periodTicks), ...
    'release_count_by_task', releaseCountByTask, ...
    'completion_count_by_task', completionCountByTask, ...
    'deadline_miss_count_by_task', missCountByTask, ...
    'deadline_cancel_count_by_task', cancelCountByTask, ...
    'unfinished_count_by_task', unfinishedCountByTask, ...
    'service_time_ms_by_task', serviceTicksByTask .* tickMs, ...
    'worst_response_ms_by_task', worstResponseTicksByTask .* tickMs, ...
    'preemption_count', sum(jobPreemptionCount), ...
    'busy_time_ms', busyTicks .* tickMs, ...
    'idle_time_ms', idleTicks .* tickMs, ...
    'busy_fraction', busyTicks ./ horizonTicks, ...
    'idle_fraction', idleTicks ./ horizonTicks, ...
    'max_ready_jobs', max([0 readyJobDepth]), ...
    'released_demand_ms', releasedDemandTicks .* tickMs, ...
    'served_work_ms', servedTicks .* tickMs, ...
    'cancelled_work_ms', cancelledTicks .* tickMs, ...
    'remaining_work_ms', remainingTicks .* tickMs, ...
    'demand_conservation_error_ms', ...
    (releasedDemandTicks - servedTicks - cancelledTicks - ...
    remainingTicks) .* tickMs);
out.claim_boundary = [ ...
    'Deterministic discrete-time fixed-priority preemptive scheduler ' ...
    'calculation; not a MATLAB-runtime, RTOS, processor, or hardware ' ...
    'timing measurement.'];
end

function value = validateNumericVector(value, identifier, label)
valid = isnumeric(value) && ~islogical(value) && isreal(value) && ...
    isvector(value) && ~isempty(value) && all(isfinite(value(:)));
if ~valid
    error(identifier, ...
        '%s must be a nonempty finite real numeric vector.', label);
end
value = double(value(:).');
end

function value = validatePositiveScalar(value, identifier, label)
valid = isnumeric(value) && ~islogical(value) && isreal(value) && ...
    isscalar(value) && isfinite(value) && value > 0;
if ~valid
    error(identifier, '%s must be a positive finite real numeric scalar.', ...
        label);
end
value = double(value);
end

function deadlineAction = validateDeadlineAction(deadlineAction)
if ~(ischar(deadlineAction) || ...
        (isstring(deadlineAction) && isscalar(deadlineAction)))
    error('P09:model:DeadlineAction', ...
        'deadlineAction must be a character vector or scalar string.');
end
deadlineAction = lower(strtrim(char(deadlineAction)));
if ~any(strcmp(deadlineAction, ...
        {'continue-late', 'cancel-at-deadline'}))
    error('P09:model:DeadlineAction', ...
        ['deadlineAction must be continue-late or ' ...
        'cancel-at-deadline.']);
end
end
