%% P03 - Compare Polling and Interrupts
% Guiding question:
% What inputs, observable effects, and failure modes matter when you compare
% Polling and Interrupts?
%
% P02 qualified a sampled input before changing controller state. P03 keeps
% that event meaning fixed and changes how software notices each request.

%% Read the observation and capacity rules
disp('Polling detects a transient pulse only when an actual poll instant lies inside it.');
disp('Interrupts retain finite outstanding work; masking delays dispatch and a full queue drops arrivals.');
disp('Prediction: which baseline mechanism will miss a 0.3 ms pulse between 0.5 ms checks?');

%% Visualize the deterministic baseline and controlled changes
experiment;

%% Move one live lever at a time
% Reset one lever before changing the next. The UI calls the same pure
% model used by the experiment and executable checks.
interactive;
