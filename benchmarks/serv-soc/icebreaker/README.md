# Vexim SoC V6 on iCEBreaker

The iCEBreaker board wrapper targets the iCE40 UP5K-SG48 with its
12 MHz oscillator. The constraints use the clock, USB UART, user button
and green LED pins from the [IceStorm iCEBreaker constraints](https://github.com/YosysHQ/icestorm/blob/main/examples/icebreaker/icebreaker.pcf).
The SPI signals are on PMOD 1A pins 1 through 4 in MOSI, MISO, SCK, CS
order. Connect PMOD 1A pin 1 to pin 2 to enable the SPI loopback.

The board profile synchronizes reset release and registers the UART
output to avoid spurious transitions. It uses 104 clock cycles per
UART bit, approximately 115,385 baud. The firmware sends `V`, checks
DMA, SPI and timer behavior, then sends `PASS\r\n`. The green LED lights
when the firmware writes its success signature.

The RTL and synthesized netlist both emitted bytes
`56 50 41 53 53 0d 0a` and lit the simulated green LED. The pin-constrained
design used 1,096 of 5,280 packed logic cells, one EBR and two SPRAMs.
nextpnr reported 27.90 MHz Fmax with the 12 MHz constraint. These are
simulation and tool results. Physical programming has not been verified.

## Reproduce in PowerShell

From the Vexim checkout, with the pinned SERV checkout used by the
[SoC benchmark](../README.md):

~~~powershell
docker build -f benchmarks/Dockerfile -t vexim-benchmarks .
docker build -f benchmarks/serv/Dockerfile -t vexim-serv .
docker build -f benchmarks/serv-soc/icebreaker/Dockerfile -t vexim-icebreaker .
New-Item -ItemType Directory -Force build/serv-icebreaker | Out-Null
docker run --rm --network none --mount "type=bind,source=$((Get-Location).Path)/build/serv-upstream/rtl,target=/rtl,readonly" --mount "type=bind,source=$((Get-Location).Path)/benchmarks,target=/benchmarks,readonly" --mount "type=bind,source=$((Get-Location).Path)/build/serv-icebreaker,target=/output" -e PYTHONDONTWRITEBYTECODE=1 vexim-icebreaker python3 /benchmarks/serv-soc/icebreaker/run.py
~~~

The runner saves `vexim-icebreaker.bin`, the timing and resource reports,
and UART simulation logs in `build/serv-icebreaker`.

With the iCEBreaker and loopback jumper connected, program its
configuration flash using `iceprog build/serv-icebreaker/vexim-icebreaker.bin`
from a host with USB access. Open the board serial port at 115200 baud,
8-N-1, with hardware flow control disabled. Press the onboard user
button to rerun and capture the `VPASS` line.
