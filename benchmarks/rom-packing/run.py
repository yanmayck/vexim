"""Compare inferred EBR with logic mapping for a synchronous Vexim ROM."""
import json
import subprocess
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = Path("/output")
CELLS = "/usr/share/yosys/ice40/cells_sim.v"


def command(args, name):
    log = OUT / f"{name}.log"
    with log.open("w") as stream:
        result = subprocess.run(args, stdout=stream, stderr=stream, timeout=120)
    if result.returncode:
        raise RuntimeError(log.read_text()[-5000:])
    return log.read_text()


def simulate(design, name):
    sim = OUT / f"{name}.sim"
    command(["iverilog", "-g2012", "-s", "tb", "-o", str(sim), str(design),
             CELLS, str(HERE / "tb.sv")], f"{name}-compile")
    report = command(["vvp", str(sim)], f"{name}-simulate")
    if "PASS 256 registered lookups" not in report:
        raise RuntimeError(f"{name}: missing simulation success")
    print(name, report.splitlines()[0], flush=True)


def main():
    source = HERE / "aes_sbox.vxm"
    values = next(line.split()[3:] for line in source.read_text().splitlines()
                  if line.startswith("rom table "))
    (OUT / "expected.hex").write_text("".join(f"{int(value):02x}\n" for value in values))
    emitted = OUT / "emitted.sv"
    command(["veximc", "build", str(source), "-o", str(emitted)], "vexim")
    simulate(emitted, "rtl")

    counts = {}
    for name, option in (("logic_only", "-nobram"), ("auto", "")):
        netlist = OUT / f"{name}.json"
        mapped = OUT / f"{name}.sv"
        command(["yosys", "-Q", "-p", f"read_verilog -sv {emitted}; "
                 f"synth_ice40 -device u {option} -top aes_sbox -json {netlist}; "
                 f"check -assert; write_verilog -noattr {mapped}"], f"{name}-synth")
        simulate(mapped, name)
        cells = json.loads(netlist.read_text())["modules"]["aes_sbox"]["cells"]
        counts[name] = dict(Counter(cell["type"] for cell in cells.values()))
    if counts["auto"].get("SB_RAM40_4K", 0) != 1:
        raise RuntimeError("expected one automatically inferred EBR")
    if counts["auto"].get("SB_LUT4", 0) >= counts["logic_only"].get("SB_LUT4", 0):
        raise RuntimeError("the EBR variant did not reduce LUT usage")
    (OUT / "rom-results.json").write_text(json.dumps(counts, indent=2) + "\n")
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
