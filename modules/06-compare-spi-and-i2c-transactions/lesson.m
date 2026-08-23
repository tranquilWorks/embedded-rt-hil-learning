%% P06 - Compare SPI and I2C Transactions
% Guiding question:
% What inputs, observable effects, and failure modes matter when you compare
% SPI and I2C Transactions?
%
% P05 separated UART payload from framing overhead. P06 keeps one register
% read fixed and asks where SPI and I2C spend clock pulses, elapsed time,
% and protocol-visible responses.

%% Read the register-read and response-ownership rules
disp('SPI shifts command/dummy MOSI and dummy/payload MISO simultaneously under one chip select.');
disp('I2C gives every byte a ninth response clock; the controller NACKs the final read byte normally.');
disp('Prediction: at equal clocks, what pulse counts and efficiencies follow for four returned bytes?');

%% Visualize the deterministic baseline and controlled changes
experiment;

%% Move one live lever at a time
% Reset one lever before changing the next. The UI calls the same pure,
% bounded transaction model used by the experiment and executable checks.
interactive;
