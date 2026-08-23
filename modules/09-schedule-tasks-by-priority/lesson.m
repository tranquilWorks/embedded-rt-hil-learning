%% P09 - Schedule Tasks by Priority
% Guiding question:
% What inputs, observable effects, and failure modes matter when you
% schedule Tasks by Priority?
%
% P08 named software scheduling as omitted command latency. P09 models that
% upstream layer: separate periodic jobs compete on one preemptive CPU.

%% Read release, ready, dispatch, completion, and deadline rules
disp('Each periodic release creates a distinct job with work, priority, and an absolute deadline.');
disp('The largest priority runs; a higher ready job preempts lower work, which later resumes.');
disp('Prediction: when control releases at 5 ms while logger is running, which task owns [5,6) ms?');

%% Visualize the deterministic baseline and controlled changes
experiment;

%% Move one live lever at a time
% Reset priority before changing WCET. The UI calls the same pure, bounded
% fixed-priority model used by the experiment and executable checks.
interactive;
