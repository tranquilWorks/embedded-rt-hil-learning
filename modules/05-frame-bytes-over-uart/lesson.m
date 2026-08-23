%% P05 - Frame Bytes over UART
% Guiding question:
% What inputs, observable effects, and failure modes matter when you frame
% Bytes over UART?
%
% P04 exposed finite timer ticks. P05 keeps the byte values fixed and asks
% where an asynchronous receiver's own clock samples each UART logic slot.

%% Read the byte-frame and sampling rules
disp('UART idles high, starts low, sends d0 through d7, then parity if used and high stop bits.');
disp('For binary UART, T_bit = 10^6 / baud us and 8-N-1 spends ten bits per byte.');
disp('Prediction: what payload efficiency and line time follow at the baseline baud?');

%% Visualize the deterministic baseline and controlled changes
experiment;

%% Move one live lever at a time
% Reset one lever before changing the next. The UI calls the same pure
% frame and sampling model used by the experiment and executable checks.
interactive;
