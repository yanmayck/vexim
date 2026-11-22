"""Run the configurable Vexim packet switch against independent SystemVerilog."""
import json
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import median

from traffic import make_test, reference_wrapper

sys.path.insert(0, "/benchmarks")
from run import OUTPUT, build_harness, command
from ecp5_route import route_seed

TOP = "packet_switch"
SYNTH = "synth_ecp5"
HERE = Path(__file__).resolve().parent


def route(harness, label, seed):
    try:
        return route_seed(OUTPUT, harness, label, seed, timeout=120)
    except subprocess.TimeoutExpired:
        return {"seed": seed, "error": "Routing exceeded 120 seconds"}
    except subprocess.CalledProcessError as error:
        return {"seed": seed, "error": f"nextpnr exited with status {error.returncode}"}


def simulate(compiler, n):
    output = OUTPUT / str(n)
    output.mkdir(exist_ok=True)
    source = HERE / "switch.vxm"
    vexim = output / "vexim.sv"
    compiler_seconds = command([str(compiler), "build", str(source),
                                "--param", f"PORTS={n}", "-o", str(vexim)],
                               output / "compiler.log")
    reference = output / "systemverilog.sv"
    reference.write_text((HERE / "reference.sv").read_text() + "\n" + reference_wrapper(n))
    traffic = make_test(n, output)
    designs = {"systemverilog": reference, "vexim": vexim}
    for label, design in designs.items():
        executable = output / f"{label}.sim"
        command(["iverilog", "-g2012", "-s", "tb", "-o", str(executable),
                 str(design), str(output / "tb.sv")], output / f"{label}-compile.log")
        for scenario, stats in traffic.items():
            log = output / f"{label}-{scenario}.log"
            command(["vvp", str(executable), f"+vectors={output / (scenario + '.hex')}"], log)
            if f"PASS {stats['vectors']}" not in log.read_text().splitlines():
                raise RuntimeError(f"{label}: incomplete trace for {scenario}")
        print(n, label, "passed all packet traces", flush=True)
    return {"traffic": traffic, "compiler_seconds": compiler_seconds}, designs


def main():
    compiler = OUTPUT / "veximc"
    results = {"simulation": {}, "variants_4x4": {}}
    harnesses = {}
    for n in (2, 4, 8):
        stats, designs = simulate(compiler, n)
        results["simulation"][n] = stats
        if n != 4:
            continue
        for label, design in designs.items():
            prefix = OUTPUT / str(n) / label
            mapped = prefix.with_suffix(".json")
            command(["yosys", "-Q", "-p", f"read_verilog -sv {design}; "
                     f"{SYNTH} -top {TOP} -json {mapped}; check -assert"],
                    prefix.with_suffix(".synth.log"))
            counts = Counter(cell["type"] for cell in
                             json.loads(mapped.read_text())["modules"][TOP]["cells"].values())
            results["variants_4x4"][label] = {"cells": dict(counts)}
            harnesses[label] = build_harness(TOP, design, mapped, prefix, synthesis=SYNTH)
            print(n, label, dict(counts), flush=True)

    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {label: [pool.submit(route, harness, label, seed) for seed in range(1, 6)]
                for label, harness in harnesses.items()}
        for label, futures in jobs.items():
            runs = [job.result() for job in futures]
            fmax = [run["fmax_mhz"] for run in runs if "fmax_mhz" in run]
            variant = results["variants_4x4"][label]
            variant.update(runs=runs, median_fmax_mhz=median(fmax) if fmax else None)
            if fmax:
                variant["throughput_mb_s_per_port"] = {
                    case: [beats*4/metrics["cycles"]*median(fmax) for beats in metrics["beats"]]
                    for case, metrics in results["simulation"][4]["traffic"].items()}
            print(label, variant["median_fmax_mhz"], flush=True)
    (OUTPUT / "results.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
