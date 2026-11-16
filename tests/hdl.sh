#!/bin/sh
set -eu
yosys -Q -p 'read_verilog -sv tests/adder_ref.sv; read_verilog -sv build/adder.sv; proc; equiv_make adder_ref adder equivalence; hierarchy -top equivalence; equiv_simple; equiv_status -assert'
iverilog -g2012 -s tb -o build/register-test build/register_demo.sv tests/register_tb.sv
vvp build/register-test
yosys -Q -p 'read_verilog -sv build/uart_tx.sv; synth -top uart_tx; check -assert'
iverilog -g2012 -s tb -o build/uart-test build/uart_tx.sv tests/uart_tb.sv
vvp build/uart-test
yosys -Q -p 'read_verilog -sv build/ram.sv; synth -top ram; check -assert'
iverilog -g2012 -s tb -o build/ram-test build/ram.sv tests/ram_tb.sv
vvp build/ram-test
yosys -Q -p 'read_verilog -sv build/ram_shallow.sv; synth -top ram; check -assert'
iverilog -g2012 -DSHALLOW -s tb -o build/ram-shallow-test build/ram_shallow.sv tests/ram_tb.sv
vvp build/ram-shallow-test
