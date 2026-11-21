"""Compare the compiler's operator sharing with FPGA synthesis in both arms."""
import json
import subprocess
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = Path("/output")


def run(args, label):
    with (OUT / f"{label}.log").open("w") as log:
        subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=60)


def yosys(script, label):
    run(["yosys", "-Q", "-p", script], label)


def main():
    normal = OUT / "default.sv"
    optimized = OUT / "shared.sv"
    for design, options in ((normal, []), (optimized, ["--opt-area"])):
        run(["veximc", "build", str(HERE / "state_add.vxm"), "-o", str(design), *options],
            design.stem + "-compile")

    yosys(f"read_verilog -sv {normal}; rename state_add gold; "
          f"read_verilog -sv {optimized}; rename state_add gate; "
          "proc; opt; equiv_make gold gate equiv; hierarchy -top equiv; "
          "equiv_simple; equiv_induct -seq 4; equiv_status -assert", "equivalence")
    results = {}
    for design in (normal, optimized):
        generic = OUT / f"{design.stem}-generic.json"
        mapped = OUT / f"{design.stem}-mapped.json"
        yosys(f"read_verilog -sv {design}; proc; write_json {generic}", design.stem + "-generic")
        yosys(f"read_verilog -sv {design}; synth_ice40 -device u -top state_add -json {mapped}; "
              "check -assert", design.stem + "-mapped")
        for path in (generic, mapped):
            cells = json.loads(path.read_text())["modules"]["state_add"]["cells"]
            results[path.stem] = dict(Counter(cell["type"] for cell in cells.values()))

    if (results["default-generic"].get("$add"), results["shared-generic"].get("$add")) != (2, 1):
        raise RuntimeError("expected the compiler to merge two adders into one")

    print(json.dumps(results, indent=2))
    (OUT / "sharing-results.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
