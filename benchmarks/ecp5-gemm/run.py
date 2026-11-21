"""Measure the same signed INT8 systolic array from Vexim and SystemVerilog."""
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from statistics import median

sys.path.insert(0, "/work/benchmarks")
from run import OUTPUT, build_harness, command
from ecp5_route import route_seed
from generate import generate, TOP

SYNTHESIS = "synth_ecp5"


def main():
    generate(OUTPUT)
    source = OUTPUT / "gemm.vxm"
    generated = OUTPUT / "vexim.sv"
    rss = OUTPUT / "compiler-rss.txt"
    compiler = []
    for _ in range(5):
        seconds = command(["/usr/bin/time", "-f", "%M", "-o", str(rss),
                           "veximc", "build", str(source), "-o", str(generated)],
                          OUTPUT / "compiler.log")
        compiler.append({"seconds": seconds, "peak_rss_kib": int(rss.read_text())})
    results = {"vexim_lines": len(source.read_text().splitlines()),
               "compiler": compiler, "variants": {}}
    print("Compiler:", results["vexim_lines"], "lines", compiler, flush=True)
    for label, design in (("direct", OUTPUT / "direct.sv"), ("vexim", generated)):
        binary = OUTPUT / f"{label}.sim"
        command(["iverilog", "-g2012", "-s", "tb", "-o", str(binary),
                 str(design), str(OUTPUT / "tb.sv")], OUTPUT / f"{label}-compile.log")
        sim_log = OUTPUT / f"{label}-sim.log"
        command(["vvp", str(binary)], sim_log)
        if "PASS" not in sim_log.read_text().splitlines():
            raise RuntimeError(f"simulation failed for {label}")
        print(f"{label}: all 432 matrix outputs passed", flush=True)
        prefix = OUTPUT / label
        mapped = prefix.with_suffix(".json")
        synthesis_seconds = command(["yosys", "-Q", "-p", f"read_verilog -sv {design}; "
                                     f"{SYNTHESIS} -top {TOP} -json {mapped}; check -assert"],
                                    prefix.with_suffix(".synth.log"))
        cells = Counter(c["type"] for c in
                        json.loads(mapped.read_text())["modules"][TOP]["cells"].values())
        harness = build_harness(TOP, design, mapped, prefix, synthesis=SYNTHESIS)
        with ThreadPoolExecutor(max_workers=4) as executor:
            jobs = [executor.submit(route_seed, OUTPUT, harness, label, seed)
                    for seed in range(1, 6)]
            runs = []
            for job in jobs:
                run = job.result()
                runs.append(run)
                print(label, run["seed"], round(run["fmax_mhz"], 2), run["usage"], flush=True)
        results["variants"][label] = {"standalone_cells": dict(cells),
                                      "synthesis_seconds": synthesis_seconds,
                                      "median_fmax_mhz": median(r["fmax_mhz"] for r in runs),
                                      "runs": runs}
        (OUTPUT / "results.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
