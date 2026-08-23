function input = p09_scenario(kind, horizonMs)
%P09_SCENARIO Return bounded deterministic fixed-priority task fixtures.
%   Fixtures are synthetic scheduler inputs, not RTOS or processor traces.

if nargin < 1
    kind = 'baseline';
end
if nargin < 2
    horizonMs = 40;
end
if ~(ischar(kind) || (isstring(kind) && isscalar(kind)))
    error('P09:scenario:Kind', ...
        'Scenario kind must be a character vector or scalar string.');
end
validHorizon = isnumeric(horizonMs) && ~islogical(horizonMs) && ...
    isreal(horizonMs) && isscalar(horizonMs) && isfinite(horizonMs) && ...
    horizonMs == round(horizonMs) && horizonMs >= 1 && ...
    horizonMs <= 100000;
if ~validHorizon
    error('P09:scenario:Horizon', ...
        'horizonMs must be an integer in [1, 100000].');
end

name = lower(strtrim(char(kind)));
input = struct();
input.name = name;
input.task_names = {'Control', 'Telemetry', 'Logger'};
input.period_ms = [5 10 20];
input.execution_ms = [1 2 5];
input.relative_deadline_ms = [5 10 20];
input.priority = [3 2 1];
input.phase_ms = [0 0 0];
input.tick_ms = 1;
input.horizon_ms = double(horizonMs);
input.deadline_action = 'continue-late';

switch name
    case 'baseline'
        % Deadline-monotonic priorities produce two visible preemptions.
    case 'priority-misassigned'
        input.priority = [2 1 3];
    case 'deadline-cancel'
        input.execution_ms = [6 2 5];
        input.deadline_action = 'cancel-at-deadline';
    case 'heavy-logger'
        input.execution_ms = [1 2 8];
    otherwise
        error('P09:scenario:Kind', 'Unknown scenario kind: %s.', name);
end

maxJobs = 10000;
releaseCount = 0;
for taskId = 1:numel(input.period_ms)
    if input.phase_ms(taskId) < input.horizon_ms
        releaseCount = releaseCount + floor( ...
            (input.horizon_ms - 1 - input.phase_ms(taskId)) ./ ...
            input.period_ms(taskId)) + 1;
    end
end
if releaseCount > maxJobs
    error('P09:scenario:JobResourceBound', ...
        ['The requested horizon would release more than 10000 jobs; ' ...
        'reduce horizonMs.']);
end

input.claim_boundary = [ ...
    'Synthetic discrete-time uniprocessor scheduler fixture; not an RTOS, ' ...
    'processor, MATLAB-runtime, or hardware timing measurement.'];
end
