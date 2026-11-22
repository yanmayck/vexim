"""Generate deterministic bus traces from an independent FIFO/DMA model."""
import math
import random
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from statistics import median

from design import INPUTS, OUTPUTS

CHECKED = {"rd_addr": "rd_valid", "wr_addr": "wr_valid",
           "wr_data": "wr_valid", "done_channel": "done"}


@dataclass
class Transfer:
    src: int
    dst: int
    words: int
    accepted: int = 0

    def advance(self):
        self.src = (self.src + 4) & 65535
        self.dst = (self.dst + 4) & 65535
        self.words -= 1


def pattern(address):
    return ((address * 0x9E3779B1) ^ 0xA35E1780) & 0xFFFFFFFF


def trace(seed, stress):
    rng = random.Random(seed)
    pending = deque((ch, Transfer(
        65532 if i == 0 else 4*rng.randrange(16384),
        ch*0x4000 + i*0x180,
        rng.choice((1, 2, 3, 9, 16, 44, 80))))
        for i in range(32) for ch in range(4))
    queues = [deque() for _ in range(4)]
    latencies = [[] for _ in range(4)]
    first = last = None
    writes = blocked = stalls = 0
    peak_depth = [0]*4
    state, owner, next_channel = "idle", 0, 0
    response_at = None
    data = 0
    for cycle in range(100000):
        channel, cmd = pending[0] if pending else (0, Transfer(0, 0, 0))
        drop_probe = not pending and state == "idle" and not any(queues)
        signals = dict(rst=int(cycle == 0), cmd_valid=int(bool(pending) or drop_probe),
                       cmd_channel=channel, cmd_src=cmd.src, cmd_dst=cmd.dst, cmd_words=cmd.words,
                       rd_ready=int(not stress or rng.random() < .74),
                       rsp_valid=int(cycle == response_at), rsp_data=data if cycle == response_at else 0,
                       wr_ready=int(not stress or (cycle % 97 >= 23 and rng.random() < .81)))
        present = queues[owner][0] if queues[owner] else None
        ready = not signals["rst"] and cmd.words != 0 and len(queues[channel]) < 2
        rd, wr = state == "read", state == "write"
        fire = wr and signals["wr_ready"]
        done = fire and present.words == 1
        outputs = dict(cmd_ready=int(ready), rd_valid=int(rd), rd_addr=present.src if rd else 0,
                       wr_valid=int(wr), wr_addr=present.dst if wr else 0, wr_data=data if wr else 0,
                       done=int(done), done_channel=owner)
        yield signals, outputs
        if drop_probe:
            break

        blocked += bool(pending and not ready and not signals["rst"])
        stalls += bool((rd and not signals["rd_ready"]) or (wr and not signals["wr_ready"]))
        if state == "idle":
            candidates = ((next_channel + offset) % 4 for offset in range(4))
            selected = next((ch for ch in candidates if queues[ch]), None)
            if selected is not None:
                owner, state = selected, "read"
        elif rd and signals["rd_ready"]:
            data = pattern(present.src)
            response_at = cycle + (rng.randint(1, 12) if stress else 1)
            state = "response"
        elif signals["rsp_valid"]:
            response_at = None
            state = "write"
        elif fire:
            writes += 1
            if done:
                latencies[owner].append(cycle - present.accepted)
                queues[owner].popleft()
                last = cycle
            else:
                present.advance()
            next_channel, state = (owner+1) % 4, "idle"
        if ready:
            _, cmd = pending.popleft()
            cmd.accepted = cycle
            queues[channel].append(cmd)
            peak_depth[channel] = max(peak_depth[channel], len(queues[channel]))
            if first is None:
                first = cycle
    else:
        raise RuntimeError("Traffic model did not drain")
    if peak_depth != [2]*4 or any(len(samples) != 32 for samples in latencies):
        raise RuntimeError("Traffic did not exercise all queues and completions")
    if stress and not stalls:
        raise RuntimeError("Stress traffic did not exercise bus backpressure")
    return {"seed": seed, "stress": stress, "words": writes, "bytes": writes*4,
            "cycles": last-first+1, "command_backpressure_cycles": blocked,
            "bus_backpressure_cycles": stalls,
            "channel_latency_cycles": [
                {"channel": ch, "median": median(samples),
                 "p95": sorted(samples)[math.ceil(.95*len(samples))-1],
                 "max": max(samples)}
                for ch, samples in enumerate(latencies)]}


def write_case(path, seed, stress):
    """Write one packed stimulus/expectation record per clock cycle."""
    widths = [width for name, width in INPUTS.items() if name != "clk"] + list(OUTPUTS.values())
    digits = (sum(widths)+3)//4
    rows = []
    generator = trace(seed, stress)
    while True:
        try:
            inputs, outputs = next(generator)
        except StopIteration as completed:
            metrics = completed.value
            break
        row = 0
        for value, width in zip([*inputs.values(), *outputs.values()], widths, strict=True):
            row = (row << width) | value
        rows.append(f"{row:0{digits}x}")
    path.write_text("\n".join(rows) + "\n")
    return metrics | {"vectors": len(rows)}


def write_bench(path):
    inputs = [name for name in INPUTS if name != "clk"]
    outputs = list(OUTPUTS)
    total = sum(INPUTS.values())-1 + sum(OUTPUTS.values())
    declarations = []
    for kind, ports in (("reg", INPUTS), ("wire", OUTPUTS)):
        for name, width in ports.items():
            declarations.append(f"{kind} [{width-1}:0] {name};")
    for name, width in OUTPUTS.items():
        declarations.append(f"reg [{width-1}:0] exp_{name};")
    checks = []
    for name in outputs:
        guard = f"exp_{CHECKED[name]} && " if name in CHECKED else ""
        checks.append(f'if ({guard}{name} !== exp_{name}) '
                      f'$fatal(1, "cycle %0d {name}: got %h expected %h", '
                      f'cycle, {name}, exp_{name});')
    parts = [
        "module tb;",
        *declarations,
        f"reg [{total-1}:0] row;",
        "string vectors;",
        "integer fd, cycle, status;",
        "dma4 dut(.*);",
        "initial begin",
        "  clk=0; cycle=0;",
        '  if (!$value$plusargs("vectors=%s", vectors)) $fatal;',
        '  fd=$fopen(vectors,"r"); if (!fd) $fatal;',
        '  status=$fscanf(fd,"%h",row);',
        "  while (status==1) begin",
        "    {" + ", ".join(inputs + [f"exp_{n}" for n in outputs]) + "} = row;",
        "    #4;",
        *["    " + check for check in checks],
        "    clk=1; #5; clk=0; #1; cycle=cycle+1;",
        '    status=$fscanf(fd,"%h",row);',
        "  end",
        "  if (!$feof(fd) || cycle==0) $fatal;",
        '  $display("PASS %0d", cycle); $finish;',
        "end",
        "endmodule",
    ]
    path.write_text("\n".join(parts) + "\n")
