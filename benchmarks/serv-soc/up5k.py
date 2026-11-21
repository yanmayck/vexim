"""Measure the official SERV SoC baseline on the iCE40 UP5K."""
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
    original = sorted(Path("/rtl").glob("*.v"))
    if not original:
        raise ValueError("mount the pinned official SERV sources at /rtl")
    boot_rom(OUT / "boot.hex")
    sources = ["-DUP5K_SPRAM", *map(str, original), str(HERE / "soc.sv")]
    model = "/usr/share/yosys/ice40/cells_sim.v"
    run(["iverilog", "-g2012", "-s", "tb", "-o", "up5k.sim", *sources, model,
         str(HERE / "tb.sv")], "up5k-compile")
    simulation = run(["vvp", "up5k.sim"], "up5k-boot")
    if "PASS boot=" not in simulation:
        raise RuntimeError("official SERV boot failed with the SPRAM model")
    print(simulation.strip(), flush=True)
    netlist = OUT / "up5k.json"
    run(["yosys", "-Q", "-p", f"read_verilog -sv {' '.join(sources)}; "
         f"synth_ice40 -device u -spram -top serv_soc -json {netlist}; check -assert"],
        "up5k-synth")
    module = json.loads(netlist.read_text())["modules"]["serv_soc"]
    cells = Counter(cell["type"] for cell in module["cells"].values())
    if cells["SB_SPRAM256KA"] != 2:
        raise RuntimeError("expected exactly two hard SPRAM blocks")
    prefix = OUT / "up5k"
    print("Mapped LUT4:", cells["SB_LUT4"], "SPRAM:", cells["SB_SPRAM256KA"], flush=True)
    runs = route(netlist, prefix, "up5k", "sg48")
    report = json.loads((OUT / "up5k.up5k-sg48-seed-1.json").read_text())
    results = {"boot": simulation.splitlines()[0], "cells": dict(cells),
               "utilization": report["utilization"], "runs": runs,
               "median_fmax_mhz": median(r["fmax_mhz"] for r in runs)}
    (OUT / "up5k-results.json").write_text(json.dumps(results, indent=2) + "\n")
    print("Fmax MHz:", [round(r["fmax_mhz"], 2) for r in runs], flush=True)
    print("Utilization:", report["utilization"], flush=True)


if __name__ == "__main__":
    main()
