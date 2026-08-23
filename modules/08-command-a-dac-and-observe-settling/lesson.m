%% P08 - Command a DAC and Observe Settling
% Guiding question:
% What inputs, observable effects, and failure modes matter when you command
% a DAC and Observe Settling?
%
% P07 asked whether sampled ADC codes preserve an analog input. P08 follows
% the reverse direction: a DAC code selects a held target, but the analog
% output reaches that target only through a finite output stage.

%% Read the quantizer, latch, and settling rules
disp('A recorded DAC code is not evidence that the active output latch changed or that the pin settled.');
disp('The ideal target is k*V_ref/2^B; the analog error is first-order with a declared slew cap.');
disp('Prediction: after a 0.5 V to 2.5 V request, which happens first: code recording or 10 mV settling?');

%% Visualize the deterministic baseline and controlled changes
experiment;

%% Move one live lever at a time
% Reset one lever before changing the next. The UI calls the same pure,
% bounded analytical model used by the experiment and executable checks.
interactive;
