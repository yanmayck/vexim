"""Build a pin-constrained iCEBreaker bitstream and test its firmware."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOC = HERE.parent
OUT = Path("/output")
sys.path.insert(0, str(SOC))
from boot import boot_rom


def run(args, label):
    log = OUT / f"{label}.log"
    with log.open("w") as stream:
        result = subprocess.run(args, cwd=OUT, stdout=stream, stderr=stream, timeout=180)
    contents = log.read_text()
    if result.returncode:
        raise RuntimeError(contents[-5000:])
    return contents


def board_serial_source():
    source = (SOC / "shared_peripherals.vxm").read_text()
    # UART rate is 12 MHz / 104. SPI uses the low divider bit as before.
    for name in ("zero3", "one3", "div_max", "divider", "div_inc", "div_run"):
        old = f"wire {name} u3"
        if source.count(old + "\n") != 1:
            raise ValueError(f"UART specialization could not locate {name}")
        source = source.replace(old + "\n", f"wire {name} u7\n")
    source = source.replace("comb div_max const 7\n", "comb div_max const 103\n")
    source = source.replace("comb div_run mux busy div_inc zero3", """wire uart_wrap u1
comb uart_wrap and mode_uart uart_end
wire no_uart_wrap u1
comb no_uart_wrap xor uart_wrap one
wire divider_running u1
comb divider_running and busy no_uart_wrap
comb div_run mux divider_running div_inc zero3""")
    # Register the pin so simultaneous state transitions cannot create a false start edge.
    return source.replace("comb uart_tx mux uart_busy uart_value one", """wire uart_line_next u1
comb uart_line_next mux uart_busy uart_value one
sync uart_tx clk rst uart_line_next 1""")


def main():
    upstream = sorted(Path("/rtl").glob("*.v"))
    if not upstream:
        raise ValueError("mount the pinned SERV RTL at /rtl")
    boot_rom(OUT / "boot.hex", board_uart=True)
    serial_source = OUT / "board_peripherals.vxm"
    serial_source.write_text(board_serial_source())
    parts = []
    for name, source in (("bus_dma", SOC / "bus_dma.vxm"), ("peripherals", serial_source)):
        generated = OUT / f"{name}.sv"
        run(["veximc", "build", str(source), "--opt-area", "-o", str(generated)],
            f"{name}-compile")
        parts.append(str(generated))
    files = ["-DUP5K_SPRAM", "-DVEXIM_BUS_DMA", "-DVEXIM_PERIPHERALS", "-DCOMPACT_SOC",
             *map(str, upstream), *parts, str(SOC / "soc.sv"), str(HERE / "top.sv")]
    run(["iverilog", "-g2012", "-s", "board_tb", "-o", "board.sim", *files,
         "/usr/share/yosys/ice40/cells_sim.v", str(HERE / "tb.sv")], "board-compile")
    trace = run(["vvp", "board.sim"], "board-test")
    if "PASS board wrapper:" not in trace:
        raise RuntimeError("board firmware test did not pass")
    print(trace.strip(), flush=True)
    run(["yosys", "-Q", "-p", f"read_verilog -sv {' '.join(files)}; "
         "synth_ice40 -device u -spram -top icebreaker_soc -json board.json; check -assert"], "synth")
    run(["yosys", "-Q", "-p", "read_json board.json; write_verilog -noattr board-mapped.sv"],
        "mapped-export")
    run(["iverilog", "-g2012", "-s", "board_tb", "-o", "mapped.sim", "board-mapped.sv",
         "/usr/share/yosys/ice40/cells_sim.v", str(HERE / "tb.sv")], "mapped-compile")
    mapped_trace = run(["vvp", "mapped.sim"], "mapped-test")
    if "PASS board wrapper:" not in mapped_trace:
        raise RuntimeError("mapped board netlist test did not pass")
    print("PASS board netlist UART and green LED", flush=True)
    run(["nextpnr-ice40", "--up5k", "--package", "sg48", "--json", "board.json",
         "--pcf", str(HERE / "icebreaker.pcf"), "--freq", "12", "--seed", "1",
         "--asc", "board.asc", "--report", "timing.json"], "route")
    run(["icepack", "board.asc", "vexim-icebreaker.bin"], "pack")
    timing = json.loads((OUT / "timing.json").read_text())
    bitstream = (OUT / "vexim-icebreaker.bin").read_bytes()
    results = {"fmax": timing["fmax"], "utilization": timing["utilization"],
               "sha256": hashlib.sha256(bitstream).hexdigest(), "bytes": len(bitstream)}
    (OUT / "board-results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
