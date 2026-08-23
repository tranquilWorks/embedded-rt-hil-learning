function input = p16_scenario(name, decimationFactor, fastCostUs, ...
    slowCostUs, outputTimeoutUs, timeoutAction, executionOrder, varargin)
%P16_SCENARIO Return bounded deterministic multi-rate graph fixtures.
%   Editable baseline controls change one mechanism at a time. Named
%   diagnostics replace every override so returning to baseline is clean.

if nargin < 1 || isempty(name)
    name = 'baseline';
end
if nargin < 2 || isempty(decimationFactor)
    decimationFactor = 4;
end
if nargin < 3 || isempty(fastCostUs)
    fastCostUs = 100;
end
if nargin < 4 || isempty(slowCostUs)
    slowCostUs = 1200;
end
if nargin < 5 || isempty(outputTimeoutUs)
    outputTimeoutUs = 2000;
end
if nargin < 6 || isempty(timeoutAction)
    timeoutAction = 'continue-processing';
end
if nargin < 7 || isempty(executionOrder)
    executionOrder = 'producer-first';
end
if nargin > 7
    error('P16:scenario:Arity', ...
        'p16_scenario accepts at most seven inputs.');
end

name = validateName(name);
decimationFactor = validateInteger(decimationFactor, ...
    'DecimationFactor', 1, 32);
if ~any(decimationFactor == [1 2 4 8 16 32])
    error('P16:scenario:FramePartition', ...
        'Editable decimation factor must divide the 32-sample fixture.');
end
fastCostUs = validateInteger(fastCostUs, 'FastCost', 0, 10000);
slowCostUs = validateInteger(slowCostUs, 'SlowCost', 0, 10000);
outputTimeoutUs = validateInteger(outputTimeoutUs, ...
    'OutputTimeout', 0, 10000);
timeoutAction = validateChoice(timeoutAction, 'TimeoutAction', ...
    {'continue-processing', 'cancel-frame'});
executionOrder = validateChoice(executionOrder, 'ExecutionOrder', ...
    {'producer-first', 'consumer-first'});

input = baselineInput();
if strcmp(name, 'baseline')
    input.decimation_factor = decimationFactor;
    input.fast_cost_us = fastCostUs;
    input.slow_cost_us = slowCostUs;
    input.output_timeout_us = outputTimeoutUs;
    input.timeout_action = timeoutAction;
    input.execution_order = executionOrder;
end

switch name
    case 'baseline'
        % Keep the validated editable overrides.
    case 'unity-rate'
        input.decimation_factor = 1;
        input.slow_cost_us = 800;
    case 'zero-cost'
        input.fast_cost_us = 0;
        input.slow_cost_us = 0;
        input.output_timeout_us = 0;
    case 'broken-consumer-first'
        input.execution_order = 'consumer-first';
    case 'timeout-continue'
        input.decimation_factor = 1;
        input.slow_cost_us = 1200;
        input.output_timeout_us = 2000;
        input.timeout_action = 'continue-processing';
    case 'timeout-cancel'
        input.decimation_factor = 1;
        input.slow_cost_us = 1200;
        input.output_timeout_us = 2000;
        input.timeout_action = 'cancel-frame';
    otherwise
        error('P16:scenario:Name', ...
            ['Unknown scenario. Use baseline, unity-rate, zero-cost, ' ...
            'broken-consumer-first, timeout-continue, or timeout-cancel.']);
end
end

function input = baselineInput()
input = struct( ...
    'sample_value', 0:31, ...
    'sample_time_us', 0:1000:31000, ...
    'decimation_factor', 4, ...
    'fast_cost_us', 100, ...
    'slow_cost_us', 1200, ...
    'output_timeout_us', 2000, ...
    'timeout_action', 'continue-processing', ...
    'execution_order', 'producer-first');
end

function name = validateName(name)
if ~(ischar(name) || (isstring(name) && isscalar(name)))
    error('P16:scenario:Name', ...
        'Scenario name must be a character vector or scalar string.');
end
name = lower(strtrim(char(name)));
end

function value = validateInteger(value, label, minimum, maximum)
valid = isnumeric(value) && ~islogical(value) && isreal(value) && ...
    isscalar(value) && isfinite(value) && value >= minimum && ...
    value <= maximum && value == fix(value);
if ~valid
    error(['P16:scenario:' label], ...
        '%s must be an integer from %g through %g.', ...
        label, minimum, maximum);
end
value = double(value);
end

function value = validateChoice(value, label, choices)
if ~(ischar(value) || (isstring(value) && isscalar(value)))
    error(['P16:scenario:' label], ...
        '%s must be a character vector or scalar string.', label);
end
value = lower(strtrim(char(value)));
if ~any(strcmp(value, choices))
    error(['P16:scenario:' label], ...
        '%s is not a supported value.', label);
end
end
