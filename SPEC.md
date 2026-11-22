# Vexim 0.3 language specification

Vexim describes digital hardware with explicitly sized signals. Write a module in a `.vxm` file, run `veximc check FILE.vxm` to validate it, and run `veximc build FILE.vxm -o FILE.sv` to emit synthesizable SystemVerilog. Omitting `-o` writes SystemVerilog to standard output.

## Source layout

A file contains one module. Its first statement is `module NAME` and its last is `end`. Each statement occupies one line. Whitespace separates tokens. Blank lines and text from `#` to the end of the line are ignored. A name starts with an ASCII letter or underscore and continues with ASCII letters, digits, or underscores. Names are case-sensitive.

Use `input NAME uN`, `output NAME uN`, and `wire NAME uN` to declare ports and internal signals. `uN` is an unsigned bit vector of width 1 through 64. All signal names in a module must be unique. Drivers may refer to signals declared later in the file.

## Combinational logic

A combinational driver has the form `comb DEST OP OPERANDS`. Each destination is a declared output or wire. Except where an operation specifies a different width rule, the compiler requires exact widths.

| Operation and operands | Result and width rule |
|---|---|
| `const VALUE` | Unsigned decimal integer from 0 through 2^N − 1 for a destination of width N. |
| `copy SRC` | Value of a signal with the same width as the destination. |
| `zext SRC` | Value of a strictly narrower signal padded with zeros at the high end. |
| `add A B`, `sub A B`, `mul A B` | Addition, subtraction, or multiplication modulo 2^N. Both operands have destination width N. |
| `and A B`, `or A B`, `xor A B` | Bitwise operation. Both operands have destination width. |
| `slice SRC MSB LSB` | Inclusive range with zero-based indices. Both indices must be within the source, with MSB ≥ LSB. The destination width is MSB − LSB + 1. |
| `concat A B` | Joins signals with `A` in the high bits. The destination width is the sum of both widths. |
| `eq A B`, `ne A B` | Equality or inequality. The operands must have equal width and the destination must be `u1`. |
| `lt A B`, `le A B`, `gt A B`, `ge A B` | Unsigned comparison. Operands have equal width and the destination is `u1`. |
| `slt A B`, `sle A B`, `sgt A B`, `sge A B` | Signed two’s-complement comparison of equal-width operand bit patterns. The destination is `u1`. |
| `mux SELECT A B` | Selects `A` for 1 and `B` for 0. The selector is `u1` and both branches have destination width. |

Operands are signal names except the decimal literal in `const` and the decimal indices in `slice`. Use virtual wiring through declared signals to compose operations.

This example preserves the carry by widening both operands before adding:

```vexim
module adder
input a u8
input b u8
output sum u9
wire a_wide u9
wire b_wide u9
comb a_wide zext a
comb b_wide zext b
comb sum add a_wide b_wide
end
```

## Sequential logic

`sync DEST CLOCK RESET DATA [RESET_VALUE]` updates `DEST` on the rising edge of `CLOCK`. When `RESET` is high at that edge, it assigns the reset value. Otherwise it samples `DATA`. The clock and reset must be `u1` module inputs, and data must match the destination width. The optional reset value follows the same rules as a combinational constant and defaults to zero. The reset is synchronous.

Feed the current register value through a multiplexer to hold state when an enable is low:

```vexim
module enabled_register
input clk u1
input rst u1
input enable u1
input data u8
output q u8
wire next_q u8
comb next_q mux enable data q
sync q clk rst next_q 42
end
```

## Validation

After validation, the emitter eliminates internal signal chains that cannot
affect outputs. It preserves input/output ports, live register dependencies,
and all memory write ports and their dependencies. Partial unused bits may
remain in a live signal and can produce lint warnings.

`veximc build FILE.vxm --opt-area` folds combinational constants
before this elimination pass. It evaluates width-limited arithmetic,
comparisons, slices and concatenations, folds selected branches when a
mux selector is constant, and simplifies AND with zero and OR with
all ones. Registers remain stateful and memory writes are preserved.
With `--opt-area`, a mux may also share two additions, subtractions,
equalities, or inequalities over operands wider than eight bits. The
branches must use the same operator, share an operand, and have no
other consumers. Subtraction preserves operand order. The compiler
moves the selection before the shared operator. This rewrite preserves
binary behavior and may change four-state simulation with an unknown
selector. FPGA area and timing depend on the mapping. The flag is
opt-in. Builds without it keep the original emission path.

The compiler also tracks conservative unsigned upper bounds through
combinational drivers. It can emit narrower adders and multipliers when
those bounds prove that upper bits are zero, and smaller registers when
both the reset value and stored data fit. Outputs retain their declared
widths through zero extension. Unproven bounds, including full-range
feedback, retain the original widths. The narrowing preserves binary
behavior after the first defined register update.

Every output and wire must have exactly one driver. Inputs are driven by the caller. The compiler rejects combinational cycles, including cycles through multiplexer selectors. Feedback through a register is allowed. Compiler diagnostics identify the source line, and generated SystemVerilog includes the source line alongside each driver.

See the [UART transmitter](examples/uart_tx.vxm) for a complete design that combines counters, bit slicing, and conditional state updates.

## Parameters

`param NAME DEFAULT` declares an unsigned decimal compile-time value. Declare it before use. Use `uNAME` as a signal or memory word type, or `NAME` in place of a memory depth. The resolved value must meet the bounds for its position. Parameters, signals, and memories share one namespace.

Both `check` and `build` accept a repeatable `--param NAME=VALUE` option. Unknown and duplicate overrides are errors. The compiler validates the specialized module and emits concrete widths and depths in SystemVerilog.

## Structural generation

`generate INDEX COUNT` repeats a module body fragment, ending at
`endgenerate`. The count is a literal or previously declared parameter
in the range 1–1024. The index is zero-based and scoped to the block.
Nested blocks use distinct index names. Use `${INDEX}` to insert the
decimal index into a name or constant, `${INDEX+1}` to add a literal
offset, and `$(PARAM)` to insert a parameter value. Generated statements
obey the ordinary type and driver rules and report the original source
line. Generation is limited to 16 nested levels and 100,000 expansion
steps per module.

```vexim
module lanes
param N 4
generate I N
input in_${I} u8
output out_${I} u8
comb out_${I} copy in_${I}
endgenerate
end
```

## Indexed memory

- `mem NAME uN DEPTH` declares an array of unsigned words. Depth can be a decimal integer or a parameter from 1 to 2,147,483,647. The practical depth depends on the synthesis target.
- `write NAME CLK ENABLE ADDR DATA` defines the memory's single write port. It writes on the rising edge of the one-bit clock input when the one-bit enable is set. The data width must match the word width.
- `comb DEST read NAME ADDR` adds a combinational read. The destination width must match the word width. A read from an address just written observes the new word after the clock edge.
- `read_sync DEST NAME CLK ADDR` samples the address and registers the result on the rising edge of a one-bit clock input. It can run concurrently with `write`. On a same-edge read and write to the same address on one clock, RTL simulation reads the old word. A caller that requires forwarding can add an explicit bypass. The read output has no implicit reset.
- All addresses have width `max(1, ceil(log2(DEPTH)))`. An out-of-range read returns zero and an out-of-range write leaves the memory intact. Valid words have unspecified contents until written. The memory has no implicit reset.
- Combinational read addresses participate in combinational cycle checks. Writes and registered reads cross a clock edge.

The [RAM example](examples/ram.vxm) accepts independent read and write addresses. Specialize it to 12 words with:

```sh
cargo run -- build examples/ram.vxm --param DEPTH=12 -o ram.sv
```

## Constant ROM

Declare an immutable table as `rom NAME uN VALUE VALUE ...` with
space-separated unsigned decimal entries. The address width is
`max(1, ceil(log2(entries)))`. A registered read
`rom_read DEST NAME CLK ADDR` samples the address on the rising edge
of the one-bit clock. Padding addresses return zero. The read result
is unspecified before the first edge. No reset or write port is
required. The emitted synchronous array supports target-specific
ROM inference. See the [UP5K ROM benchmark](benchmarks/rom-packing/README.md).

## Whole-design optimization

`veximc design TOP INPUT.sv INPUT.vxm ... -o OUTPUT.sv [--share] [--prune]`
elaborates a connected design using Yosys from PATH and emits flattened
SystemVerilog. The input list contains self-contained modules, and
inter-module wiring is expressed in SystemVerilog. Relative includes
and external memory files are outside this command's staging contract.

`--share` runs SAT-based resource sharing after flattening. It can
merge operators from different instances when their activation is
exclusive. It leaves concurrently used resources in place. `--prune`
removes unobserved internal logic and retains the top-level ports.
CPU firmware access patterns are outside this analysis unless the
hardware connectivity itself makes an internal value unused.
