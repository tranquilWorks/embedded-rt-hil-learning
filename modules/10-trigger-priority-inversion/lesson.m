%% P10 - Trigger Priority Inversion
% Guiding question:
% What inputs, observable effects, and failure modes matter when you trigger Priority Inversion?
%
% P09 scheduled independent ready jobs. P10 adds one mutex: High can be
% blocked by Low while unrelated Medium work decides how long Low waits to
% run and release the resource.

%% Read owner, waiter, and effective-priority rules
disp('CPU owner and mutex owner are separate: a preempted task keeps its mutex.');
disp('High is not ready while blocked; direct blocking is Low service, while Medium service is inversion delay.');
disp('Prediction: when High blocks at 2 ms with inheritance enabled, which task owns [2,3) ms?');

%% Visualize the deterministic baseline and controlled changes
experiment;

%% Move one live lever at a time
% Reset Medium work before moving Low's mutex-held share. The UI calls the
% same pure bounded model used by the experiment and executable checks.
interactive;
