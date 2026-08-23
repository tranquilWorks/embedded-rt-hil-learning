function input = p04_scenario(kind, trueIntervalUs)
%P04_SCENARIO Return bounded deterministic paired-capture fixtures for P04.
%   Fixtures are synthetic event times, not timer or hardware measurements.

if nargin < 1
    kind = 'baseline';
end
if nargin < 2
    trueIntervalUs = 37;
end
if ~(ischar(kind) || (isstring(kind) && isscalar(kind)))
    error('P04:scenario:Kind', ...
        'Scenario kind must be a character vector or scalar string.');
end
validInterval = isnumeric(trueIntervalUs) && isreal(trueIntervalUs) && ...
    isscalar(trueIntervalUs) && isfinite(trueIntervalUs) && ...
    trueIntervalUs >= 0 && trueIntervalUs <= 10000;
if ~validInterval
    error('P04:scenario:TrueInterval', ...
        'trueIntervalUs must be a finite scalar in [0, 10000] microseconds.');
end
trueIntervalUs = double(trueIntervalUs);
name = lower(strtrim(char(kind)));

switch name
    case 'baseline'
        startTimeUs = 100 + (0:11) .* 37;
        intervalUs = trueIntervalUs .* ones(size(startTimeUs));
    case 'wrap-recovery'
        startTimeUs = [2550 2700];
        intervalUs = trueIntervalUs .* ones(size(startTimeUs));
    case 'range-recovery'
        startTimeUs = [0 3000];
        intervalUs = [2560 trueIntervalUs];
    otherwise
        error('P04:scenario:Kind', 'Unknown scenario kind: %s.', name);
end

input = struct();
input.name = name;
input.start_time_us = startTimeUs;
input.true_interval_us = intervalUs;
input.recommended_tick_period_us = 10;
input.recommended_timer_phase_us = 0;
input.recommended_counter_bits = 8;
input.claim_boundary = [ ...
    'Synthetic paired event captures; not a hardware measurement.'];
end
