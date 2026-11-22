# Whole-design dead port and register pruning

A SystemVerilog top connects to a Vexim child IP. The child exports an
8-bit result and a 16-bit diagnostic, with an independent register
feeding each output. The top connects only the result.

`veximc design` stages self-contained SystemVerilog and Vexim sources,
elaborates the selected top, and flattens the instances with Yosys.
`--prune` removes unused cells and wires from that connected design.
Declared top-level ports are preserved. The flow uses actual RTL
connections and does not infer whether software will access a mapped
register. External include files and memory initialization files must
be embedded or resolved before sending RTL through this staged frontend.

| Before FPGA mapping | Default | With `--prune` |
|---|---:|---:|
| Register bits | 24 | 8 |
| Adders | 1 | 0 |
| Top-level port names, directions and widths | Identical | Identical |

Yosys proved sequential equivalence of the resulting top modules.
These counts are measured before FPGA synthesis. Downstream synthesis
can already remove disconnected logic.

## Reproduce

From the Vexim checkout in PowerShell:

~~~powershell
docker build -f benchmarks/Dockerfile -t vexim-benchmarks .
docker build -f benchmarks/serv/Dockerfile -t vexim-serv .
New-Item -ItemType Directory -Force build/dead-port-pruning | Out-Null
docker run --rm --network none --mount "type=bind,source=$((Get-Location).Path)/benchmarks/dead-port-pruning,target=/case,readonly" --mount "type=bind,source=$((Get-Location).Path)/build/dead-port-pruning,target=/output" vexim-serv python3 /case/run.py
~~~

Outside Docker, on a host with Yosys in the path:

~~~sh
veximc design prune_demo benchmarks/dead-port-pruning/top.sv benchmarks/dead-port-pruning/ip_leaf.vxm -o pruned.sv --prune
~~~
