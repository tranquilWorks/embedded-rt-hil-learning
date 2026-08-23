%% P07 - Sample an ADC Without Aliasing
% Guiding question:
% What inputs, observable effects, and failure modes matter when you sample
% an ADC Without Aliasing?
%
% P06 showed that bus completion does not prove payload meaning. P07 asks
% what analog information remains distinguishable before those ADC codes
% are framed and transported.

%% Read the sampling, front-end, and code rules
disp('The analog front end acts before t_n=n/f_s; digital filtering cannot undo an existing fold.');
disp('The strict fixture rule is f_in < f_s/2; ADC bits change voltage resolution, not alias frequency.');
disp('Prediction: at f_in=180 Hz and f_s=1000 sample/s, what frequency should the codes represent?');

%% Visualize the deterministic baseline and controlled changes
experiment;

%% Move one live lever at a time
% Reset one lever before changing the next. The UI calls the same pure,
% bounded analytical model used by the experiment and executable checks.
interactive;
