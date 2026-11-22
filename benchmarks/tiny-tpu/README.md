# TinyTPU vs. native Vexim

This benchmark compares the original TinyTPU at commit
[97c28d7](https://github.com/tinycomputers/tiny-tpu/tree/97c28d7587689707fe7ff9311eabc7a3949eaef6)
with a native Vexim implementation of its 4x4 weight-stationary array.
Both have 16 multiply-accumulate elements, signed INT8 inputs and
32-bit accumulation. The Vexim controller uses a single phase counter.
The upstream design has an asynchronous reset. Vexim uses a synchronous
reset, and the shared test holds reset across a rising edge.

The runner checks upstream source hashes and uses sv2v 0.0.13 to lower
unpacked SystemVerilog ports for Yosys. Both wrappers expose the same
packed matrix ports. The upstream debug ports are unconnected.

Icarus checks 64 consecutive tiles per design against integer matrix
multiplication, including signed extremes and 61 seeded random pairs.
All 16 words are checked for each tile. The done pulse is checked on
cycle 14 after start. The last word is captured on cycle 15, so estimated
tile latency is calculated as 15 clock periods. This includes the internal
weight load and result capture. The wide input and output buses are
parallel at the design boundary. Serial transport in the timing harness
and external board I/O are outside the tile latency measurement.

The optional compact Vexim design narrows the four rows to 16, 17, 17
and 18 bits. A signed INT8 product is in [-16,256, 16,384]. Adding up
to four such products stays within the selected signed widths. The
output registers store 18 bits and sign-extend to the same 32-bit ports.
This is an explicit datapath change, not an automatic compiler pass.

## ECP5 results

Yosys 0.33 maps both designs to ECP5. nextpnr uses the same five-pin
serial harness, LFE5U-85F CABGA381 speed grade 6 and router2 with a 75 MHz
target. Seeds 1 through 5 each get a 120-second routing budget. Medians
use successful routes. Standalone LUT4 counts and packed logic cells
from the wrapped design are separate measures.

| Metric | TinyTPU upstream | Vexim 32-bit | Vexim compact |
|---|---:|---:|---:|
| Output words checked | 1,024 | 1,024 | 1,024 |
| Standalone LUT4 | 227 | 274 | 274 |
| Standalone flip-flops | 1,394 | 1,445 | 1,045 |
| Wrapped TRELLIS_COMB | 1,119 | 1,222 | 1,054 |
| DSP / BRAM blocks | 16 / 0 | 16 / 0 | 16 / 0 |
| Median routed Fmax | 69.00 MHz | 61.20 MHz | 66.79 MHz |
| Estimated tile latency | 217.40 ns | 245.09 ns | 224.58 ns |
| Successful routes | 5/5 | 4/5 | 5/5 |
| Routes meeting 75 MHz | 1/5 | 0/5 | 0/5 |

The compact design uses 25.0% fewer standalone flip-flops and 5.8% fewer
wrapped combinational cells, but 20.7% more standalone LUT4s. Its
estimated tile latency is 3.3% longer.

| Routing seed | TinyTPU upstream (MHz) | Vexim 32-bit (MHz) | Vexim compact (MHz) |
|---|---:|---:|---:|
| 1 | 67.22 | 60.26 | 65.50 |
| 2 | 69.45 | 62.14 | 67.62 |
| 3 | 76.36 | 62.92 | 67.85 |
| 4 | 69.00 | Timeout | 66.79 |
| 5 | 67.61 | 59.60 | 62.38 |

## Reproduce in PowerShell

Run from the repository root. Build the ECP5 image as documented in
[the ECP5 GEMM benchmark](../ecp5-gemm/README.md).

~~~powershell
git clone https://github.com/tinycomputers/tiny-tpu build/tiny-tpu-upstream
git -C build/tiny-tpu-upstream checkout --detach 97c28d7587689707fe7ff9311eabc7a3949eaef6
New-Item -ItemType Directory -Force build/tiny-tpu | Out-Null
curl.exe -fLsS https://github.com/zachjs/sv2v/releases/download/v0.0.13/sv2v-Linux.zip -o build/tiny-tpu/sv2v.zip
Expand-Archive build/tiny-tpu/sv2v.zip build/tiny-tpu/tools -Force
docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -v "$($pwd.Path)/benchmarks:/benchmarks:ro" -v "$($pwd.Path)/build/tiny-tpu-upstream:/upstream:ro" -v "$($pwd.Path)/build/tiny-tpu/tools/sv2v-Linux:/tools:ro" -v "$($pwd.Path)/build/tiny-tpu:/output" vexim-ecp5-tools python3 /benchmarks/tiny-tpu/run.py
~~~

The output directory contains the native Vexim source, test vectors,
synthesis and placement logs, timing reports and `results.json`.
For the compact run, create a separate output directory, point the
`/output` mount at it and append `--compact` to the command. That run
measures the compact design against the same software oracle. Use the
baseline measurements from the first run.
