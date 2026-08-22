function input = p02_scenario(kind, samplePeriodMs, horizonMs, bounceMs)
%P02_SCENARIO Build deterministic sampled button and cancellation traces.
%   The traces represent logic observations only; they are not hardware
%   measurements. Every output vector has one element per sample.

if nargin < 1
    kind = 'normal';
end
if nargin < 2
    samplePeriodMs = 1;
end
if nargin < 3
    horizonMs = 120;
end
if nargin < 4
    bounceMs = 6;
end

validateScalar(samplePeriodMs, true, 'SamplePeriod');
validateScalar(horizonMs, true, 'Horizon');
validateScalar(bounceMs, false, 'Bounce');
samplePeriodMs = double(samplePeriodMs);
horizonMs = double(horizonMs);
bounceMs = double(bounceMs);
if ~(ischar(kind) || (isstring(kind) && isscalar(kind)))
    error('P02:scenario:Kind', 'Scenario kind must be a character vector or scalar string.');
end

sampleCount = floor(horizonMs / samplePeriodMs) + 1;
maxSamples = 1000000;
if ~isfinite(sampleCount) || sampleCount > maxSamples
    error('P02:scenario:ResourceBound', ...
        'Scenario exceeds the one-million-sample educational resource bound.');
end

timeMs = (0:sampleCount-1) * samplePeriodMs;
rawButton = false(1, sampleCount);
cancel = false(1, sampleCount);
name = lower(strtrim(char(kind)));

switch name
    case 'normal'
        transitionsMs = [12 45];
        newLevels = [true false];
    case 'stuck-high'
        transitionsMs = 12;
        newLevels = true;
    case 'cancel-recovery'
        transitionsMs = [12 45 65 95];
        newLevels = [true false true false];
        cancel(timeMs >= 30 & timeMs < 35) = true;
    otherwise
        error('P02:scenario:Kind', 'Unknown scenario kind: %s.', name);
end

for transitionIndex = 1:numel(transitionsMs)
    rawButton = applyBouncyTransition(rawButton, timeMs, transitionsMs(transitionIndex), ...
        newLevels(transitionIndex), bounceMs, samplePeriodMs);
end

input = struct();
input.name = name;
input.time_ms = timeMs;
input.raw_button = rawButton;
input.cancel = cancel;
input.sample_period_ms = samplePeriodMs;
input.horizon_ms = horizonMs;
input.bounce_ms = bounceMs;
end

function signal = applyBouncyTransition(signal, timeMs, transitionMs, newLevel, bounceMs, samplePeriodMs)
oldLevel = ~newLevel;
bounceMask = timeMs >= transitionMs & timeMs < transitionMs + bounceMs;
bounceIndices = find(bounceMask);
for index = reshape(bounceIndices, 1, [])
    bounceStep = floor((timeMs(index) - transitionMs) / samplePeriodMs);
    if mod(bounceStep, 2) == 0
        signal(index) = newLevel;
    else
        signal(index) = oldLevel;
    end
end
signal(timeMs >= transitionMs + bounceMs) = newLevel;
end

function validateScalar(value, mustBeStrictlyPositive, name)
valid = isnumeric(value) && isreal(value) && isscalar(value) && isfinite(value);
if mustBeStrictlyPositive
    valid = valid && value > 0;
else
    valid = valid && value >= 0;
end
if ~valid
    error(['P02:scenario:' name], '%s must be a finite scalar in milliseconds.', name);
end
end
