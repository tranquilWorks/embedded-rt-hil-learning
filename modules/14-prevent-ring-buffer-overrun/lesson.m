%% P14 - Prevent Ring-Buffer Overrun
% Guiding question:
% What inputs, observable effects, and failure modes matter when you prevent
% Ring-Buffer Overrun?

%% Read the mechanism inherited from P13
% P13 made completed-record timing and ownership explicit. P14 starts at
% that boundary. A producer advances a wrapped tail, a consumer advances a
% wrapped head, and the separate occupancy q makes all C slots usable:
% empty iff q=0, full iff q=C, next slot = 1+mod(slot,C).
disp('P14 keeps source identity, occupancy, and wrapped head/tail separate.');

%% Make one prediction, then show the baseline
% If average input and output capacities are exactly equal, must the finite
% ring capacity be one, four, or unbounded for this phase-aligned trace?
disp('Prediction: how much capacity absorbs records before each consumer visit?');

%% Observe baseline, two isolated levers, and the broken case
% experiment resets before each sweep and explains the transition after the
% plot. It then breaks the assumption that bounded occupancy and accepted
% writes prove loss-free delivery.
experiment;

%% Move one control at a time
% Capacity absorbs finite accumulation. Consumer quota changes long-run
% service capacity. Drop and overwrite choose loss; backpressure changes
% production timing and is valid only for a throttleable source.
interactive;
