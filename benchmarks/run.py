"""Reproduce simulation, generic synthesis and iCE40 mapping of frozen pairs."""
import hashlib
import json
import subprocess
import time
from collections import Counter
from pathlib import Path

SOURCE = Path(__file__).resolve().parent / "paired-2026-11-18"
OUTPUT = Path("/output")


def command(arguments, log):
    started = time.monotonic()
    with log.open("w") as stream:
        result = subprocess.run(arguments, stdout=stream, stderr=subprocess.STDOUT,
                                timeout=180)
    if result.returncode:
        raise RuntimeError(log.read_text()[-5000:])
    return round(time.monotonic() - started, 3)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows = []
    version = subprocess.check_output(["yosys", "-V"], text=True).strip()
    print("block | language | generic | LUT4 | FF | RAM4K | synthesis seconds")
    for block in ("rr_arbiter", "mem_controller", "home_computer"):
        for language in ("vexim", "systemverilog"):
            source = SOURCE / f"{block}-{language}.sv"
            prefix = OUTPUT / f"{block}-{language}"
            command(["verilator", "--lint-only", "-Wall", "-Wno-DECLFILENAME",
                     "--top-module", block, str(source)], prefix.with_suffix(".lint.log"))
            simulation = prefix.with_suffix(".sim")
            command(["iverilog", "-g2012", "-s", "tb", "-o", str(simulation),
                     str(source), str(SOURCE / f"{block}-tb.sv")],
                    prefix.with_suffix(".compile.log"))
            command(["vvp", str(simulation)], prefix.with_suffix(".simulation.log"))
            if "PASS" not in prefix.with_suffix(".simulation.log").read_text().splitlines():
                raise RuntimeError(f"{block}/{language} simulation did not pass")
            generic = prefix.with_suffix(".generic.json")
            command(["yosys", "-Q", "-p",
                     f"read_verilog -sv {source}; synth -top {block}; check -assert; write_json {generic}"],
                    prefix.with_suffix(".generic.log"))
            generic_count = len(json.loads(generic.read_text())["modules"][block]["cells"])
            mapped = prefix.with_suffix(".ice40.json")
            seconds = command(["yosys", "-Q", "-p",
                               f"read_verilog -sv {source}; synth_ice40 -top {block}; check -assert; write_json {mapped}"],
                              prefix.with_suffix(".ice40.log"))
            cells = Counter(cell["type"] for cell in
                            json.loads(mapped.read_text())["modules"][block]["cells"].values())
            row = {"block": block, "language": language, "passed": True,
                   "generic_cells": generic_count, "lut4": cells["SB_LUT4"],
                   "flip_flops": sum(count for name, count in cells.items() if name.startswith("SB_DFF")),
                   "ram4k": cells["SB_RAM40_4K"], "mapped_cells": dict(cells),
                   "synthesis_seconds": seconds,
                   "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
            rows.append(row)
            print(f"{block} | {language} | {generic_count} | {row['lut4']} | "
                  f"{row['flip_flops']} | {row['ram4k']} | {seconds}", flush=True)
    (OUTPUT / "results.json").write_text(json.dumps({
        "yosys": version, "verilator": subprocess.check_output(["verilator", "--version"], text=True).strip(), "target": "iCE40 (synthesis only)", "runs": rows,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
