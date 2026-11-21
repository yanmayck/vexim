# SERV SoC pilot on ECP5

The pilot boots the pinned official SERV default profile, with the same
system tested against the Vexim reconstruction. Both variants use the same
SystemVerilog SoC fabric and peripherals. This experiment swaps the CPU.

The CPU fetches from a 256-byte boot ROM through its instruction port.
A round-robin arbiter serves CPU data and DMA requests. The shared data
bus uses the SERV Wishbone-style cycle/acknowledge interface and exposes
16 KiB of byte-write SRAM plus memory-mapped peripherals.

| Address | Register |
|---|---|
| 0x10000000 | DMA source byte address |
| 0x10000004 | DMA destination byte address |
| 0x10000008 | DMA length in aligned 32-bit words |
| 0x1000000c | DMA busy on read, start on write |
| 0x10000010 | UART transmit |
| 0x10000014 | UART busy |
| 0x10000018 | Timer counter |
| 0x1000001c | Timer compare |
| 0x10000020 | Timer interrupt enable |
| 0x10000024 | SPI transmit |
| 0x10000028 | SPI busy |
| 0x1000002c | SPI receive |
| 0x10000030 | Firmware test signature |

The DMA is a forward-copy engine for aligned, in-range word transfers.
The UART uses a fixed eight clocks per bit and 8-N-1 framing. SPI runs
in mode 0 with an internal half-period of one clock. The boot program
verifies 32 copied words, reads the running timer, checks SPI loopback
and transmits a byte over UART. The testbench checks the UART frame,
counts SPI pulses and verifies that CPU and DMA contend for the bus.
Timer interrupt delivery is outside this pilot test.

## Pilot results

| Metric | Official SERV CPU | Vexim SERV CPU |
|---|---:|---:|
| Firmware boot/test cycles | 17,199 | 17,199 |
| LUT4s | 1,169 | 1,207 |
| Flip-flops | 574 | 575 |
| BRAM blocks | 9 | 9 |
| Median routed Fmax | 67.50 MHz | 68.37 MHz |
| Seeds meeting 75 MHz | 0/5 | 0/5 |

Both builds produced the same test signature and one observed cycle with
CPU and DMA requesting the data bus together. Eight BRAM blocks hold the
16 KiB data SRAM and one holds the CPU register file. The Fmax figures
are post-route estimates for the SoC with automatic pin placement.

## Reproduce in PowerShell

From the Vexim checkout, using the dependency images described in the
[ECP5 accelerator benchmark](../ecp5-gemm/README.md):

~~~powershell
git clone https://github.com/olofk/serv.git build/serv-upstream
git -C build/serv-upstream checkout --detach f200eb2ed7b69ac1c6b8eddd47654522aeee5ce8
New-Item -ItemType Directory -Force build/serv-soc | Out-Null
docker run --rm --network none --mount "type=bind,source=$((Get-Location).Path)/build/serv-upstream/rtl,target=/rtl,readonly" --mount "type=bind,source=$((Get-Location).Path)/benchmarks,target=/benchmarks,readonly" --mount "type=bind,source=$((Get-Location).Path)/build/serv-soc,target=/output" -e PYTHONDONTWRITEBYTECODE=1 vexim-ecp5-tools python3 /benchmarks/serv-soc/benchmark.py
~~~

The runner writes the firmware image, boot logs, synthesized netlists and
five nextpnr reports per CPU variant. It uses the ECP5-85F/CABGA381,
speed grade 6, and a 75 MHz constraint with automatic pin placement.

## iCE40 UP5K baseline

This baseline uses the pinned official SERV CPU and the existing firmware.
The only target-specific RTL change is the data memory backend. Two
16-bit SPRAM primitives are addressed together to retain the 32-bit,
16 KiB memory map. Each software byte enable controls the corresponding
two nibble enables. Firmware passes in 17,199 cycles against the Yosys
primitive simulation models, matching the existing generic-memory run.

| Metric | UP5K-SG48 |
|---|---:|
| Mapped LUT4s | 1,236 |
| Packed logic cells | 1,535 / 5,280 |
| Logic cells free | 3,745 (70.9%) |
| SPRAM blocks | 2 / 4 |
| EBR blocks | 1 / 30 |
| Global buffers | 8 / 8 |
| Fmax across seeds 1–5 (MHz) | 24.69, 24.50, 24.63, 24.77, 24.30 |
| Median routed Fmax | 24.63 MHz |
| Seeds meeting 50 MHz | 0 / 5 |

Leaving 75% of packed logic cells free allows at most 1,320 occupied
cells. The baseline is 215 cells above that budget. Pin placement is
automatic and the reported Fmax is a tool estimate.

Use the same dependencies and pinned checkout as above, then run:

~~~powershell
New-Item -ItemType Directory -Force build/serv-soc-up5k | Out-Null
docker run --rm --network none --mount "type=bind,source=$((Get-Location).Path)/build/serv-upstream/rtl,target=/rtl,readonly" --mount "type=bind,source=$((Get-Location).Path)/benchmarks,target=/benchmarks,readonly" --mount "type=bind,source=$((Get-Location).Path)/build/serv-soc-up5k,target=/output" -e PYTHONDONTWRITEBYTECODE=1 vexim-ecp5-tools python3 /benchmarks/serv-soc/up5k.py
~~~

The runner writes `up5k-results.json`, the synthesized netlist, and all
five routing reports in `build/serv-soc-up5k`.
