%% P02 - Drive GPIO with a State Machine
% Guiding question:
% What inputs, observable effects, and failure modes matter when you drive
% GPIO with a State Machine?
%
% P01 showed that software must finish before a physical deadline. Here the
% sampled decision is made explicit: qualify a noisy request, drive a logic
% output only in named active states, and return safe on timeout or cancel.

%% Read the state/output rule
disp('A sampled button becomes a command only after consecutive agreeing samples.');
disp('GPIO is high only in ACTIVE and QUALIFY_RELEASE; timeout or cancel enters safe-low LOCKOUT.');
disp('Prediction: which trace changes first when debounce time is increased?');

%% Visualize the deterministic baseline and controlled changes
experiment;

%% Move one live lever at a time
% Reset a lever before changing the next one. The UI calls the same pure
% model used by the experiment and executable checks.
interactive;
