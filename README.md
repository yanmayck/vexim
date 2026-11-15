# Vexim

Vexim is a small, explicitly typed hardware description language. The Rust compiler, `veximc`, checks `.vxm` files, builds a typed internal representation, and emits synthesizable SystemVerilog.

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

Version 0.1 accepts one module per file, with `#` comments and one statement per line. Names may contain ASCII letters, digits, and underscores, and may not start with a digit.

- `input NAME uN`, `output NAME uN`, and `wire NAME uN` declare unsigned signals of 1 to 64 bits.
- `comb DEST copy SRC` copies an equal-width signal. `zext` explicitly extends a narrower signal with zeros.
- `comb DEST OP A B` supports `add`, `sub`, `and`, `or`, and `xor` on equal-width signals. Arithmetic wraps at the declared width.
- `sync DEST CLOCK RESET DATA` samples equal-width data on a rising clock edge. The active-high synchronous reset clears the register. Clock and reset are one-bit inputs.
- Every output and wire requires exactly one driver. The compiler rejects combinational cycles and reports errors by source line.

This initial version covers native Vexim input and SystemVerilog output. Legacy HDL import, cloud verification, and AI agents are outside the public compiler. The planned hosted product is Vexim Cloud.

The language and compiler are released under the [Apache License 2.0](LICENSE).
