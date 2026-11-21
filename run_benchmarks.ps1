$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    docker build -f benchmarks/Dockerfile -t vexim-benchmarks .
    if ($LASTEXITCODE -ne 0) { throw 'Benchmark image build failed' }
    New-Item -Force -ItemType Directory build/benchmarks | Out-Null
    docker run --rm --network none --mount "type=bind,source=$((Get-Location).Path)/build/benchmarks,target=/output" vexim-benchmarks
    if ($LASTEXITCODE -ne 0) { throw 'Benchmark verification failed' }
} finally {
    Pop-Location
}
