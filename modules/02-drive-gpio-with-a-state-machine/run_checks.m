function run_checks
%RUN_CHECKS Independent deterministic and limiting-case checks for P02.

%% Constant-low limiting case and output/state mapping
constantLow = model(zeros(1, 20), 1, 3, 10);
assert(all(constantLow.state_code == 0), 'Constant-low input must stay IDLE.');
assert(~any(constantLow.gpio), 'Constant-low input must keep GPIO safe low.');
assert(all(constantLow.gpio == ...
    (constantLow.state_code == 2 | constantLow.state_code == 3)), ...
    'GPIO must be high exactly in ACTIVE and QUALIFY_RELEASE.');

%% Exact debounce edges and pulse rejection
cleanRaw = [0 1 1 1 1 0 0 0 0];
clean = model(cleanRaw, 1, 3, 100);
assert(all(clean.gpio == (clean.state_code == 2 | clean.state_code == 3)), ...
    'GPIO/state equivalence must hold on a trace that visits active states.');
assert(find(clean.gpio, 1, 'first') == 4, ...
    'A clean press must energize on the N_d-th consecutive high sample.');
assert(all(clean.gpio(4:7)) && ~clean.gpio(8), ...
    'A clean release must de-energize on the N_d-th consecutive low sample.');
shortPulse = model([0 1 1 0 0 0], 1, 3, 100);
assert(~any(shortPulse.gpio), 'A pulse shorter than N_d must be rejected.');

%% Timeout, lockout, and no held-input retrigger
stuck = model([0 ones(1, 20)], 1, 0, 4);
assert(stuck.debounce_samples == 1 && stuck.timeout_samples == 4, ...
    'Quantized limiting counts are incorrect.');
assert(sum(stuck.gpio) == 4, 'A stuck request must receive exactly N_t high samples.');
assert(stuck.events.timeout(6), 'The sample after N_t high outputs must enter timeout lockout.');
assert(~any(stuck.gpio(6:end)), 'Held-high input must not retrigger from LOCKOUT.');
assert(stuck.metrics.max_high_run_samples == 4, 'Maximum high run must equal N_t.');

%% Same-sample cancellation, safe rollback, re-arm, and recovery
recoveryRaw = [0 1 1 1 0 0 0 1 1 1 0 0];
cancel = false(size(recoveryRaw));
cancel(4) = true;
recovery = model(recoveryRaw, 1, 2, 50, cancel);
assert(~recovery.gpio(4) && recovery.state_code(4) == 4, ...
    'Cancel must force same-sample safe-low LOCKOUT.');
assert(recovery.events.cancel(4), 'Cancellation event must be observable.');
assert(recovery.events.rearm(6), 'N_d stable-low samples must re-arm IDLE.');
assert(all(~recovery.gpio(4:8)), ...
    'Lockout and renewed qualification must isolate recovery from the cancelled drive.');
assert(recovery.events.accepted_press(9) && recovery.gpio(9), ...
    'A later qualified press must prove recovery after re-arm.');
assert(sum(recovery.events.accepted_press) == 2, ...
    'Recovery trace must contain exactly the initial and recovered accepted presses.');

%% N_d = 1 and N_t = 1 limiting cases
oneSample = model([0 1 1 0], 1, 0, 1);
assert(oneSample.debounce_samples == 1 && oneSample.timeout_samples == 1, ...
    'Zero debounce and one-sample timeout must quantize to one sample.');
assert(sum(oneSample.gpio) == 1, 'N_t = 1 must permit exactly one high sample.');
fractionalMaximum = model([0 ones(1, 30)], 1, 0, 17.2);
assert(fractionalMaximum.timeout_samples == 17, ...
    'Fractional maximum-on time must quantize conservatively with floor.');
assert(fractionalMaximum.metrics.max_high_run_ms == 17 && ...
    fractionalMaximum.quantized_max_on_ms <= fractionalMaximum.requested_max_on_ms, ...
    'Quantized energization must never exceed the requested maximum-on bound.');

%% Determinism, optional cancel compatibility, and state isolation
fixture = p02_scenario('normal', 1, 120, 8);
first = model(fixture.raw_button, 1, 5, 80, fixture.cancel);
second = model(fixture.raw_button, 1, 5, 80, fixture.cancel);
withoutCancel = model(fixture.raw_button, 1, 5, 80);
columnInput = model([0; 1; 1; 0], 1, 0, 10);
integerTiming = model(uint8([0 1 1 0]), uint8(1), uint8(0), uint8(2));
assert(isequal(first, second), 'Repeated calls must be deterministic and state-isolated.');
assert(isequal(first.gpio, withoutCancel.gpio), ...
    'Omitted cancellation must match an all-low cancellation vector.');
assert(numel(first.time_ms) == numel(fixture.raw_button), ...
    'Every output trace must stay one-to-one with the bounded input trace.');
assert(first.time_ms(1) == 0, 'The sampled timeline must start at zero milliseconds.');
assert(all(abs(diff(first.time_ms) - 1) < eps), 'Time spacing must equal the sample period.');
assert(all(ismember(unique(first.state_code), uint8(0:4))), 'State code is outside the contract.');
assert(isrow(columnInput.gpio) && numel(columnInput.gpio) == 4, ...
    'Column-vector input must normalize to the documented row-vector output.');
assert(isa(integerTiming.time_ms, 'double') && integerTiming.timeout_samples == 2, ...
    'Accepted integer timing scalars must normalize to double before arithmetic.');

%% Callback dependency lifetime across launcher cleanup and module switches
callbackModel = @model;
callbackScenario = @p02_scenario;
moduleFolder = fileparts(mfilename('fullpath'));
modulesFolder = fileparts(moduleFolder);
p01Folder = fullfile(modulesFolder, '01-see-a-periodic-scheduler-miss-a-deadline');
originalSearchPath = path;
searchPathCleanup = onCleanup(@() path(originalSearchPath));
rmpath(moduleFolder);
addpath(p01Folder, '-begin');
callbackFixture = callbackScenario('normal', 1, 120, 6);
callbackOut = callbackModel(callbackFixture.raw_button, 1, 5, 80, ...
    callbackFixture.cancel);
assert(callbackOut.debounce_samples == 5 && ...
    callbackOut.metrics.gpio_rising_edges == 1, ...
    ['Callback-bound P02 dependencies must survive module path cleanup ' ...
    'and a conflicting model path.']);
clear searchPathCleanup;

%% Independent sweeps and deliberately broken qualification
debounceBypassed = model(fixture.raw_button, 1, 0, 200, fixture.cancel);
debounceQualified = model(fixture.raw_button, 1, 5, 200, fixture.cancel);
assert(debounceBypassed.metrics.gpio_rising_edges > ...
    debounceQualified.metrics.gpio_rising_edges, ...
    'Debounce bypass must expose extra GPIO edges from the same input.');
assert(debounceBypassed.timeout_samples == debounceQualified.timeout_samples, ...
    'The debounce lever must not mutate the independent timeout setting.');
stuckFixture = p02_scenario('stuck-high', 1, 120, 6);
shortTimeout = model(stuckFixture.raw_button, 1, 5, 15, stuckFixture.cancel);
longTimeout = model(stuckFixture.raw_button, 1, 5, 40, stuckFixture.cancel);
assert(shortTimeout.metrics.max_high_run_ms == 15, ...
    'Short maximum-on setting must bound the high run independently.');
assert(longTimeout.metrics.max_high_run_ms == 40, ...
    'Long maximum-on setting must bound the high run independently.');
assert(shortTimeout.debounce_samples == longTimeout.debounce_samples, ...
    'The maximum-on lever must not mutate debounce qualification.');

%% Malformed-input and resource-bound rejection
assertReject(@() model([], 1, 1, 1), 'P02:model:RawButton');
assertReject(@() model(ones(2, 2), 1, 1, 1), 'P02:model:RawButton');
assertReject(@() model([0 1i], 1, 1, 1), 'P02:model:RawButton');
assertReject(@() model([0 NaN], 1, 1, 1), 'P02:model:RawButton');
assertReject(@() model([0 2], 1, 1, 1), 'P02:model:RawButton');
assertReject(@() model([0 1], 1, 1, 1, [0 2]), 'P02:model:Cancel');
assertReject(@() model([0 1], 1, 1, 1, [0 0 0]), 'P02:model:LengthMismatch');
assertReject(@() model([0 1], 0, 1, 1), 'P02:model:SamplePeriod');
assertReject(@() model([0 1], 1, -1, 1), 'P02:model:Debounce');
assertReject(@() model([0 1], 1, 1, 0), 'P02:model:MaxOn');
assertReject(@() model([0 1], 1, 1, 0.5), 'P02:model:MaxOnResolution');
assertReject(@() model([0 1], realmin, realmax, realmax), ...
    'P02:model:TimingResourceBound');
tooLong = false(1, 1000001);
assertReject(@() model(tooLong, 1, 1, 1), 'P02:model:ResourceBound');
clear tooLong;
assertReject(@() p02_scenario('unknown', 1, 20, 0), 'P02:scenario:Kind');
assertReject(@() p02_scenario('normal', 0, 20, 0), 'P02:scenario:SamplePeriod');
assertReject(@() p02_scenario('normal', 1, 0, 0), 'P02:scenario:Horizon');
assertReject(@() p02_scenario('normal', 1, 20, -1), 'P02:scenario:Bounce');
assertReject(@() p02_scenario('normal', 1, 1000001, 0), ...
    'P02:scenario:ResourceBound');
integerScenario = p02_scenario('normal', uint8(1), uint8(120), uint8(6));
assert(isa(integerScenario.time_ms, 'double'), ...
    'Accepted integer scenario timings must normalize to double before arithmetic.');

disp('P02 checks passed.');
end

function assertReject(callable, expectedIdentifier)
didReject = false;
try
    callable();
catch caught
    didReject = strcmp(caught.identifier, expectedIdentifier);
end
assert(didReject, 'Expected rejection with identifier %s.', expectedIdentifier);
end
