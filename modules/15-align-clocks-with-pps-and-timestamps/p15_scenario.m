function input = p15_scenario(name, clockOffsetUs, clockSkewPpm, ...
    timestampTickUs, ppsWaitTimeoutUs, timeoutAction, associationMode)
%P15_SCENARIO Return bounded deterministic PPS/timestamp fixtures.
%   Editable baseline controls change one clock mechanism at a time. Named
%   diagnostics replace every override so returning to baseline is clean.

if nargin < 1 || isempty(name)
    name = 'baseline';
end
if nargin < 2 || isempty(clockOffsetUs)
    clockOffsetUs = 2500;
end
if nargin < 3 || isempty(clockSkewPpm)
    clockSkewPpm = 40;
end
if nargin < 4 || isempty(timestampTickUs)
    timestampTickUs = 1;
end
if nargin < 5 || isempty(ppsWaitTimeoutUs)
    ppsWaitTimeoutUs = Inf;
end
if nargin < 6 || isempty(timeoutAction)
    timeoutAction = 'continue-waiting';
end
if nargin < 7 || isempty(associationMode)
    associationMode = 'sequence-id';
end
if nargin > 7
    error('P15:scenario:Arity', ...
        'p15_scenario accepts at most seven inputs.');
end

name = validateName(name);
clockOffsetUs = validateBoundedScalar(clockOffsetUs, ...
    'ClockOffset', 0, 1e9);
clockSkewPpm = validateBoundedScalar(clockSkewPpm, ...
    'ClockSkew', -500000, 500000);
timestampTickUs = validateBoundedScalar(timestampTickUs, ...
    'TimestampTick', eps, 1e6);
ppsWaitTimeoutUs = validateTimeout(ppsWaitTimeoutUs);
timeoutAction = validateChoice(timeoutAction, 'TimeoutAction', ...
    {'continue-waiting', 'cancel-alignment'});
associationMode = validateChoice(associationMode, 'AssociationMode', ...
    {'sequence-id', 'arrival-index'});

input = baselineInput();
if strcmp(name, 'baseline')
    input.clock_offset_us = clockOffsetUs;
    input.clock_skew_ppm = clockSkewPpm;
    input.timestamp_tick_us = timestampTickUs;
    input.pps_wait_timeout_us = ppsWaitTimeoutUs;
    input.timeout_action = timeoutAction;
    input.association_mode = associationMode;
end

switch name
    case 'baseline'
        % Keep the validated editable overrides.
    case 'zero-error'
        input.clock_offset_us = 0;
        input.clock_skew_ppm = 0;
    case 'missing-id-correct'
        input.pps_sequence_id = [0 2 3 4];
    case 'broken-arrival-index'
        input.pps_sequence_id = [0 2 3 4];
        input.association_mode = 'arrival-index';
    case 'coarse-timestamp'
        input.timestamp_tick_us = 100;
    case 'timeout-continue'
        input.pps_sequence_id = [0 2 3 4];
        input.pps_wait_timeout_us = 1.5e6;
        input.timeout_action = 'continue-waiting';
    case 'timeout-cancel'
        input.pps_sequence_id = [0 2 3 4];
        input.pps_wait_timeout_us = 1.5e6;
        input.timeout_action = 'cancel-alignment';
    otherwise
        error('P15:scenario:Name', ...
            ['Unknown scenario. Use baseline, zero-error, ' ...
            'missing-id-correct, broken-arrival-index, ' ...
            'coarse-timestamp, timeout-continue, or timeout-cancel.']);
end
end

function input = baselineInput()
input = struct( ...
    'event_reference_us', 250000:500000:3750000, ...
    'pps_sequence_id', 0:4, ...
    'pps_period_us', 1e6, ...
    'clock_offset_us', 2500, ...
    'clock_skew_ppm', 40, ...
    'timestamp_tick_us', 1, ...
    'pps_wait_timeout_us', Inf, ...
    'timeout_action', 'continue-waiting', ...
    'association_mode', 'sequence-id');
end

function name = validateName(name)
if ~(ischar(name) || (isstring(name) && isscalar(name)))
    error('P15:scenario:Name', ...
        'Scenario name must be a character vector or scalar string.');
end
name = lower(strtrim(char(name)));
end

function value = validateBoundedScalar(value, label, minimum, maximum)
valid = isnumeric(value) && ~islogical(value) && isreal(value) && ...
    isscalar(value) && isfinite(value) && value >= minimum && ...
    value <= maximum;
if ~valid
    error(['P15:scenario:' label], ...
        '%s must be a finite scalar from %g through %g.', ...
        label, minimum, maximum);
end
value = double(value);
end

function value = validateTimeout(value)
valid = isnumeric(value) && ~islogical(value) && isreal(value) && ...
    isscalar(value) && ~isnan(value) && value >= 0 && value <= Inf;
if ~valid || (isfinite(value) && value > 1e12)
    error('P15:scenario:PpsWaitTimeout', ...
        'PPS wait timeout must lie from 0 through 1e12 us or be Inf.');
end
value = double(value);
end

function value = validateChoice(value, label, choices)
if ~(ischar(value) || (isstring(value) && isscalar(value)))
    error(['P15:scenario:' label], ...
        '%s must be a character vector or scalar string.', label);
end
value = lower(strtrim(char(value)));
if ~any(strcmp(value, choices))
    error(['P15:scenario:' label], ...
        '%s is not a supported value.', label);
end
end
