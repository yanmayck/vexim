# Vexim

Vexim is a small, explicitly typed hardware description language. The Rust compiler, `veximc`, checks `.vxm` files, builds a typed internal representation, and emits synthesizable SystemVerilog.

The [language specification](SPEC.md) describes the syntax, width rules, and register behavior with complete examples.

```sh
cargo run -- check examples/adder.vxm
cargo run -- build examples/adder.vxm -o adder.sv
```

Requires Rust 1.85 or newer. The compiler has no third-party Rust dependencies.

```text
module adder
input a u8
input b u8
output sum u9
wire left u9
wire right u9
comb left zext a
comb right zext b
comb sum add left right
end
```

Version 0.2 accepts one module per file, with `#` comments and one statement per line. Names may contain ASCII letters, digits, and underscores, and may not start with a digit.

- `input NAME uN`, `output NAME uN`, and `wire NAME uN` declare unsigned signals of 1 to 64 bits.
- `comb DEST copy SRC` copies an equal-width signal. `zext` explicitly extends a narrower signal with zeros.
- `comb DEST OP A B` supports `add`, `sub`, `and`, `or`, and `xor` on equal-width signals. Arithmetic wraps at the declared width.
- `comb DEST const VALUE` assigns a decimal unsigned literal that fits the destination.
- `comb DEST slice SRC MSB LSB` extracts an inclusive range with the most significant index first. `comb DEST concat A B` joins two signals with `A` at the high end. The result must match the destination width.
- `comb DEST eq A B` and `comb DEST ne A B` compare equal-width signals and produce a `u1` result.
- `comb DEST mux SELECT A B` selects `A` when the one-bit selector is 1, and `B` when it is 0. Both branches must match the destination width.
- `sync DEST CLOCK RESET DATA [RESET_VALUE]` samples equal-width data on a rising clock edge. The active-high synchronous reset assigns an optional decimal value that fits the destination and defaults to zero. Clock and reset are one-bit inputs.
- Every output and wire requires exactly one driver. The compiler rejects combinational cycles and reports errors by source line.

`examples/uart_tx.vxm` implements an 8N1 UART transmitter at four clock cycles per bit. The public HDL suite simulates all 256 byte values, restart attempts while busy, successive frames, and a reset during transmission.

```sh
mkdir -p build
cargo run --locked -- build examples/uart_tx.vxm -o build/uart_tx.sv
```

With a local RTL Forge checkout, run `sh tests/check_rtl_forge_uart.sh ../rtl-forge` using Icarus Verilog, Yosys, SymbiYosys, and Z3. This runs the original testbench and compares `tx` and `busy` against the original module for 84 cycles after the initial reset. The reference is read from the local checkout.

The public compiler covers native Vexim input and SystemVerilog output. Legacy HDL import, cloud verification, and AI agents are planned for Vexim Cloud.

The language and compiler are released under the [Apache License 2.0](LICENSE).
