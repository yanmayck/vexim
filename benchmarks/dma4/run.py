"""Compare Vexim and SystemVerilog DMA implementations on ECP5."""
import argparse
import json
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import median

from design import native
from traffic import write_bench, write_case

sys.path.insert(0, "/benchmarks")
from run import OUTPUT, build_harness, command
from ecp5_route import route_seed

TOP = "dma4"
SYNTH = "synth_ecp5"


def measure_route(harness, label, seed):
    try:
        return route_seed(OUTPUT, harness, label, seed, timeout=120)
    except subprocess.TimeoutExpired:
        return {"seed": seed, "error": "Routing exceeded 120 seconds"}
    except subprocess.CalledProcessError as error:
        return {"seed": seed, "error": f"nextpnr exited with status {error.returncode}"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--onehot", action="store_true", help="measure the decoded Vexim read mux")
    args = parser.parse_args()
    case_dir = Path(__file__).resolve().parent
    src = OUTPUT / "dma4.vxm"
    emitted = OUTPUT / "vexim.sv"
    src.write_text(native(args.onehot))
    compile_seconds = command(["veximc", "build", str(src), "-o", str(emitted)],
                              OUTPUT / "compiler.log")
    tb = OUTPUT / "tb.sv"
    write_bench(tb)
    traffic = {}
    for case, seed, stress in (("sustained", 583, False), ("stalls-1", 583, True),
                               ("stalls-2", 913, True)):
        traffic[case] = write_case(OUTPUT / f"{case}.hex", seed, stress)

    results = {"compiler_seconds": compile_seconds, "onehot": args.onehot,
               "traffic": traffic, "variants": {}}
    harnesses = {}
    variants = (("vexim", emitted),) if args.onehot else (
        ("systemverilog", case_dir / "reference.sv"), ("vexim", emitted))
    for label, design in variants:
        executable = OUTPUT / f"{label}.sim"
        command(["iverilog", "-g2012", "-s", "tb", "-o", str(executable), str(design), str(tb)],
                OUTPUT / f"{label}-compile.log")
        for case, metrics in traffic.items():
            log = OUTPUT / f"{label}-{case}.log"
            command(["vvp", str(executable), f"+vectors={OUTPUT / (case+'.hex')}"], log)
            if f"PASS {metrics['vectors']}" not in log.read_text().splitlines():
                raise RuntimeError(f"{label}: incomplete trace for {case}")
        prefix = OUTPUT / label
        mapped = prefix.with_suffix(".json")
        command(["yosys", "-Q", "-p", f"read_verilog -sv {design}; "
                 f"{SYNTH} -top {TOP} -json {mapped}; check -assert"],
                prefix.with_suffix(".synth.log"))
        cells = Counter(cell["type"] for cell in
                        json.loads(mapped.read_text())["modules"][TOP]["cells"].values())
        harnesses[label] = build_harness(TOP, design, mapped, prefix, synthesis=SYNTH)
        results["variants"][label] = {"cells": dict(cells)}
        print(label, "passed all cycle traces", dict(cells), flush=True)

    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {label: [pool.submit(measure_route, harness, label, seed) for seed in range(1, 6)]
                for label, harness in harnesses.items()}
        for label, routes in jobs.items():
            runs = [job.result() for job in routes]
            frequencies = [run["fmax_mhz"] for run in runs if "fmax_mhz" in run]
            fmax = median(frequencies) if frequencies else None
            variant = results["variants"][label]
            variant.update(routes=runs, median_fmax_mhz=fmax)
            if fmax is not None:
                variant["throughput_mb_s"] = {
                    case: metrics["bytes"] / metrics["cycles"] * fmax
                    for case, metrics in traffic.items()}
            print(label, fmax, variant.get("throughput_mb_s"), flush=True)
    (OUTPUT / "results.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
