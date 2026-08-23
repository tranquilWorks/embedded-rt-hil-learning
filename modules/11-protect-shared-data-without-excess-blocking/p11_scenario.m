function input = p11_scenario(kind, writerPrepareMs, recordWords, ...
    readerReleaseMs, readerProcessMs, horizonMs)
%P11_SCENARIO Return bounded deterministic shared-record fixtures.
%   Fixtures are synthetic scheduler inputs, not RTOS, processor, or
%   memory-ordering traces.

if nargin < 1
    kind = 'baseline';
end
if nargin < 2
    writerPrepareMs = 2;
end
if nargin < 3
    recordWords = 2;
end
if nargin < 4
    readerReleaseMs = 3;
end
if nargin < 5
    readerProcessMs = 2;
end
if nargin < 6
    horizonMs = 16;
end
if ~(ischar(kind) || (isstring(kind) && isscalar(kind)))
    error('P11:scenario:Kind', ...
        'Scenario kind must be a character vector or scalar string.');
end
validateIntegerScalar(writerPrepareMs, 0, 1000, ...
    'P11:scenario:WriterPrepare', 'writerPrepareMs');
validateIntegerScalar(recordWords, 2, 64, ...
    'P11:scenario:RecordWords', 'recordWords');
validateIntegerScalar(readerReleaseMs, 0, 1000, ...
    'P11:scenario:ReaderRelease', 'readerReleaseMs');
validateIntegerScalar(readerProcessMs, 0, 1000, ...
    'P11:scenario:ReaderProcess', 'readerProcessMs');
validateIntegerScalar(horizonMs, 1, 100000, ...
    'P11:scenario:Horizon', 'horizonMs');

name = lower(strtrim(char(kind)));
input = struct();
input.name = name;
input.task_names = {'Low writer', 'High reader'};
input.writer_prepare_ms = double(writerPrepareMs);
input.record_words = double(recordWords);
input.reader_release_ms = double(readerReleaseMs);
input.reader_process_ms = double(readerProcessMs);
input.protection = 'short-mutex';
input.tick_ms = 1;
input.horizon_ms = double(horizonMs);
input.wait_timeout_ms = Inf;
input.timeout_action = 'continue-waiting';

switch name
    case 'baseline'
        % Protect only the in-place commit and copy operations.
    case 'coarse-lock'
        input.protection = 'coarse-mutex';
    case 'unprotected-torn'
        input.protection = 'unprotected';
    case 'timeout-continue'
        input.record_words = 4;
        input.wait_timeout_ms = 1;
    case 'timeout-cancel'
        input.record_words = 4;
        input.wait_timeout_ms = 1;
        input.timeout_action = 'cancel-reader';
    case 'early-reader'
        input.reader_release_ms = 1;
    otherwise
        error('P11:scenario:Kind', 'Unknown scenario kind: %s.', name);
end

input.claim_boundary = [ ...
    'Synthetic two-task shared-record fixture; not MATLAB-runtime, ' ...
    'RTOS, processor, cache, memory-ordering, or hardware evidence.'];
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
