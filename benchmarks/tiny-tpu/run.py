"""Compare the pinned TinyTPU top against a native Vexim 4x4 array."""
import argparse
import hashlib
import json
import random
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import median

sys.path.insert(0, "/benchmarks")
from run import OUTPUT, build_harness, command
from ecp5_route import route_seed

REV = "97c28d7587689707fe7ff9311eabc7a3949eaef6"
HASHES = {
    "rtl/controller.sv": "545a4982bb61b9437582b02b4353912d9a96aa6f7ab802cfcf4c366c4855892f",
    "rtl/pe.sv": "e4ba80e45c24d7b1c6f7d7d74cb55825de222aa4287613bcda7a4d031683cecd",
    "rtl/systolic_array.sv": "e20703c7ba632ed964e154efc441a7d2804e6bbede43736f725b96d4274fc30e",
    "rtl/tiny_tpu_top.sv": "f978832202c28bdebe44d500c320a21d72eb82c792e39cfedb0f66ea2079ad08",
}
TOP = "matmul"
UPSTREAM = Path("/upstream")
PORTS = """
module matmul(input clk, rst, start, input [127:0] a, b,
              output [511:0] c, output done);
"""
WRAPPER = PORTS + """
  wire signed [7:0] aa [4][4], bb [4][4];
  wire signed [31:0] cc [4][4];
  for (genvar r=0; r<4; r++) begin
    for (genvar j=0; j<4; j++) begin
      assign aa[r][j] = a[8*(4*r+j)+:8];
      assign bb[r][j] = b[8*(4*r+j)+:8];
      assign c[32*(4*r+j)+:32] = cc[r][j];
    end
  end
  tiny_tpu_top dut(.clk(clk), .rst_n(!rst), .start(start),
                  .a_in(aa), .b_in(bb), .c_buf(cc), .done(done));
endmodule
"""


def native(compact):
    # Vexim words are at most 64 bits. Pack the external bus in SystemVerilog.
    lines = ["module native_array", "input clk u1", "input rst u1",
             "input start u1", "output done u1"]
    wrapper = [".clk(clk)", ".rst(rst)", ".start(start)", ".done(done)"]

    def wire(name, width, expr=None):
        lines.append(f"wire {name} u{width}")
        if expr:
            lines.append(f"comb {name} {expr}")
        return name

    def reg(name, width, expr):
        wire(name, width)
        data = wire(f"{name}_d", width, expr)
        lines.append(f"sync {name} clk rst {data}")

    def selected(name, steps):
        value = "zero8"
        for phase, operand in steps:
            value = wire(f"{name}_{phase}", 8, f"mux phase{phase} {operand} {value}")
        return value

    def sign_extend(name, operand, width, target):
        if width == target:
            return operand
        sign = wire(f"{name}_sign", 1, f"slice {operand} {width-1} {width-1}")
        ones = wire(f"{name}_ones", target-width, f"const {(1 << (target-width))-1}")
        zeros = wire(f"{name}_zeros", target-width, "const 0")
        high = wire(f"{name}_hi", target-width, f"mux {sign} {ones} {zeros}")
        return wire(name, target, f"concat {high} {operand}")

    for name, width, value in (("zero4", 4, 0), ("one4", 4, 1), ("zero8", 8, 0),
                               ("ones8", 8, 255), ("zero16", 16, 0),
                               ("ones16", 16, 65535), ("zero32", 32, 0)):
        wire(name, width, f"const {value}")
    for phase in range(15):
        constant = wire(f"p{phase}", 4, f"const {phase}")
        wire(f"phase{phase}", 1, f"eq phase {constant}")
    wire("inc", 4, "add phase one4")
    wire("begin_phase", 4, "mux start one4 zero4")
    wire("advance", 4, "mux phase14 zero4 inc")
    reg("phase", 4, "mux phase0 begin_phase advance")
    lines.append("sync done clk rst phase14")

    for row in range(4):
        for col in range(4):
            suffix = f"{row}_{col}"
            offset = 4 * row + col
            for bus in "ab":
                name = f"{bus}{suffix}"
                lines.append(f"input {name} u8")
                wrapper.append(f".{name}({bus}[{offset*8}+:8])")
                reg(f"{name}_buf", 8, f"mux start {name} {name}_buf")
            result = f"c{suffix}"
            lines.append(f"output {result} u32")
            wrapper.append(f".{result}(c[{offset*32}+:32])")
            capture = f"phase{9+row+col}" if row+col < 6 else "done"
            if compact:
                reg(f"{result}_packed", 18, f"mux {capture} sum3_{col} {result}_packed")
                extended = sign_extend(f"{result}_wide", f"{result}_packed", 18, 32)
                lines.append(f"comb {result} copy {extended}")
            else:
                data = wire(f"{result}_d", 32, f"mux {capture} sum3_{col} {result}")
                lines.append(f"sync {result} clk rst {data}")

    for row in range(4):
        west = selected(f"west{row}", [(5+row+i, f"a{i}_{row}_buf") for i in range(4)])
        for col in range(4):
            suffix = f"{row}_{col}"
            activation = west if col == 0 else f"act{row}_{col-1}"
            partial = "zero32" if row == 0 else f"sum{row-1}_{col}"
            reg(f"act{suffix}", 8, f"copy {activation}")
            weight = f"weight{suffix}"
            reg(weight, 8, f"mux phase{col+1} b{row}_{col}_buf {weight}")
            for tag, operand in (("w", weight), ("a", activation)):
                sign = wire(f"{tag}sign{suffix}", 1, f"slice {operand} 7 7")
                high = wire(f"{tag}hi{suffix}", 8, f"mux {sign} ones8 zero8")
                wire(f"{tag}ext{suffix}", 16, f"concat {high} {operand}")
            product = wire(f"product{suffix}", 16, f"mul wext{suffix} aext{suffix}")
            if compact:
                widths = (16, 17, 17, 18)
                width = widths[row]
                if row == 0:
                    reg(f"sum{suffix}", width, f"copy {product}")
                else:
                    term = sign_extend(f"term{suffix}", product, 16, width)
                    incoming = sign_extend(f"incoming{suffix}", partial, widths[row-1], width)
                    reg(f"sum{suffix}", width, f"add {incoming} {term}")
            else:
                sign = wire(f"sign{suffix}", 1, f"slice {product} 15 15")
                high = wire(f"hi{suffix}", 16, f"mux {sign} ones16 zero16")
                term = wire(f"term{suffix}", 32, f"concat {high} {product}")
                reg(f"sum{suffix}", 32, f"add {partial} {term}")

    shim = PORTS + "  native_array dut(" + ", ".join(wrapper) + ");\nendmodule\n"
    return "\n".join(lines + ["end", ""]), shim


def bench():
    rng = random.Random(789)
    cases = [([0]*16, [0]*16), ([-128]*16, [-128]*16),
             ([127, -128]*8, [-128, 127]*8)]
    cases += [([rng.randrange(-128, 128) for _ in range(16)],
               [rng.randrange(-128, 128) for _ in range(16)]) for _ in range(61)]

    def pack(values, width):
        return sum((value % (1 << width)) << (i*width) for i, value in enumerate(values))

    calls = []
    for a, b in cases:
        c = [sum(a[4*i+k]*b[4*k+j] for k in range(4))
             for i in range(4) for j in range(4)]
        calls.append(f"run(128'h{pack(a,8):x},128'h{pack(b,8):x},512'h{pack(c,32):x});")
    return """module tb;
  reg clk=0, rst=1, start=0;
  reg [127:0] a=0, b=0;
  wire [511:0] c;
  wire done;
  matmul dut(.*);
  task tick;
    begin #5; clk=1; #5; clk=0; end
  endtask
  task run(input [127:0] av,bv,input [511:0] expected);
    begin
      a=av; b=bv; start=1; tick; start=0;
      for(integer i=1;i<=14;i=i+1) begin
        tick;
        if(done !== (i==14)) $fatal(1,"done mismatch at cycle %0d",i);
      end
      tick;
      if(done !== 1'b0 || c !== expected)
        $fatal(1,"matmul mismatch: got %h expected %h",c,expected);
    end
  endtask
  initial begin
    tick; rst=0;
""" + "\n".join(calls) + '\n    $display("PASS"); $finish;\n  end\nendmodule\n'


def measure_route(harness, label, seed):
    try:
        return route_seed(OUTPUT, harness, label, seed, timeout=120)
    except subprocess.TimeoutExpired:
        return {"seed": seed, "error": "Routing exceeded 120 seconds"}
    except subprocess.CalledProcessError as error:
        return {"seed": seed, "error": f"nextpnr exited with status {error.returncode}"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compact", action="store_true", help="narrow internal sums and result registers")
    args = parser.parse_args()
    # Check source contents even when mounted from a detached archive.
    for file, expected in HASHES.items():
        raw = (UPSTREAM / file).read_bytes().replace(b"\r\n", b"\n")
        if hashlib.sha256(raw).hexdigest() != expected:
            raise RuntimeError(f"Unexpected TinyTPU source: {file}")
    wrapper = OUTPUT / "upstream_wrapper.sv"
    wrapper.write_text(WRAPPER)
    official = OUTPUT / "official.v"
    with official.open("w") as out:
        subprocess.run(["/tools/sv2v", *(str(UPSTREAM / name) for name in HASHES),
                        str(wrapper)], stdout=out, check=True, timeout=60)
    source, shim = native(args.compact)
    (OUTPUT / "native.vxm").write_text(source)
    vexim = OUTPUT / "vexim.sv"
    compile_seconds = command(["veximc", "build", str(OUTPUT / "native.vxm"),
                               "-o", str(vexim)], OUTPUT / "compiler.log")
    vexim.write_text(vexim.read_text() + shim)
    tb = OUTPUT / "tb.sv"
    tb.write_text(bench())
    results = {"upstream": REV, "compiler_seconds": compile_seconds, "compact": args.compact,
               "matrices_per_variant": 64, "cycles_to_read": 15, "variants": {}}
    harnesses = {}
    variants = (("vexim", vexim),) if args.compact else (("official", official), ("vexim", vexim))
    for label, design in variants:
        binary = OUTPUT / f"{label}.sim"
        command(["iverilog", "-g2012", "-s", "tb", "-o", str(binary), str(design), str(tb)],
                OUTPUT / f"{label}-compile.log")
        log = OUTPUT / f"{label}-sim.log"
        command(["vvp", str(binary)], log)
        if "PASS" not in log.read_text().splitlines():
            raise RuntimeError(f"{label}: matrix checks did not finish")
        prefix = OUTPUT / label
        mapped = prefix.with_suffix(".json")
        command(["yosys", "-Q", "-p", f"read_verilog -sv {design}; "
                 f"synth_ecp5 -top {TOP} -json {mapped}; check -assert"],
                prefix.with_suffix(".synth.log"))
        cells = Counter(cell["type"] for cell in
                        json.loads(mapped.read_text())["modules"][TOP]["cells"].values())
        results["variants"][label] = {"cells": dict(cells)}
        harnesses[label] = build_harness(TOP, design, mapped, prefix, synthesis="synth_ecp5")
        print(label, "passed 64 matrices", dict(cells), flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        runs = {label: [pool.submit(measure_route, harness, label, seed)
                        for seed in range(1, 6)]
                for label, harness in harnesses.items()}
        for label, jobs in runs.items():
            routes = [job.result() for job in jobs]
            frequencies = [route["fmax_mhz"] for route in routes if "fmax_mhz" in route]
            fmax = median(frequencies) if frequencies else None
            results["variants"][label].update(
                routes=routes, median_fmax_mhz=fmax,
                tile_latency_ns=15000/fmax if fmax else None)
            print(label, fmax, flush=True)
    (OUTPUT / "results.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
