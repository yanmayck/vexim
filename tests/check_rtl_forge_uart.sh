#!/bin/sh
# Run from the Vexim root with the generated build/uart_tx.sv in place.
set -eu
rtl_forge=${1:?provide the RTL Forge checkout path}
sed 's/^module uart_tx /module uart_tx_reference /' "$rtl_forge/rtl/uart_tx.sv" > build/uart_tx_reference.sv
iverilog -g2012 -s tb -o build/uart-original-test build/uart_tx.sv "$rtl_forge/tests/uart_tx.sv"
vvp build/uart-original-test
sby -f -d build/uart-equivalence tests/uart_equivalence.sby
