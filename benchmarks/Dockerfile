FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends python3 yosys=0.33-5build2 iverilog=12.0-2build2 verilator=5.020-1 && rm -rf /var/lib/apt/lists/*
WORKDIR /work
COPY benchmarks/ /work/benchmarks/
CMD ["python3", "benchmarks/run.py"]
