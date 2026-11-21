"""Boot both SERV variants and measure the same SoC on ECP5."""
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import median
from subprocess import run

from boot import boot_rom

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from ecp5_route import route_seed

OUT = Path("/output")


def command(args, label):
    log = OUT / f"{label}.log"
    with log.open("w") as stream:
        result = run(args, cwd=OUT, stdout=stream, stderr=stream, timeout=300)
    report = log.read_text()
    if result.returncode:
        raise RuntimeError(report[-5000:])
    return report


def main():
    upstream = sorted(Path("/rtl").glob("*.v"))
    if not upstream:
        raise ValueError("mount the pinned upstream SERV rtl directory at /rtl")
    boot_rom(OUT / "boot.hex")
    generated = OUT / "serv-vexim.sv"
    command(["veximc", "build", str(HERE.parent / "serv-core" / "serv_rf_top.vxm"),
             "-o", str(generated)], "vexim-compile")
    results = {}
    baseline = None
    for name, rtl in (("official", list(map(str, upstream))),
                      ("vexim", ["-DVEXIM_CPU", str(generated)])):
        files = [*rtl, str(HERE / "soc.sv")]
        binary = OUT / f"{name}.sim"
        command(["iverilog", "-g2012", "-s", "tb", "-o", str(binary),
                 *files, str(HERE / "tb.sv")], f"{name}-compile")
        report = command(["vvp", str(binary)], f"{name}-boot")
        passes = [line for line in report.splitlines() if line.startswith("PASS boot=")]
        if len(passes) != 1:
            raise RuntimeError(f"{name} boot failed")
        if baseline is not None and passes[0] != baseline:
            raise RuntimeError(f"boot observations diverged: {passes[0]} vs {baseline}")
        baseline = passes[0]
        print(name, baseline, flush=True)
        netlist = OUT / f"{name}.json"
        command(["yosys", "-Q", "-p", f"read_verilog -sv {' '.join(files)}; "
                 f"synth_ecp5 -top serv_soc -json {netlist}; check -assert"],
                f"{name}-synth")
        cells = Counter(c["type"] for c in
                        json.loads(netlist.read_text())["modules"]["serv_soc"]["cells"].values())
        seeds = [route_seed(OUT, netlist, name, seed) for seed in range(1, 6)]
        results[name] = {"boot": baseline, "cells": dict(cells), "seeds": seeds,
                         "median_fmax_mhz": median(seed["fmax_mhz"] for seed in seeds)}
        print(name, results[name], flush=True)
        (OUT / "soc-results.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
