FROM vexim-serv:latest AS compiler
FROM vexim-benchmarks:latest
RUN apt-get update && apt-get install -y --no-install-recommends nextpnr-ecp5=0.6-3build5 nextpnr-ecp5-chipdb=0.6-3build5 time && rm -rf /var/lib/apt/lists/*
COPY --from=compiler /usr/local/bin/veximc /usr/local/bin/veximc
