#!/bin/sh
set -eu
cd "$(dirname "$0")"
docker build -f benchmarks/Dockerfile -t vexim-benchmarks .
mkdir -p build/benchmarks
docker run --rm --network none --mount "type=bind,source=$(pwd)/build/benchmarks,target=/output" vexim-benchmarks
