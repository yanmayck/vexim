"""Compile, compare, and route the complete rv32_demo CPU profile."""
import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import median
import sys

sys.path.insert(0, "/work/benchmarks")
from run import OUTPUT, build_harness, command, route

HERE = Path(__file__).resolve().parent
TOP = "rv32_demo"


def invoke(args, name):
    log = OUTPUT / f"rv32-{name}.log"
    command(args, log)
    return log.read_text()


def simulate(top, files, name):
    binary = OUTPUT / f"{name}.sim"
    invoke(["iverilog", "-g2012", "-s", top, "-o", str(binary), *map(str, files)], name + "-compile")
    if "PASS" not in invoke(["vvp", str(binary)], name + "-test").splitlines():
        raise RuntimeError(f"simulation did not pass: {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registers", action="store_true",
                        help="Use the resettable flip-flop register bank")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    reference = HERE / "reference.sv"
    generated = OUTPUT / "rv32-vexim.sv"
    design_file = "rv32_registers.vxm" if args.registers else "rv32_demo.vxm"
    invoke(["veximc", "build", str(HERE / design_file), "-o", str(generated)], "compile")
    for label, design in (("reference", reference), ("vexim", generated)):
        simulate("tb", [design, HERE / "tb.sv"], label)
    renamed = OUTPUT / "rv32-reference-renamed.sv"
    renamed.write_text(reference.read_text().replace("module rv32_demo(", "module rv32_reference(", 1))
    simulate("differential", [renamed, generated, HERE / "differential.sv"], "differential")
    print("PASS: original program and 20,000 differential cycles", flush=True)

    results = {}
    for label, design in (("reference", reference), ("vexim", generated)):
        prefix = OUTPUT / f"rv32-{label}"
        mapped = prefix.with_suffix(".ice40.json")
        invoke(["yosys", "-Q", "-p", f"read_verilog -sv {design}; synth_ice40 -top {TOP}; "
                f"check -assert; write_json {mapped}"], label + "-area")
        cells = Counter(cell["type"] for cell in
                        json.loads(mapped.read_text())["modules"][TOP]["cells"].values())
        harness = build_harness(TOP, design, mapped, prefix)
        timing = route(harness, prefix, "hx8k", "ct256")
        routed = prefix.with_name(prefix.name + ".hx8k-ct256-seed-1.json")
        usage = json.loads(routed.read_text())["utilization"]
        results[label] = {"lut4": cells["SB_LUT4"],
                          "flip_flops": sum(n for kind, n in cells.items() if kind.startswith("SB_DFF")),
                          "mapped_cells": dict(cells),
                          "routed_logic_cells": usage["ICESTORM_LC"]["used"],
                          "routed_ram4k": usage["ICESTORM_RAM"]["used"],
                          "median_fmax_mhz": median(seed["fmax_mhz"] for seed in timing),
                          "runs": timing}
        print(label, {key: value for key, value in results[label].items() if key != "runs"}, flush=True)
    (OUTPUT / "rv32-results.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
