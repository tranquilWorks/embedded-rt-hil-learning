function input = p07_scenario(kind, sampleCount)
%P07_SCENARIO Return bounded deterministic ADC sampling fixtures.
%   Fixtures are analytical signals and ideal codes, not ADC captures.

if nargin < 1
    kind = 'baseline';
end
if nargin < 2
    sampleCount = 51;
end
if ~(ischar(kind) || (isstring(kind) && isscalar(kind)))
    error('P07:scenario:Kind', ...
        'Scenario kind must be a character vector or scalar string.');
end
validCount = isnumeric(sampleCount) && isreal(sampleCount) && ...
    isscalar(sampleCount) && isfinite(sampleCount) && ...
    sampleCount == round(sampleCount) && sampleCount >= 2 && ...
    sampleCount <= 10000;
if ~validCount
    error('P07:scenario:SampleCount', ...
        'sampleCount must be an integer in [2, 10000].');
end

name = lower(strtrim(char(kind)));
input = struct();
input.name = name;
input.signal_frequency_hz = 180;
input.sample_rate_hz = 1000;
input.sample_count = double(sampleCount);
input.amplitude_v = 1;
input.offset_v = 1.65;
input.phase_rad = 0;
input.anti_alias_cutoff_hz = 400;
input.adc_bits = 12;
input.reference_voltage_v = 3.3;
input.fault = struct('mode', 'none');
input.acquisition_deadline_s = Inf;

switch name
    case 'baseline'
        % A 180 Hz tone is strictly below the 500 Hz Nyquist boundary.
    case 'alias-trap'
        input.signal_frequency_hz = 820;
        input.fault = struct('mode', 'anti-alias-bypass');
    case 'nyquist-boundary'
        input.signal_frequency_hz = 500;
        % Keep the intended phase-loss voltage inside one ADC bin so tiny
        % trigonometric residue cannot masquerade as converter activity.
        input.offset_v = 1.6;
        input.phase_rad = pi ./ 2;
        input.fault = struct('mode', 'anti-alias-bypass');
    case 'clipping'
        input.amplitude_v = 2;
        input.fault = struct('mode', 'anti-alias-bypass');
    case 'deadline'
        input.acquisition_deadline_s = 0.05;
    otherwise
        error('P07:scenario:Kind', 'Unknown scenario kind: %s.', name);
end

input.claim_boundary = [ ...
    'Synthetic sinusoid, first-order front end, and ideal ADC fixture; ' ...
    'not a hardware measurement.'];
end
