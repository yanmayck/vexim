"""Reconstruct a pinned PicoRV32 IM profile, run firmware, and measure area."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from time import monotonic

HERE = Path(__file__).resolve().parent
OUT = Path("/output")
sys.path.insert(0, str(HERE.parent / "serv-core"))
from import_serv import translate

TOP = "picorv32"
CORE = "pico_vex"
DIVIDER = "picorv32_pcpi_div"
DEFINES = "-chparam ENABLE_MUL 1 -chparam ENABLE_DIV 1"


def run(args, label):
    log = OUT / f"{label}.log"
    with log.open("w") as stream:
        result = subprocess.run(args, cwd=OUT, stdout=stream, stderr=stream, timeout=240)
    if result.returncode:
        raise RuntimeError(log.read_text()[-5000:])


def yosys(script, name):
    run(["yosys", "-Q", "-p", script], name)


def divider_boundary(module):
    matches = [name for name, cell in module["cells"].items() if cell["type"] == DIVIDER]
    if len(matches) != 1:
        raise ValueError("expected one retained divider")
    divider = module["cells"].pop(matches[0])
    links = {}
    for port, direction in divider["port_directions"].items():
        net = f"div_link_{port}"
        bits = divider["connections"][port]
        core_direction = "output" if direction == "input" else "input"
        module["ports"][net] = {"direction": core_direction, "bits": bits}
        links[port] = net, len(bits)
    return links


def build_divider(mode, module, upstream):
    if mode == "official":
        match = re.search(r"^module picorv32_pcpi_div\s*\(.*?^endmodule\b",
                          upstream.read_text(), re.MULTILINE | re.DOTALL)
        if not match:
            raise ValueError("official divider module not found")
        return DIVIDER, match.group() + "\n", []
    name = "divider_vex"
    (OUT / "divider.vxm").write_text(translate(
        module, name=name, source="pinned ISC-licensed PicoRV32 divider"))
    run(["veximc", "build", "divider.vxm", "-o", "divider.sv"], "divider-compile")
    return name, (OUT / "divider.sv").read_text(), [".no_reset(1'b0)"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--word", action="store_true", help="Preserve word-level add and sub cells")
    parser.add_argument("--mux", action="store_true", help="Also preserve word-level muxes")
    parser.add_argument("--compare", action="store_true", help="Also preserve word-level ordering comparisons")
    parser.add_argument("--registers", action="store_true",
                        help="Preserve word registers together with arithmetic, muxes and comparisons")
    parser.add_argument("--divider", choices=("official", "imported"),
                        help="Isolate the divider and choose its implementation")
    args = parser.parse_args()
    if args.divider:
        args.mux = args.compare = True
    if args.registers:
        args.mux = args.compare = True
    upstream = Path("/rtl/picorv32.v")
    verify = json.loads((HERE / "upstream.json").read_text())
    if hashlib.sha256(upstream.read_bytes().replace(b"\r\n", b"\n")).hexdigest() != verify["sha256_lf"]:
        raise ValueError("source does not match the pinned PicoRV32 revision")
    preserved = ["$add", "$sub"] if args.word or args.mux or args.compare else []
    if args.mux:
        preserved.append("$mux")
    if args.compare:
        preserved.extend(("$lt", "$le", "$gt", "$ge"))
    if args.registers:
        preserved.extend(("$dff", "$dffe", "$sdff", "$sdffe", "$sdffce"))
    selection = f"t:{preserved[0]}" if preserved else ""
    selection += "".join(f" t:{kind} %u" for kind in preserved[1:])
    mapping = f"techmap {selection} %n" if preserved else "techmap"
    fence = f"setattr -set keep_hierarchy 1 t:{DIVIDER}; " if args.divider else ""
    yosys(f"read_verilog {upstream}; hierarchy -top {TOP} {DEFINES}; "
          f"proc; {fence}flatten; opt; memory -nomap -nordff; {mapping}; opt; write_json coarse.json",
          "extract")
    modules = json.loads((OUT / "coarse.json").read_text())["modules"]
    module = modules[TOP]
    external_ports = module["ports"].copy()
    links = divider_boundary(module) if args.divider else {}
    source = translate(module, name=CORE, source="pinned ISC-licensed PicoRV32 RTL")
    candidate = OUT / "pico.vxm"
    candidate.write_text(source)
    (OUT / "COPYING.pico").write_bytes((HERE / "COPYING").read_bytes())
    started = monotonic()
    run(["veximc", "build", "pico.vxm", "-o", "pico.sv"], "compile")
    compile_seconds = monotonic() - started
    ports = []
    wiring = [".no_reset(1'b0)"]
    for name, port in external_ports.items():
        width = len(port["bits"])
        dimension = f" [{width - 1}:0]" if width > 1 else ""
        ports.append(f'{port["direction"]} wire{dimension} {name}')
        wiring.append(f".{name}({name})")
    path = OUT / "pico.sv"
    declarations = []
    divider_instance = ""
    if args.divider:
        divider_type, divider_source, divider_wiring = build_divider(
            args.divider, modules[DIVIDER], upstream)
        for port, (net, width) in links.items():
            dimension = f" [{width - 1}:0]" if width > 1 else ""
            declarations.append(f"  wire{dimension} {net};\n")
            wiring.append(f".{net}({net})")
            divider_wiring.append(f".{port}({net})")
        divider_instance = f"  {divider_type} divider({', '.join(divider_wiring)});\n"
        with path.open("a") as file:
            file.write("\n" + divider_source)
    with path.open("a") as file:
        file.write(f"\nmodule {TOP}({', '.join(ports)});\n"
                   f"{''.join(declarations)}"
                   f"  {CORE} cpu({', '.join(wiring)});\n"
                   f"{divider_instance}endmodule\n")
    arithmetic = Counter(cell["type"] for cell in module["cells"].values())
    results = {"vexim_lines": len(source.splitlines()), "compile_seconds": compile_seconds,
               "word_cells": {name: arithmetic[name] for name in preserved},
               "divider": args.divider, "seeds": {}, "ecp5": {}}

    for label, design, definitions in (("official", str(upstream), ["-DOFFICIAL"]),
                                       ("vexim", str(path), [])):
        run(["iverilog", "-g2012", "-s", "tb", "-o", f"{label}.sim",
             *definitions, design, str(HERE / "tb.sv")], f"{label}-sim-compile")
    for seed in (1, 73, 913):
        traces = []
        for label in ("official", "vexim"):
            name = f"{label}-seed-{seed}"
            run(["vvp", f"{label}.sim", f"+seed={seed}"], name)
            lines = (OUT / f"{name}.log").read_text().splitlines()
            trace = [line for line in lines if line.startswith(("BUS ", "PASS "))]
            if not trace or not trace[-1].startswith("PASS "):
                raise RuntimeError(f"{name} never reached PASS")
            traces.append(trace)
        if traces[0] != traces[1]:
            raise RuntimeError(f"bus trace mismatch for seed {seed}")
        print(traces[0][-1], "matching transactions:", len(traces[0])-1, flush=True)
        results["seeds"][seed] = {"summary": traces[0][-1], "transactions": len(traces[0])-1}
    # Repeated techmap can collide with generated names in this combined profile.
    intermediate = "read_json coarse.json"
    if args.mux and args.compare:
        intermediate += "; rename -enumerate"
    flows = (
        ("official", f"read_verilog -sv {upstream}; hierarchy -top {TOP} {DEFINES}"),
        ("intermediate", intermediate),
        ("vexim", f"read_verilog -sv {path}"),
    )
    if args.divider:
        flows = tuple(flow for flow in flows if flow[0] != "intermediate")
    if args.mux and args.compare and not args.divider:
        yosys("read_json coarse.json; write_verilog -noattr intermediate-sv.sv",
              "intermediate-sv-export")
        flows += (("intermediate-sv", "read_verilog -sv intermediate-sv.sv"),)
    for label, input_command in flows:
        yosys(f"{input_command}; synth_ecp5 -top {TOP} "
              f"-json {label}.ecp5.json; check -assert", f"{label}-ecp5")
        cells = json.loads((OUT / f"{label}.ecp5.json").read_text())["modules"][TOP]["cells"]
        results["ecp5"][label] = dict(Counter(c["type"] for c in cells.values()))
    (OUT / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
