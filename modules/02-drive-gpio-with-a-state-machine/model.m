function out = model(rawButton, samplePeriodMs, debounceMs, maxOnMs, cancel)
%MODEL Deterministic sampled GPIO state machine with debounce and lockout.
%   GPIO is a simulated logic command, high only in ACTIVE and
%   QUALIFY_RELEASE. Cancellation has highest priority and is safe-low in
%   the same sample. No hardware, plotting, random, or persistent state is
%   used.

if nargin < 4 || nargin > 5
    error('P02:model:Arity', ...
        'Expected rawButton, samplePeriodMs, debounceMs, maxOnMs, and optional cancel.');
end
maxSamples = 1000000;
validateBinaryVectorShape(rawButton, 'P02:model:RawButton', 'rawButton');
sampleCount = numel(rawButton);
if sampleCount > maxSamples
    error('P02:model:ResourceBound', ...
        'Input exceeds the one-million-sample educational resource bound.');
end
if nargin < 5
    cancel = false(size(rawButton));
else
    validateBinaryVectorShape(cancel, 'P02:model:Cancel', 'cancel');
    if numel(cancel) ~= numel(rawButton)
        error('P02:model:LengthMismatch', ...
            'rawButton and cancel must contain the same number of samples.');
    end
end
validateBinaryVectorValues(rawButton, 'P02:model:RawButton', 'rawButton');
validateBinaryVectorValues(cancel, 'P02:model:Cancel', 'cancel');
validateTimingScalar(samplePeriodMs, true, 'P02:model:SamplePeriod', 'samplePeriodMs');
validateTimingScalar(debounceMs, false, 'P02:model:Debounce', 'debounceMs');
validateTimingScalar(maxOnMs, true, 'P02:model:MaxOn', 'maxOnMs');
samplePeriodMs = double(samplePeriodMs);
debounceMs = double(debounceMs);
maxOnMs = double(maxOnMs);
if maxOnMs < samplePeriodMs
    error('P02:model:MaxOnResolution', ...
        'maxOnMs must be at least one sample period to preserve a hard upper bound.');
end

rawButton = logical(reshape(rawButton, 1, []));
cancel = logical(reshape(cancel, 1, []));
debounceRatio = debounceMs / samplePeriodMs;
timeoutRatio = maxOnMs / samplePeriodMs;
debounceSamples = max(1, ceil(debounceRatio));
timeoutSamples = floor(timeoutRatio);
derivedCounts = [debounceSamples timeoutSamples];
derivedDurationsMs = derivedCounts .* samplePeriodMs;
if any(~isfinite([debounceRatio timeoutRatio derivedCounts derivedDurationsMs])) || ...
        any(derivedCounts > maxSamples) || ~isfinite(sampleCount * samplePeriodMs)
    error('P02:model:TimingResourceBound', ...
        'Timing parameters exceed finite one-million-sample educational bounds.');
end

IDLE = uint8(0);
QUALIFY_PRESS = uint8(1);
ACTIVE = uint8(2);
QUALIFY_RELEASE = uint8(3);
LOCKOUT = uint8(4);

stateCode = zeros(1, sampleCount, 'uint8');
gpio = false(1, sampleCount);
acceptedPress = false(1, sampleCount);
acceptedRelease = false(1, sampleCount);
timeoutEvent = false(1, sampleCount);
cancelEvent = false(1, sampleCount);
rearmEvent = false(1, sampleCount);

state = IDLE;
pressCount = 0;
releaseCount = 0;
activeCount = 0;
lockoutReleaseCount = 0;

for sampleIndex = 1:sampleCount
    if cancel(sampleIndex)
        if state ~= LOCKOUT
            cancelEvent(sampleIndex) = true;
        end
        state = LOCKOUT;
        pressCount = 0;
        releaseCount = 0;
        activeCount = 0;
        lockoutReleaseCount = 0;
    else
        switch state
            case IDLE
                if rawButton(sampleIndex)
                    pressCount = pressCount + 1;
                    if pressCount >= debounceSamples
                        state = ACTIVE;
                        acceptedPress(sampleIndex) = true;
                        activeCount = 1;
                        pressCount = 0;
                    else
                        state = QUALIFY_PRESS;
                    end
                else
                    pressCount = 0;
                end

            case QUALIFY_PRESS
                if rawButton(sampleIndex)
                    pressCount = pressCount + 1;
                    if pressCount >= debounceSamples
                        state = ACTIVE;
                        acceptedPress(sampleIndex) = true;
                        activeCount = 1;
                        pressCount = 0;
                    end
                else
                    state = IDLE;
                    pressCount = 0;
                end

            case ACTIVE
                if activeCount >= timeoutSamples
                    state = LOCKOUT;
                    timeoutEvent(sampleIndex) = true;
                    activeCount = 0;
                    releaseCount = 0;
                elseif ~rawButton(sampleIndex)
                    releaseCount = 1;
                    if releaseCount >= debounceSamples
                        state = IDLE;
                        acceptedRelease(sampleIndex) = true;
                        releaseCount = 0;
                        activeCount = 0;
                    else
                        state = QUALIFY_RELEASE;
                        activeCount = activeCount + 1;
                    end
                else
                    activeCount = activeCount + 1;
                end

            case QUALIFY_RELEASE
                if activeCount >= timeoutSamples
                    state = LOCKOUT;
                    timeoutEvent(sampleIndex) = true;
                    activeCount = 0;
                    releaseCount = 0;
                elseif ~rawButton(sampleIndex)
                    releaseCount = releaseCount + 1;
                    if releaseCount >= debounceSamples
                        state = IDLE;
                        acceptedRelease(sampleIndex) = true;
                        releaseCount = 0;
                        activeCount = 0;
                    else
                        activeCount = activeCount + 1;
                    end
                else
                    state = ACTIVE;
                    releaseCount = 0;
                    activeCount = activeCount + 1;
                end

            case LOCKOUT
                if rawButton(sampleIndex)
                    lockoutReleaseCount = 0;
                else
                    lockoutReleaseCount = lockoutReleaseCount + 1;
                    if lockoutReleaseCount >= debounceSamples
                        state = IDLE;
                        rearmEvent(sampleIndex) = true;
                        lockoutReleaseCount = 0;
                    end
                end
        end
    end

    stateCode(sampleIndex) = state;
    gpio(sampleIndex) = state == ACTIVE || state == QUALIFY_RELEASE;
end

out = struct();
out.time_ms = (0:sampleCount-1) * samplePeriodMs;
out.raw_button = rawButton;
out.cancel = cancel;
out.state_code = stateCode;
out.state_names = {'IDLE', 'QUALIFY_PRESS', 'ACTIVE', 'QUALIFY_RELEASE', 'LOCKOUT'};
out.gpio = gpio;
out.events = struct('accepted_press', acceptedPress, 'accepted_release', acceptedRelease, ...
    'timeout', timeoutEvent, 'cancel', cancelEvent, 'rearm', rearmEvent);
out.sample_period_ms = samplePeriodMs;
out.requested_debounce_ms = debounceMs;
out.requested_max_on_ms = maxOnMs;
out.debounce_samples = debounceSamples;
out.timeout_samples = timeoutSamples;
out.quantized_debounce_ms = debounceSamples * samplePeriodMs;
out.quantized_max_on_ms = timeoutSamples * samplePeriodMs;
out.metrics = struct();
out.metrics.accepted_presses = sum(acceptedPress);
out.metrics.accepted_releases = sum(acceptedRelease);
out.metrics.timeout_count = sum(timeoutEvent);
out.metrics.cancel_count = sum(cancelEvent);
out.metrics.gpio_rising_edges = sum(diff(double([false gpio])) == 1);
out.metrics.gpio_falling_edges = sum(diff(double([false gpio])) == -1);
out.metrics.gpio_high_samples = sum(gpio);
out.metrics.gpio_high_time_ms = sum(gpio) * samplePeriodMs;
out.metrics.max_high_run_samples = longestTrueRun(gpio);
out.metrics.max_high_run_ms = out.metrics.max_high_run_samples * samplePeriodMs;
end

function validateBinaryVectorShape(value, identifier, name)
validType = isnumeric(value) || islogical(value);
validShape = isvector(value) && ~isempty(value);
if ~(validType && validShape)
    error(identifier, ...
        '%s must be a nonempty numeric or logical vector.', name);
end
end

function validateBinaryVectorValues(value, identifier, name)
validValues = isreal(value) && all(isfinite(value(:))) && ...
    all(value(:) == 0 | value(:) == 1);
if ~validValues
    error(identifier, '%s must contain only real, finite binary values.', name);
end
end

function validateTimingScalar(value, mustBeStrictlyPositive, identifier, name)
valid = isnumeric(value) && isreal(value) && isscalar(value) && isfinite(value);
if mustBeStrictlyPositive
    valid = valid && value > 0;
else
    valid = valid && value >= 0;
end
if ~valid
    error(identifier, '%s must be a finite scalar in milliseconds.', name);
end
end

function longest = longestTrueRun(signal)
longest = 0;
current = 0;
for index = 1:numel(signal)
    if signal(index)
        current = current + 1;
        longest = max(longest, current);
    else
        current = 0;
    end
end
end
