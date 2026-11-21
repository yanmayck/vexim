# Complete educational RISC-V CPU in Vexim

This benchmark reimplements the RTL Forge rv32_demo profile in Vexim.
It includes instruction decoding, PC and branch control, arithmetic,
32 architectural registers including hardwired x0, a load/store interface
and illegal-instruction handling. The profile executes LUI, ADDI, ADD, SUB,
BEQ, LW and SW. The interface accepts an external instruction word and
read data on each cycle. It is a complete implementation of that profile.

The default Vexim design shares the load/store and immediate-add datapath
and uses indexed memory with resettable validity bits. An alternative
Vexim design uses resettable registers and balanced read multiplexer trees.

| Metric | Reference SystemVerilog | Vexim indexed memory | Vexim flip-flop bank |
|---|---:|---:|---:|
| Standalone LUT4s | 1,926 | 2,239 | 2,028 |
| Standalone flip-flops | 1,023 | 1,086 | 1,023 |
| Routed logic cells with harness | 3,211 | 869 | 3,156 |
| Routed RAM4K blocks with harness | 0 | 4 | 0 |
| Median post-route Fmax | 46.30 MHz | 47.76 MHz | 44.24 MHz |
| Seeds meeting 50 MHz | 0/5 | 1/5 | 0/5 |

Both ports passed the original program and a 20,000-cycle deterministic
differential simulation. The differential test compares every output
before and after each rising edge and exercises periodic resets, illegal
instructions, branches, loads and stores. The experiment does not
establish RV32I compliance, unbounded equivalence or board performance.

Yosys 0.33 synthesized the standalone top and then the same serial
test harness around each variant. nextpnr 0.6 routed each harness on an
iCE40 HX8K/CT256 for seeds 1–5. With the harness, synthesis can absorb
output registers into the indexed register file and infer four RAM4K
blocks. The standalone synthesis does not infer those blocks. LUT4s and
packed logic cells are different measures. Post-route timing includes
the harness and excludes external board timing.

## Reproduce

Run from Vexim in PowerShell. The compiler image is shared with the SERV
benchmark.

~~~powershell
docker build -f benchmarks/Dockerfile -t vexim-benchmarks .
docker build -f benchmarks/serv/Dockerfile -t vexim-serv .
New-Item -ItemType Directory -Force build/rv32-benchmark | Out-Null
docker run --rm --network none --mount "type=bind,source=$((Get-Location).Path)/benchmarks/rv32,target=/rv32,readonly" --mount "type=bind,source=$((Get-Location).Path)/build/rv32-benchmark,target=/output" vexim-serv python3 /rv32/run.py
~~~

Append `--registers` and use a separate output directory to measure the
flip-flop design. Each run writes emitted RTL, simulation and synthesis
logs, all seed reports and `rv32-results.json`.
