"""Run a measured ECP5-85F routing seed."""
import json
import subprocess


def route_seed(output, harness, label, seed):
    report = output / f"{label}-seed-{seed}.json"
    with report.with_suffix(".log").open("w") as log:
        subprocess.run([
            "nextpnr-ecp5", "--85k", "--package", "CABGA381",
            "--speed", "6", "--router", "router2", "--json", str(harness), "--freq", "75",
            "--lpf-allow-unconstrained", "--timing-allow-fail",
            "--seed", str(seed), "--report", str(report),
            "--textcfg", str(report.with_suffix(".config")),
        ], stdout=log, stderr=subprocess.STDOUT, check=True, timeout=900)
    data = json.loads(report.read_text())
    (clock, timing), = data["fmax"].items()
    usage = {kind: count["used"] for kind, count in data["utilization"].items()
             if count["used"]}
    return {"seed": seed, "fmax_mhz": timing["achieved"], "clock": clock,
            "target_mhz": timing["constraint"], "usage": usage}
