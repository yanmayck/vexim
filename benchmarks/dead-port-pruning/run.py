"""Check and measure dead hierarchical state with the Yosys design command."""
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = Path("/output")


def run(args, label):
    log = OUT / f"{label}.log"
    with log.open("w") as output:
        result = subprocess.run(args, stdout=output, stderr=subprocess.STDOUT, timeout=60)
    if result.returncode:
        raise RuntimeError(log.read_text()[-4000:])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    emitted = {}
    results = {}
    for label, options in (("original", []), ("pruned", ["--prune"])):
        emitted[label] = OUT / f"{label}.sv"
        output_json = OUT / f"{label}.json"
        run(["veximc", "design", "prune_demo", str(HERE / "top.sv"),
             str(HERE / "ip_leaf.vxm"), "-o", str(emitted[label]), *options], label + "-design")
        run(["yosys", "-Q", "-p", f"read_verilog -sv {emitted[label]}; proc; "
             f"write_json {output_json}"], label + "-inspect")
        top = json.loads(output_json.read_text())["modules"]["prune_demo"]
        results[label] = {
            "register_bits": sum(len(cell["connections"]["Q"])
                                 for cell in top["cells"].values() if cell["type"] == "$dff"),
            "adders": sum(cell["type"] == "$add" for cell in top["cells"].values()),
            "ports": {name: (port["direction"], len(port["bits"]))
                      for name, port in top["ports"].items()},
        }
    original, pruned = results["original"], results["pruned"]
    if (original["register_bits"], pruned["register_bits"]) != (24, 8):
        raise RuntimeError("unused child diagnostic state was not removed")
    if (original["adders"], pruned["adders"]) != (1, 0) or original["ports"] != pruned["ports"]:
        raise RuntimeError("unexpected datapath or top interface")
    run(["yosys", "-Q", "-p",
         f"read_verilog -sv {emitted['original']}; rename prune_demo gold; "
         f"read_verilog -sv {emitted['pruned']}; rename prune_demo gate; "
         "proc; equiv_make gold gate equiv; hierarchy -top equiv; "
         "equiv_simple; equiv_induct -seq 4; equiv_status -assert"], "equivalence")
    (OUT / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print("PASS: top interfaces match and Yosys proved sequential equivalence")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
