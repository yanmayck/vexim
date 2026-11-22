"""Reconstruct a pinned PicoRV32 IM profile, run firmware, and measure area."""
import hashlib
import json
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
DEFINES = "-chparam ENABLE_MUL 1 -chparam ENABLE_DIV 1"


def run(args, label):
    log = OUT / f"{label}.log"
    with log.open("w") as stream:
        result = subprocess.run(args, cwd=OUT, stdout=stream, stderr=stream, timeout=240)
    if result.returncode:
        raise RuntimeError(log.read_text()[-5000:])


def yosys(script, name):
    run(["yosys", "-Q", "-p", script], name)


def main():
    upstream = Path("/rtl/picorv32.v")
    verify = json.loads((HERE / "upstream.json").read_text())
    if hashlib.sha256(upstream.read_bytes().replace(b"\r\n", b"\n")).hexdigest() != verify["sha256_lf"]:
        raise ValueError("source does not match the pinned PicoRV32 revision")
    yosys(f"read_verilog {upstream}; hierarchy -top {TOP} {DEFINES}; "
          "proc; flatten; opt; memory -nomap -nordff; techmap; opt; write_json coarse.json",
          "extract")
    module = json.loads((OUT / "coarse.json").read_text())["modules"][TOP]
    source = translate(module, name=CORE, source="pinned ISC-licensed PicoRV32 RTL")
    candidate = OUT / "pico.vxm"
    candidate.write_text(source)
    (OUT / "COPYING.pico").write_bytes((HERE / "COPYING").read_bytes())
    started = monotonic()
    run(["veximc", "build", "pico.vxm", "-o", "pico.sv"], "compile")
    compile_seconds = monotonic() - started
    ports = []
    wiring = [".no_reset(1'b0)"]
    for name, port in module["ports"].items():
        width = len(port["bits"])
        dimension = f" [{width - 1}:0]" if width > 1 else ""
        ports.append(f'{port["direction"]} wire{dimension} {name}')
        wiring.append(f".{name}({name})")
    path = OUT / "pico.sv"
    with path.open("a") as file:
        file.write(f"\nmodule {TOP}({', '.join(ports)});\n"
                   f"  {CORE} cpu({', '.join(wiring)});\nendmodule\n")
    results = {"vexim_lines": len(source.splitlines()), "compile_seconds": compile_seconds,
               "seeds": {}, "ecp5": {}}

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
    flows = (
        ("official", f"read_verilog -sv {upstream}; hierarchy -top {TOP} {DEFINES}"),
        ("intermediate", "read_json coarse.json"),
        ("vexim", f"read_verilog -sv {path}"),
    )
    for label, input_command in flows:
        yosys(f"{input_command}; synth_ecp5 -top {TOP} "
              f"-json {label}.ecp5.json; check -assert", f"{label}-ecp5")
        cells = json.loads((OUT / f"{label}.ecp5.json").read_text())["modules"][TOP]["cells"]
        results["ecp5"][label] = dict(Counter(c["type"] for c in cells.values()))
    (OUT / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
