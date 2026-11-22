# PicoRV32 reconstruction in Vexim

The baseline is the official
[PicoRV32 source](https://github.com/YosysHQ/picorv32/blob/ef203c2b0a3fb793280f5114941416c425c5b461/picorv32.v)
at `ef203c2b0a3fb793280f5114941416c425c5b461`. The benchmark enables
`ENABLE_MUL` and `ENABLE_DIV` with the other upstream defaults. The
original configuration excludes compressed instructions and interrupts.

Yosys elaborates and lowers the whole CPU to primitive logic while
preserving the two-read, single-write register file. The Vexim importer
reconstructs that representation, and veximc compiles it to SystemVerilog.
Undefined constants are concretized to zero during import. The generated
Vexim design has 24,199 lines and compiled in about 67 ms in one run
inside Docker.

The official and reconstructed cores each pass a custom program under
three deterministic memory stall patterns. The 41 observed transactions
match in content and cycle number for each seed.

| Seed | Matching bus transactions | Final cycle |
|---:|---:|---:|
| 1 | 41 | 574 |
| 73 | 41 | 579 |
| 913 | 41 | 554 |

The test checks multiplication, signed and unsigned division, remainder,
division by zero, signed overflow, a memory read/write and a taken
branch. The test does not establish full ISA compliance.

| ECP5 synthesis metric | Official RTL | Intermediate directly | Vexim round trip |
|---|---:|---:|---:|
| LUT4 | 2,479 | 3,476 | 3,597 |
| Flip-flops | 1,067 | 1,070 | 1,070 |
| CCU2C carry cells | 371 | 0 | 0 |
| Distributed memory primitives | 32 | 32 | 32 |

The intermediate control feeds the same pre-Vexim Yosys JSON directly
to `synth_ecp5`. That control already loses dedicated carry mapping
and accounts for 997 of the 1,118 additional LUT4s relative to the original.
The round trip adds another 121 LUT4s. The table describes synthesis.
It does not measure place-and-route, Fmax or board behavior.

## Reproduce in PowerShell

Run from the Vexim checkout:

~~~powershell
git clone https://github.com/YosysHQ/picorv32.git build/picorv32-upstream
git -C build/picorv32-upstream checkout --detach ef203c2b0a3fb793280f5114941416c425c5b461
docker build -f benchmarks/Dockerfile -t vexim-benchmarks .
docker build -f benchmarks/serv/Dockerfile -t vexim-serv .
New-Item -ItemType Directory -Force build/picorv32-vexim | Out-Null
docker run --rm --network none --mount "type=bind,source=$((Get-Location).Path)/build/picorv32-upstream,target=/rtl,readonly" --mount "type=bind,source=$((Get-Location).Path)/benchmarks,target=/benchmarks,readonly" --mount "type=bind,source=$((Get-Location).Path)/build/picorv32-vexim,target=/output" -e PYTHONDONTWRITEBYTECODE=1 vexim-serv python3 /benchmarks/picorv32/run.py
~~~

The importer checks the pinned source hash. The output includes the
generated `pico.vxm`, emitted SystemVerilog, traces, license and
`results.json`.
