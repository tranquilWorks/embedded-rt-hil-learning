%% P16 - Execute a Multi-Rate Processing Graph
% Guiding question:
% What inputs, observable effects, and failure modes matter when you execute
% a Multi-Rate Processing Graph?

%% Read the mechanism inherited from P15
% P15 aligned record timestamps. P16 treats those timestamps as releases:
% one fast filter fires per sample and one slow frame node fires after every
% D samples. Values, timestamps, rate relations, order, cost, and deadline
% policy are separate parts of correctness.
disp('P16 turns aligned samples into explicit fast and slow graph firings.');

%% Make one prediction, then show the baseline
% If the slow node costs 1200 us, will changing its period from 4000 us to
% 1000 us keep outstanding work bounded even though its calculation is unchanged?
disp('Prediction: what happens when slow-node demand exceeds its service rate?');

%% Observe baseline, two isolated levers, and the broken case
% experiment resets between the decimation-factor and execution-cost
% sweeps. It then violates producer-before-consumer order at a frame edge.
experiment;

%% Move one control at a time
% D changes firing rate; cost changes latency; order changes which sample
% version is visible; timeout action chooses late output or cancellation.
interactive;
