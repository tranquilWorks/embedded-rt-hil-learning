function out = model(payloadBytes, txBaudBps, receiverErrorPct, ...
    parityMode, stopBits, interFrameGapBits, fault, receiveTimeoutUs)
%MODEL Frame bytes on an asynchronous UART line and sample them explicitly.
%   Each frame is idle-high, one low start bit, eight data bits sent least
%   significant bit first, optional parity, and one or two high stop bits.
%   The receiver detects qualified transmitter start edges and samples each
%   slot at the center predicted by its own baud clock.
%
%   receiverErrorPct defines
%       receiver baud = txBaudBps * (1 + receiverErrorPct / 100).
%   interFrameGapBits is high-idle time between frames in transmitter-bit
%   units. receiveTimeoutUs is an absolute deterministic receive deadline,
%   not an asynchronous wait. Pass [] or omit the last two inputs for no
%   fault and an infinite deadline.

if nargin < 6 || nargin > 8
    error('P05:model:Arity', ...
        ['Expected payloadBytes, txBaudBps, receiverErrorPct, parityMode, ' ...
        'stopBits, interFrameGapBits, and optional fault and receiveTimeoutUs.']);
end
if nargin < 7 || isempty(fault)
    fault = defaultFault();
end
if nargin < 8 || isempty(receiveTimeoutUs)
    receiveTimeoutUs = Inf;
end

maxFrames = 100000;
maxLineBitCells = 1000000;
maxSamplePoints = 1000000;
frameCount = numel(payloadBytes);
if frameCount > maxFrames
    error('P05:model:ResourceBound', ...
        'At most one hundred thousand payload bytes are allowed.');
end
payloadBytes = validatePayload(payloadBytes);
txBaudBps = validateScalar(txBaudBps, 'P05:model:BaudRate', ...
    'txBaudBps');
if txBaudBps < 1 || txBaudBps > 1e9
    error('P05:model:BaudRate', ...
        'txBaudBps must lie in [1, 1e9] bits per second.');
end
receiverErrorPct = validateScalar(receiverErrorPct, ...
    'P05:model:ReceiverError', 'receiverErrorPct');
if receiverErrorPct <= -40 || receiverErrorPct >= 40
    error('P05:model:ReceiverError', ...
        'receiverErrorPct must lie strictly between -40 and 40 percent.');
end
parityMode = validateParityMode(parityMode);
stopBits = validateScalar(stopBits, 'P05:model:StopBits', 'stopBits');
if stopBits ~= round(stopBits) || ~any(stopBits == [1 2])
    error('P05:model:StopBits', 'stopBits must be the integer 1 or 2.');
end
interFrameGapBits = validateScalar(interFrameGapBits, ...
    'P05:model:InterFrameGap', 'interFrameGapBits');
if interFrameGapBits < 0 || interFrameGapBits > 1000
    error('P05:model:InterFrameGap', ...
        'interFrameGapBits must lie in [0, 1000] transmitter-bit times.');
end
receiveTimeoutUs = validateTimeout(receiveTimeoutUs);
fault = validateFault(fault, frameCount);

parityBitCount = double(~strcmp(parityMode, 'none'));
bitsPerFrame = 1 + 8 + parityBitCount + stopBits;
samplePointCount = frameCount .* bitsPerFrame;
lineBitCells = frameCount .* bitsPerFrame + ...
    max(0, frameCount - 1) .* interFrameGapBits;
if samplePointCount > maxSamplePoints || lineBitCells > maxLineBitCells
    error('P05:model:ResourceBound', ...
        ['Frame samples and transmitter-bit cells must each remain at or ' ...
        'below one million.']);
end

receiverBaudBps = txBaudBps .* (1 + receiverErrorPct ./ 100);
txBitPeriodUs = 1e6 ./ txBaudBps;
receiverBitPeriodUs = 1e6 ./ receiverBaudBps;
frameStrideBits = bitsPerFrame + interFrameGapBits;
if frameCount == 0
    lineTimeUs = 0;
else
    lineTimeUs = ((frameCount - 1) .* frameStrideBits + bitsPerFrame) .* ...
        txBitPeriodUs;
end
if ~isfinite(txBitPeriodUs) || ~isfinite(receiverBitPeriodUs) || ...
        ~isfinite(lineTimeUs)
    error('P05:model:TimingResourceBound', ...
        'The configured baud and frame count must produce finite times.');
end

nominalFrameBits = zeros(frameCount, bitsPerFrame);
for bitIndex = 0:7
    nominalFrameBits(:, 2 + bitIndex) = ...
        mod(floor(payloadBytes(:) ./ (2 .^ bitIndex)), 2);
end
parityColumn = [];
if parityBitCount == 1
    parityColumn = 10;
    dataOnesParity = mod(sum(nominalFrameBits(:, 2:9), 2), 2);
    if strcmp(parityMode, 'even')
        nominalFrameBits(:, parityColumn) = dataOnesParity;
    else
        nominalFrameBits(:, parityColumn) = 1 - dataOnesParity;
    end
end
stopColumns = (bitsPerFrame - stopBits + 1):bitsPerFrame;
nominalFrameBits(:, stopColumns) = 1;
actualFrameBits = nominalFrameBits;
if strcmp(fault.mode, 'flip-data')
    for faultBit = fault.data_bit_indices
        column = 2 + faultBit;
        actualFrameBits(fault.frame_index, column) = ...
            1 - actualFrameBits(fault.frame_index, column);
    end
elseif strcmp(fault.mode, 'force-stop-low')
    actualFrameBits(fault.frame_index, stopColumns) = 0;
end

frameStartBits = (0:(frameCount - 1)) .* frameStrideBits;
frameStartUs = frameStartBits .* txBitPeriodUs;
frameEndUs = frameStartUs + bitsPerFrame .* txBitPeriodUs;
startEdgeAvailable = true(1, frameCount);
for frameIndex = 2:frameCount
    startEdgeAvailable(frameIndex) = interFrameGapBits > 0 || ...
        actualFrameBits(frameIndex - 1, end) == 1;
end

sampleOffsets = (0:(bitsPerFrame - 1)) + 0.5;
receiverSamplePositionsBits = sampleOffsets .* ...
    (txBaudBps ./ receiverBaudBps);
slotStarts = 0:(bitsPerFrame - 1);
slotEnds = 1:bitsPerFrame;
samplingMarginBits = min(receiverSamplePositionsBits - slotStarts, ...
    slotEnds - receiverSamplePositionsBits);
marginToleranceBits = 32 .* eps(max(1, ...
    max(abs(receiverSamplePositionsBits))));
timingSafe = all(samplingMarginBits > marginToleranceBits);
if frameCount == 0
    scheduledSampleTimeUs = zeros(0, bitsPerFrame);
else
    scheduledSampleTimeUs = frameStartUs(:) + ...
        receiverBitPeriodUs .* sampleOffsets;
end
sampleTimeUs = nan(frameCount, bitsPerFrame);
sampleLevel = nan(frameCount, bitsPerFrame);
attempted = false(1, frameCount);
timedOut = false(1, frameCount);
noStartEdge = false(1, frameCount);
receiverBusy = false(1, frameCount);
startSampleError = false(1, frameCount);
parityError = false(1, frameCount);
framingError = false(1, frameCount);
decodedBytes = nan(1, frameCount);
receiverReadySourceFrameIndex = NaN;

for frameIndex = 1:frameCount
    completionUs = scheduledSampleTimeUs(frameIndex, end);
    if isfinite(receiveTimeoutUs)
        timeoutToleranceUs = 16 .* eps(max([1, abs(completionUs), ...
            abs(receiveTimeoutUs)]));
        if completionUs > receiveTimeoutUs + timeoutToleranceUs
            timedOut(frameIndex) = true;
            continue;
        end
    end
    if ~startEdgeAvailable(frameIndex)
        noStartEdge(frameIndex) = true;
        continue;
    end
    if ~isnan(receiverReadySourceFrameIndex)
        elapsedFromReadySourceBits = ...
            (frameIndex - receiverReadySourceFrameIndex) .* frameStrideBits;
        readyToleranceBits = 16 .* eps(max([1, ...
            abs(elapsedFromReadySourceBits), ...
            abs(receiverSamplePositionsBits(end))]));
        if elapsedFromReadySourceBits < ...
                receiverSamplePositionsBits(end) - readyToleranceBits
            receiverBusy(frameIndex) = true;
            continue;
        end
    end

    attempted(frameIndex) = true;
    sampleTimeUs(frameIndex, :) = scheduledSampleTimeUs(frameIndex, :);
    sampleLevel(frameIndex, :) = lineLevelAt(frameIndex, ...
        receiverSamplePositionsBits, actualFrameBits, frameStrideBits, ...
        bitsPerFrame);
    receiverReadySourceFrameIndex = frameIndex;

    startSampleError(frameIndex) = sampleLevel(frameIndex, 1) ~= 0;
    sampledDataBits = sampleLevel(frameIndex, 2:9);
    decodedBytes(frameIndex) = sum(sampledDataBits .* (2 .^ (0:7)));
    if parityBitCount == 1
        sampledDataParity = mod(sum(sampledDataBits), 2);
        if strcmp(parityMode, 'even')
            expectedParity = sampledDataParity;
        else
            expectedParity = 1 - sampledDataParity;
        end
        parityError(frameIndex) = ...
            sampleLevel(frameIndex, parityColumn) ~= expectedParity;
    end
    framingError(frameIndex) = ...
        any(sampleLevel(frameIndex, stopColumns) ~= 1);
end

missedStart = noStartEdge | receiverBusy;
byteValid = attempted & ~startSampleError & ~parityError & ~framingError;
byteCorrect = byteValid & decodedBytes == payloadBytes;
undetectedCorruption = byteValid & decodedBytes ~= payloadBytes;
failed = ~byteCorrect;
firstFailureIndex = find(failed, 1, 'first');
recoveryFrameIndex = [];
if ~isempty(firstFailureIndex)
    recoveryOffset = find(byteCorrect((firstFailureIndex + 1):end), 1, 'first');
    if ~isempty(recoveryOffset)
        recoveryFrameIndex = firstFailureIndex + recoveryOffset;
    end
end
if isempty(firstFailureIndex)
    firstFailureIndex = NaN;
end
if isempty(recoveryFrameIndex)
    recoveryFrameIndex = NaN;
end

if lineBitCells > 0
    payloadEfficiency = frameCount .* 8 ./ lineBitCells;
else
    payloadEfficiency = NaN;
end
if lineTimeUs > 0
    payloadGoodputBps = sum(byteCorrect) .* 8 ./ (lineTimeUs .* 1e-6);
else
    payloadGoodputBps = NaN;
end
if frameCount == 0
    minimumSamplingMarginBits = NaN;
else
    minimumSamplingMarginBits = min(samplingMarginBits);
end

out = struct();
out.input = struct( ...
    'payload_bytes', payloadBytes, ...
    'frame_count', frameCount);
out.config = struct( ...
    'tx_baud_bps', txBaudBps, ...
    'receiver_error_pct', receiverErrorPct, ...
    'receiver_baud_bps', receiverBaudBps, ...
    'tx_bit_period_us', txBitPeriodUs, ...
    'receiver_bit_period_us', receiverBitPeriodUs, ...
    'parity_mode', parityMode, ...
    'parity_bit_count', parityBitCount, ...
    'stop_bits', stopBits, ...
    'inter_frame_gap_bits', interFrameGapBits, ...
    'bits_per_frame', bitsPerFrame, ...
    'frame_stride_bits', frameStrideBits, ...
    'receive_timeout_us', receiveTimeoutUs, ...
    'fault', fault);
out.tx = struct( ...
    'nominal_frame_bits', nominalFrameBits, ...
    'actual_frame_bits', actualFrameBits, ...
    'frame_start_us', frameStartUs, ...
    'frame_end_us', frameEndUs, ...
    'start_edge_available', startEdgeAvailable, ...
    'line_bit_cells', lineBitCells, ...
    'line_time_us', lineTimeUs);
out.rx = struct( ...
    'slot_sample_offset', sampleOffsets, ...
    'sample_position_tx_bits', receiverSamplePositionsBits, ...
    'sampling_margin_bits', samplingMarginBits, ...
    'scheduled_sample_time_us', scheduledSampleTimeUs, ...
    'sample_time_us', sampleTimeUs, ...
    'sample_level', sampleLevel, ...
    'attempted', attempted, ...
    'timed_out', timedOut, ...
    'no_start_edge', noStartEdge, ...
    'receiver_busy', receiverBusy, ...
    'missed_start', missedStart, ...
    'start_sample_error', startSampleError, ...
    'parity_error', parityError, ...
    'framing_error', framingError, ...
    'decoded_bytes', decodedBytes, ...
    'byte_valid', byteValid, ...
    'byte_correct', byteCorrect, ...
    'undetected_corruption', undetectedCorruption);
out.metrics = struct( ...
    'attempted_count', sum(attempted), ...
    'valid_count', sum(byteValid), ...
    'correct_count', sum(byteCorrect), ...
    'timed_out_count', sum(timedOut), ...
    'missed_start_count', sum(missedStart), ...
    'no_start_edge_count', sum(noStartEdge), ...
    'receiver_busy_count', sum(receiverBusy), ...
    'start_sample_error_count', sum(startSampleError), ...
    'parity_error_count', sum(parityError), ...
    'framing_error_count', sum(framingError), ...
    'undetected_corruption_count', sum(undetectedCorruption), ...
    'minimum_sampling_margin_bits', minimumSamplingMarginBits, ...
    'pattern_independent_timing_safe', timingSafe && frameCount > 0, ...
    'nominal_frame_efficiency', 8 ./ bitsPerFrame, ...
    'payload_efficiency', payloadEfficiency, ...
    'payload_goodput_bps', payloadGoodputBps, ...
    'first_failure_index', firstFailureIndex, ...
    'recovery_frame_index', recoveryFrameIndex);
out.claim_boundary = [ ...
    'Deterministic synthetic UART logic levels and idealized start-edge ' ...
    'qualification; not a hardware measurement.'];
end

function payloadBytes = validatePayload(payloadBytes)
validType = isnumeric(payloadBytes) && isreal(payloadBytes) && ...
    (isvector(payloadBytes) || isempty(payloadBytes));
if ~validType
    error('P05:model:PayloadBytes', ...
        'payloadBytes must be a real numeric vector.');
end
payloadBytes = reshape(double(payloadBytes), 1, []);
if any(~isfinite(payloadBytes)) || any(payloadBytes ~= round(payloadBytes)) || ...
        any(payloadBytes < 0) || any(payloadBytes > 255)
    error('P05:model:PayloadBytes', ...
        'payloadBytes values must be finite integers in [0, 255].');
end
end

function value = validateScalar(value, identifier, label)
validValue = isnumeric(value) && isreal(value) && isscalar(value) && ...
    isfinite(value);
if ~validValue
    error(identifier, '%s must be a finite real numeric scalar.', label);
end
value = double(value);
end

function parityMode = validateParityMode(parityMode)
if ~(ischar(parityMode) || (isstring(parityMode) && isscalar(parityMode)))
    error('P05:model:ParityMode', ...
        'parityMode must be none, even, or odd.');
end
parityMode = lower(strtrim(char(parityMode)));
if ~any(strcmp(parityMode, {'none', 'even', 'odd'}))
    error('P05:model:ParityMode', ...
        'parityMode must be none, even, or odd.');
end
end

function receiveTimeoutUs = validateTimeout(receiveTimeoutUs)
validType = isnumeric(receiveTimeoutUs) && isreal(receiveTimeoutUs) && ...
    isscalar(receiveTimeoutUs);
validValue = validType && ...
    ((isfinite(receiveTimeoutUs) && receiveTimeoutUs >= 0) || ...
    (isinf(receiveTimeoutUs) && receiveTimeoutUs > 0));
if ~validValue
    error('P05:model:ReceiveTimeout', ...
        'receiveTimeoutUs must be nonnegative and finite, or positive Inf.');
end
receiveTimeoutUs = double(receiveTimeoutUs);
end

function fault = defaultFault()
fault = struct( ...
    'mode', 'none', ...
    'frame_index', 0, ...
    'data_bit_indices', []);
end

function fault = validateFault(fault, frameCount)
if isempty(fault)
    fault = defaultFault();
    return;
end
if ~isstruct(fault) || ~isscalar(fault) || ~isfield(fault, 'mode')
    error('P05:model:Fault', ...
        'fault must be a scalar struct with a mode field.');
end
allowedFields = {'mode', 'frame_index', 'data_bit_indices'};
if any(~ismember(fieldnames(fault), allowedFields))
    error('P05:model:Fault', 'fault contains an unsupported field.');
end
mode = fault.mode;
if ~(ischar(mode) || (isstring(mode) && isscalar(mode)))
    error('P05:model:Fault', 'fault.mode must be scalar text.');
end
mode = lower(strtrim(char(mode)));
if ~any(strcmp(mode, {'none', 'flip-data', 'force-stop-low'}))
    error('P05:model:Fault', ...
        'fault.mode must be none, flip-data, or force-stop-low.');
end
normalized = defaultFault();
normalized.mode = mode;
if strcmp(mode, 'none')
    fault = normalized;
    return;
end
if ~isfield(fault, 'frame_index')
    error('P05:model:FaultFrame', ...
        'An active fault requires frame_index.');
end
frameIndex = fault.frame_index;
validFrame = isnumeric(frameIndex) && isreal(frameIndex) && ...
    isscalar(frameIndex) && isfinite(frameIndex) && ...
    frameIndex == round(frameIndex) && frameIndex >= 1 && ...
    frameIndex <= frameCount;
if ~validFrame
    error('P05:model:FaultFrame', ...
        'fault.frame_index must identify one payload frame.');
end
normalized.frame_index = double(frameIndex);
if strcmp(mode, 'flip-data')
    if ~isfield(fault, 'data_bit_indices')
        error('P05:model:FaultBit', ...
            'A flip-data fault requires data_bit_indices.');
    end
    bitIndices = fault.data_bit_indices;
    validBits = isnumeric(bitIndices) && isreal(bitIndices) && ...
        isvector(bitIndices) && ~isempty(bitIndices);
    if ~validBits
        error('P05:model:FaultBit', ...
            'data_bit_indices must be a nonempty numeric vector.');
    end
    if numel(bitIndices) > 8
        error('P05:model:ResourceBound', ...
            'A flip-data fault accepts at most eight data-bit indices.');
    end
    bitIndices = reshape(double(bitIndices), 1, []);
    if any(~isfinite(bitIndices)) || any(bitIndices ~= round(bitIndices)) || ...
            any(bitIndices < 0) || any(bitIndices > 7) || ...
            numel(unique(bitIndices)) ~= numel(bitIndices)
        error('P05:model:FaultBit', ...
            'data_bit_indices must be unique integers in [0, 7].');
    end
    normalized.data_bit_indices = bitIndices;
elseif isfield(fault, 'data_bit_indices') && ~isempty(fault.data_bit_indices)
    error('P05:model:FaultBit', ...
        'force-stop-low does not accept data_bit_indices.');
end
fault = normalized;
end

function levels = lineLevelAt(sourceFrameIndex, localSamplePositionsBits, ...
    frameBits, frameStrideBits, bitsPerFrame)
% Half-open transmitter bit cells make an exact boundary read the new bit.
% Resolve each lookup from its source frame and bounded local offset. This
% avoids absolute-time cancellation and frame-index-scaled tolerances.
levels = ones(size(localSamplePositionsBits));
frameCount = size(frameBits, 1);
for sampleIndex = 1:numel(localSamplePositionsBits)
    localSampleBits = localSamplePositionsBits(sampleIndex);
    if localSampleBits < 0
        continue;
    end
    relativeFrame = localSampleBits ./ frameStrideBits;
    relativeFrame = normalizeNearInteger(relativeFrame);
    frameOffset = floor(relativeFrame);
    targetFrameIndex = sourceFrameIndex + frameOffset;
    if targetFrameIndex < 1 || targetFrameIndex > frameCount
        continue;
    end
    targetLocalBits = localSampleBits - frameOffset .* frameStrideBits;
    targetLocalBits = normalizeNearInteger(targetLocalBits);
    if targetLocalBits < 0 || targetLocalBits >= bitsPerFrame
        continue;
    end
    bitColumn = floor(targetLocalBits) + 1;
    levels(sampleIndex) = frameBits(targetFrameIndex, bitColumn);
end
end

function value = normalizeNearInteger(value)
nearest = round(value);
tolerance = 8 .* eps(max(1, abs(value)));
if abs(value - nearest) <= tolerance
    value = nearest;
end
end
