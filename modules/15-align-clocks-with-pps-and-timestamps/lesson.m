%% P15 - Align Clocks with PPS and Timestamps
% Guiding question:
% What inputs, observable effects, and failure modes matter when you align
% Clocks with PPS and Timestamps?

%% Read the mechanism inherited from P14
% P14 preserved record identity and order, but one ordered stream does not
% prove that two devices share time. P15 gives the local timestamp counter
% an offset, oscillator skew, and finite tick. A PPS capture supplies phase;
% its sequence ID and timestamp label supply epoch.
disp('P15 separates a sharp PPS edge from the identity of the second it names.');

%% Make one prediction, then show the baseline
% If the first PPS removes local-clock offset, does a 40-ppm oscillator stay
% aligned for the next four seconds, or does its error keep accumulating?
disp('Prediction: what remains after a one-pulse offset correction?');

%% Observe baseline, two isolated levers, and the broken case
% experiment resets between initial-offset and oscillator-skew sweeps. It
% then drops one PPS ID and breaks the assumption that receive-array index
% still identifies the reference second.
experiment;

%% Move one control at a time
% Offset translates timestamps; skew changes their slope; timestamp tick
% quantizes captures; identity associates each PPS with its epoch. Timeout
% continuation and cancellation change anchor availability, not past time.
interactive;
