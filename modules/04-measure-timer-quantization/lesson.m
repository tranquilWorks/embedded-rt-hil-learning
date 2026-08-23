%% P04 - Measure Timer Quantization
% Guiding question:
% What inputs, observable effects, and failure modes matter when you measure
% Timer Quantization?
%
% P03 produced ideal event and service times. P04 keeps each edge meaning
% fixed and exposes what a finite completed-tick counter can encode.

%% Read the capture and range rules
disp('Each edge captures floor((time + phase) / tick), then the finite counter wraps.');
disp('Valid modular interval error can have either sign but remains inside one tick.');
disp('Prediction: will a true 37 us interval become 30 us, 40 us, or both at q = 10 us?');

%% Visualize the deterministic baseline and controlled changes
experiment;

%% Move one live lever at a time
% Reset one lever before changing the next. The UI calls the same pure
% model used by the experiment and executable checks.
interactive;
