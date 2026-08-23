function input = p06_scenario(kind, payloadCount)
%P06_SCENARIO Return bounded deterministic SPI/I2C register-read fixtures.
%   Fixtures are synthetic clock-cell descriptions, not bus captures.

if nargin < 1
    kind = 'baseline';
end
if nargin < 2
    payloadCount = 4;
end
if ~(ischar(kind) || (isstring(kind) && isscalar(kind)))
    error('P06:scenario:Kind', ...
        'Scenario kind must be a character vector or scalar string.');
end
validCount = isnumeric(payloadCount) && isreal(payloadCount) && ...
    isscalar(payloadCount) && isfinite(payloadCount) && ...
    payloadCount == round(payloadCount) && payloadCount >= 1 && ...
    payloadCount <= 90000;
if ~validCount
    error('P06:scenario:PayloadCount', ...
        'payloadCount must be an integer in [1, 90000].');
end

name = lower(strtrim(char(kind)));
fixtureBytes = [163 86 201 30 0 255 90 165];
indices = mod(0:(double(payloadCount) - 1), numel(fixtureBytes)) + 1;

input = struct();
input.name = name;
input.payload_bytes = fixtureBytes(indices);
input.spi_clock_hz = 400000;
input.i2c_clock_hz = 400000;
input.i2c_address_7bit = 72;
input.register_address = 45;
input.fault = struct('mode', 'none');
input.transaction_timeout_us = Inf;

switch name
    case 'baseline'
        % Equal configured clocks isolate transaction framing overhead.
    case 'target-nack'
        input.fault = struct('mode', 'i2c-target-nack', ...
            'i2c_ack_index', 2);
    case 'spi-corruption'
        if payloadCount < 2
            error('P06:scenario:PayloadCount', ...
                'The SPI corruption fixture requires at least two bytes.');
        end
        input.fault = struct('mode', 'spi-bit-flip', ...
            'spi_payload_index', 2, 'spi_bit_index', 0);
    case 'stretch-timeout'
        input.fault = struct('mode', 'i2c-clock-stretch', ...
            'i2c_stretch_us', 300);
        input.transaction_timeout_us = 250;
    otherwise
        error('P06:scenario:Kind', 'Unknown scenario kind: %s.', name);
end

input.claim_boundary = [ ...
    'Synthetic device-specific register-read fixture; not a bus capture ' ...
    'or hardware measurement.'];
end
