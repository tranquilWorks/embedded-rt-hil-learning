function input = p12_scenario(name, releaseAmplitudeMs, ...
    blockingBudgetMs, periodMs, executionBaseMs, deadlineMs, ...
    timestampTickMs, varargin)
%P12_SCENARIO Build bounded seedless timestamp-measurement fixtures.

if nargin < 1 || isempty(name)
    name = 'baseline';
end
if nargin < 2 || isempty(releaseAmplitudeMs)
    releaseAmplitudeMs = 1;
end
if nargin < 3 || isempty(blockingBudgetMs)
    blockingBudgetMs = 1;
end
if nargin < 4 || isempty(periodMs)
    periodMs = 20;
end
if nargin < 5 || isempty(executionBaseMs)
    executionBaseMs = 2;
end
if nargin < 6 || isempty(deadlineMs)
    deadlineMs = 7;
end
if nargin < 7 || isempty(timestampTickMs)
    timestampTickMs = 1;
end
if nargin > 7
    error('P12:scenario:Arity', ...
        'At most seven scenario inputs are accepted.');
end

name = normalizeName(name);
releaseAmplitudeMs = boundedScalar(releaseAmplitudeMs, 0, 4, ...
    'P12:scenario:ReleaseAmplitude', 'releaseAmplitudeMs');
blockingBudgetMs = boundedScalar(blockingBudgetMs, 0, 5, ...
    'P12:scenario:BlockingBudget', 'blockingBudgetMs');
periodMs = boundedScalar(periodMs, 10, 100, ...
    'P12:scenario:Period', 'periodMs');
executionBaseMs = boundedScalar(executionBaseMs, 0, 10, ...
    'P12:scenario:Execution', 'executionBaseMs');
deadlineMs = boundedScalar(deadlineMs, 1, 50, ...
    'P12:scenario:Deadline', 'deadlineMs');
timestampTickMs = boundedScalar(timestampTickMs, 0.25, 8, ...
    'P12:scenario:TimestampTick', 'timestampTickMs');

responseTimeoutMs = Inf;
timeoutAction = 'continue-observing';
switch name
    case 'baseline'
        % Retain editable values.
    case 'completion-jitter-trap'
        releaseAmplitudeMs = 0;
        timestampTickMs = 1;
    case 'coarse-clock'
        releaseAmplitudeMs = 0;
        periodMs = 10;
        timestampTickMs = 4;
    case 'timeout-continue'
        responseTimeoutMs = 5;
    case 'timeout-cancel'
        responseTimeoutMs = 5;
        timeoutAction = 'cancel-observation';
    case 'deadline-boundary'
        deadlineMs = 6;
    otherwise
        error('P12:scenario:Name', 'Unknown P12 scenario.');
end

jobCount = 8;
releaseShape = [0 1 -1 0 1 -1 0 1];
blockingShape = [0 1 0 1 0 1 0 1];
interferenceMs = [0 0 1 0 2 0 1 3];

input = struct();
input.period_ms = double(periodMs);
input.job_count = jobCount;
input.release_offset_ms = double(releaseAmplitudeMs) .* releaseShape;
input.execution_ms = double(executionBaseMs) .* ones(1, jobCount);
input.blocking_ms = double(blockingBudgetMs) .* blockingShape;
input.interference_ms = interferenceMs;
input.deadline_ms = double(deadlineMs);
input.timestamp_tick_ms = double(timestampTickMs);
input.response_timeout_ms = responseTimeoutMs;
input.timeout_action = timeoutAction;
end

function name = normalizeName(name)
validCharacter = ischar(name) && isrow(name);
validString = isstring(name) && isscalar(name) && ~ismissing(name);
if ~validCharacter && ~validString
    error('P12:scenario:Name', ...
        'Scenario name must be a character vector or scalar string.');
end
name = char(name);
end

function value = boundedScalar(value, minimum, maximum, identifier, label)
validValue = isnumeric(value) && ~islogical(value) && isreal(value) && ...
    isscalar(value) && isfinite(value);
if ~validValue || value < minimum || value > maximum
    error(identifier, '%s must be a finite scalar in [%g, %g].', ...
        label, minimum, maximum);
end
value = double(value);
end
