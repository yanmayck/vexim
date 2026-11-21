"""Prove the fixed SERV memory-interface profile and measure its routed timing."""
import json
from pathlib import Path
from statistics import median
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run import OUTPUT, command, route

FIXTURE = Path(__file__).resolve().parent


def yosys(script, log):
    command(["yosys", "-Q", "-p", script], OUTPUT / log)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    original = FIXTURE / "upstream.v"
    wrapper = FIXTURE / "profile.sv"
    translated = OUTPUT / "serv-vexim.sv"
    command(["veximc", "build", str(FIXTURE / "serv_mem_core.vxm"),
             "-o", str(translated)], OUTPUT / "veximc.log")
    read = f"read_verilog -sv {original} {translated} {wrapper}; "
    setup = read + ("rename serv_mem_if gold; rename serv_mem_if_profile gate; "
                    "proc; flatten gate; opt; ")
    yosys(setup + ("miter -equiv -flatten gold gate miter; prep -top miter; "
                   "sat -verify -seq 5 -set-at 1 in_i_word 1 -prove-skip 1 -prove trigger 0"),
          "serv-equivalence-base.log")
    yosys(setup + ("cd gate; rename dut.signbit signbit; cd ..; equiv_make gold gate equiv; hierarchy -top equiv; "
                   "equiv_simple; equiv_induct -seq 4; equiv_status -assert"),
          "serv-equivalence-induction.log")
    rows = {}
    for name, top in (("upstream", "serv_mem_if"), ("vexim", "serv_mem_if_profile")):
        area = OUTPUT / f"serv-{name}-area.json"
        yosys(read + f"synth_ice40 -top {top}; check -assert; write_json {area}",
              f"serv-{name}-area.log")
        cells = json.loads(area.read_text())["modules"][top]["cells"].values()
        lut4 = sum(cell["type"] == "SB_LUT4" for cell in cells)
        ff = sum(cell["type"].startswith("SB_DFF") for cell in cells)
        netlist = OUTPUT / f"serv-{name}-timing.json"
        yosys(read + f"read_verilog -sv -DDUT={top} {FIXTURE / 'timing.sv'}; "
              f"synth_ice40 -top timing_harness; check -assert; write_json {netlist}",
              f"serv-{name}-timing.log")
        runs = route(netlist, OUTPUT / f"serv-{name}", "hx8k", "ct256")
        fmax = median(run["fmax_mhz"] for run in runs)
        rows[name] = {"lut4": lut4, "flip_flops": ff, "median_fmax_mhz": fmax, "runs": runs}
        print(f"{name}: {lut4} LUT4, {ff} FF, median Fmax {fmax:.2f} MHz", flush=True)
    (OUTPUT / "serv-results.json").write_text(json.dumps(rows, indent=2) + "\n")


if __name__ == "__main__":
    main()
