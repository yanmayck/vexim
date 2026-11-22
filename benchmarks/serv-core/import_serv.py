"""Import the pinned SERV profile's flattened RTLIL as synthesizable Vexim."""
import json
import re
import sys
from pathlib import Path


def translate(module, *, name="serv_rf_vex", source="the pinned ISC-licensed SERV RTL"):
    lines = [f"# Generated from {source}.", f"module {name}"]
    sources = {"0": "zero", "1": "one", "x": "zero", "z": "zero"}
    initialized = [name for name, net in module["netnames"].items()
                   if "init" in net["attributes"]]
    if initialized:
        raise ValueError(f"unsupported initial values: {initialized}")
    for name, port in module["ports"].items():
        lines.append(f'{port["direction"]} {name} u{len(port["bits"])}')
        if port["direction"] == "input":
            for i, bit in enumerate(port["bits"]):
                sources[bit] = name if len(port["bits"]) == 1 else f"n{bit}"
                if len(port["bits"]) > 1:
                    lines += [f"wire n{bit} u1", f"comb n{bit} slice {name} {i} {i}"]
    lines += ["wire zero u1", "comb zero const 0", "wire one u1", "comb one const 1"]

    def bit(value):
        return sources.get(value, f"n{value}")

    def comb(name, width, expression):
        lines.extend([f"wire {name} u{width}", f"comb {name} {expression}"])
        return name

    def pack(bits, name):
        value = bit(bits[-1])
        for width, item in enumerate(reversed(bits[:-1]), 2):
            value = comb(f"{name}_{width}", width, f"concat {value} {bit(item)}")
        return value

    for i, cell in enumerate(module["cells"].values()):
        kind, ports = cell["type"], cell["connections"]
        args = {key: bit(value[0]) for key, value in ports.items()}
        if kind == "$mem_v2":
            p = {key: int(value, 2) for key, value in cell["parameters"].items()
                 if set(value) <= {"0", "1"}}
            expected = {"WR_PORTS": 1, "RD_CLK_ENABLE": 0,
                        "WR_CLK_ENABLE": 1, "WR_CLK_POLARITY": 1, "OFFSET": 0,
                        "RD_TRANSPARENCY_MASK": 0, "RD_COLLISION_X_MASK": 0}
            reads = p["RD_PORTS"]
            if (any(p.get(key) != value for key, value in expected.items()) or
                    set(cell["parameters"]["INIT"]) != {"x"} or
                    ports["RD_EN"] != ["1"] * reads or ports["RD_ARST"] != ["0"] * reads or
                    ports["RD_SRST"] != ["0"] * reads or len(set(ports["WR_EN"])) != 1):
                raise ValueError("unsupported memory profile: expected asynchronous reads and one synchronous write")
            name = f"memory{i}"
            width, depth = p["WIDTH"], p["SIZE"]
            lines.append(f"mem {name} u{width} {depth}")
            if reads == 1:
                read_addresses = [pack(ports["RD_ADDR"], f"{name}_rd")]
            else:
                addr_bits = p["ABITS"]
                read_addresses = [
                    pack(ports["RD_ADDR"][port * addr_bits:(port + 1) * addr_bits],
                         f"{name}_{port}_rd")
                    for port in range(reads)
                ]
            wr_addr = pack(ports["WR_ADDR"], f"{name}_wr")
            data = pack(ports["WR_DATA"], f"{name}_data")
            for port, rd_addr in enumerate(read_addresses):
                tag = name if reads == 1 else f"{name}_{port}"
                read = comb(f"{tag}_data_out", width, f"read {name} {rd_addr}")
                start = port * width
                for index, output in enumerate(ports["RD_DATA"][start:start + width]):
                    comb(bit(output), 1, f"slice {read} {index} {index}")
            lines.append(f"write {name} {args['WR_CLK']} {args['WR_EN']} {wr_addr} {data}")
        elif kind == "$mux":
            width = len(ports["Y"])
            if not 1 <= width <= 64 or len(ports["S"]) != 1:
                raise ValueError(f"unsupported mux width {width}")
            a = pack(ports["A"], f"mux{i}_a")
            b = pack(ports["B"], f"mux{i}_b")
            result = comb(f"mux{i}_result", width, f"mux {args['S']} {b} {a}")
            for index, output in enumerate(ports["Y"]):
                comb(bit(output), 1, f"slice {result} {index} {index}")
        elif kind in {"$add", "$sub", "$lt", "$le", "$gt", "$ge"}:
            params = cell["parameters"]
            result_width = int(params["Y_WIDTH"], 2)
            compare = kind in {"$lt", "$le", "$gt", "$ge"}
            width = max(len(ports["A"]), len(ports["B"])) if compare else result_width
            if not 1 <= width <= 64:
                raise ValueError(f"{kind} result width {width} is outside Vexim's range")
            signed = all(int(params[f"{name}_SIGNED"], 2) for name in ("A", "B"))
            operands = []
            for name in ("A", "B"):
                bits = ports[name][:width]
                value = pack(bits, f"arith{i}_{name}")
                if len(bits) < width:
                    if signed:
                        value = pack(bits + [bits[-1]] * (width - len(bits)), f"arith{i}_{name}_sign")
                    else:
                        value = comb(f"arith{i}_{name}_wide", width, f"zext {value}")
                operands.append(value)
            op = kind[1:]
            if compare:
                op = f"s{op}" if signed else op
            result = comb(f"arith{i}_result", 1 if compare else width, f"{op} {' '.join(operands)}")
            for index, output in enumerate(ports["Y"]):
                if compare:
                    comb(bit(output), 1, f"copy {result if index == 0 else 'zero'}")
                else:
                    comb(bit(output), 1, f"slice {result} {index} {index}")
        elif kind in {"$_AND_", "$_OR_", "$_XOR_", "$_NOT_", "$_MUX_"}:
            if kind == "$_MUX_":
                expression = f"mux {args['S']} {args['B']} {args['A']}"
            elif kind == "$_NOT_":
                expression = f"xor {args['A']} one"
            else:
                expression = f"{kind[2:-1].lower()} {args['A']} {args['B']}"
            comb(args["Y"], 1, expression)
        else:
            flop = re.fullmatch(r"\$_(DFF|DFFE|SDFF|SDFFE|SDFFCE)_(P)([PN]?[01]?)([PN]?)_", kind)
            if not flop:
                raise ValueError(f"unsupported cell {kind}")
            form, _, reset_mode, enable_mode = flop.groups()
            data, q = args["D"], args["Q"]
            has_reset = form.startswith("S")
            if form == "DFFE":
                enable_mode = reset_mode
            if "E" in args:
                en = args["E"]
                if enable_mode == "N":
                    en = comb(f"ce{i}", 1, f"xor {en} one")
            if has_reset:
                reset = args["R"]
                if reset_mode[0] == "N":
                    reset = comb(f"rst{i}", 1, f"xor {reset} one")
                reset_value = "one" if reset_mode[1] == "1" else "zero"
                if form == "SDFFCE":
                    data = comb(f"rd{i}", 1, f"mux {reset} {reset_value} {data}")
            if "E" in args:
                data = comb(f"ed{i}", 1, f"mux {en} {data} {q}")
            if has_reset and form != "SDFFCE":
                data = comb(f"sd{i}", 1, f"mux {reset} {reset_value} {data}")
            lines.append(f"wire {q} u1")
            lines.append(f"sync {q} {args['C']} no_reset {data}")
    for name, port in module["ports"].items():
        if port["direction"] == "output":
            value = pack(port["bits"], f"out_{name}")
            lines.append(f"comb {name} copy {value}")
    # The original MINI reset is expressed in the data muxes. A wrapper ties this
    # additional compiler-required reset port low to preserve the external interface.
    lines.insert(2, "input no_reset u1")
    return "\n".join(lines + ["end", ""])


if __name__ == "__main__":
    source, target = map(Path, sys.argv[1:])
    module = json.loads(source.read_text())["modules"]["serv_rf_top"]
    target.write_text(translate(module))
