%% P12 - Measure Jitter and Worst-Case Response Time
% Guiding question:
% What inputs, observable effects, and failure modes matter when you measure Jitter and Worst-Case Response Time?
%
% P11 supplied bounded resource blocking. P12 keeps nominal release,
% actual release, first start, and completion distinct so release jitter,
% response time, and nominal completion latency cannot be conflated.

%% Read the timestamp and response identities
disp('j = actual release - nominal release.');
disp('R = completion - actual release = blocking + interference + execution.');
disp('L = completion - nominal release = j + R.');
disp('Prediction: if only actual release moves, which of R and L changes?');

%% Visualize the deterministic baseline and controlled changes
experiment;

%% Move one live lever at a time
% Reset release-offset amplitude before changing the P11 blocking bound.
% The UI calls the same pure bounded model used by the experiment and checks.
interactive;
