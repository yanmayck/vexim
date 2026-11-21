# Frozen paired synthesis benchmark

These sources are the six approved outputs from the 2026-11-18 Gemini 4 Argon
comparison, captured before the Vexim 0.3.1 dead-code elimination pass.
The Vexim-generated SystemVerilog is preserved so the published comparison
can be repeated independently of subsequent compiler changes. The original
`.vxm` sources are included for inspection.

Run `sh run_benchmarks.sh` from the repository root, or
`.\run_benchmarks.ps1` in PowerShell. Docker builds pinned Ubuntu packages
Yosys 0.33, Icarus 12 and Verilator 5.020. The runner lints and simulates
every design, synthesizes generic cells,
and maps every design using the same `synth_ice40` command. No API key,
model calls or GPU are needed. Results, logs, hashes and netlists are written
to `build/benchmarks`.

| Block | Vexim LUT4 | SystemVerilog LUT4 | Vexim FF | SystemVerilog FF |
|---|---:|---:|---:|---:|
| Round-robin arbiter | 23 | 21 | 7 | 7 |
| Memory controller | 151 | 237 | 68 | 68 |
| Automation CPU | 228 | 229 | 163 | 163 |

The paired behavioral specifications were identical and the reference
implementations and testbenches were excluded from model prompts. Each
language received up to two submissions and a fresh conversation. Vexim
additionally received its grammar. The fixed benches exercise arbitration,
memory descriptors and partial writes, and a software-interpreted CPU.

Both memory candidates also passed a separate 1 GiB write/readback harness.
Its `stream.cpp` is included. Running it requires Verilator and a C++
compiler and is outside the default lightweight benchmark image.

LUT4, flip-flop, carry and memory cell types remain in the JSON results.
This experiment establishes neither a general language advantage nor a
physical power/area benefit. Device-specific placement, routing and timing
are outside this benchmark.
