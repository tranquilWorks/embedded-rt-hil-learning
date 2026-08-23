function out = model(sourceSamples, producerPeriodUs, consumerPeriodUs, ...
    consumerQuotaSamples, consumerStartUs, capacitySamples, ...
    overrunPolicy, drainTimeoutUs, timeoutAction)
%MODEL Deterministic finite ring-buffer producer/consumer calculation.
%   This pure model treats P13-completed records as producer-ready events.
%   It owns no figures, UI, timers, hardware APIs, or persistent state.

if nargin ~= 9
    error('P14:model:Arity', 'model requires exactly nine inputs.');
end

maxSamples = 10000;
maxCapacitySamples = 100000;
maxTimelineUs = 1e12;
sourceSamples = validateSourceSamples(sourceSamples, maxSamples);
producerPeriodUs = validatePositiveTime(producerPeriodUs, ...
    'ProducerPeriod');
consumerPeriodUs = validatePositiveTime(consumerPeriodUs, ...
    'ConsumerPeriod');
consumerQuotaSamples = validatePositiveInteger(consumerQuotaSamples, ...
    'ConsumerQuota', maxSamples);
consumerStartUs = validateNonnegativeTime(consumerStartUs, ...
    'ConsumerStart');
capacitySamples = validatePositiveInteger(capacitySamples, ...
    'Capacity', maxCapacitySamples);
overrunPolicy = validatePolicy(overrunPolicy);
drainTimeoutUs = validateTimeout(drainTimeoutUs);
timeoutAction = validateTimeoutAction(timeoutAction);

sampleCount = numel(sourceSamples);
maxEventCount = 4 .* sampleCount + 32;
conservativeEndUs = consumerStartUs + ...
    (sampleCount + 2) .* (producerPeriodUs + consumerPeriodUs);
if isfinite(drainTimeoutUs)
    conservativeEndUs = conservativeEndUs + drainTimeoutUs;
end
if ~isfinite(conservativeEndUs) || conservativeEndUs > maxTimelineUs
    error('P14:model:TimelineResourceBound', ...
        'The bounded producer, consumer, and timeout horizon exceeds 1e12 us.');
end
if sampleCount > 1
    lastNominalProducerUs = (sampleCount - 1) .* producerPeriodUs;
    if ~isfinite(lastNominalProducerUs) || ...
            lastNominalProducerUs > maxTimelineUs
        error('P14:model:TimelineResourceBound', ...
            'The producer timeline exceeds the 1e12-us resource bound.');
    end
    if lastNominalProducerUs + producerPeriodUs == ...
            lastNominalProducerUs
        error('P14:model:TimingPrecision', ...
            'Producer timestamps collapse at double precision.');
    end
end
if consumerStartUs + consumerPeriodUs == consumerStartUs || ...
        conservativeEndUs + consumerPeriodUs == conservativeEndUs
    error('P14:model:TimingPrecision', ...
        'Consumer timestamps collapse at double precision.');
end

requiredCapacitySamples = finiteTraceRequiredCapacity(sampleCount, ...
    producerPeriodUs, consumerPeriodUs, consumerQuotaSamples, ...
    consumerStartUs);

reference = simulateCampaign(sourceSamples, producerPeriodUs, ...
    consumerPeriodUs, consumerQuotaSamples, consumerStartUs, ...
    capacitySamples, overrunPolicy, drainTimeoutUs, ...
    'continue-waiting', maxEventCount, maxTimelineUs);
if strcmp(timeoutAction, 'cancel-consumer') && ...
        reference.observation.wait_timed_out
    observed = simulateCampaign(sourceSamples, producerPeriodUs, ...
        consumerPeriodUs, consumerQuotaSamples, consumerStartUs, ...
        capacitySamples, overrunPolicy, drainTimeoutUs, ...
        'cancel-consumer', maxEventCount, maxTimelineUs);
else
    observed = reference;
end

producerRateSamplesPerS = 1e6 ./ producerPeriodUs;
consumerCapacitySamplesPerS = ...
    consumerQuotaSamples .* 1e6 ./ consumerPeriodUs;
offeredLoadRatio = consumerPeriodUs ./ ...
    (consumerQuotaSamples .* producerPeriodUs);
offeredLoadPct = 100 .* offeredLoadRatio;
if any(~isfinite([producerRateSamplesPerS, ...
        consumerCapacitySamplesPerS, offeredLoadRatio, offeredLoadPct])) || ...
        any([producerRateSamplesPerS, ...
        consumerCapacitySamplesPerS, offeredLoadRatio, offeredLoadPct] <= 0)
    error('P14:model:TimingPrecision', ...
        'Derived rate or load diagnostics are not positive and finite.');
end

out = observed;
out.input = struct( ...
    'source_samples', sourceSamples, ...
    'producer_period_us', producerPeriodUs, ...
    'consumer_period_us', consumerPeriodUs, ...
    'consumer_quota_samples', consumerQuotaSamples, ...
    'consumer_start_us', consumerStartUs, ...
    'capacity_samples', capacitySamples, ...
    'overrun_policy', overrunPolicy, ...
    'drain_timeout_us', drainTimeoutUs, ...
    'timeout_action', timeoutAction);
out.semantics = struct( ...
    'capacity_convention', 'all C slots are usable', ...
    'empty_rule', 'occupancy == 0', ...
    'full_rule', 'occupancy == capacity', ...
    'slot_rule', 'next = 1 + mod(current, capacity)', ...
    'equal_time_order', 'consumer, producer, then timeout', ...
    'producer_origin', 'P13-completed synthetic records', ...
    'producer_schedule_rule', ...
    'ready_i = (i-1) T_p + cumulative backpressure stall', ...
    'reference_metric_rule', ...
    'rho and required capacity use the unthrottled nominal source', ...
    'backpressure_boundary', ...
    ['valid only for a throttleable producer; no later record is ' ...
    'generated while the current write is blocked']);
out.observation.reference_campaign_completion_us = ...
    reference.observation.campaign_completion_us;
out.observation.reference_pending_count_at_timeout = ...
    reference.observation.pending_count_at_timeout;
out.metrics.producer_rate_samples_per_s = producerRateSamplesPerS;
out.metrics.consumer_capacity_samples_per_s = ...
    consumerCapacitySamplesPerS;
out.metrics.offered_load_ratio = offeredLoadRatio;
out.metrics.offered_load_pct = offeredLoadPct;
out.metrics.finite_trace_required_capacity_samples = ...
    requiredCapacitySamples;
out.metrics.long_run_rate_sustainable = offeredLoadRatio <= 1;
out.metrics.minimum_capacity_headroom_samples = ...
    capacitySamples - out.metrics.peak_occupancy_samples;
out.metrics.pointer_equality_ambiguous = ...
    out.metrics.full_pointer_equality_count > 0 && ...
    out.metrics.empty_pointer_equality_count > 0;
out.claim_boundary = [ ...
    'Deterministic simulated ring arithmetic only; not MATLAB-runtime, ' ...
    'rendered-UI, atomic-pointer, cache-coherency, ISR/task-race, DMA ' ...
    'flow-control, scheduler, bench, HIL, field, or production evidence.'];
end

function out = simulateCampaign(sourceSamples, producerPeriodUs, ...
    consumerPeriodUs, consumerQuotaSamples, consumerStartUs, ...
    capacitySamples, overrunPolicy, drainTimeoutUs, timeoutAction, ...
    maxEventCount, maxTimelineUs)
sampleCount = numel(sourceSamples);

ringSamples = nan(1, capacitySamples);
ringSourceId = nan(1, capacitySamples);
ringWriteUs = nan(1, capacitySamples);
slotValid = false(1, capacitySamples);
readSlot = 1;
writeSlot = 1;
occupancy = 0;
peakOccupancy = 0;

readyUs = nan(1, sampleCount);
decisionUs = nan(1, sampleCount);
stallUs = zeros(1, sampleCount);
accepted = false(1, sampleCount);
droppedNewest = false(1, sampleCount);
overwrittenOldest = false(1, sampleCount);
fullEncounter = false(1, sampleCount);
producerWriteSlot = nan(1, sampleCount);
producerOccupancyAfter = nan(1, sampleCount);

consumedSourceId = nan(1, sampleCount);
consumedSamples = nan(1, sampleCount);
consumedReadUs = nan(1, sampleCount);
consumedAgeUs = nan(1, sampleCount);
consumedReadSlot = nan(1, sampleCount);
consumedCount = 0;

consumerServiceUs = nan(1, maxEventCount);
consumerDrainedCount = zeros(1, maxEventCount);
consumerOccupancyBefore = zeros(1, maxEventCount);
consumerOccupancyAfter = zeros(1, maxEventCount);
consumerEventCount = 0;
emptyServiceCount = 0;

eventTimeUs = nan(1, maxEventCount);
eventCode = zeros(1, maxEventCount);
eventSourceId = zeros(1, maxEventCount);
eventOccupancyBefore = zeros(1, maxEventCount);
eventOccupancyAfter = zeros(1, maxEventCount);
eventReadSlot = zeros(1, maxEventCount);
eventWriteSlot = zeros(1, maxEventCount);
eventCount = 0;

producerIndex = 1;
readyUs(1) = 0;
nextProducerUs = 0;
producerBlocked = false;
cumulativeProducerStallUs = 0;
consumerTick = 0;
nextConsumerUs = consumerStartUs;
lastProducerDecisionUs = NaN;
lastConsumedUs = NaN;
fullPointerEqualityCount = 0;
emptyPointerEqualityCount = 1;
timeoutEvaluated = false;
waitTimedOut = false;
consumerCancelled = false;
pendingCountAtTimeout = 0;
drainDeadlineUs = Inf;
transitionCount = 0;

while true
    transitionCount = transitionCount + 1;
    if transitionCount > 8 .* maxEventCount
        error('P14:model:EventResourceBound', ...
            'The event transition ceiling was exceeded.');
    end

    producerDone = producerIndex > sampleCount;
    if producerDone && occupancy == 0
        break;
    end
    if producerDone && ~timeoutEvaluated && isfinite(drainTimeoutUs)
        drainDeadlineUs = addBoundedTime(lastProducerDecisionUs, ...
            drainTimeoutUs, 'Drain timeout', maxTimelineUs);
    end

    if ~producerDone && ~producerBlocked
        nextProducerEventUs = nextProducerUs;
    else
        nextProducerEventUs = Inf;
    end

    if occupancy == 0 && ~producerBlocked && ...
            nextConsumerUs < nextProducerEventUs
        skipped = ceil((nextProducerEventUs - nextConsumerUs) ./ ...
            consumerPeriodUs);
        if isfinite(skipped) && skipped > 0
            emptyServiceCount = emptyServiceCount + skipped;
            consumerTick = consumerTick + skipped;
            nextConsumerUs = consumerStartUs + ...
                consumerTick .* consumerPeriodUs;
            continue;
        end
    end

    if producerDone && ~timeoutEvaluated && ...
            drainDeadlineUs < nextConsumerUs
        pendingCountAtTimeout = occupancy;
        waitTimedOut = occupancy > 0;
        timeoutEvaluated = true;
        if waitTimedOut && strcmp(timeoutAction, 'cancel-consumer')
            consumerCancelled = true;
            break;
        end
        drainDeadlineUs = Inf;
        continue;
    end

    if nextConsumerUs <= nextProducerEventUs
        currentUs = nextConsumerUs;
        occupancyBefore = occupancy;
        drainCount = min(consumerQuotaSamples, occupancy);
        for drainIndex = 1:drainCount
            if ~slotValid(readSlot)
                error('P14:model:RingInvariant', ...
                    'The counted consumer selected an invalid ring slot.');
            end
            consumedCount = consumedCount + 1;
            sourceId = ringSourceId(readSlot);
            consumedSourceId(consumedCount) = sourceId;
            consumedSamples(consumedCount) = ringSamples(readSlot);
            consumedReadUs(consumedCount) = currentUs;
            consumedAgeUs(consumedCount) = ...
                currentUs - ringWriteUs(readSlot);
            consumedReadSlot(consumedCount) = readSlot;
            slotValid(readSlot) = false;
            ringSamples(readSlot) = NaN;
            ringSourceId(readSlot) = NaN;
            ringWriteUs(readSlot) = NaN;
            readSlot = advanceSlot(readSlot, capacitySamples);
            occupancy = occupancy - 1;
        end
        if drainCount == 0
            emptyServiceCount = emptyServiceCount + 1;
        else
            lastConsumedUs = currentUs;
        end
        consumerEventCount = consumerEventCount + 1;
        if consumerEventCount > numel(consumerServiceUs)
            error('P14:model:EventResourceBound', ...
                'The consumer event ceiling was exceeded.');
        end
        consumerServiceUs(consumerEventCount) = currentUs;
        consumerDrainedCount(consumerEventCount) = drainCount;
        consumerOccupancyBefore(consumerEventCount) = occupancyBefore;
        consumerOccupancyAfter(consumerEventCount) = occupancy;
        eventCount = eventCount + 1;
        if eventCount > maxEventCount
            error('P14:model:EventResourceBound', ...
                'The retained event trace ceiling was exceeded.');
        end
        eventTimeUs(eventCount) = currentUs;
        eventCode(eventCount) = 1;
        eventOccupancyBefore(eventCount) = occupancyBefore;
        eventOccupancyAfter(eventCount) = occupancy;
        eventReadSlot(eventCount) = readSlot;
        eventWriteSlot(eventCount) = writeSlot;
        if occupancy == 0 && readSlot == writeSlot
            emptyPointerEqualityCount = emptyPointerEqualityCount + 1;
        end
        consumerTick = consumerTick + 1;
        nextConsumerUs = consumerStartUs + ...
            consumerTick .* consumerPeriodUs;
        if producerBlocked && occupancy < capacitySamples
            nextProducerUs = currentUs;
            producerBlocked = false;
        end
        continue;
    end

    currentUs = nextProducerEventUs;
    occupancyBefore = occupancy;
    sourceId = producerIndex;
    if occupancy < capacitySamples
        accepted(sourceId) = true;
        decisionUs(sourceId) = currentUs;
        stallUs(sourceId) = currentUs - readyUs(sourceId);
        cumulativeProducerStallUs = cumulativeProducerStallUs + ...
            stallUs(sourceId);
        if ~isfinite(cumulativeProducerStallUs) || ...
                cumulativeProducerStallUs > maxTimelineUs
            error('P14:model:TimelineResourceBound', ...
                'Cumulative producer stall exceeds the 1e12-us resource bound.');
        end
        producerWriteSlot(sourceId) = writeSlot;
        ringSamples(writeSlot) = sourceSamples(sourceId);
        ringSourceId(writeSlot) = sourceId;
        ringWriteUs(writeSlot) = currentUs;
        slotValid(writeSlot) = true;
        writeSlot = advanceSlot(writeSlot, capacitySamples);
        occupancy = occupancy + 1;
        producerOccupancyAfter(sourceId) = occupancy;
        eventKind = 2;
        producerIndex = producerIndex + 1;
        lastProducerDecisionUs = currentUs;
        if producerIndex <= sampleCount
            readyUs(producerIndex) = anchoredProducerTime(producerIndex, ...
                producerPeriodUs, cumulativeProducerStallUs, currentUs, ...
                maxTimelineUs);
            nextProducerUs = readyUs(producerIndex);
        end
    else
        fullEncounter(sourceId) = true;
        switch overrunPolicy
            case 'drop-newest'
                droppedNewest(sourceId) = true;
                decisionUs(sourceId) = currentUs;
                producerOccupancyAfter(sourceId) = occupancy;
                eventKind = 3;
                producerIndex = producerIndex + 1;
                lastProducerDecisionUs = currentUs;
                if producerIndex <= sampleCount
                    readyUs(producerIndex) = anchoredProducerTime( ...
                        producerIndex, producerPeriodUs, ...
                        cumulativeProducerStallUs, currentUs, ...
                        maxTimelineUs);
                    nextProducerUs = readyUs(producerIndex);
                end
            case 'overwrite-oldest'
                evictedSourceId = ringSourceId(readSlot);
                overwrittenOldest(evictedSourceId) = true;
                slotValid(readSlot) = false;
                readSlot = advanceSlot(readSlot, capacitySamples);
                occupancy = occupancy - 1;
                accepted(sourceId) = true;
                decisionUs(sourceId) = currentUs;
                producerWriteSlot(sourceId) = writeSlot;
                ringSamples(writeSlot) = sourceSamples(sourceId);
                ringSourceId(writeSlot) = sourceId;
                ringWriteUs(writeSlot) = currentUs;
                slotValid(writeSlot) = true;
                writeSlot = advanceSlot(writeSlot, capacitySamples);
                occupancy = occupancy + 1;
                producerOccupancyAfter(sourceId) = occupancy;
                eventKind = 4;
                producerIndex = producerIndex + 1;
                lastProducerDecisionUs = currentUs;
                if producerIndex <= sampleCount
                    readyUs(producerIndex) = anchoredProducerTime( ...
                        producerIndex, producerPeriodUs, ...
                        cumulativeProducerStallUs, currentUs, ...
                        maxTimelineUs);
                    nextProducerUs = readyUs(producerIndex);
                end
            case 'backpressure'
                producerBlocked = true;
                nextProducerUs = Inf;
                eventKind = 5;
            otherwise
                error('P14:model:Policy', 'Unexpected overrun policy.');
        end
    end

    peakOccupancy = max(peakOccupancy, occupancy);
    if occupancy == capacitySamples && readSlot == writeSlot
        fullPointerEqualityCount = fullPointerEqualityCount + 1;
    end
    eventCount = eventCount + 1;
    if eventCount > maxEventCount
        error('P14:model:EventResourceBound', ...
            'The retained event trace ceiling was exceeded.');
    end
    eventTimeUs(eventCount) = currentUs;
    eventCode(eventCount) = eventKind;
    eventSourceId(eventCount) = sourceId;
    eventOccupancyBefore(eventCount) = occupancyBefore;
    eventOccupancyAfter(eventCount) = occupancy;
    eventReadSlot(eventCount) = readSlot;
    eventWriteSlot(eventCount) = writeSlot;
end

if ~isfinite(drainDeadlineUs) && isfinite(drainTimeoutUs)
    drainDeadlineUs = addBoundedTime(lastProducerDecisionUs, ...
        drainTimeoutUs, 'Drain timeout', maxTimelineUs);
end
campaignComplete = producerIndex > sampleCount && occupancy == 0;
if campaignComplete
    if isnan(lastConsumedUs)
        campaignCompletionUs = lastProducerDecisionUs;
    else
        campaignCompletionUs = max(lastProducerDecisionUs, lastConsumedUs);
    end
else
    campaignCompletionUs = NaN;
end

pendingSourceId = nan(1, occupancy);
pendingSamples = nan(1, occupancy);
pendingSlot = nan(1, occupancy);
scanSlot = readSlot;
for pendingIndex = 1:occupancy
    if ~slotValid(scanSlot)
        error('P14:model:RingInvariant', ...
            'Pending FIFO traversal found an invalid ring slot.');
    end
    pendingSourceId(pendingIndex) = ringSourceId(scanSlot);
    pendingSamples(pendingIndex) = ringSamples(scanSlot);
    pendingSlot(pendingIndex) = scanSlot;
    scanSlot = advanceSlot(scanSlot, capacitySamples);
end

consumedSourceId = consumedSourceId(1:consumedCount);
consumedSamples = consumedSamples(1:consumedCount);
consumedReadUs = consumedReadUs(1:consumedCount);
consumedAgeUs = consumedAgeUs(1:consumedCount);
consumedReadSlot = consumedReadSlot(1:consumedCount);
consumerServiceUs = consumerServiceUs(1:consumerEventCount);
consumerDrainedCount = consumerDrainedCount(1:consumerEventCount);
consumerOccupancyBefore = ...
    consumerOccupancyBefore(1:consumerEventCount);
consumerOccupancyAfter = ...
    consumerOccupancyAfter(1:consumerEventCount);

consumedMask = false(1, sampleCount);
consumedMask(consumedSourceId) = true;
pendingMask = false(1, sampleCount);
pendingMask(pendingSourceId) = true;
classificationCount = double(consumedMask) + double(pendingMask) + ...
    double(droppedNewest) + double(overwrittenOldest);
conservationErrorSamples = sampleCount - ...
    (consumedCount + occupancy + sum(droppedNewest) + ...
    sum(overwrittenOldest));
if any(classificationCount ~= 1) || conservationErrorSamples ~= 0 || ...
        occupancy ~= sum(slotValid) || occupancy < 0 || ...
        occupancy > capacitySamples
    error('P14:model:RingInvariant', ...
        'Source classification, occupancy, or storage conservation failed.');
end
if any(diff(consumedSourceId) <= 0) || ...
        ~isequal(consumedSamples, sourceSamples(consumedSourceId))
    error('P14:model:FifoInvariant', ...
        'Consumed survivors must retain source identity, value, and FIFO order.');
end

if isempty(consumedAgeUs)
    minimumAgeUs = NaN;
    meanAgeUs = NaN;
    maximumAgeUs = NaN;
else
    minimumAgeUs = min(consumedAgeUs);
    meanAgeUs = mean(consumedAgeUs);
    maximumAgeUs = max(consumedAgeUs);
end
if numel(consumedSourceId) < 2
    internalGapCount = 0;
else
    internalGapCount = sum(max(diff(consumedSourceId) - 1, 0));
end

out.producer = struct( ...
    'source_id', 1:sampleCount, ...
    'source_samples', sourceSamples, ...
    'ready_us', readyUs, ...
    'decision_us', decisionUs, ...
    'stall_us', stallUs, ...
    'accepted', accepted, ...
    'dropped_newest', droppedNewest, ...
    'overwritten_oldest', overwrittenOldest, ...
    'full_encounter', fullEncounter, ...
    'write_slot', producerWriteSlot, ...
    'occupancy_after', producerOccupancyAfter);
out.consumer = struct( ...
    'service_us', consumerServiceUs, ...
    'drained_count', consumerDrainedCount, ...
    'occupancy_before', consumerOccupancyBefore, ...
    'occupancy_after', consumerOccupancyAfter, ...
    'consumed_source_id', consumedSourceId, ...
    'consumed_samples', consumedSamples, ...
    'read_us', consumedReadUs, ...
    'age_us', consumedAgeUs, ...
    'read_slot', consumedReadSlot, ...
    'empty_service_count', emptyServiceCount);
out.ring = struct( ...
    'event_time_us', eventTimeUs(1:eventCount), ...
    'event_code', eventCode(1:eventCount), ...
    'event_source_id', eventSourceId(1:eventCount), ...
    'occupancy_before', eventOccupancyBefore(1:eventCount), ...
    'occupancy_after', eventOccupancyAfter(1:eventCount), ...
    'read_slot_after', eventReadSlot(1:eventCount), ...
    'write_slot_after', eventWriteSlot(1:eventCount), ...
    'final_samples_by_slot', ringSamples, ...
    'final_source_id_by_slot', ringSourceId, ...
    'final_valid_slot', slotValid, ...
    'final_read_slot', readSlot, ...
    'final_write_slot', writeSlot, ...
    'final_occupancy_samples', occupancy, ...
    'pending_source_id', pendingSourceId, ...
    'pending_samples', pendingSamples, ...
    'pending_slot', pendingSlot);
out.observation = struct( ...
    'last_producer_decision_us', lastProducerDecisionUs, ...
    'drain_deadline_us', drainDeadlineUs, ...
    'wait_timed_out', waitTimedOut, ...
    'consumer_cancelled', consumerCancelled, ...
    'pending_count_at_timeout', pendingCountAtTimeout, ...
    'campaign_complete', campaignComplete, ...
    'campaign_completion_us', campaignCompletionUs, ...
    'timeout_boundary_order', ...
    'consumer and producer events at equality precede timeout');
out.metrics = struct( ...
    'sample_count', sampleCount, ...
    'capacity_samples', capacitySamples, ...
    'accepted_write_count', sum(accepted), ...
    'consumed_count', consumedCount, ...
    'pending_count', occupancy, ...
    'dropped_newest_count', sum(droppedNewest), ...
    'overwritten_oldest_count', sum(overwrittenOldest), ...
    'data_loss_count', sum(droppedNewest) + sum(overwrittenOldest), ...
    'full_write_encounter_count', sum(fullEncounter), ...
    'producer_stall_event_count', sum(stallUs > 0), ...
    'total_producer_stall_us', sum(stallUs), ...
    'peak_occupancy_samples', peakOccupancy, ...
    'minimum_age_us', minimumAgeUs, ...
    'mean_age_us', meanAgeUs, ...
    'maximum_age_us', maximumAgeUs, ...
    'internal_consumed_gap_count', internalGapCount, ...
    'fifo_order_preserved', all(diff(consumedSourceId) > 0), ...
    'source_conservation_error_samples', conservationErrorSamples, ...
    'full_pointer_equality_count', fullPointerEqualityCount, ...
    'empty_pointer_equality_count', emptyPointerEqualityCount, ...
    'occupancy_bound_respected', ...
    all(eventOccupancyAfter(1:eventCount) >= 0 & ...
    eventOccupancyAfter(1:eventCount) <= capacitySamples));
end

function requiredCapacity = finiteTraceRequiredCapacity(sampleCount, ...
    producerPeriodUs, consumerPeriodUs, consumerQuotaSamples, ...
    consumerStartUs)
producerIndex = 1;
producerUs = 0;
consumerTick = 0;
consumerUs = consumerStartUs;
occupancy = 0;
requiredCapacity = 0;
while producerIndex <= sampleCount
    if occupancy == 0 && consumerUs < producerUs
        skipped = ceil((producerUs - consumerUs) ./ consumerPeriodUs);
        consumerTick = consumerTick + skipped;
        consumerUs = consumerStartUs + ...
            consumerTick .* consumerPeriodUs;
    elseif consumerUs <= producerUs
        occupancy = max(0, occupancy - consumerQuotaSamples);
        consumerTick = consumerTick + 1;
        consumerUs = consumerStartUs + ...
            consumerTick .* consumerPeriodUs;
    else
        occupancy = occupancy + 1;
        requiredCapacity = max(requiredCapacity, occupancy);
        producerIndex = producerIndex + 1;
        producerUs = (producerIndex - 1) .* producerPeriodUs;
    end
end
end

function slot = advanceSlot(slot, capacitySamples)
slot = 1 + mod(slot, capacitySamples);
end

function readyUs = anchoredProducerTime(sourceId, producerPeriodUs, ...
    cumulativeProducerStallUs, previousDecisionUs, maxTimelineUs)
nominalReadyUs = (sourceId - 1) .* producerPeriodUs;
readyUs = nominalReadyUs + cumulativeProducerStallUs;
if ~isfinite(readyUs) || readyUs > maxTimelineUs
    error('P14:model:TimelineResourceBound', ...
        'The producer timeline exceeds the 1e12-us resource bound.');
end
if readyUs <= previousDecisionUs
    error('P14:model:TimingPrecision', ...
        'Producer timestamps do not advance at double precision.');
end
end

function nextUs = addBoundedTime(currentUs, deltaUs, label, maxTimelineUs)
nextUs = currentUs + deltaUs;
if ~isfinite(nextUs) || nextUs > maxTimelineUs
    error('P14:model:TimelineResourceBound', ...
        '%s advances beyond the 1e12-us resource bound.', label);
end
if deltaUs > 0 && nextUs == currentUs
    error('P14:model:TimingPrecision', ...
        '%s collapses to zero at double precision.', label);
end
end

function values = validateSourceSamples(values, maximum)
valid = isnumeric(values) && ~islogical(values) && isreal(values) && ...
    isvector(values) && ~isempty(values) && all(isfinite(values(:)));
if ~valid
    error('P14:model:SourceSamples', ...
        'sourceSamples must be a nonempty finite real numeric vector.');
end
if numel(values) > maximum
    error('P14:model:SampleResourceBound', ...
        'sourceSamples exceeds the 10,000-sample resource bound.');
end
if isa(values, 'uint64') && any(values(:) > uint64(flintmax))
    error('P14:model:SourcePrecision', ...
        'uint64 source identities above flintmax cannot normalize exactly.');
end
if isa(values, 'int64') && ...
        (any(values(:) > int64(flintmax)) || ...
        any(values(:) < -int64(flintmax)))
    error('P14:model:SourcePrecision', ...
        'int64 source identities outside +/-flintmax cannot normalize exactly.');
end
values = double(values(:)');
if any(abs(values) > flintmax)
    error('P14:model:SourcePrecision', ...
        'Source values outside +/-flintmax cannot retain identity.');
end
end

function value = validatePositiveTime(value, label)
if ~(isnumeric(value) && ~islogical(value) && isreal(value) && ...
        isscalar(value) && isfinite(value) && value > 0)
    error(['P14:model:' label], ...
        '%s must be a positive finite real numeric scalar.', label);
end
value = double(value);
end

function value = validateNonnegativeTime(value, label)
if ~(isnumeric(value) && ~islogical(value) && isreal(value) && ...
        isscalar(value) && isfinite(value) && value >= 0)
    error(['P14:model:' label], ...
        '%s must be a nonnegative finite real numeric scalar.', label);
end
value = double(value);
end

function value = validatePositiveInteger(value, label, maximum)
if ~(isnumeric(value) && ~islogical(value) && isreal(value) && ...
        isscalar(value) && isfinite(value) && value >= 1 && ...
        value == fix(value))
    error(['P14:model:' label], ...
        '%s must be a positive integer scalar.', label);
end
if value > maximum
    error(['P14:model:' label 'ResourceBound'], ...
        '%s exceeds its declared resource bound of %d.', label, maximum);
end
value = double(value);
end

function policy = validatePolicy(policy)
if isempty(policy)
    policy = 'drop-newest';
end
if ~(ischar(policy) || (isstring(policy) && isscalar(policy)))
    error('P14:model:Policy', ...
        'overrunPolicy must be a character vector or scalar string.');
end
policy = lower(strtrim(char(policy)));
if ~any(strcmp(policy, ...
        {'drop-newest', 'overwrite-oldest', 'backpressure'}))
    error('P14:model:Policy', ...
        'Policy must be drop-newest, overwrite-oldest, or backpressure.');
end
end

function timeoutUs = validateTimeout(timeoutUs)
if isempty(timeoutUs)
    timeoutUs = Inf;
end
valid = isnumeric(timeoutUs) && ~islogical(timeoutUs) && ...
    isreal(timeoutUs) && isscalar(timeoutUs) && ...
    ~isnan(timeoutUs) && timeoutUs >= 0;
if ~valid
    error('P14:model:DrainTimeout', ...
        'drainTimeoutUs must be nonnegative; Inf disables timeout.');
end
timeoutUs = double(timeoutUs);
end

function action = validateTimeoutAction(action)
if isempty(action)
    action = 'continue-waiting';
end
if ~(ischar(action) || (isstring(action) && isscalar(action)))
    error('P14:model:TimeoutAction', ...
        'timeoutAction must be a character vector or scalar string.');
end
action = lower(strtrim(char(action)));
if ~any(strcmp(action, {'continue-waiting', 'cancel-consumer'}))
    error('P14:model:TimeoutAction', ...
        'Timeout action must be continue-waiting or cancel-consumer.');
end
end
