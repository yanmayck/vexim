# Cross-module sharing on iCE40 UP5K

The project command accepts a mixed Vexim and SystemVerilog design.
`--share` flattens the instantiated hierarchy and runs Yosys
SAT-based resource sharing on the resulting netlist. Sharing can merge
compatible arithmetic operations when their controls prove that the
results are never needed at the same time. The original selector
state and cycle schedule are preserved.

| Fixture | Default export | Shared export | Result after UP5K synthesis |
|---|---:|---:|---|
| Two 32-bit Vexim incrementer instances | 2 adders | 1 adder | 95 → 65 LUT4s, 60 → 30 carry cells, 1 FF |
| Two 8×8 multiply instances | 2 multipliers | 1 multiplier | 18 LUT4s and 1 DSP in both builds |
| Two simultaneously visible products | 2 multipliers | 2 multipliers | Negative control at export |

The incrementer output and phase register passed temporal induction
from the common reset state. The multiply fixture checked all 65,536
operand pairs in each phase in Icarus Verilog. Standard UP5K synthesis
already shares the multipliers in this case. The numbers are synthesized
resources without placement or frequency measurement.

`--share` is opt-in. It does not merge arbitrary state machines,
share operations that must run concurrently, or reschedule AES
rounds. Hierarchy flattening permits sharing across former module
boundaries. It can lose source-level hierarchy names and changes the
area/timing trade-off based on the resulting muxes.

## Reproduce

Build the benchmark image and run the fixtures in PowerShell:

~~~powershell
docker build -f benchmarks/Dockerfile -t vexim-benchmarks .
docker build -f benchmarks/serv/Dockerfile -t vexim-serv .
New-Item -ItemType Directory -Force build/global-sharing | Out-Null
docker run --rm --network none --mount "type=bind,source=$((Get-Location).Path)/benchmarks/global-sharing,target=/case,readonly" --mount "type=bind,source=$((Get-Location).Path)/build/global-sharing,target=/output" vexim-serv python3 /case/run.py
~~~

To run just the project pass inside the tooling image:

~~~sh
veximc design increment_selector inc_lane.vxm increment_selector.sv -o shared.sv --share
~~~
