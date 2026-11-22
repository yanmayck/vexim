"""Measure sharing across flattened module boundaries on the UP5K."""
import json
import subprocess
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = Path("/output")


def run(args, label):
    log = OUT / (label + ".log")
    with log.open("w") as stream:
        result = subprocess.run(args, cwd=OUT, stdout=stream, stderr=stream, timeout=120)
    if result.returncode:
        raise RuntimeError(log.read_text()[-5000:])
    return log.read_text()


def yosys(script, label):
    return run(["yosys", "-Q", "-p", script], label)


def cell_counts(path, top):
    cells = json.loads(path.read_text())["modules"][top]["cells"].values()
    return dict(Counter(cell["type"] for cell in cells))


def verify(top, baseline, shared):
    if top == "increment_selector":
        yosys(f"read_verilog -sv {baseline}; rename {top} gold; "
              f"read_verilog -sv {shared}; rename {top} gate; proc; "
              "miter -equiv -flatten gold gate miter; hierarchy -top miter; opt; "
              "sat -set-init-zero -tempinduct -seq 1 -maxsteps 2 -verify -prove trigger 0",
              top + "-equivalence")
        return
    gold = OUT / "gold.sv"
    gate = OUT / "gate.sv"
    for source, dest in ((baseline, gold), (shared, gate)):
        yosys(f"read_verilog -sv {source}; rename {top} {dest.stem}; "
              f"write_verilog -noattr {dest}", dest.stem + "-export")
    binary = OUT / "rounds.sim"
    run(["iverilog", "-g2012", "-s", "round_selector_tb", "-o", str(binary),
         str(gold), str(gate), str(HERE / "round_selector_tb.sv")], "rounds-compile")
    report = run(["vvp", str(binary)], "rounds-sim")
    if "PASS all 65,536 operand pairs in both phases" not in report.splitlines():
        raise RuntimeError("round-selector simulation did not pass")


def benchmark(top, module, operator):
    results = {}
    netlists = {}
    for mode, flags in (("baseline", []), ("shared", ["--share"])):
        label = f"{top}-{mode}"
        netlists[mode] = design = OUT / f"{label}.sv"
        run(["veximc", "design", top, str(HERE / module),
             str(HERE / f"{top}.sv"), "-o", str(design), *flags], label + "-export")
        generic = OUT / f"{label}-generic.json"
        mapped = OUT / f"{label}-up5k.json"
        yosys(f"read_verilog -sv {design}; proc; write_json {generic}", label + "-generic")
        yosys(f"read_verilog -sv {design}; synth_ice40 -device u -dsp -top {top} -json {mapped}; "
              "check -assert", label + "-mapped")
        results[mode] = {"generic": cell_counts(generic, top), "up5k": cell_counts(mapped, top)}
    expected = (results["baseline"]["generic"].get(operator), results["shared"]["generic"].get(operator))
    if expected != (2, 1):
        raise RuntimeError(f"{top}: expected two operators to become one, found {expected}")
    verify(top, netlists["baseline"], netlists["shared"])
    return results


def check_parallel_lanes():
    design = OUT / "parallel-shared.sv"
    generic = OUT / "parallel-generic.json"
    run(["veximc", "design", "parallel_lanes", str(HERE / "mul_lane.sv"),
         str(HERE / "parallel_lanes.sv"), "-o", str(design), "--share"], "parallel-export")
    yosys(f"read_verilog -sv {design}; proc; write_json {generic}", "parallel-generic")
    count = cell_counts(generic, "parallel_lanes").get("$mul")
    if count != 2:
        raise RuntimeError(f"expected concurrent multipliers to remain separate, found {count}")
    return count


def main():
    results = {
        "increment_selector": benchmark("increment_selector", "inc_lane.vxm", "$add"),
        "round_selector": benchmark("round_selector", "mul_lane.sv", "$mul"),
        "simultaneously_observable_multipliers": check_parallel_lanes(),
    }
    report = json.dumps(results, indent=2)
    (OUT / "global-sharing-results.json").write_text(report + "\n")
    print(report)


if __name__ == "__main__":
    main()
