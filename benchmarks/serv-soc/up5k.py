"""Measure the official SERV SoC baseline on the iCE40 UP5K."""
import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from statistics import median

from boot import boot_rom

HERE = Path(__file__).resolve().parent
OUT = Path("/output")
sys.path.insert(0, str(HERE.parent))
from run import route


def run(args, label):
    log = OUT / f"{label}.log"
    with log.open("w") as stream:
        result = subprocess.run(args, cwd=OUT, stdout=stream, stderr=stream, timeout=180)
    contents = log.read_text()
    if result.returncode:
        raise RuntimeError(contents[-5000:])
    return contents


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v2", action="store_true", help="Use the native Vexim bus and DMA")
    parser.add_argument("--v3", action="store_true", help="Use the V2 source with veximc --opt-area")
    parser.add_argument("--v4", action="store_true", help="Use Vexim peripherals with register storage")
    parser.add_argument("--v4-ebr", action="store_true", help="Use Vexim peripherals with EBR UART storage")
    parser.add_argument("--v5", action="store_true", help="Use shared serial hardware and smaller MMIO")
    args = parser.parse_args()
    if sum((args.v2, args.v3, args.v4, args.v4_ebr, args.v5)) > 1:
        parser.error("select only one SoC variant")
    original = sorted(Path("/rtl").glob("*.v"))
    if not original:
        raise ValueError("mount the pinned official SERV sources at /rtl")
    boot_rom(OUT / "boot.hex")
    sources = ["-DUP5K_SPRAM", *map(str, original), str(HERE / "soc.sv")]
    if args.v2 or args.v3 or args.v4 or args.v4_ebr or args.v5:
        bus_dma = OUT / "bus_dma.sv"
        options = ["--opt-area"] if args.v3 or args.v4 or args.v4_ebr or args.v5 else []
        run(["veximc", "build", str(HERE / "bus_dma.vxm"), "-o", str(bus_dma), *options],
            "vexim-compile")
        if args.v3:
            reference = OUT / "bus_dma_unoptimized.sv"
            run(["veximc", "build", str(HERE / "bus_dma.vxm"), "-o", str(reference)],
                "vexim-reference")
            run(["yosys", "-Q", "-p", f"read_verilog -sv {reference}; "
                 f"rename soc_bus_dma gold; read_verilog -sv {bus_dma}; rename soc_bus_dma gate; "
                 "proc; opt; equiv_make gold gate equiv; hierarchy -top equiv; "
                 "equiv_simple; equiv_induct -seq 4; equiv_status -assert"],
                "vexim-equivalence")
            print("PASS V2/V3 DMA equivalence", flush=True)
        sources.insert(0, "-DVEXIM_BUS_DMA")
        sources.append(str(bus_dma))
        run(["iverilog", "-g2012", "-s", "dma_tb", "-o", "dma.sim",
             str(bus_dma), str(HERE / "dma_tb.sv")], "dma-compile")
        dma_test = run(["vvp", "dma.sim"], "dma-test")
        if "PASS DMA" not in dma_test:
            raise RuntimeError("native DMA boundary test failed")
        print(dma_test.strip(), flush=True)
    if args.v4 or args.v4_ebr or args.v5:
        peripherals = OUT / "peripherals.sv"
        serial = "shared_peripherals.vxm" if args.v5 else "peripherals.vxm"
        run(["veximc", "build", str(HERE / serial), "-o", str(peripherals),
             "--opt-area"], "peripherals-compile")
        sources.insert(0, "-DVEXIM_PERIPHERALS")
        if args.v5:
            sources.insert(0, "-DCOMPACT_SOC")
        if args.v4_ebr:
            sources.insert(0, "-DUART_EBR")
        sources.append(str(peripherals))
    model = "/usr/share/yosys/ice40/cells_sim.v"
    run(["iverilog", "-g2012", "-s", "tb", "-o", "up5k.sim", *sources, model,
         str(HERE / "tb.sv")], "up5k-compile")
    simulation = run(["vvp", "up5k.sim"], "up5k-boot")
    if "PASS boot=" not in simulation:
        raise RuntimeError("official SERV boot failed with the SPRAM model")
    print(simulation.strip(), flush=True)
    if args.v5:
        boot_rom(OUT / "boot.hex", serial_overlap=True)
        stressed = run(["vvp", "up5k.sim", "+require_serial_wait"], "serial-overlap")
        if "PASS boot=" not in stressed:
            raise RuntimeError("serial overlap case failed")
        print(stressed.strip(), flush=True)
        boot_rom(OUT / "boot.hex")
    netlist = OUT / "up5k.json"
    run(["yosys", "-Q", "-p", f"read_verilog -sv {' '.join(sources)}; "
         f"synth_ice40 -device u -spram -top serv_soc -json {netlist}; check -assert; stat -top serv_soc"],
        "up5k-synth")
    module = json.loads(netlist.read_text())["modules"]["serv_soc"]
    cells = Counter(cell["type"] for cell in module["cells"].values())
    groups = Counter()
    for name, cell in module["cells"].items():
        if cell["type"] == "SB_LUT4":
            if name.startswith("cpu."):
                group = "serv"
            elif name.startswith("bus_dma."):
                group = "bus_dma"
            elif name.startswith("peripherals.timer_"):
                group = "timer_named"
            elif name.startswith("peripherals."):
                group = "serial_and_other_peripheral"
            else:
                group = "top_and_mmio"
            groups[group] += 1
    print("Mapped LUT4 attribution by cell names:", dict(groups), flush=True)
    if cells["SB_SPRAM256KA"] != 2:
        raise RuntimeError("expected exactly two hard SPRAM blocks")
    prefix = OUT / "up5k"
    print("Mapped LUT4:", cells["SB_LUT4"], "SPRAM:", cells["SB_SPRAM256KA"], flush=True)
    runs = route(netlist, prefix, "up5k", "sg48")
    report = json.loads((OUT / "up5k.up5k-sg48-seed-1.json").read_text())
    results = {"boot": next(line for line in simulation.splitlines()
                            if line.startswith("PASS boot=")), "cells": dict(cells),
               "lut4_named_groups": dict(groups),
               "utilization": report["utilization"], "runs": runs,
               "median_fmax_mhz": median(r["fmax_mhz"] for r in runs)}
    (OUT / "up5k-results.json").write_text(json.dumps(results, indent=2) + "\n")
    print("Fmax MHz:", [round(r["fmax_mhz"], 2) for r in runs], flush=True)
    print("Utilization:", report["utilization"], flush=True)


if __name__ == "__main__":
    main()
