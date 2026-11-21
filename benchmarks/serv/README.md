# SERV memory-interface port

This benchmark ports the load/store data and alignment interface from
[SERV](https://github.com/olofk/serv/blob/f200eb2ed7b69ac1c6b8eddd47654522aeee5ce8/rtl/serv_mem_if.v)
for its one-bit, CSR-enabled profile. The ISC-licensed upstream source
is included unchanged. The Vexim profile preserves the original ports.
Its compiler-required reset input is tied low because the upstream sign
register has no reset.

| Metric | Upstream Verilog | Vexim |
|---|---:|---:|
| Standalone LUT4s | 9 | 9 |
| Standalone flip-flops | 1 | 1 |
| Median routed Fmax on HX8K/CT256 | 257.60 MHz | 257.60 MHz |
| Minimum to maximum across five seeds | 257.60–284.82 MHz | 238.27–284.82 MHz |

The registered timing harness is identical for both variants. The Fmax
is a nextpnr estimate for that harness and ported block. CPU-level
timing and RISC-V instruction compliance were outside this experiment.

Yosys checks a five-step SAT base case with a word operation on the
first edge to initialize the sign registers. It compares every output
from step two and proves equivalence by induction, matching the single
state bit in each design. Initial sign state is unspecified in both
implementations.

## Run with Docker

From the Vexim checkout in PowerShell:

~~~powershell
docker build -f benchmarks/Dockerfile -t vexim-benchmarks .
docker build -f benchmarks/serv/Dockerfile -t vexim-serv .
New-Item -ItemType Directory -Force build/serv-benchmark | Out-Null
docker run --rm --network none --mount "type=bind,source=$((Get-Location).Path)/build/serv-benchmark,target=/output" vexim-serv
~~~

The output directory contains the emitted SystemVerilog, equivalence
logs, seed reports and `serv-results.json`.
