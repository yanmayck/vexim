# Signed INT8 matrix accelerator on ECP5

This benchmark compares two descriptions of a 12×12 systolic array with
144 processing elements. Each element forwards signed eight-bit operands
and accumulates signed 16-bit products into a 32-bit accumulator. Input
vectors enter on the north and west sides with row/column skew. A shared
step input stalls the entire pipeline. Row and column inputs select the
result to read.

The generator emits a Vexim design and a direct SystemVerilog baseline.
Both have the same datapath, pipeline depth and step/reset contract. The
Vexim version uses explicit sign extension and width-preserving modular
multiplication. The direct version uses native signed expressions. Their
readout reduction trees also differ. The comparison measures these two
implementations and the complete synthesis flow.

Icarus checks 432 output values per implementation against integer
matrix multiplication, including negative operands, repeated reset,
stalls and an out-of-range output selector. Yosys 0.33 runs
`synth_ecp5` for standalone resource counts and again with the common
serial test harness. nextpnr-ecp5 0.6 uses router2 to route the harness on the
LFE5U-85F, CABGA381, speed grade 6, for seeds 1–5 with a 75 MHz target.
I/O pins are assigned automatically. Board I/O timing and power are
outside this benchmark.

The runner measures compiler wall time and peak process RSS five times
inside Docker. Wall time includes process startup and reading/writing the
mounted directory. It also saves standalone synthesis time, per-seed
resource utilization, post-route Fmax and text configuration files.

## Measured results

| Measure | Direct SystemVerilog | Vexim |
|---|---:|---:|
| Output values checked | 432/432 | 432/432 |
| Standalone LUT4s | 6,557 | 6,557 |
| Standalone flip-flops | 9,024 | 9,024 |
| Post-pack combinational cells with harness | 11,767 | 11,767 |
| DSP multipliers | 144 | 144 |
| BRAM blocks | 0 | 0 |
| Median routed Fmax | 58.03 MHz | 55.29 MHz |
| Seeds meeting 75 MHz | 0/5 | 0/5 |

| Seed | Direct Fmax (MHz) | Vexim Fmax (MHz) |
|---|---:|---:|
| 1 | 58.03 | 58.45 |
| 2 | 57.39 | 50.69 |
| 3 | 58.88 | 60.47 |
| 4 | 43.97 | 55.29 |
| 5 | 60.92 | 55.03 |

Vexim compiled 6,449 lines in a median of
67 ms across five runs,
with a maximum peak RSS of 3.75 MiB.
Both routed designs used 144 of the device's 156 multiplier blocks.
The two median runs were limited by a route through the result readout
into the harness capture register.

## Reproduce in PowerShell

Run from the Vexim checkout:

~~~powershell
docker build -f benchmarks/Dockerfile -t vexim-benchmarks .
docker build -f benchmarks/serv/Dockerfile -t vexim-serv .
docker build -f benchmarks/ecp5-gemm/Dockerfile -t vexim-ecp5-tools .
New-Item -ItemType Directory -Force build/ecp5-gemm | Out-Null
docker run --rm --network none --mount "type=bind,source=$((Get-Location).Path)/benchmarks/ecp5-gemm,target=/case,readonly" --mount "type=bind,source=$((Get-Location).Path)/build/ecp5-gemm,target=/output" vexim-ecp5-tools python3 /case/run.py
~~~

Read `build/ecp5-gemm/results.json` for the metrics and seed data.
