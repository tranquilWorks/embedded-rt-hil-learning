function input = p05_scenario(kind)
%P05_SCENARIO Return bounded deterministic UART fixtures for P05.
%   These byte streams and line faults are synthetic, not serial hardware
%   captures or measurements.

if nargin < 1
    kind = 'baseline';
end
if ~(ischar(kind) || (isstring(kind) && isscalar(kind)))
    error('P05:scenario:Kind', ...
        'Scenario kind must be a character vector or scalar string.');
end
name = lower(strtrim(char(kind)));
noFault = struct('mode', 'none', 'frame_index', 0, ...
    'data_bit_indices', []);

input = struct();
input.name = name;
input.payload_bytes = [163 85 60 126];
input.tx_baud_bps = 115200;
input.receiver_error_pct = 0;
input.parity_mode = 'none';
input.stop_bits = 1;
input.inter_frame_gap_bits = 0;
input.fault = noFault;
input.receive_timeout_us = Inf;

switch name
    case 'baseline'
        % Defaults above are the matched-clock 8-N-1 reference.
    case 'parity-fault'
        input.parity_mode = 'even';
        input.fault = struct('mode', 'flip-data', 'frame_index', 1, ...
            'data_bit_indices', 0);
    case 'stop-fault-recovery'
        input.fault = struct('mode', 'force-stop-low', ...
            'frame_index', 2, 'data_bit_indices', []);
    case 'deadline'
        % At 115200 bit/s this retains two complete 8-N-1 frames.
        input.receive_timeout_us = 170;
    otherwise
        error('P05:scenario:Kind', 'Unknown scenario kind: %s.', name);
end

input.claim_boundary = [ ...
    'Synthetic UART logic-level fixture; not a hardware measurement.'];
end
