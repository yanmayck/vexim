# Frozen paired synthesis benchmark

These sources are the six approved outputs from the 2026-11-18 Gemini 4 Argon
comparison, captured before the Vexim 0.3.1 dead-code elimination pass.
The Vexim-generated SystemVerilog is preserved so the published comparison
can be repeated independently of subsequent compiler changes. The original
`.vxm` sources are included for inspection.

Run `sh run_benchmarks.sh` from the repository root, or
`.\run_benchmarks.ps1` in PowerShell. Docker builds pinned Ubuntu packages
Yosys 0.33, Icarus 12, Verilator 5.020, and nextpnr-ice40 0.6. The runner lints and simulates
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
The memory controller also runs through nextpnr on the iCE40 HX8K in
the CT256 package, with seeds 1 through 5 and a shared 50 MHz target.
The standalone controller exposes 386 I/O bits, beyond the package
capacity. Both variants use the same five-pin serial harness, generated
from their sorted port lists. The tool assigns those five pins automatically.
The reported Fmax estimates the single clock domain of the wrapped
design after routing. Board pin constraints, external I/O
timing and power are outside this benchmark. Per-seed timing and utilization
reports are written to the same output directory.

| Seed | Vexim Fmax (MHz) | SystemVerilog Fmax (MHz) |
|---:|---:|---:|
| 1 | 106.61 | 86.95 |
| 2 | 116.71 | 82.05 |
| 3 | 102.76 | 86.95 |
| 4 | 107.17 | 92.95 |
| 5 | 116.52 | 92.95 |
| Median | 107.17 | 86.95 |

The wrapped designs use 562 and 649 packed logic cells respectively.
The standalone LUT4 counts in the preceding table exclude the harness.
