function input = p03_scenario(kind, pulseWidthMs)
%P03_SCENARIO Return bounded deterministic request-pulse fixtures for P03.
%   These are synthetic logic requests, not sampled hardware measurements.

if nargin < 1
    kind = 'mixed';
end
if nargin < 2
    pulseWidthMs = 0.3;
end
if ~(ischar(kind) || (isstring(kind) && isscalar(kind)))
    error('P03:scenario:Kind', ...
        'Scenario kind must be a character vector or scalar string.');
end
validWidth = isnumeric(pulseWidthMs) && isreal(pulseWidthMs) && ...
    isscalar(pulseWidthMs) && isfinite(pulseWidthMs) && ...
    pulseWidthMs > 0 && pulseWidthMs <= 0.5;
if ~validWidth
    error('P03:scenario:PulseWidth', ...
        'pulseWidthMs must be a finite scalar in (0, 0.5] milliseconds.');
end
pulseWidthMs = double(pulseWidthMs);
name = lower(strtrim(char(kind)));

switch name
    case 'mixed'
        eventTimesMs = [1.2 3.4 6.1 6.7 7.3 7.9 8.5 9.1 11.5 14.0];
        horizonMs = 16;
    case 'sparse'
        eventTimesMs = [1.2 5.2 9.2 13.2];
        horizonMs = 16;
    case 'burst-recovery'
        eventTimesMs = [1.2 6.1 6.7 7.3 7.9 8.5 9.1 11.5 14.0];
        horizonMs = 16;
    otherwise
        error('P03:scenario:Kind', 'Unknown scenario kind: %s.', name);
end

maxEvents = 1000000;
if numel(eventTimesMs) > maxEvents
    error('P03:scenario:ResourceBound', ...
        'Scenario exceeds the one-million-event educational bound.');
end
if any(eventTimesMs(2:end) < eventTimesMs(1:end-1) + pulseWidthMs)
    error('P03:scenario:PulseWidth', ...
        'The requested pulse width would overlap this single-source fixture.');
end

input = struct();
input.name = name;
input.event_times_ms = eventTimesMs;
input.pulse_width_ms = pulseWidthMs;
input.horizon_ms = horizonMs;
input.mask_start_ms = 6;
input.claim_boundary = 'Synthetic logic requests; not a hardware measurement.';
end
