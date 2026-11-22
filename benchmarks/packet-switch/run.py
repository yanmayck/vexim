"""Run the configurable Vexim packet switch against independent SystemVerilog."""
import argparse
import json
import re
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


def logged_timing(log):
    """Read timing only after router2 has reported successful routing."""
    _, marker, final = log.read_text().partition("Routing complete.")
    if not marker:
        return {}
    match = re.search(
        r"Max frequency for clock '([^']+)': ([\d.]+) MHz \((?:PASS|FAIL) at ([\d.]+) MHz\)",
        final,
    )
    if not match:
        return {}
    clock, actual, target = match.groups()
    return {"clock": clock, "fmax_mhz": float(actual), "target_mhz": float(target),
            "timing_source": "post-route log"}


def route(harness, label, seed, timeout):
    try:
        return route_seed(OUTPUT, harness, label, seed, timeout=timeout)
    except subprocess.TimeoutExpired:
        log = OUTPUT / f"{label}-seed-{seed}.log"
        return {"seed": seed, "error": f"Run exceeded {timeout} seconds",
                **logged_timing(log)}
    except subprocess.CalledProcessError as error:
        return {"seed": seed, "error": f"nextpnr exited with status {error.returncode}"}


def simulate(compiler, n, registered=False):
    output = OUTPUT / str(n)
    output.mkdir(exist_ok=True)
    label = "registered" if registered else "vexim"
    source = HERE / ("switch_registered.vxm" if registered else "switch.vxm")
    vexim = output / f"{label}.sv"
    compiler_seconds = command([str(compiler), "build", str(source),
                                "--param", f"PORTS={n}", "-o", str(vexim)],
                               output / "compiler.log")
    if registered:
        designs = {label: vexim}
    else:
        reference = output / "systemverilog.sv"
        reference.write_text((HERE / "reference.sv").read_text() + "\n" + reference_wrapper(n))
        designs = {"systemverilog": reference, label: vexim}
    traffic = make_test(n, output)
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


def summarize(runs, traffic):
    frequencies = [run["fmax_mhz"] for run in runs if "fmax_mhz" in run]
    fmax = median(frequencies) if frequencies else None
    result = {"runs": runs, "median_fmax_mhz": fmax}
    if fmax is not None:
        result["throughput_mb_s_per_port"] = {
            case: [beats*4/metrics["cycles"]*fmax for beats in metrics["beats"]]
            for case, metrics in traffic.items()
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-ports", type=int, choices=(4, 8), default=4)
    parser.add_argument("--registered", action="store_true", help="measure the registered Vexim switch only")
    parser.add_argument("--seed", type=int, choices=range(1, 6), action="append",
                        help="route only the selected seeds (default: all five)")
    args = parser.parse_args()
    physical = args.physical_ports
    timeout = 240 if physical == 8 else 120
    seeds = dict.fromkeys(args.seed or range(1, 6))
    variants = f"variants_{physical}x{physical}"
    compiler = OUTPUT / "veximc"
    results = {"simulation": {}, variants: {}}
    harnesses = {}
    sizes = (physical,) if args.registered else (2, 4, 8)
    for n in sizes:
        stats, designs = simulate(compiler, n, args.registered)
        results["simulation"][n] = stats
        if n != physical:
            continue
        for label, design in designs.items():
            prefix = OUTPUT / str(n) / label
            mapped = prefix.with_suffix(".json")
            command(["yosys", "-Q", "-p", f"read_verilog -sv {design}; "
                     f"{SYNTH} -top {TOP} -json {mapped}; check -assert"],
                    prefix.with_suffix(".synth.log"))
            counts = Counter(cell["type"] for cell in
                             json.loads(mapped.read_text())["modules"][TOP]["cells"].values())
            results[variants][label] = {"cells": dict(counts)}
            harnesses[label] = build_harness(TOP, design, mapped, prefix, synthesis=SYNTH)
            print(n, label, dict(counts), flush=True)

    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {label: [pool.submit(route, harness, label, seed, timeout)
                        for seed in seeds]
                for label, harness in harnesses.items()}
        for label, futures in jobs.items():
            runs = [job.result() for job in futures]
            variant = results[variants][label]
            variant.update(summarize(runs, results["simulation"][physical]["traffic"]))
            print(label, variant["median_fmax_mhz"], flush=True)
    (OUTPUT / "results.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
