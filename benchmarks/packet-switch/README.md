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
All three port counts are simulated. The physical comparison defaults
to 4x4. Use `--physical-ports 8` to synthesize and route the 8x8 pair.

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

### Scaling to 8x8

Both implementations pass 2,304 packet transfers across the three
8x8 scenarios. With output zero blocked, the seven remaining outputs
each deliver 312 consecutive beats, one per cycle. The common mixed
traffic p99 for outputs 0–7 is 270, 83, 242, 99, 230, 223, 179 and
174 cycles. In the blocked case, the free outputs each have an
eight-cycle p99. The blocked output has a 326-cycle p99.

| Measure | SystemVerilog | Vexim |
|---|---:|---:|
| Standalone LUT4 | 12,944 | 8,990 |
| Standalone flip-flops | 2,336 | 2,336 |
| BRAM blocks (DP16KD) | 64 | 64 |
| Packed combinational cells with harness | 13,631 | 11,041 |
| Post-route Fmax measurements | 5/5 | 0/5 |
| Complete routing artifacts within budget | 2/5 | 0/5 |
| Median measured Fmax | 50.20 MHz | — |
| Estimated aggregate mixed throughput | 1,095.1 MB/s | — |

The router2 SystemVerilog frequencies for seeds 1–5 are 50.20, 51.84,
46.86, 50.76 and 41.80 MHz. For the last three, nextpnr printed final
timing after reporting routing complete, then timed out before saving
the JSON report. The runner marks these as log-derived timing. All
five Vexim attempts timed out before router2 reported completion, so
their pre-route frequencies are excluded. Vexim saves 30.5% of the
standalone LUTs but has no comparable router2 Fmax under this budget.

A supplemental run used `--router router1 --seed 2` on both existing
harness netlists, without requesting `--textcfg`. Both runs reached
the same 240-second budget before completing routing. A routed Vexim
critical path is therefore unavailable for evaluating a balanced
arbiter or data selector.

### Registering the egress grant

`switch_registered.vxm` is an alternative with a one-hot grant
registered at each egress. The scheduler reads the next-cycle FIFO
valid bits, lock and round-robin cursor. This lets the grant be
registered without inserting an idle cycle at packet boundaries.
The data mux uses the registered grant. The original cycle-by-cycle
oracle passes unchanged across all three 8x8 workloads.

The registered implementation maps to 11,978 standalone LUT4,
2,400 flip-flops and 64 BRAM blocks. Compared with the original
Vexim implementation it adds 2,988 LUT4 (33.2%) and 64 flip-flops.
The common timing harness packs into 13,036 combinational cells,
up from 11,041 in the original Vexim run.

Neither seed 2 nor seed 3 finished routing within 240 seconds with
router2, matching the original Vexim outcome for those seeds. There
is no post-route frequency or throughput estimate for this variant.
The registered grant preserved simulated throughput but did not solve
the routing problem and increased the mapped resource count.

To reproduce the timing trial, use a fresh output directory as below
and append `--physical-ports 8 --registered --seed 2 --seed 3`.

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

For 8x8, use a separate output directory for both commands and append
`--physical-ports 8` to the Python command. The 8x8 run gives each
routing seed 240 seconds.
