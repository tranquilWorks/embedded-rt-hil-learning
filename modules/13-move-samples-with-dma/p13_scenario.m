function input = p13_scenario(name, blockSamples, busRateBytesPerUs, ...
    samplePeriodUs, arbitrationUs, completionIsrCpuUs, ...
    processorCopyCpuUsPerSample, varargin)
%P13_SCENARIO Build bounded, seedless DMA sample-movement fixtures.

if nargin < 1 || isempty(name)
    name = 'baseline';
end
if nargin < 2 || isempty(blockSamples)
    blockSamples = 8;
end
if nargin < 3 || isempty(busRateBytesPerUs)
    busRateBytesPerUs = 0.2;
end
if nargin < 4 || isempty(samplePeriodUs)
    samplePeriodUs = 50;
end
if nargin < 5 || isempty(arbitrationUs)
    arbitrationUs = 1;
end
if nargin < 6 || isempty(completionIsrCpuUs)
    completionIsrCpuUs = 3;
end
if nargin < 7 || isempty(processorCopyCpuUsPerSample)
    processorCopyCpuUsPerSample = 4;
end
if ~isempty(varargin)
    error('P13:scenario:Arity', ...
        'No arguments are accepted after processorCopyCpuUsPerSample.');
end

name = normalizeName(name);
blockSamples = boundedScalar(blockSamples, 1, 1e6, ...
    'P13:scenario:BlockSamples', 'blockSamples');
if blockSamples ~= floor(blockSamples)
    error('P13:scenario:BlockSamples', ...
        'blockSamples must be an integer.');
end
busRateBytesPerUs = boundedScalar(busRateBytesPerUs, 0.001, 10, ...
    'P13:scenario:BusRate', 'busRateBytesPerUs');
samplePeriodUs = boundedScalar(samplePeriodUs, 1, 1e6, ...
    'P13:scenario:SamplePeriod', 'samplePeriodUs');
arbitrationUs = boundedScalar(arbitrationUs, 0, 1000, ...
    'P13:scenario:Arbitration', 'arbitrationUs');
completionIsrCpuUs = boundedScalar(completionIsrCpuUs, 0, 1000, ...
    'P13:scenario:CompletionIsrCpu', 'completionIsrCpuUs');
processorCopyCpuUsPerSample = boundedScalar( ...
    processorCopyCpuUsPerSample, 0, 1000, ...
    'P13:scenario:ProcessorCopyCpu', ...
    'processorCopyCpuUsPerSample');

defaultBlockSamples = 8;
defaultBusRateBytesPerUs = 0.2;
defaultSamplePeriodUs = 50;
defaultArbitrationUs = 1;
defaultCompletionIsrCpuUs = 3;
defaultProcessorCopyCpuUsPerSample = 4;

descriptorTimeoutUs = Inf;
timeoutAction = 'continue-waiting';
destinationMode = 'increment';
switch name
    case 'baseline'
        % Editable inputs above are retained.
    case 'fixed-destination'
        blockSamples = defaultBlockSamples;
        busRateBytesPerUs = defaultBusRateBytesPerUs;
        samplePeriodUs = defaultSamplePeriodUs;
        arbitrationUs = defaultArbitrationUs;
        completionIsrCpuUs = defaultCompletionIsrCpuUs;
        processorCopyCpuUsPerSample = ...
            defaultProcessorCopyCpuUsPerSample;
        destinationMode = 'fixed';
    case 'overloaded-bus'
        blockSamples = defaultBlockSamples;
        busRateBytesPerUs = 0.025;
        samplePeriodUs = defaultSamplePeriodUs;
        arbitrationUs = defaultArbitrationUs;
        completionIsrCpuUs = defaultCompletionIsrCpuUs;
        processorCopyCpuUsPerSample = ...
            defaultProcessorCopyCpuUsPerSample;
    case 'timeout-continue'
        blockSamples = defaultBlockSamples;
        busRateBytesPerUs = defaultBusRateBytesPerUs;
        samplePeriodUs = defaultSamplePeriodUs;
        arbitrationUs = defaultArbitrationUs;
        completionIsrCpuUs = defaultCompletionIsrCpuUs;
        processorCopyCpuUsPerSample = ...
            defaultProcessorCopyCpuUsPerSample;
        descriptorTimeoutUs = 1161;
        timeoutAction = 'continue-waiting';
    case 'timeout-abort'
        blockSamples = defaultBlockSamples;
        busRateBytesPerUs = defaultBusRateBytesPerUs;
        samplePeriodUs = defaultSamplePeriodUs;
        arbitrationUs = defaultArbitrationUs;
        completionIsrCpuUs = defaultCompletionIsrCpuUs;
        processorCopyCpuUsPerSample = ...
            defaultProcessorCopyCpuUsPerSample;
        descriptorTimeoutUs = 1161;
        timeoutAction = 'abort-transfer';
    otherwise
        error('P13:scenario:Name', 'Unknown P13 scenario: %s.', name);
end

sampleIndex = 0:31;
sourceSamples = mod(37 .* sampleIndex + 11, 4096);
input = struct( ...
    'source_samples', sourceSamples, ...
    'sample_period_us', samplePeriodUs, ...
    'bytes_per_sample', 2, ...
    'bus_rate_bytes_per_us', busRateBytesPerUs, ...
    'arbitration_us', arbitrationUs, ...
    'block_samples', blockSamples, ...
    'dma_setup_cpu_us', 8, ...
    'completion_isr_cpu_us', completionIsrCpuUs, ...
    'processor_copy_cpu_us_per_sample', ...
        processorCopyCpuUsPerSample, ...
    'descriptor_timeout_us', descriptorTimeoutUs, ...
    'timeout_action', timeoutAction, ...
    'destination_mode', destinationMode);
end

function name = normalizeName(name)
validCharacter = ischar(name) && isrow(name);
validString = isstring(name) && isscalar(name) && ~ismissing(name);
if ~validCharacter && ~validString
    error('P13:scenario:Name', ...
        'Scenario name must be a character vector or scalar string.');
end
name = char(name);
end

function value = boundedScalar(value, minimum, maximum, identifier, label)
validValue = isnumeric(value) && ~islogical(value) && isreal(value) && ...
    isscalar(value) && isfinite(value);
if ~validValue
    error(identifier, '%s must be a finite real numeric scalar.', label);
end
value = double(value);
if value < minimum || value > maximum
    error(identifier, '%s must be in [%g, %g].', ...
        label, minimum, maximum);
end
end
