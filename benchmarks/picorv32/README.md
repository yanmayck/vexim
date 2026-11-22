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

## Word-level arithmetic import

Append `--word` to the Docker command and mount a separate output
directory. This excludes RTLIL adders and subtractors from the early
`techmap`. The importer writes width-matched Vexim arithmetic and
handles widening and truncation explicitly.

| ECP5 flow | Gate-level import LUT4s | Word-level import LUT4s | Gate-level / word-level CCU2C |
|---|---:|---:|---:|
| Intermediate directly | 3,476 | 2,665 | 0 / 242 |
| Vexim round trip | 3,597 | 2,782 | 0 / 242 |

The original RTL remains at 2,479 LUT4s and 371 CCU2C. The word-level
run preserves 39 additions and six subtractions. It compiles 23,615
Vexim lines in about 67 ms and matches the official CPU's 41 bus
transactions for each of the three seeds, with identical cycle counts.
These are synthesis and simulation measurements.

## Preserve muxes and ordering comparisons

The `--mux` flag additionally retains mux cells. The `--compare` flag
retains ordering comparisons and uses the signed and unsigned Vexim
operators. Both flags retain word-level adds and subtracts. The flags
can be combined. All three profiles matched the 41 bus transactions
through the same three memory-stall patterns, including cycle counts.

| ECP5 synthesis | Direct intermediate LUT4s | Vexim round-trip LUT4s | Vexim CCU2C |
|---|---:|---:|---:|
| Add/sub only | 2,665 | 2,782 | 242 |
| Add/sub and 147 mux cells | 2,678 | 2,802 | 242 |
| Add/sub and four ordering comparisons | 2,581 | 2,723 | 291 |
| Add/sub, muxes and comparisons | 2,602 | 2,718 | 307 |

The combined control renames private Yosys objects before the second
technology mapping to avoid a name collision in Yosys 0.33. The
generated Vexim arm uses the original extracted cell IDs.

For the combined profile the runner also exports the intermediate
directly to SystemVerilog with Yosys, then resynthesizes it. This
additional control maps to 2,609 LUT4s and 307 CCU2C. The Vexim
round trip uses 109 more LUT4s than this direct SV export.

### ECP5 post-route timing

The official design and the combined Vexim profile use the same
five-pin serial harness, ECP5-85F CABGA381 speed grade 6, and router2
with a 75 MHz target.

| Metric | Official PicoRV32 | Vexim combined |
|---|---:|---:|
| Packed combinational cells | 3,722 | 3,887 |
| Median Fmax | 79.93 MHz | 71.75 MHz |
| Seeds reaching 75 MHz | 4/5 | 1/5 |
| Fmax seeds 1–5 (MHz) | 68.98, 79.93, 79.60, 88.55, 85.14 | 75.83, 70.84, 71.75, 70.41, 73.38 |

To reproduce, first run the combined synthesis profile. Build the
`vexim-ecp5-tools` image as in the [ECP5 benchmark](../ecp5-gemm/README.md).
Run the same Docker mounts with that image and command
`python3 /benchmarks/picorv32/route.py official`, then
`python3 /benchmarks/picorv32/route.py vexim`.
Timing is an estimate for the wrapped core, with automatic pin placement.
