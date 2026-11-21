# Operator sharing on the iCE40 UP5K

The same Vexim state machine chooses between two 32-bit increments.
The default compiler computes both increments and then selects a result.
With `--opt-area`, it selects an operand first and emits one increment.
Yosys proves equivalence for the two modules before FPGA synthesis.

| Metric | Default | With `--opt-area` |
|---|---:|---:|
| Adders before FPGA mapping | 2 | 1 |
| UP5K LUT4s | 94 | 64 |
| Carry cells | 60 | 30 |
| Flip-flops | 1 | 1 |

This is a synthesis result without placement or timing measurement.
The existing SoC DMA already shares its incrementer explicitly. Its
generated SystemVerilog is byte-identical with this pass enabled.

## Reproduce

From the Vexim checkout in PowerShell:

~~~powershell
docker build -f benchmarks/Dockerfile -t vexim-benchmarks .
docker build -f benchmarks/serv/Dockerfile -t vexim-serv .
New-Item -ItemType Directory -Force build/operator-sharing | Out-Null
docker run --rm --network none --mount "type=bind,source=$((Get-Location).Path)/benchmarks/operator-sharing,target=/case,readonly" --mount "type=bind,source=$((Get-Location).Path)/build/operator-sharing,target=/output" vexim-serv python3 /case/run.py
~~~
