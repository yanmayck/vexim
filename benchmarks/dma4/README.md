# Four-channel DMA on ECP5

The DMA copies 32-bit words from byte-addressed source to destination.
Four depth-two descriptor FIFOs feed one shared read/response/write
datapath. Requests are arbitrated round-robin after each transferred
word. The controller latches the owner before issuing a request, so
backpressure cannot change the address or data of an outstanding
transaction. Only one read may be outstanding. Source and destination
addresses wrap at 16 bits. Zero-length commands are refused. The last
accepted write produces a completion tagged with the channel.

The independent SystemVerilog implementation and the Vexim generator
implement this same protocol. The third variant uses decoded one-hot
selection for the active queue head in Vexim. All queues fit in
registers. Both languages have the same zero-BRAM budget.

The Python reference models FIFO ordering, word-by-word arbitration and
the memory response. Each of three scenarios enqueues and completes
32 descriptors per channel, fills every FIFO and checks valid/ready,
read addresses, write addresses/data and completion tags, cycle by cycle.
One workload has no memory stalls. Two workloads introduce read stalls,
response delays of 1-12 cycles and write stalls including a long
recurring pause. Address wrap and rejection of zero-length commands are
also exercised.

Yosys reports standalone resources. nextpnr routes the same five-pin
serial test harness on ECP5-85F CABGA381 speed grade 6 at a 75 MHz
target, with five seeds and a 120-second budget per seed. Throughput
uses the verified byte count and elapsed cycles from first enqueue to
last completion, scaled by the median post-route Fmax. These are
estimated sustained workload rates in decimal MB/s. Peak board memory
bandwidth and the harness serial transport are outside this measurement.

## Measured results

Each variant completed 384 descriptors and copied 33,372 bytes across
80,595 checked cycles, including reset and the final zero-length probe.

| Measure | SystemVerilog | Vexim | Vexim decoded mux |
|---|---:|---:|---:|
| Standalone LUT4 | 732 | 757 | 757 |
| Standalone flip-flops | 376 | 376 | 376 |
| Wrapped TRELLIS_COMB | 849 | 874 | 882 |
| DSP / BRAM | 0 / 0 | 0 / 0 | 0 / 0 |
| Median Fmax (MHz) | 67.38 | 84.98 | 87.12 |
| Fmax seeds 1-5 (MHz) | 62.96, 63.13, 73.39, 76.52, 67.38 | 88.57, 87.67, 84.37, 84.89, 84.98 | 85.49, 91.68, 85.33, 87.12, 89.96 |
| Seeds meeting 75 MHz | 1/5 | 5/5 | 5/5 |
| No-stall throughput (MB/s) | 67.37 | 84.98 | 87.11 |
| Stalls 1 throughput (MB/s) | 21.91 | 27.64 | 28.33 |
| Stalls 2 throughput (MB/s) | 21.63 | 27.28 | 27.97 |

The variants have identical queue latency in cycles. For the first
stall workload, enqueue-to-completion p95 for channels 0-3 is 2,358,
3,514, 3,337 and 3,515 cycles. Using the median Fmax, the decoded mux
variant estimates the same latencies at 27.1, 40.3, 38.3 and 40.3 us,
compared with 35.0, 52.2, 49.5 and 52.2 us for SystemVerilog. Each channel
receives a different sequence of descriptor sizes.

The decoded Vexim mux trades 3.4% more standalone LUT4 for 29.3%
higher median throughput. This measures these RTL implementations on
one target. The SystemVerilog implementation uses indexed arrays and
Vexim uses explicit muxes.

## Reproduce in PowerShell

Run from the repository root. Build the `vexim-ecp5-tools` image as
documented in [the ECP5 GEMM benchmark](../ecp5-gemm/README.md).

~~~powershell
New-Item -ItemType Directory -Force build/dma4 | Out-Null
docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -v "$($pwd.Path)/benchmarks:/benchmarks:ro" -v "$($pwd.Path)/build/dma4:/output" vexim-ecp5-tools python3 /benchmarks/dma4/run.py
~~~

For the decoded mux variant, create a separate output directory,
point the output mount at it and append `--onehot`. The runner writes
the Vexim source, compiled RTL, simulation and synthesis logs, per-seed
reports, and `results.json` with throughput and per-channel latency.
