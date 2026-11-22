"""Traffic oracle for a packet switch with independent input/destination FIFOs."""
from collections import deque
from math import ceil
from random import Random

INPUTS = {"in_valid": 1, "in_dest": 4, "in_data": 32, "in_last": 1, "out_ready": 1}
OUTPUTS = {"in_ready": 1, "out_valid": 1, "out_data": 32, "out_last": 1}
DEPTH = 64
BLOCKED_UNTIL = 320


def ports(group, n):
    return {f"{name}{index}": width for name, width in group.items() for index in range(n)}


def declaration(name, width):
    return f"[{width-1}:0] {name}" if width != 1 else name


def reference_wrapper(n):
    signals = [f"{kind} wire {declaration(name, width)}"
               for kind, group in (("input", INPUTS), ("output", OUTPUTS))
               for name, width in ports(group, n).items()]
    links = [".clk(clk)", ".rst(rst)"]
    for name in INPUTS | OUTPUTS:
        bundle = ", ".join(f"{name}{index}" for index in reversed(range(n)))
        links.append(f".{name}({{{bundle}}})")
    return ("module packet_switch(input wire clk, rst, " + ", ".join(signals) + ");\n"
            + f"packet_switch_ref #(.PORTS({n})) dut(" + ", ".join(links) + ");\nendmodule\n")


def vectors(n, scenario):
    random = Random(1701)
    streams = [deque() for _ in range(n)]
    for ingress, stream in enumerate(streams):
        for packet in range(96):
            dest = (ingress if scenario == "blocked" else
                    0 if scenario == "contended" else random.randrange(n))
            length = random.randrange(1, 9)
            for offset in range(length):
                word = (ingress << 24) | (packet << 8) | offset
                stream.append((dest, word, int(offset == length-1)))

    queues = [[deque() for _ in range(n)] for _ in range(n)]
    locks = [None]*n
    cursors = [0]*n
    beats = [0]*n
    latencies = [[] for _ in range(n)]
    ingress_accept = {}
    full_hits = 0
    free_transfers = [0]*n
    first, last = None, None
    for cycle in range(20000):
        reset = cycle == 0
        candidates = []
        for out in range(n):
            order = ([locks[out]] if locks[out] is not None else
                     [(cursors[out]+offset) % n for offset in range(n)])
            winner = next((src for src in order if queues[src][out]), None)
            candidates.append(winner)

        ins = {f"rst": int(reset)}
        outs = {}
        pushes, pops = [], []
        for index in range(n):
            dest, word, end = streams[index][0] if streams[index] else (15, 0, 0)
            ins[f"in_valid{index}"] = int(bool(streams[index]))
            ins[f"in_dest{index}"] = dest
            ins[f"in_data{index}"] = word
            ins[f"in_last{index}"] = end
            space = dest < n and len(queues[index][dest]) < DEPTH
            outs[f"in_ready{index}"] = int(space and not reset)
            if not reset and streams[index]:
                if space:
                    pushes.append(index)
                else:
                    full_hits += 1

            ready = (not (index == 0 and cycle < BLOCKED_UNTIL) if scenario == "blocked"
                     else random.random() < .80 if scenario == "mixed" else True)
            ins[f"out_ready{index}"] = int(ready)
            winner = candidates[index]
            valid = winner is not None and not reset
            out_word, out_end = queues[winner][index][0] if valid else (0, 0)
            outs[f"out_valid{index}"] = int(valid)
            outs[f"out_data{index}"] = out_word
            outs[f"out_last{index}"] = out_end
            if valid:
                locks[index] = winner
                if ready:
                    pops.append((winner, index))
                    if out_end:
                        locks[index] = None
                        cursors[index] = (winner+1) % n

        yield ins, outs
        for index in pushes:
            dest, word, end = streams[index].popleft()
            if word & 255 == 0:
                ingress_accept[word >> 8] = cycle
            queues[index][dest].append((word, end))
            if first is None:
                first = cycle
        for src, dest in pops:
            word, end = queues[src][dest].popleft()
            beats[dest] += 1
            last = cycle
            if end:
                latencies[dest].append(cycle-ingress_accept.pop(word >> 8))
            if 8 <= cycle < BLOCKED_UNTIL:
                free_transfers[dest] += 1
        if cycle and not any(streams) and not any(queue for bank in queues for queue in bank):
            break
    else:
        raise RuntimeError("switch traffic did not drain")
    if ingress_accept or sum(map(len, latencies)) != n*96:
        raise RuntimeError("missing packet completions")
    if scenario == "blocked" and (not full_hits or free_transfers != [0]+[BLOCKED_UNTIL-8]*(n-1)):
        raise RuntimeError("blocked-output coverage failed")
    return {"cycles": last-first+1, "full_hits": full_hits, "packets": n*96,
            "beats": beats, "free_window_beats": free_transfers,
            "p99_cycles": [sorted(samples)[ceil(.99*len(samples))-1] if samples else None
                           for samples in latencies]}


def make_test(n, output):
    inputs = {"rst": 1} | ports(INPUTS, n)
    outputs = ports(OUTPUTS, n)
    bits = sum(inputs.values()) + sum(outputs.values())
    assignments = ", ".join([*inputs, *(f"exp_{name}" for name in outputs)])
    lines = ["module tb;", "reg clk=0;",
             *(f"reg {declaration(name, width)};" for name, width in inputs.items()),
             *(f"wire {declaration(name, width)};" for name, width in outputs.items()),
             *(f"reg {declaration('exp_'+name, width)};" for name, width in outputs.items()),
             f"reg [{bits-1}:0] row;", "packet_switch dut(.*);",
             "integer fd, status, cycle;", "string file;",
             "initial begin", "  cycle=0;",
             '  if (!$value$plusargs("vectors=%s",file)) $fatal;',
             '  fd=$fopen(file,"r"); if (!fd) $fatal;',
             '  status=$fscanf(fd,"%h",row);',
             "  while (status==1) begin", f"    {{{assignments}}}=row; #4;"]
    for name in outputs:
        guard = ""
        for prefix in ("out_data", "out_last"):
            if name.startswith(prefix):
                guard = f"exp_out_valid{name[len(prefix):]} && "
        lines.append(f'    if ({guard}({name} !== exp_{name})) '
                     f'$fatal(1,"cycle %0d {name} got %h expected %h",cycle,{name},exp_{name});')
    lines += ["    clk=1; #5; clk=0; #1; cycle=cycle+1;",
              '    status=$fscanf(fd,"%h",row);', "  end",
              "  if (!$feof(fd) || cycle==0) $fatal;",
              '  $display("PASS %0d",cycle); $finish;', "end", "endmodule"]
    (output / "tb.sv").write_text("\n".join(lines)+"\n")
    cases = {}
    for case in ("mixed", "contended", "blocked"):
        source = vectors(n, case)
        rows = []
        while True:
            try:
                inp, out = next(source)
            except StopIteration as finished:
                cases[case] = finished.value | {"vectors": len(rows)}
                break
            row = 0
            for name, width in (inputs | outputs).items():
                row = (row << width) | (inp | out)[name]
            rows.append(f"{row:0{(bits+3)//4}x}")
        (output / f"{case}.hex").write_text("\n".join(rows)+"\n")
    return cases
