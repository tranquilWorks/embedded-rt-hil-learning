%% P13 - Move Samples with DMA
% Guiding question:
% What inputs, observable effects, and failure modes matter when you move
% Samples with DMA?
%
% P12 separated request, start, and completion timing. P13 applies those
% timestamps to peripheral DMA beats, then separates completed movement,
% block ownership, processor service demand, and destination integrity.

%% Read the serialized DMA-beat and ownership rules
disp('a_i=(i-1)T_s; q=A+b/r; s_i=max(a_i,f_(i-1)); f_i=s_i+q.');
disp('A block completion transfers ownership; it does not prove that destination addresses or data are correct.');
disp('Prediction: if only block size grows, which changes first: bus load, completion interrupts, or block-ready latency?');

%% Visualize the deterministic baseline and controlled changes
experiment;

%% Move one live lever at a time
% Reset block size before changing DMA payload rate. The UI calls the same
% pure bounded model used by the experiment and executable checks.
interactive;
