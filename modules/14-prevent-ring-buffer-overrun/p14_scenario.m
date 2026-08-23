function input = p14_scenario(name, capacitySamples, consumerQuotaSamples, ...
    producerPeriodUs, consumerPeriodUs, drainTimeoutUs)
%P14_SCENARIO Return bounded deterministic P14 ring-buffer fixtures.
%   INPUT = P14_SCENARIO(NAME, CAPACITY, QUOTA, PRODUCERPERIOD,
%   CONSUMERPERIOD, TIMEOUT) keeps the source record identities fixed while
%   allowing the editable baseline controls to change one mechanism at a
%   time. Diagnostic scenarios intentionally replace those overrides.

if nargin < 1 || isempty(name)
    name = 'baseline';
end
if nargin < 2 || isempty(capacitySamples)
    capacitySamples = 8;
end
if nargin < 3 || isempty(consumerQuotaSamples)
    consumerQuotaSamples = 4;
end
if nargin < 4 || isempty(producerPeriodUs)
    producerPeriodUs = 50;
end
if nargin < 5 || isempty(consumerPeriodUs)
    consumerPeriodUs = 200;
end
if nargin < 6 || isempty(drainTimeoutUs)
    drainTimeoutUs = Inf;
end
if nargin > 6
    error('P14:scenario:Arity', ...
        'p14_scenario accepts at most six inputs.');
end

name = validateName(name);
capacitySamples = validatePositiveInteger(capacitySamples, ...
    'CapacitySamples', 100000);
consumerQuotaSamples = validatePositiveInteger(consumerQuotaSamples, ...
    'ConsumerQuotaSamples', 10000);
producerPeriodUs = validatePositiveScalar(producerPeriodUs, ...
    'ProducerPeriod');
consumerPeriodUs = validatePositiveScalar(consumerPeriodUs, ...
    'ConsumerPeriod');
drainTimeoutUs = validateTimeout(drainTimeoutUs);

sampleIndex = 0:31;
sourceSamples = mod(37 .* sampleIndex + 11, 4096);
if ~strcmp(name, 'baseline')
    capacitySamples = 8;
    consumerQuotaSamples = 4;
    producerPeriodUs = 50;
    consumerPeriodUs = 200;
    drainTimeoutUs = Inf;
end
input = struct( ...
    'source_samples', sourceSamples, ...
    'producer_period_us', producerPeriodUs, ...
    'consumer_period_us', consumerPeriodUs, ...
    'consumer_quota_samples', consumerQuotaSamples, ...
    'consumer_start_us', 200, ...
    'capacity_samples', capacitySamples, ...
    'overrun_policy', 'drop-newest', ...
    'drain_timeout_us', drainTimeoutUs, ...
    'timeout_action', 'continue-waiting');

switch name
    case 'baseline'
        % Keep validated editable overrides.
    case 'undersized-buffer'
        input.capacity_samples = 2;
    case 'slow-consumer'
        input.consumer_quota_samples = 1;
    case 'overwrite-oldest'
        input.capacity_samples = 4;
        input.consumer_quota_samples = 1;
        input.overrun_policy = 'overwrite-oldest';
    case 'backpressure'
        input.capacity_samples = 4;
        input.consumer_quota_samples = 1;
        input.overrun_policy = 'backpressure';
    case 'timeout-continue'
        input.drain_timeout_us = 49;
        input.timeout_action = 'continue-waiting';
    case 'timeout-cancel'
        input.drain_timeout_us = 49;
        input.timeout_action = 'cancel-consumer';
    otherwise
        error('P14:scenario:Name', ...
            ['Unknown scenario. Use baseline, undersized-buffer, ' ...
            'slow-consumer, overwrite-oldest, backpressure, ' ...
            'timeout-continue, or timeout-cancel.']);
end
end

function name = validateName(name)
if ~(ischar(name) || (isstring(name) && isscalar(name)))
    error('P14:scenario:Name', ...
        'Scenario name must be a character vector or scalar string.');
end
name = lower(strtrim(char(name)));
end

function value = validatePositiveInteger(value, label, maximum)
if ~(isnumeric(value) && ~islogical(value) && isreal(value) && ...
        isscalar(value) && isfinite(value) && value >= 1 && ...
        value == fix(value) && value <= maximum)
    error(['P14:scenario:' label], ...
        '%s must be an integer from 1 through %d.', label, maximum);
end
value = double(value);
end

function value = validatePositiveScalar(value, label)
if ~(isnumeric(value) && ~islogical(value) && isreal(value) && ...
        isscalar(value) && isfinite(value) && value >= 1 && value <= 1e9)
    error(['P14:scenario:' label], ...
        '%s must be a finite scalar from 1 through 1e9 us.', label);
end
value = double(value);
end

function value = validateTimeout(value)
if ~(isnumeric(value) && ~islogical(value) && isreal(value) && ...
        isscalar(value) && ~isnan(value) && ...
        (value == 0 || value == Inf || (value >= 1 && value <= 1e9)))
    error('P14:scenario:DrainTimeout', ...
        ['Drain timeout must be 0, Inf, or a finite scalar from 1 ' ...
        'through 1e9 us.']);
end
value = double(value);
end
