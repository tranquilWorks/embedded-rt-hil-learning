function input = p08_scenario(kind, sampleCount)
%P08_SCENARIO Return bounded deterministic DAC command fixtures.
%   Fixtures are synthetic command/response calculations, not DAC captures.

if nargin < 1
    kind = 'baseline';
end
if nargin < 2
    sampleCount = 601;
end
if ~(ischar(kind) || (isstring(kind) && isscalar(kind)))
    error('P08:scenario:Kind', ...
        'Scenario kind must be a character vector or scalar string.');
end
validCount = isnumeric(sampleCount) && ~islogical(sampleCount) && ...
    isreal(sampleCount) && isscalar(sampleCount) && isfinite(sampleCount) && ...
    sampleCount == round(sampleCount) && sampleCount >= 2 && ...
    sampleCount <= 10000;
if ~validCount
    error('P08:scenario:SampleCount', ...
        'sampleCount must be an integer in [2, 10000].');
end

name = lower(strtrim(char(kind)));
input = struct();
input.name = name;
input.command_voltage_v = 2.5;
input.initial_voltage_v = 0.5;
input.reference_voltage_v = 3.3;
input.dac_bits = 12;
input.update_latency_s = 100e-6;
input.time_constant_s = 250e-6;
input.slew_rate_v_per_s = 4000;
input.tolerance_v = 10e-3;
input.sample_period_s = 5e-6;
input.sample_count = double(sampleCount);
input.fault = struct('mode', 'none');
input.command_deadline_s = Inf;

switch name
    case 'baseline'
        % The requested step is quantized, latched, slew-limited, and settled.
    case 'update-not-latched'
        input.fault = struct('mode', 'update-not-latched');
    case 'deadline'
        input.command_deadline_s = 50e-6;
    case 'short-observation'
        input.sample_count = min(double(sampleCount), 201);
    case 'slow-output'
        input.time_constant_s = 1e-3;
        input.slew_rate_v_per_s = 500;
    otherwise
        error('P08:scenario:Kind', 'Unknown scenario kind: %s.', name);
end

% Direct display-unit mirrors keep fixed UI diagnostics explicit and avoid
% hiding unit conversions inside callback state.
input.update_latency_us = 1e6 .* input.update_latency_s;
input.time_constant_us = 1e6 .* input.time_constant_s;
input.slew_rate_v_per_ms = input.slew_rate_v_per_s ./ 1000;
input.tolerance_mv = 1000 .* input.tolerance_v;
input.sample_period_us = 1e6 .* input.sample_period_s;

input.claim_boundary = [ ...
    'Synthetic ideal DAC transfer and analog settling fixture; ' ...
    'not a hardware measurement.'];
end
