"""Render the benchmark comparison from the Docker runner's results.json."""
import argparse
import json
from pathlib import Path
from statistics import median

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

BLOCKS = ("rr_arbiter", "mem_controller", "home_computer")
LABELS = ("Round-robin arbiter", "Memory controller", "Automation CPU")
VARIANTS = (
    ("vexim", "Vexim → SystemVerilog", "#005f73", -0.17),
    ("systemverilog", "Direct SystemVerilog", "#a04714", 0.17),
)


def plot(results, output):
    rows = {(row["block"], row["language"]): row for row in results["runs"]}
    fig, axes = plt.subplots(1, 3, figsize=(14, 5.1), sharey=True)
    fig.patch.set_facecolor("#f4f7fa")
    fig.subplots_adjust(left=.17, right=.97, top=.69, bottom=.22, wspace=.30)
    fig.text(.05, .91, "Vexim FPGA benchmark", fontsize=24, weight="bold", color="#102334")
    fig.text(.05, .84, "3 RTL blocks  /  2 iCE40 devices  /  5 routing seeds per pair",
             fontsize=12, color="#42576b")
    for ax, title, unit in zip(axes, ("Mapped area", "iCE40 HX8K", "iCE40 UP5K"),
                               ("LUT4s · fewer is better", "Fmax (MHz) · higher is better",
                                "Fmax (MHz) · higher is better"), strict=True):
        ax.set_title(title, loc="left", weight="bold", pad=13)
        ax.set_xlabel(unit, labelpad=9)
        ax.grid(axis="x", color="#dbe3ea", zorder=0)
        ax.set_axisbelow(True)
        ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
        ax.tick_params(length=0, pad=6)
        ax.set_xlim(left=0)
    axes[0].set_yticks(range(len(BLOCKS)), LABELS)
    axes[0].invert_yaxis()
    for index, block in enumerate(BLOCKS):
        for key, label, color, offset in VARIANTS:
            row = rows[block, key]
            y = index + offset
            axes[0].barh(y, row["lut4"], height=.25, color=color,
                         label=label if index == 0 else None)
            axes[0].annotate(str(row["lut4"]), (row["lut4"], y),
                             xytext=(4, 0), textcoords="offset points", va="center", color=color)
            for ax, device in zip(axes[1:], ("hx8k_ct256", "up5k_sg48"), strict=True):
                values = [run["fmax_mhz"] for run in row[device]]
                ax.hlines(y, min(values), max(values), color=color, alpha=.5)
                ax.scatter(values, [y] * len(values), color=color, s=15, alpha=.55, zorder=3)
                ax.scatter([median(values)], [y], color=color, marker="D", s=36, zorder=4)
    axes[0].set_xlim(0, 270)
    axes[1].set_xlim(0, 165)
    axes[2].set_xlim(0, 70)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower left",
               bbox_to_anchor=(.045, .065), frameon=False, ncols=2)
    fig.text(.05, .045, "Timing dots show routing seeds. Diamonds mark medians. Fmax includes the common serial harness.",
             color="#42576b", fontsize=9)
    fig.savefig(output, dpi=160, facecolor=fig.get_facecolor())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    plot(json.loads(args.results.read_text()), args.output)
