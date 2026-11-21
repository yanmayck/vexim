# Full SERV core reconstructed in Vexim

The baseline is the official [SERV repository](https://github.com/olofk/serv/tree/f200eb2ed7b69ac1c6b8eddd47654522aeee5ce8),
commit `f200eb2ed7b69ac1c6b8eddd47654522aeee5ce8`. The experiment uses
`serv_rf_top` with the upstream defaults, including the one-bit datapath,
CSR support, and the register-file RAM. Compressed instructions and MDU
are disabled in this profile.

For the Vexim variant, Yosys elaborates and flattens the upstream RTL
without expanding the register file into flip-flops. The importer
reconstructs the logic, synchronous state, and memory in Vexim. The
Vexim compiler emits SystemVerilog, and a port adapter ties its
additional reset input low. The original reset behavior is encoded in
the data paths. The importer resolves undefined netlist constants to
zero where they are used in Vexim. This is a structural migration of
the pinned profile.

The intermediate control feeds the same pre-Vexim RTLIL snapshot directly
into FPGA synthesis with Yosys `read_json`. Only its simulation uses an
exported Verilog file.

| Metric | Official SERV | Intermediate directly | Vexim reconstruction |
|---|---:|---:|---:|
| Standalone LUT4s | 266 | 1,753 | 291 |
| Standalone flip-flops | 182 | 1,336 | 184 |
| RAM4K blocks, standalone and with harness | 1 | 0 | 1 |
| Routed logic cells with shared serial harness | 635 | 3,269 | 665 |
| Median post-route Fmax on HX8K/CT256 | 73.93 MHz | 61.61 MHz | 71.96 MHz |
| Seeds meeting the 50 MHz target | 5/5 | 5/5 | 5/5 |

The direct intermediate snapshot no longer let Yosys find the
registers on the RAM read address. The memory therefore mapped into
logic. The Vexim round trip restored RAM inference in this flow,
with a modest remaining area and timing gap to the official baseline.

All three designs passed the same RISC-V program in Icarus with wait states
in instruction and data buses. The 12 acknowledged bus transactions
matched exactly, including cycle numbers. The program exercises
arithmetic, a shift, load/store, a taken branch and a jump. This is one
directed integration test. The experiment does not establish full ISA
compliance or formal equivalence. Fmax is estimated after nextpnr
routing, with the same serial test harness in all three designs.

## Reproduce with Docker

Run from the Vexim repository in PowerShell:

~~~powershell
git clone https://github.com/olofk/serv.git build/serv-upstream
git -C build/serv-upstream checkout --detach f200eb2ed7b69ac1c6b8eddd47654522aeee5ce8
docker build -f benchmarks/Dockerfile -t vexim-benchmarks .
docker build -f benchmarks/serv/Dockerfile -t vexim-serv .
New-Item -ItemType Directory -Force build/serv-core-results | Out-Null
docker run --rm --network none --mount "type=bind,source=$((Get-Location).Path)/build/serv-upstream/rtl,target=/rtl,readonly" --mount "type=bind,source=$((Get-Location).Path)/benchmarks/serv-core,target=/case,readonly" --mount "type=bind,source=$((Get-Location).Path)/build/serv-core-results,target=/output" vexim-serv python3 /case/run.py
~~~

The runner verifies the regenerated Vexim against the checked-in
source. It saves the generated RTL, the simulation traces, the report
for each of five nextpnr seeds and `serv-core-results.json`.
