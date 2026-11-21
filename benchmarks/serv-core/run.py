"""Compare the official SERV RTL with the Vexim reconstruction."""
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import median

sys.path.insert(0, "/work/benchmarks")
from run import OUTPUT, build_harness, command, route
from import_serv import translate

CASE = Path(__file__).resolve().parent
TOP = "serv_rf_top"


def log_command(args, name):
    log = OUTPUT / (name + ".log")
    command(args, log)
    return log.read_text()


def yosys(script, name):
    log_command(["yosys", "-Q", "-p", script], name)


def main():
    original = sorted(Path("/rtl").glob("*.v"))
    if not original:
        raise ValueError("mount the pinned official SERV rtl folder at /rtl")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    coarse = OUTPUT / "coarse.json"
    yosys(f"read_verilog {' '.join(map(str, original))}; hierarchy -top {TOP}; "
          f"proc; flatten; opt; memory -nordff -nomap; techmap; opt; write_json {coarse}",
          "extract")
    module = json.loads(coarse.read_text())["modules"][TOP]
    candidate = OUTPUT / "serv_rf_top.vxm"
    candidate.write_text(translate(module))
    if candidate.read_text() != (CASE / "serv_rf_top.vxm").read_text():
        raise ValueError("regenerated Vexim differs from the checked-in source")
    generated = OUTPUT / "generated.sv"
    log_command(["veximc", "build", str(candidate), "-o", str(generated)], "compile")
    source = generated.read_text()
    ports = []
    connections = [".no_reset(1'b0)"]
    for name, port in module["ports"].items():
        width = len(port["bits"])
        size = f" [{width - 1}:0]" if width > 1 else ""
        ports.append(f'{port["direction"]} wire{size} {name}')
        connections.append(f".{name}({name})")
    generated.write_text(source + f"\nmodule {TOP}({', '.join(ports)});\n"
                         f"  serv_rf_vex cpu({', '.join(connections)});\nendmodule\n")
    intermediate = OUTPUT / "intermediate.sv"
    yosys(f"read_json {coarse}; write_verilog -noattr {intermediate}", "intermediate-export")
    results = {}
    baseline_trace = None
    variants = (("official", original), ("intermediate", [intermediate]), ("vexim", [generated]))
    for label, rtl in variants:
        binary = OUTPUT / f"{label}.sim"
        log_command(["iverilog", "-g2012", "-s", "tb", "-o", str(binary),
                     *map(str, rtl), str(CASE / "tb.sv")], f"{label}-sim-compile")
        report = log_command(["vvp", str(binary)], f"{label}-sim")
        trace = [line for line in report.splitlines()
                 if line.startswith(("fetch ", "load ", "store ")) or line == "PASS"]
        if not trace or trace[-1] != "PASS":
            raise RuntimeError(f"{label} failed the program")
        if baseline_trace is None:
            baseline_trace = trace
        elif trace != baseline_trace:
            raise RuntimeError("bus transactions differ")
        print(f"{label}: PASS ({len(trace)-1} matching program bus transactions)", flush=True)
        prefix = OUTPUT / label
        mapped = prefix.with_suffix(".ice40.json")
        use_json = label == "intermediate"
        rtl_sources = str(coarse) if use_json else " ".join(map(str, rtl))
        import_design = f"read_json {coarse}" if use_json else f"read_verilog -sv {rtl_sources}"
        yosys(f"{import_design}; synth_ice40 -top {TOP} -flatten; "
              f"check -assert; write_json {mapped}", f"{label}-synth")
        cells = Counter(cell["type"] for cell in
                        json.loads(mapped.read_text())["modules"][TOP]["cells"].values())
        harness = build_harness(TOP, rtl_sources, mapped, prefix, read_json=use_json)
        seeds = route(harness, prefix, "hx8k", "ct256")
        utilization = json.loads(Path(f"{prefix}.hx8k-ct256-seed-1.json").read_text())["utilization"]
        results[label] = {
            "lut4": cells["SB_LUT4"],
            "flip_flops": sum(n for t, n in cells.items() if t.startswith("SB_DFF")),
            "ram4k": cells["SB_RAM40_4K"],
            "routed_logic_cells": utilization["ICESTORM_LC"]["used"],
            "routed_ram4k": utilization["ICESTORM_RAM"]["used"],
            "median_fmax_mhz": median(seed["fmax_mhz"] for seed in seeds),
            "seeds": [seed["fmax_mhz"] for seed in seeds],
        }
        print(label, results[label], flush=True)
    (OUTPUT / "serv-core-results.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
