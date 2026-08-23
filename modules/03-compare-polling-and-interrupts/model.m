function out = model(eventTimesMs, pulseWidthMs, horizonMs, pollPeriodMs, ...
        pollCheckCostMs, interruptLatencyMs, handlerCostMs, queueCapacity, maskWindowsMs)
%MODEL Compare deterministic polling and interrupt handling of request pulses.
%   Request pulses occupy half-open intervals [arrival, arrival + width) in
%   milliseconds. Polling observes a pulse only when an actual poll instant
%   falls inside that interval. Interrupt arrivals enter a finite FIFO whose
%   capacity includes requests in service and waiting. Mask windows delay
%   dispatch; they do not abort a handler that has already started. Poll
%   interval comparisons snap values within a scale-aware tolerance to the
%   nearer boundary so accumulated binary time-step roundoff cannot reverse
%   arrival-inclusive, end-exclusive pulse, mask, capacity, or horizon rules.

if nargin < 8 || nargin > 9
    error('P03:model:Arity', [ ...
        'Expected event times, pulse width, horizon, poll period, poll-check cost, ' ...
        'interrupt latency, handler cost, queue capacity, and optional mask windows.']);
end
if nargin < 9
    maskWindowsMs = zeros(0, 2);
end

maxRecords = 1000000;
validateEventShape(eventTimesMs, maxRecords);
eventCount = numel(eventTimesMs);
validatePulseWidthShape(pulseWidthMs, eventCount, maxRecords);
validateMaskShape(maskWindowsMs, maxRecords);
maskCount = size(maskWindowsMs, 1);
validatePulseWidthValues(double(reshape(pulseWidthMs, 1, [])));

validateTimingScalar(horizonMs, true, 'P03:model:Horizon', 'horizonMs');
validateTimingScalar(pollPeriodMs, true, 'P03:model:PollPeriod', 'pollPeriodMs');
validateTimingScalar(pollCheckCostMs, false, ...
    'P03:model:PollCheckCost', 'pollCheckCostMs');
validateTimingScalar(interruptLatencyMs, false, ...
    'P03:model:InterruptLatency', 'interruptLatencyMs');
validateTimingScalar(handlerCostMs, false, ...
    'P03:model:HandlerCost', 'handlerCostMs');
validateQueueCapacity(queueCapacity, maxRecords);

horizonMs = double(horizonMs);
pollPeriodMs = double(pollPeriodMs);
pollCheckCostMs = double(pollCheckCostMs);
interruptLatencyMs = double(interruptLatencyMs);
handlerCostMs = double(handlerCostMs);
queueCapacity = double(queueCapacity);
eventTimesMs = double(reshape(eventTimesMs, 1, []));
if isempty(maskWindowsMs)
    maskWindowsMs = zeros(0, 2);
else
    maskWindowsMs = double(maskWindowsMs);
end

if eventCount == 0
    pulseWidthMs = zeros(1, 0);
elseif isscalar(pulseWidthMs)
    pulseWidthMs = repmat(double(pulseWidthMs), 1, eventCount);
else
    pulseWidthMs = double(reshape(pulseWidthMs, 1, []));
end

validateEventValues(eventTimesMs);

if eventCount > 1 && any(diff(eventTimesMs) <= 0)
    error('P03:model:EventOrder', ...
        'Event arrival times must be strictly increasing.');
end
eventEndMs = eventTimesMs + pulseWidthMs;
if any(~isfinite(eventEndMs)) || any(eventEndMs <= eventTimesMs)
    error('P03:model:TimingResourceBound', ...
        'Each positive pulse width must produce a finite, later end time.');
end
timeScaleMs = max([1 horizonMs abs(eventTimesMs) abs(eventEndMs)]);
comparisonToleranceMs = 16 * eps(timeScaleMs);
maskWindowsMs = validateAndNormalizeMaskValues( ...
    maskWindowsMs, horizonMs, comparisonToleranceMs);
if any(eventTimesMs < 0) || any(eventTimesMs >= horizonMs) || ...
        any(eventEndMs > horizonMs + comparisonToleranceMs)
    error('P03:model:EventBounds', ...
        'Every half-open request pulse must fit inside [0, horizonMs).');
end
eventEndMs(eventEndMs > horizonMs) = horizonMs;
for eventIndex = 1:max(0, eventCount - 1)
    overlapMs = eventEndMs(eventIndex) - eventTimesMs(eventIndex + 1);
    if overlapMs > comparisonToleranceMs
        error('P03:model:PulseOverlap', ...
            'Request pulses must not overlap in this single-source input model.');
    elseif overlapMs > 0
        eventEndMs(eventIndex) = eventTimesMs(eventIndex + 1);
    end
end

pollRatio = horizonMs / pollPeriodMs;
projectedPollCount = ceil(pollRatio) + 1;
totalRecords = projectedPollCount + eventCount + maskCount;
maximumDerivedMs = horizonMs + pollCheckCostMs + handlerCostMs + ...
    (eventCount + 1) * (interruptLatencyMs + handlerCostMs) + ...
    sum(maskWindowsMs(:, 2) - maskWindowsMs(:, 1));
if ~isfinite(pollRatio) || ~isfinite(projectedPollCount) || ...
        ~isfinite(totalRecords) || projectedPollCount > maxRecords || ...
        totalRecords > maxRecords
    error('P03:model:ResourceBound', ...
        'Events, masks, and projected polls exceed the one-million-record bound.');
end
if ~isfinite(maximumDerivedMs)
    error('P03:model:TimingResourceBound', ...
        'Derived schedule times exceed finite educational bounds.');
end

poll = simulatePolling(eventTimesMs, eventEndMs, horizonMs, pollPeriodMs, ...
    pollCheckCostMs, handlerCostMs, projectedPollCount, comparisonToleranceMs);
interrupt = simulateInterrupts(eventTimesMs, horizonMs, interruptLatencyMs, ...
    handlerCostMs, queueCapacity, maskWindowsMs, comparisonToleranceMs);

out = struct();
out.horizon_ms = horizonMs;
out.comparison_tolerance_ms = comparisonToleranceMs;
out.events = struct('arrival_ms', eventTimesMs, 'width_ms', pulseWidthMs, ...
    'end_ms', eventEndMs, 'count', eventCount);
out.poll = poll;
out.interrupt = interrupt;
out.metrics = struct();
out.metrics.total_events = eventCount;
out.metrics.poll_detected_count = sum(poll.detected);
out.metrics.poll_missed_count = sum(poll.missed);
out.metrics.poll_worst_response_ms = maximumOrNaN(poll.response_latency_ms(poll.detected));
out.metrics.poll_mean_response_ms = meanOrNaN(poll.response_latency_ms(poll.detected));
out.metrics.poll_completion_after_horizon_count = sum( ...
    poll.detected & poll.finish_ms > horizonMs + comparisonToleranceMs);
out.metrics.interrupt_captured_count = sum(interrupt.captured);
out.metrics.interrupt_dropped_count = sum(interrupt.dropped_overrun);
out.metrics.interrupt_worst_response_ms = maximumOrNaN( ...
    interrupt.response_latency_ms(interrupt.captured));
out.metrics.interrupt_mean_response_ms = meanOrNaN( ...
    interrupt.response_latency_ms(interrupt.captured));
out.metrics.interrupt_completion_after_horizon_count = sum( ...
    interrupt.captured & interrupt.finish_ms > horizonMs + comparisonToleranceMs);
out.metrics.events_arriving_while_masked = sum(interrupt.arrived_while_masked);
end

function poll = simulatePolling(eventTimesMs, eventEndMs, horizonMs, pollPeriodMs, ...
        pollCheckCostMs, handlerCostMs, projectedPollCount, comparisonToleranceMs)
eventCount = numel(eventTimesMs);
sampleTimesMs = zeros(1, projectedPollCount);
workFinishMs = zeros(1, projectedPollCount);
detectedAtPoll = zeros(1, projectedPollCount);
detected = false(1, eventCount);
detectionTimeMs = nan(1, eventCount);
serviceStartMs = nan(1, eventCount);
finishMs = nan(1, eventCount);
responseLatencyMs = nan(1, eventCount);

pollTimeMs = 0;
pollCount = 0;
eventCursor = 1;
cpuBusyMs = 0;

for boundedPollIndex = 1:projectedPollCount
    [horizonRelation, pollTimeMs] = classifyHalfOpenTime( ...
        pollTimeMs, 0, horizonMs, comparisonToleranceMs);
    if horizonRelation > 0
        break;
    end

    relation = -1;
    for scanIndex = eventCursor:eventCount
        if detected(scanIndex)
            eventCursor = scanIndex + 1;
            continue;
        end
        [relation, pollTimeMs] = classifyHalfOpenTime(pollTimeMs, ...
            eventTimesMs(scanIndex), eventEndMs(scanIndex), ...
            comparisonToleranceMs);
        if relation > 0
            eventCursor = scanIndex + 1;
        else
            break;
        end
    end
    [horizonRelation, pollTimeMs] = classifyHalfOpenTime( ...
        pollTimeMs, 0, horizonMs, comparisonToleranceMs);
    if horizonRelation > 0
        break;
    end

    pollCount = pollCount + 1;
    sampleTimesMs(pollCount) = pollTimeMs;
    checkFinishMs = pollTimeMs + pollCheckCostMs;
    if ~isfinite(checkFinishMs) || ...
            (pollCheckCostMs > 0 && checkFinishMs <= pollTimeMs)
        error('P03:model:TimingResourceBound', ...
            'Positive poll-check cost must advance to a finite work-finish time.');
    end

    detectedEventIndex = 0;
    if eventCursor <= eventCount && relation == 0
        detectedEventIndex = eventCursor;
        detected(eventCursor) = true;
        detectionTimeMs(eventCursor) = pollTimeMs;
        serviceStartMs(eventCursor) = checkFinishMs;
        finishMs(eventCursor) = serviceStartMs(eventCursor) + handlerCostMs;
        if ~isfinite(finishMs(eventCursor)) || ...
                (handlerCostMs > 0 && ...
                finishMs(eventCursor) <= serviceStartMs(eventCursor))
            error('P03:model:TimingResourceBound', ...
                'Positive handler cost must advance to a finite finish time.');
        end
        responseLatencyMs(eventCursor) = serviceStartMs(eventCursor) - ...
            eventTimesMs(eventCursor);
        eventCursor = eventCursor + 1;
    end
    detectedAtPoll(pollCount) = detectedEventIndex;

    workFinish = checkFinishMs;
    if detectedEventIndex > 0
        workFinish = workFinish + handlerCostMs;
    end
    workFinishMs(pollCount) = workFinish;
    cpuBusyMs = cpuBusyMs + max(0, min(workFinish, horizonMs) - pollTimeMs);

    nextPollTimeMs = max(pollTimeMs + pollPeriodMs, workFinish);
    if ~isfinite(nextPollTimeMs) || nextPollTimeMs <= pollTimeMs
        error('P03:model:TimingResourceBound', ...
            'The polling recurrence stopped making finite forward progress.');
    end
    pollTimeMs = nextPollTimeMs;
end

poll = struct();
poll.sample_times_ms = sampleTimesMs(1:pollCount);
poll.work_finish_ms = workFinishMs(1:pollCount);
poll.detected_event_index = detectedAtPoll(1:pollCount);
poll.detected = detected;
poll.missed = ~detected;
poll.detection_time_ms = detectionTimeMs;
poll.service_start_ms = serviceStartMs;
poll.finish_ms = finishMs;
poll.response_latency_ms = responseLatencyMs;
poll.period_ms = pollPeriodMs;
poll.check_cost_ms = pollCheckCostMs;
poll.handler_cost_ms = handlerCostMs;
poll.cpu_busy_ms = cpuBusyMs;
poll.cpu_busy_fraction = min(1, max(0, cpuBusyMs / horizonMs));
end

function [relation, normalizedTimeMs] = classifyHalfOpenTime( ...
        timeMs, startMs, endMs, toleranceMs)
% Return -1 before [start, end), 0 inside it, and 1 at/after its end.
normalizedTimeMs = timeMs;
distanceToStartMs = abs(timeMs - startMs);
distanceToEndMs = abs(timeMs - endMs);
if distanceToStartMs <= toleranceMs && distanceToStartMs <= distanceToEndMs
    normalizedTimeMs = startMs;
    relation = 0;
elseif distanceToEndMs <= toleranceMs
    normalizedTimeMs = endMs;
    relation = 1;
elseif timeMs < startMs
    relation = -1;
elseif timeMs < endMs
    relation = 0;
else
    relation = 1;
end
end

function interrupt = simulateInterrupts(eventTimesMs, horizonMs, interruptLatencyMs, ...
        handlerCostMs, queueCapacity, maskWindowsMs, comparisonToleranceMs)
eventCount = numel(eventTimesMs);
captured = false(1, eventCount);
droppedOverrun = false(1, eventCount);
arrivedWhileMasked = false(1, eventCount);
serviceStartMs = nan(1, eventCount);
finishMs = nan(1, eventCount);
responseLatencyMs = nan(1, eventCount);
acceptedFinishMs = zeros(1, eventCount);
acceptedCount = 0;
completedCount = 0;
maxOutstanding = 0;
arrivalMaskCursor = 1;
dispatchMaskCursor = 1;

for eventIndex = 1:eventCount
    arrivalMs = eventTimesMs(eventIndex);
    [arrivedWhileMasked(eventIndex), arrivalMaskCursor] = ...
        maskMembership(arrivalMs, maskWindowsMs, arrivalMaskCursor, ...
        comparisonToleranceMs);

    for completionIndex = completedCount + 1:acceptedCount
        if acceptedFinishMs(completionIndex) <= ...
                arrivalMs + comparisonToleranceMs
            completedCount = completionIndex;
        else
            break;
        end
    end
    outstandingBeforeArrival = acceptedCount - completedCount;
    if outstandingBeforeArrival >= queueCapacity
        droppedOverrun(eventIndex) = true;
        continue;
    end

    if completedCount == acceptedCount
        readyMs = arrivalMs;
    else
        readyMs = max(arrivalMs, acceptedFinishMs(acceptedCount));
    end
    dispatchCandidateMs = readyMs + interruptLatencyMs;
    if ~isfinite(dispatchCandidateMs) || ...
            (interruptLatencyMs > 0 && dispatchCandidateMs <= readyMs)
        error('P03:model:TimingResourceBound', ...
            'Positive interrupt latency must advance to a finite dispatch time.');
    end
    [startMs, dispatchMaskCursor] = nextUnmaskedTime( ...
        dispatchCandidateMs, maskWindowsMs, dispatchMaskCursor, ...
        comparisonToleranceMs);
    finishedMs = startMs + handlerCostMs;
    if any(~isfinite([startMs finishedMs])) || ...
            (handlerCostMs > 0 && finishedMs <= startMs)
        error('P03:model:TimingResourceBound', ...
            'Positive handler cost must advance to a finite interrupt finish time.');
    end

    acceptedCount = acceptedCount + 1;
    acceptedFinishMs(acceptedCount) = finishedMs;
    captured(eventIndex) = true;
    serviceStartMs(eventIndex) = startMs;
    finishMs(eventIndex) = finishedMs;
    responseLatencyMs(eventIndex) = startMs - arrivalMs;
    maxOutstanding = max(maxOutstanding, acceptedCount - completedCount);
end

acceptedStarts = serviceStartMs(captured);
acceptedFinishes = finishMs(captured);
busySegmentsMs = max(zeros(size(acceptedStarts)), ...
    min(acceptedFinishes, horizonMs) - acceptedStarts);
cpuBusyMs = sum(busySegmentsMs);

interrupt = struct();
interrupt.captured = captured;
interrupt.dropped_overrun = droppedOverrun;
interrupt.arrived_while_masked = arrivedWhileMasked;
interrupt.service_start_ms = serviceStartMs;
interrupt.finish_ms = finishMs;
interrupt.response_latency_ms = responseLatencyMs;
interrupt.latency_ms = interruptLatencyMs;
interrupt.handler_cost_ms = handlerCostMs;
interrupt.queue_capacity = queueCapacity;
interrupt.mask_windows_ms = maskWindowsMs;
interrupt.max_outstanding = maxOutstanding;
interrupt.cpu_busy_ms = cpuBusyMs;
interrupt.cpu_busy_fraction = min(1, max(0, cpuBusyMs / horizonMs));
interrupt.backlog_at_horizon = sum( ...
    captured & finishMs > horizonMs + comparisonToleranceMs);
end

function [inside, nextCursor] = maskMembership( ...
        timeMs, maskWindowsMs, startCursor, comparisonToleranceMs)
inside = false;
nextCursor = startCursor;
maskCount = size(maskWindowsMs, 1);
for maskIndex = startCursor:maskCount
    relation = classifyHalfOpenTime(timeMs, maskWindowsMs(maskIndex, 1), ...
        maskWindowsMs(maskIndex, 2), comparisonToleranceMs);
    if relation > 0
        nextCursor = maskIndex + 1;
    elseif relation == 0
        inside = true;
        nextCursor = maskIndex;
        break;
    else
        nextCursor = maskIndex;
        break;
    end
end
end

function [shiftedTimeMs, nextCursor] = nextUnmaskedTime( ...
        candidateTimeMs, maskWindowsMs, startCursor, comparisonToleranceMs)
shiftedTimeMs = candidateTimeMs;
nextCursor = startCursor;
maskCount = size(maskWindowsMs, 1);
for maskIndex = startCursor:maskCount
    [relation, shiftedTimeMs] = classifyHalfOpenTime(shiftedTimeMs, ...
        maskWindowsMs(maskIndex, 1), maskWindowsMs(maskIndex, 2), ...
        comparisonToleranceMs);
    if relation > 0
        nextCursor = maskIndex + 1;
    elseif relation == 0
        shiftedTimeMs = maskWindowsMs(maskIndex, 2);
        nextCursor = maskIndex + 1;
    else
        nextCursor = maskIndex;
        break;
    end
end
end

function validateEventShape(value, maxRecords)
validType = isnumeric(value) && isreal(value);
validShape = isempty(value) || isvector(value);
if ~(validType && validShape)
    error('P03:model:EventTimes', ...
        'eventTimesMs must be an empty or nonempty real numeric vector.');
end
if numel(value) > maxRecords
    error('P03:model:ResourceBound', ...
        'Event input exceeds the one-million-record educational bound.');
end
end

function validatePulseWidthShape(value, eventCount, maxRecords)
validType = isnumeric(value) && isreal(value);
validShape = isscalar(value) || ...
    (eventCount == 0 && isempty(value)) || ...
    (isvector(value) && numel(value) == eventCount);
if ~(validType && validShape)
    error('P03:model:PulseWidth', ...
        'pulseWidthMs must be a scalar or one value per event.');
end
if numel(value) > maxRecords
    error('P03:model:ResourceBound', ...
        'Pulse-width input exceeds the one-million-record educational bound.');
end
end

function validateMaskShape(value, maxRecords)
validType = isnumeric(value) && isreal(value);
validShape = isempty(value) || (ismatrix(value) && size(value, 2) == 2);
if ~(validType && validShape)
    error('P03:model:MaskWindows', ...
        'maskWindowsMs must be empty or an N-by-2 real numeric matrix.');
end
if ~isempty(value) && size(value, 1) > maxRecords
    error('P03:model:ResourceBound', ...
        'Mask input exceeds the one-million-record educational bound.');
end
end

function validateEventValues(value)
if any(~isfinite(value))
    error('P03:model:EventTimes', ...
        'eventTimesMs must contain only finite values.');
end
end

function validatePulseWidthValues(value)
if any(~isfinite(value)) || any(value <= 0)
    error('P03:model:PulseWidth', ...
        'Every pulse width must be finite and strictly positive.');
end
end

function value = validateAndNormalizeMaskValues(value, horizonMs, toleranceMs)
if isempty(value)
    return;
end
if any(~isfinite(value(:))) || any(value(:, 1) < -toleranceMs) || ...
        any(value(:, 2) > horizonMs + toleranceMs)
    error('P03:model:MaskWindows', ...
        'Mask windows must be finite, positive-width intervals inside the horizon.');
end
value(value(:, 1) < 0, 1) = 0;
value(value(:, 2) > horizonMs, 2) = horizonMs;
if any(value(:, 1) >= value(:, 2))
    error('P03:model:MaskWindows', ...
        'Mask windows must be finite, positive-width intervals inside the horizon.');
end
if size(value, 1) > 1 && any(diff(value(:, 1)) <= 0)
    error('P03:model:MaskOrder', ...
        'Mask windows must be sorted, distinct, and nonoverlapping.');
end
for maskIndex = 1:max(0, size(value, 1) - 1)
    overlapMs = value(maskIndex, 2) - value(maskIndex + 1, 1);
    if overlapMs > toleranceMs
        error('P03:model:MaskOrder', ...
            'Mask windows must be sorted, distinct, and nonoverlapping.');
    elseif overlapMs > 0
        value(maskIndex, 2) = value(maskIndex + 1, 1);
    end
end
end

function validateTimingScalar(value, strictlyPositive, identifier, name)
valid = isnumeric(value) && isreal(value) && isscalar(value) && isfinite(value);
if strictlyPositive
    valid = valid && value > 0;
else
    valid = valid && value >= 0;
end
if ~valid
    error(identifier, '%s must be a finite scalar in milliseconds.', name);
end
end

function validateQueueCapacity(value, maxRecords)
valid = isnumeric(value) && isreal(value) && isscalar(value) && isfinite(value) && ...
    value >= 1 && value == floor(value) && value <= maxRecords;
if ~valid
    error('P03:model:QueueCapacity', ...
        'queueCapacity must be a positive integer within the record bound.');
end
end

function value = maximumOrNaN(values)
if isempty(values)
    value = NaN;
else
    value = max(values);
end
end

function value = meanOrNaN(values)
if isempty(values)
    value = NaN;
else
    value = mean(values);
end
end
