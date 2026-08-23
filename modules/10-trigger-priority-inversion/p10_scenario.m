function input = p10_scenario(kind, mediumWorkMs, lowCriticalMs, horizonMs)
%P10_SCENARIO Return bounded deterministic one-mutex scheduling fixtures.
%   Fixtures are synthetic scheduler inputs, not RTOS or processor traces.

if nargin < 1
    kind = 'baseline';
end
if nargin < 2
    mediumWorkMs = 5;
end
if nargin < 3
    lowCriticalMs = 4;
end
if nargin < 4
    horizonMs = 16;
end
if ~(ischar(kind) || (isstring(kind) && isscalar(kind)))
    error('P10:scenario:Kind', ...
        'Scenario kind must be a character vector or scalar string.');
end
validateIntegerScalar(mediumWorkMs, 0, 1000, ...
    'P10:scenario:MediumWork', 'mediumWorkMs');
validateIntegerScalar(lowCriticalMs, 1, 6, ...
    'P10:scenario:LowCritical', 'lowCriticalMs');
validateIntegerScalar(horizonMs, 1, 100000, ...
    'P10:scenario:Horizon', 'horizonMs');

name = lower(strtrim(char(kind)));
input = struct();
input.name = name;
input.task_names = {'Low owner', 'Medium worker', 'High control'};
input.release_ms = [0 1 2];
input.pre_critical_ms = [0 double(mediumWorkMs) 0];
input.critical_ms = [double(lowCriticalMs) 0 1];
input.post_critical_ms = [(6 - double(lowCriticalMs)) 0 1];
input.relative_deadline_ms = [20 20 6];
input.base_priority = [1 2 3];
input.protocol = 'priority-inheritance';
input.tick_ms = 1;
input.horizon_ms = double(horizonMs);
input.wait_timeout_ms = [Inf Inf Inf];
input.timeout_action = 'continue-waiting';

switch name
    case 'baseline'
        % Low owns first; inheritance bounds High's wait to Low's remainder.
    case 'plain-mutex'
        input.protocol = 'none';
    case 'wait-continue'
        input.wait_timeout_ms(3) = 2;
    case 'wait-cancel'
        input.wait_timeout_ms(3) = 2;
        input.timeout_action = 'cancel-waiter';
    case 'high-first'
        input.release_ms(3) = 0;
    case 'direct-block-only'
        input.pre_critical_ms(2) = 0;
        input.protocol = 'none';
    otherwise
        error('P10:scenario:Kind', 'Unknown scenario kind: %s.', name);
end

input.claim_boundary = [ ...
    'Synthetic one-shot single-core mutex fixture; not an RTOS, ' ...
    'processor, MATLAB-runtime, or hardware timing measurement.'];
end

function validateIntegerScalar(value, minimum, maximum, identifier, label)
valid = isnumeric(value) && ~islogical(value) && isreal(value) && ...
    isscalar(value) && isfinite(value) && value == round(value) && ...
    value >= minimum && value <= maximum;
if ~valid
    error(identifier, '%s must be an integer in [%d, %d].', ...
        label, minimum, maximum);
end
end
