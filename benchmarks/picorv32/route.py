"""Route one previously synthesized PicoRV32 benchmark arm on ECP5."""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ecp5_route import route_seed
from run import build_harness

OUT = Path("/output")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("variant", choices=("official", "vexim", "intermediate-sv"))
    args = parser.parse_args()
    variant = args.variant
    if variant == "official":
        rtl = Path("/rtl/picorv32.v")
        synth = "chparam -set ENABLE_MUL 1 -set ENABLE_DIV 1 picorv32; synth_ecp5"
    else:
        rtl = OUT / ("pico.sv" if variant == "vexim" else "intermediate-sv.sv")
        synth = "synth_ecp5"
    harness = build_harness("picorv32", rtl, OUT / f"{variant}.ecp5.json",
                            OUT / f"{variant}-timing", synthesis=synth)
    with ThreadPoolExecutor(max_workers=3) as executor:
        jobs = [executor.submit(route_seed, OUT, harness, f"{variant}-route", seed) for seed in range(1, 6)]
        results = [job.result() for job in jobs]
    summary = {"variant": variant, "runs": results,
               "median_fmax_mhz": median(row["fmax_mhz"] for row in results)}
    (OUT / f"{variant}-timing.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
