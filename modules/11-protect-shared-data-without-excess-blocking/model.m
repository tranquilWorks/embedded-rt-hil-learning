function out = model(writerPrepareMs, recordWords, readerReleaseMs, ...
    readerProcessMs, protection, tickMs, horizonMs, waitTimeoutMs, ...
    timeoutAction)
%MODEL Simulate one writer and one reader sharing a versioned record.
%   The low-priority writer prepares data, then commits one word per tick.
%   The high-priority reader copies one word per tick, then processes it.
%   A short mutex protects only commit and copy; a coarse mutex also covers
%   unrelated preparation and processing; unprotected access can tear.

if nargin < 7 || nargin > 9
    error('P11:model:Arity', ...
        ['Expected writer preparation, record words, reader release, ' ...
        'reader processing, protection, tick, horizon, and optional ' ...
        'wait-timeout and timeout-action inputs.']);
end
if isempty(protection)
    protection = 'short-mutex';
end
if nargin < 8 || isempty(waitTimeoutMs)
    waitTimeoutMs = Inf;
end
if nargin < 9 || isempty(timeoutAction)
    timeoutAction = 'continue-waiting';
end

maxRecordWords = 64;
maxHorizonTicks = 100000;
maxInputTicks = 1e9;

writerPrepareMs = validateNonnegativeScalar(writerPrepareMs, ...
    'P11:model:WriterPrepare', 'writerPrepareMs');
recordWords = validateRecordWords(recordWords, maxRecordWords);
readerReleaseMs = validateNonnegativeScalar(readerReleaseMs, ...
    'P11:model:ReaderRelease', 'readerReleaseMs');
readerProcessMs = validateNonnegativeScalar(readerProcessMs, ...
    'P11:model:ReaderProcess', 'readerProcessMs');
protection = validateProtection(protection);
tickMs = validatePositiveScalar(tickMs, ...
    'P11:model:Tick', 'tickMs');
horizonMs = validatePositiveScalar(horizonMs, ...
    'P11:model:Horizon', 'horizonMs');
waitTimeoutMs = validateWaitTimeout(waitTimeoutMs);
timeoutAction = validateTimeoutAction(timeoutAction);

scaledTimes = [writerPrepareMs, readerReleaseMs, ...
    readerProcessMs, horizonMs] ./ tickMs;
nearestTicks = round(scaledTimes);
alignmentTolerance = 32 .* eps(max(abs(scaledTimes), 1));
positiveCollapsedToZero = scaledTimes > 0 & nearestTicks == 0;
if any(~isfinite(scaledTimes)) || ...
        any(abs(scaledTimes - nearestTicks) > alignmentTolerance) || ...
        any(positiveCollapsedToZero)
    error('P11:model:GridAlignment', ...
        ['Every finite time and the horizon must align to tickMs; a ' ...
        'positive time cannot collapse to zero ticks.']);
end
if any(scaledTimes > maxInputTicks)
    error('P11:model:TimingResourceBound', ...
        'Each declared finite time may span at most 1e9 ticks.');
end

writerPrepareTicks = nearestTicks(1);
readerReleaseTicks = nearestTicks(2);
readerProcessTicks = nearestTicks(3);
horizonTicks = nearestTicks(4);
if horizonTicks < 1
    error('P11:model:Horizon', ...
        'The horizon must contain at least one scheduler tick.');
end
if horizonTicks > maxHorizonTicks
    error('P11:model:TimingResourceBound', ...
        'The observation horizon may contain at most 100000 ticks.');
end

waitTimeoutTicks = Inf;
if isfinite(waitTimeoutMs)
    scaledTimeout = waitTimeoutMs ./ tickMs;
    roundedTimeout = round(scaledTimeout);
    timeoutTolerance = 32 .* eps(max(abs(scaledTimeout), 1));
    if ~isfinite(scaledTimeout) || ...
            abs(scaledTimeout - roundedTimeout) > timeoutTolerance || ...
            (scaledTimeout > 0 && roundedTimeout == 0)
        error('P11:model:GridAlignment', ...
            'The finite reader wait timeout must align to tickMs.');
    end
    if scaledTimeout > maxInputTicks
        error('P11:model:TimingResourceBound', ...
            'The finite reader wait timeout may span at most 1e9 ticks.');
    end
    waitTimeoutTicks = roundedTimeout;
end

writerPrepareRemaining = writerPrepareTicks;
writerCommitRemaining = recordWords;
readerCopyRemaining = recordWords;
readerProcessRemaining = readerProcessTicks;

wordIndex = 1:recordWords;
initialRecord = wordIndex;
targetRecord = 100 + wordIndex;
sharedRecord = initialRecord;
readerObserved = NaN(1, recordWords);

cpuOwner = zeros(1, horizonTicks);
mutexOwnerTimeline = zeros(1, horizonTicks);
stageCode = zeros(1, horizonTicks);
readerBlockedTimeline = false(1, horizonTicks);
writerEffectivePriority = ones(1, horizonTicks);
% Ownership and stage traces describe half-open service intervals. Record
% progress and versions are states at interval boundaries, including the
% initial state and the final horizon boundary.
committedWordCount = zeros(1, horizonTicks + 1);
copiedWordCount = zeros(1, horizonTicks + 1);
recordMinVersion = zeros(1, horizonTicks + 1);
recordMaxVersion = zeros(1, horizonTicks + 1);

writerCompleted = false;
readerReleased = false;
readerCompleted = false;
readerCancelled = false;
readerBlocked = false;
readerTimedOut = false;
mutexOwner = 0;
writerCommitIndex = 0;
readerCopyIndex = 0;
writerServiceTicks = 0;
readerServiceTicks = 0;
readerBlockedTicks = 0;
commitBlockingTicks = 0;
scopeExcessBlockingTicks = 0;
cancelledReaderWorkTicks = 0;
writerStartTick = NaN;
writerCompletionTick = NaN;
readerStartTick = NaN;
readerCompletionTick = NaN;
writerRequestTick = NaN;
writerAcquireTick = NaN;
writerReleaseTick = NaN;
readerRequestTick = NaN;
readerAcquireTick = NaN;
readerReleaseTick = NaN;
readerBlockStartTick = NaN;
readerTimeoutTick = NaN;
readerCancellationTick = NaN;

% Prior-slot completion and unlock are applied during the service update.
% At a boundary, timeout classification precedes the half-open release,
% then a bounded request/block/reselection transition precedes one tick of
% CPU service. Therefore an unlock at the exact timeout boundary wins.
for boundaryTick = 0:horizonTicks
    if readerBlocked && ~readerTimedOut && ...
            readerBlockedTicks >= waitTimeoutTicks
        readerTimedOut = true;
        readerTimeoutTick = boundaryTick;
        if strcmp(timeoutAction, 'cancel-reader')
            if mutexOwner == 2
                error('P11:model:InternalMutex', ...
                    'A blocked reader cannot own the mutex it waits for.');
            end
            readerCancelled = true;
            readerBlocked = false;
            readerCancellationTick = boundaryTick;
            cancelledReaderWorkTicks = readerCopyRemaining + ...
                readerProcessRemaining;
            readerCopyRemaining = 0;
            readerProcessRemaining = 0;
        end
    end

    if boundaryTick == horizonTicks
        break;
    end

    if ~readerReleased && readerReleaseTicks == boundaryTick
        readerReleased = true;
    end

    selectedTask = 0;
    transitionResolved = false;
    for boundedTransition = 1:3
        writerReady = ~writerCompleted;
        readerReady = readerReleased && ~readerCompleted && ...
            ~readerCancelled && ~readerBlocked;
        if readerReady
            selectedTask = 2;
        elseif writerReady
            selectedTask = 1;
        else
            selectedTask = 0;
        end

        if selectedTask == 0
            transitionResolved = true;
            break;
        end

        needsMutex = false;
        if selectedTask == 1
            needsMutex = strcmp(protection, 'coarse-mutex') || ...
                (strcmp(protection, 'short-mutex') && ...
                writerPrepareRemaining == 0);
            if needsMutex && isnan(writerRequestTick)
                writerRequestTick = boundaryTick;
            end
        else
            needsMutex = strcmp(protection, 'coarse-mutex') || ...
                (strcmp(protection, 'short-mutex') && ...
                readerCopyRemaining > 0);
            if needsMutex && isnan(readerRequestTick)
                readerRequestTick = boundaryTick;
            end
        end

        if needsMutex && mutexOwner ~= selectedTask
            if mutexOwner == 0
                mutexOwner = selectedTask;
                if selectedTask == 1 && isnan(writerAcquireTick)
                    writerAcquireTick = boundaryTick;
                elseif selectedTask == 2 && isnan(readerAcquireTick)
                    readerAcquireTick = boundaryTick;
                end
            elseif selectedTask == 2
                readerBlocked = true;
                if isnan(readerBlockStartTick)
                    readerBlockStartTick = boundaryTick;
                end
                selectedTask = 0;
                continue;
            else
                error('P11:model:InternalMutex', ...
                    'The low writer cannot be selected while the high reader owns the mutex.');
            end
        end
        transitionResolved = true;
        break;
    end
    if ~transitionResolved
        error('P11:model:InternalTransition', ...
            'Lock request transitions exceeded the fixed task bound.');
    end

    writerPriority = 1;
    if readerBlocked && mutexOwner == 1 && ...
            ~strcmp(protection, 'unprotected')
        writerPriority = 2;
    end

    slotIndex = boundaryTick + 1;
    cpuOwner(slotIndex) = selectedTask;
    mutexOwnerTimeline(slotIndex) = mutexOwner;
    readerBlockedTimeline(slotIndex) = readerBlocked;
    writerEffectivePriority(slotIndex) = writerPriority;
    if selectedTask == 1
        if writerPrepareRemaining > 0
            stageCode(slotIndex) = 1;
        else
            stageCode(slotIndex) = 2;
        end
    elseif selectedTask == 2
        if readerCopyRemaining > 0
            stageCode(slotIndex) = 3;
        else
            stageCode(slotIndex) = 4;
        end
    end

    if readerBlocked
        readerBlockedTicks = readerBlockedTicks + 1;
        if selectedTask == 1 && writerPrepareRemaining > 0
            scopeExcessBlockingTicks = scopeExcessBlockingTicks + 1;
        elseif selectedTask == 1 && writerCommitRemaining > 0
            commitBlockingTicks = commitBlockingTicks + 1;
        end
    end

    if selectedTask == 1
        if isnan(writerStartTick)
            writerStartTick = boundaryTick;
        end
        writerServiceTicks = writerServiceTicks + 1;
        if writerPrepareRemaining > 0
            writerPrepareRemaining = writerPrepareRemaining - 1;
        else
            writerCommitIndex = writerCommitIndex + 1;
            sharedRecord(writerCommitIndex) = ...
                targetRecord(writerCommitIndex);
            writerCommitRemaining = writerCommitRemaining - 1;
            if writerCommitRemaining == 0
                writerCompleted = true;
                writerCompletionTick = boundaryTick + 1;
                if mutexOwner == 1
                    mutexOwner = 0;
                    writerReleaseTick = boundaryTick + 1;
                    readerBlocked = false;
                end
            end
        end
    elseif selectedTask == 2
        if isnan(readerStartTick)
            readerStartTick = boundaryTick;
        end
        readerServiceTicks = readerServiceTicks + 1;
        if readerCopyRemaining > 0
            readerCopyIndex = readerCopyIndex + 1;
            readerObserved(readerCopyIndex) = ...
                sharedRecord(readerCopyIndex);
            readerCopyRemaining = readerCopyRemaining - 1;
            if readerCopyRemaining == 0 && ...
                    strcmp(protection, 'short-mutex') && ...
                    mutexOwner == 2
                mutexOwner = 0;
                readerReleaseTick = boundaryTick + 1;
            end
            if readerCopyRemaining == 0 && readerProcessRemaining == 0
                readerCompleted = true;
                readerCompletionTick = boundaryTick + 1;
                if mutexOwner == 2
                    mutexOwner = 0;
                    readerReleaseTick = boundaryTick + 1;
                end
            end
        else
            readerProcessRemaining = readerProcessRemaining - 1;
            if readerProcessRemaining == 0
                readerCompleted = true;
                readerCompletionTick = boundaryTick + 1;
                if mutexOwner == 2
                    mutexOwner = 0;
                    readerReleaseTick = boundaryTick + 1;
                end
            end
        end
    end

    boundaryStateIndex = slotIndex + 1;
    committedWordCount(boundaryStateIndex) = writerCommitIndex;
    copiedWordCount(boundaryStateIndex) = readerCopyIndex;
    liveVersions = (sharedRecord - wordIndex) ./ 100;
    recordMinVersion(boundaryStateIndex) = min(liveVersions);
    recordMaxVersion(boundaryStateIndex) = max(liveVersions);
end

readerSnapshotComplete = readerCopyIndex == recordWords;
observedVersions = (readerObserved - wordIndex) ./ 100;
readerSnapshotConsistent = readerSnapshotComplete && ...
    all(isfinite(observedVersions)) && ...
    all(observedVersions == observedVersions(1)) && ...
    all(observedVersions == round(observedVersions));
readerObservedVersion = NaN;
if readerSnapshotConsistent
    readerObservedVersion = observedVersions(1);
end
readerTorn = readerSnapshotComplete && ~readerSnapshotConsistent;
readerStale = readerSnapshotConsistent && readerObservedVersion < 1;

finalVersions = (sharedRecord - wordIndex) ./ 100;
recordConsistent = all(finalVersions == finalVersions(1)) && ...
    all(finalVersions == round(finalVersions));
publishedVersion = double(writerCompleted);
writerRemainingTicks = writerPrepareRemaining + writerCommitRemaining;
readerRemainingTicks = 0;
if readerReleased && ~readerCancelled
    readerRemainingTicks = readerCopyRemaining + readerProcessRemaining;
end
releasedDemandTicks = writerPrepareTicks + recordWords;
if readerReleased
    releasedDemandTicks = releasedDemandTicks + ...
        recordWords + readerProcessTicks;
end
servedTicks = writerServiceTicks + readerServiceTicks;
remainingTicks = writerRemainingTicks + readerRemainingTicks;
busyTicks = sum(cpuOwner > 0);
idleTicks = horizonTicks - busyTicks;
readerResponseTicks = NaN;
if readerCompleted
    readerResponseTicks = readerCompletionTick - readerReleaseTicks;
end

if mutexOwner < 0 || mutexOwner > 2 || ...
        readerBlockedTicks ~= ...
        commitBlockingTicks + scopeExcessBlockingTicks || ...
        releasedDemandTicks ~= servedTicks + ...
        cancelledReaderWorkTicks + remainingTicks
    error('P11:model:InternalAccounting', ...
        'Shared-record scheduling did not conserve blocking, work, or ownership.');
end

out = struct();
out.input = struct( ...
    'writer_prepare_ms', writerPrepareTicks .* tickMs, ...
    'record_words', recordWords, ...
    'reader_release_ms', readerReleaseTicks .* tickMs, ...
    'reader_process_ms', readerProcessTicks .* tickMs, ...
    'tick_ms', tickMs, ...
    'horizon_ms', horizonTicks .* tickMs, ...
    'wait_timeout_ms', waitTimeoutTicks .* tickMs);
out.policy = struct( ...
    'protection', protection, ...
    'timeout_action', timeoutAction, ...
    'scheduler', 'fixed-priority-preemptive-single-core', ...
    'writer_base_priority', 1, ...
    'reader_base_priority', 2, ...
    'mutex_protocol', protectedProtocol(protection), ...
    'short_scope', 'writer commit and reader copy only', ...
    'coarse_scope', 'writer prepare+commit and reader copy+process', ...
    'unlock_before_timeout_at_same_boundary', true, ...
    'release_at_horizon_included', false, ...
    'dispatch_overhead_ms', 0, ...
    'context_switch_overhead_ms', 0);
out.timeline = struct( ...
    'time_ms', (0:(horizonTicks - 1)) .* tickMs, ...
    'time_edges_ms', (0:horizonTicks) .* tickMs, ...
    'cpu_owner_task_id', cpuOwner, ...
    'mutex_owner_task_id', mutexOwnerTimeline, ...
    'stage_code', stageCode, ...
    'stage_labels', {{'idle', 'writer prepare', 'writer commit', ...
    'reader copy', 'reader process'}}, ...
    'reader_blocked', readerBlockedTimeline, ...
    'writer_effective_priority', writerEffectivePriority, ...
    'writer_committed_word_count', committedWordCount, ...
    'reader_copied_word_count', copiedWordCount, ...
    'live_record_min_version', recordMinVersion, ...
    'live_record_max_version', recordMaxVersion);
out.record = struct( ...
    'initial_values', initialRecord, ...
    'target_values', targetRecord, ...
    'final_values', sharedRecord, ...
    'final_version_by_word', finalVersions, ...
    'published_version', publishedVersion, ...
    'consistent_at_horizon', recordConsistent, ...
    'version_stride', 100);
out.writer = struct( ...
    'released', true, ...
    'start_ms', writerStartTick .* tickMs, ...
    'completion_ms', writerCompletionTick .* tickMs, ...
    'service_ms', writerServiceTicks .* tickMs, ...
    'remaining_ms', writerRemainingTicks .* tickMs, ...
    'committed_words', writerCommitIndex, ...
    'mutex_request_ms', writerRequestTick .* tickMs, ...
    'mutex_acquire_ms', writerAcquireTick .* tickMs, ...
    'mutex_release_ms', writerReleaseTick .* tickMs, ...
    'completed', writerCompleted, ...
    'peak_effective_priority', max(writerEffectivePriority));
out.reader = struct( ...
    'released', readerReleased, ...
    'start_ms', readerStartTick .* tickMs, ...
    'completion_ms', readerCompletionTick .* tickMs, ...
    'response_ms', readerResponseTicks .* tickMs, ...
    'service_ms', readerServiceTicks .* tickMs, ...
    'remaining_ms', readerRemainingTicks .* tickMs, ...
    'cancelled_work_ms', cancelledReaderWorkTicks .* tickMs, ...
    'mutex_request_ms', readerRequestTick .* tickMs, ...
    'mutex_acquire_ms', readerAcquireTick .* tickMs, ...
    'mutex_release_ms', readerReleaseTick .* tickMs, ...
    'block_start_ms', readerBlockStartTick .* tickMs, ...
    'blocked_time_ms', readerBlockedTicks .* tickMs, ...
    'commit_blocking_ms', commitBlockingTicks .* tickMs, ...
    'scope_excess_blocking_ms', scopeExcessBlockingTicks .* tickMs, ...
    'wait_timed_out', readerTimedOut, ...
    'wait_timeout_time_ms', readerTimeoutTick .* tickMs, ...
    'cancelled_while_waiting', readerCancelled, ...
    'cancellation_time_ms', readerCancellationTick .* tickMs, ...
    'completed', readerCompleted, ...
    'snapshot_complete', readerSnapshotComplete, ...
    'observed_values', readerObserved, ...
    'observed_version_by_word', observedVersions, ...
    'observed_version', readerObservedVersion, ...
    'snapshot_consistent', readerSnapshotConsistent, ...
    'torn_read_detected', readerTorn, ...
    'stale_but_consistent', readerStale);
out.metrics = struct( ...
    'busy_time_ms', busyTicks .* tickMs, ...
    'idle_time_ms', idleTicks .* tickMs, ...
    'busy_fraction', busyTicks ./ horizonTicks, ...
    'idle_fraction', idleTicks ./ horizonTicks, ...
    'released_demand_ms', releasedDemandTicks .* tickMs, ...
    'served_work_ms', servedTicks .* tickMs, ...
    'cancelled_work_ms', cancelledReaderWorkTicks .* tickMs, ...
    'remaining_work_ms', remainingTicks .* tickMs, ...
    'work_conservation_error_ms', ...
    (releasedDemandTicks - servedTicks - ...
    cancelledReaderWorkTicks - remainingTicks) .* tickMs, ...
    'reader_blocked_ms', readerBlockedTicks .* tickMs, ...
    'commit_blocking_ms', commitBlockingTicks .* tickMs, ...
    'scope_excess_blocking_ms', scopeExcessBlockingTicks .* tickMs, ...
    'torn_read_count', double(readerTorn), ...
    'consistent_snapshot_count', double(readerSnapshotConsistent));
out.claim_boundary = [ ...
    'Deterministic two-task shared-record calculation; not MATLAB-runtime, ' ...
    'RTOS, processor, cache, compiler, memory-ordering, or hardware ' ...
    'timing evidence.'];
end

function value = validateNonnegativeScalar(value, identifier, label)
valid = isnumeric(value) && ~islogical(value) && isreal(value) && ...
    isscalar(value) && isfinite(value) && value >= 0;
if ~valid
    error(identifier, ...
        '%s must be a nonnegative finite real numeric scalar.', label);
end
value = double(value);
end

function value = validatePositiveScalar(value, identifier, label)
valid = isnumeric(value) && ~islogical(value) && isreal(value) && ...
    isscalar(value) && isfinite(value) && value > 0;
if ~valid
    error(identifier, ...
        '%s must be a positive finite real numeric scalar.', label);
end
value = double(value);
end

function value = validateRecordWords(value, maximum)
valid = isnumeric(value) && ~islogical(value) && isreal(value) && ...
    isscalar(value) && isfinite(value) && value == round(value) && ...
    value >= 2;
if ~valid
    error('P11:model:RecordWords', ...
        'recordWords must be a finite integer scalar of at least two.');
end
if value > maximum
    error('P11:model:RecordResourceBound', ...
        'The shared record may contain at most 64 words.');
end
value = double(value);
end

function protection = validateProtection(protection)
if ~(ischar(protection) || ...
        (isstring(protection) && isscalar(protection)))
    error('P11:model:Protection', ...
        'protection must be a character vector or scalar string.');
end
protection = lower(strtrim(char(protection)));
if ~any(strcmp(protection, ...
        {'short-mutex', 'coarse-mutex', 'unprotected'}))
    error('P11:model:Protection', ...
        'protection must be short-mutex, coarse-mutex, or unprotected.');
end
end

function waitTimeoutMs = validateWaitTimeout(waitTimeoutMs)
valid = isnumeric(waitTimeoutMs) && ~islogical(waitTimeoutMs) && ...
    isreal(waitTimeoutMs) && isscalar(waitTimeoutMs) && ...
    ~isnan(waitTimeoutMs) && waitTimeoutMs > 0;
if ~valid
    error('P11:model:WaitTimeout', ...
        'waitTimeoutMs must be a positive real numeric scalar; Inf disables timeout.');
end
waitTimeoutMs = double(waitTimeoutMs);
end

function timeoutAction = validateTimeoutAction(timeoutAction)
if ~(ischar(timeoutAction) || ...
        (isstring(timeoutAction) && isscalar(timeoutAction)))
    error('P11:model:TimeoutAction', ...
        'timeoutAction must be a character vector or scalar string.');
end
timeoutAction = lower(strtrim(char(timeoutAction)));
if ~any(strcmp(timeoutAction, ...
        {'continue-waiting', 'cancel-reader'}))
    error('P11:model:TimeoutAction', ...
        'timeoutAction must be continue-waiting or cancel-reader.');
end
end

function protocol = protectedProtocol(protection)
if strcmp(protection, 'unprotected')
    protocol = 'none';
else
    protocol = 'direct-priority-inheritance';
end
end
