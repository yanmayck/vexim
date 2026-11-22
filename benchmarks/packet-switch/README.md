# Parameterized packet switch

The same Vexim source specializes to two, four, or eight ingress and
egress ports with `--param PORTS=N`. The compiler expands nested
`generate` blocks directly. The Vexim source declares the ports, FIFO
banks and arbitration. The Python runner creates traffic and a pin
adapter for the SystemVerilog reference.

Each ingress has a 64-beat FIFO for each destination. A beat carries
32 data bits and a last marker. An ingress sends a whole packet to
one destination. Each egress arbitrates round-robin at packet boundaries
and keeps the winner both between beats and under backpressure.
An invalid destination has ready low. A full queue refuses a write
even if it pops on that cycle.

Each queue has independent synchronous read and write addresses.
A prefetch reads the next head on a successful pop, sustaining one
beat per cycle when data is available. A forwarding register covers
a write to the address being read. Reset empties the queues via
their valid bits and leaves RAM contents unspecified.

## Verification

An independent Python model generates cycle-by-cycle expectations for
an Icarus testbench shared by both designs. It compares ready/valid,
payload data and packet boundaries, including cycles when a valid
egress is stalled. Each ingress sends 96 packets per scenario.
The mixed scenario uses random destinations and independent egress
stalls. The contended scenario sends all ingress traffic to one egress.
The blocked scenario holds egress zero for 320 cycles and checks that
each other egress transfers a beat every cycle from cycle 8 through 319.
All three port counts are simulated. Synthesis and routing use 4x4.

## ECP5 results

Both designs passed all 4,032 packet transfers across the three port
counts and three scenarios. The 4x4 designs route in the same five-pin
serial harness on ECP5-85F CABGA381 speed grade 6 with router2 and a
75 MHz target. The throughput estimates scale the simulated delivery rate
by the median reported Fmax and exclude the serial harness transport.

| Measure | SystemVerilog | Vexim |
|---|---:|---:|
| Standalone LUT4 | 2,823 | 3,113 |
| Standalone flip-flops | 800 | 796 |
| BRAM blocks (DP16KD) | 16 | 16 |
| Packed combinational cells with harness | 4,778 | 3,565 |
| Fmax seeds 1–5 (MHz) | 60.40, 59.73, 61.20, 59.65, 62.21 | 76.96, 76.85, 68.70, 73.34, 67.93 |
| Median routed Fmax | 60.40 MHz | 73.34 MHz |
| Seeds meeting 75 MHz | 0/5 | 2/5 |
| Aggregate mixed-traffic throughput | 719.0 MB/s | 873.0 MB/s |
| Throughput per unblocked output during hold | 241.6 MB/s | 293.4 MB/s |

Mixed-traffic p99 latencies are 215, 164, 251 and 115 cycles for output
ports 0–3 in both designs. With one output blocked, the p99 latencies
are 326 cycles for that output and 8 cycles for each free output.

Vexim uses 10.3% more standalone LUT4s in this comparison. With the
harness, it packs into 25.4% fewer combinational cells and its median
Fmax is 21.4% higher. The two resource counts come from separate synthesis
flows and describe these implementations and this target.

## Reproduce in PowerShell

Run from the repository root. Build the `vexim-ecp5-tools` image as in
[the ECP5 GEMM benchmark](../ecp5-gemm/README.md).

~~~powershell
New-Item -ItemType Directory -Force build/packet-switch | Out-Null
docker run --rm --network none -v "$($pwd.Path):/src" -w /src -e CARGO_TARGET_DIR=/tmp/vexim-target rust:1.85-bookworm sh -ec 'cargo build --release --locked; cp /tmp/vexim-target/release/veximc /src/build/packet-switch/veximc'
docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -v "$($pwd.Path)/benchmarks:/benchmarks:ro" -v "$($pwd.Path)/build/packet-switch:/output" vexim-ecp5-tools python3 /benchmarks/packet-switch/run.py
~~~

The runner writes all emitted RTL, test vectors, synthesis logs,
per-seed routing reports and `results.json`.
