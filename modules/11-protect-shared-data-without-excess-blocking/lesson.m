%% P11 - Protect Shared Data Without Excess Blocking
% Guiding question:
% What inputs, observable effects, and failure modes matter when you protect Shared Data Without Excess Blocking?
%
% P10 showed that priority inheritance removes third-party inversion delay
% but not real mutex-held service. P11 moves private preparation and local
% processing outside the mutex while preserving a coherent multiword copy.

%% Read coherence, freshness, and lock-scope rules
disp('Every reader and writer must follow the same exclusion protocol for a multiword live record.');
disp('Short scope protects only commit/copy; coherence does not promise the newest in-progress generation.');
disp('Prediction: can priority inheritance make private preparation held inside a coarse mutex disappear?');

%% Visualize the deterministic baseline and controlled changes
experiment;

%% Move one live lever at a time
% Reset writer preparation before changing protected record size. The UI
% calls the same pure bounded model used by the experiment and checks.
interactive;
