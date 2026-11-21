FROM rust:1.85-bookworm AS compiler
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY src/ src/
RUN cargo build --release --locked

FROM vexim-benchmarks:latest
COPY --from=compiler /src/target/release/veximc /usr/local/bin/veximc
COPY benchmarks/serv/ /work/benchmarks/serv/
CMD ["python3", "benchmarks/serv/run.py"]
