# Registered ROM packing on iCE40 UP5K

`rom table u8 99 124 119` declares three unsigned eight-bit entries.
`rom_read q table clk address` updates `q` on a rising edge of the
one-bit input clock. The address width is the ceiling of log2 of entry
count, with a minimum of one bit. Padding positions return zero. The
output remains unspecified until the first read edge. The compiler emits
an initialized array with a synchronous read and lets the target
synthesizer infer compatible memory.

This benchmark uses all 256 entries of the AES S-box. The original RTL
and both synthesized netlists passed all 256 addresses in Icarus, including
checking that the previous value was held before the next clock edge.

| Yosys 0.33 synthesis mode | LUT4 | FF | EBR |
|---|---:|---:|---:|
| Logic only, `-nobram` | 209 | 8 | 0 |
| Automatic ROM mapping | 0 | 0 | 1 |

Both measurements use the same Vexim source and `synth_ice40 -device u`.
Inference is target-dependent. The experiment measures synthesis and
netlist simulation, with no placement or timing results.

## Reproduce

From the Vexim checkout in PowerShell:

~~~powershell
docker build -f benchmarks/Dockerfile -t vexim-benchmarks .
docker build -f benchmarks/serv/Dockerfile -t vexim-rom .
New-Item -ItemType Directory -Force build/rom-packing | Out-Null
docker run --rm --network none --mount "type=bind,source=$((Get-Location).Path)/benchmarks/rom-packing,target=/case,readonly" --mount "type=bind,source=$((Get-Location).Path)/build/rom-packing,target=/output" vexim-rom python3 /case/run.py
~~~

The runner writes the cell counts in `build/rom-packing/rom-results.json`.
