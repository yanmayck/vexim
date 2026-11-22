"""Generate the Vexim DMA with four depth-two descriptor queues."""
INPUTS = dict(clk=1, rst=1, cmd_valid=1, cmd_channel=2, cmd_src=16, cmd_dst=16,
              cmd_words=8, rd_ready=1, rsp_valid=1, rsp_data=32, wr_ready=1)
OUTPUTS = dict(cmd_ready=1, rd_valid=1, rd_addr=16, wr_valid=1, wr_addr=16,
               wr_data=32, done=1, done_channel=2)


def native(onehot=False):
    lines = ["module dma4"]
    for direction, ports in (("input", INPUTS), ("output", OUTPUTS)):
        lines.extend(f"{direction} {name} u{width}" for name, width in ports.items())

    def wire(name, width, expr):
        if name not in OUTPUTS:
            lines.append(f"wire {name} u{width}")
        lines.append(f"comb {name} {expr}")
        return name

    def reg(name, width, expr):
        if name not in OUTPUTS:
            lines.append(f"wire {name} u{width}")
        data = wire(f"{name}_d", width, expr)
        lines.append(f"sync {name} clk rst {data}")

    def select(name, width, selector, choices):
        # Four choices addressed by an unsigned two-bit index.
        low = wire(f"{name}_low", width, f"mux {selector}_lo {choices[1]} {choices[0]}")
        high = wire(f"{name}_high", width, f"mux {selector}_lo {choices[3]} {choices[2]}")
        return wire(name, width, f"mux {selector}_hi {high} {low}")

    for name, width, value in (("zero2", 2, 0), ("one2", 2, 1), ("two2", 2, 2),
                               ("three2", 2, 3), ("zero8", 8, 0), ("one8", 8, 1),
                               ("four16", 16, 4)):
        wire(name, width, f"const {value}")
    for name in ("cmd_channel", "owner"):
        wire(f"{name}_lo", 1, f"slice {name} 0 0")
        wire(f"{name}_hi", 1, f"slice {name} 1 1")

    wire("not_reset", 1, "eq rst zero1")
    wire("zero1", 1, "const 0")
    wire("valid_length", 1, "ne cmd_words zero8")
    channels = ["zero2", "one2", "two2", "three2"]
    for index in range(4):
        wire(f"queued{index}", 1, f"ne count{index} zero2")
        wire(f"full{index}", 1, f"eq count{index} two2")
        wire(f"candidate{index}", 2, f"add next_channel {channels[index]}")
        wire(f"candidate{index}_lo", 1, f"slice candidate{index} 0 0")
        wire(f"candidate{index}_hi", 1, f"slice candidate{index} 1 1")
        select(f"eligible{index}", 1, f"candidate{index}", [f"queued{i}" for i in range(4)])
    for index in range(2, -1, -1):
        default = f"pick{index+1}" if index < 2 else "candidate3"
        wire(f"pick{index}", 2, f"mux eligible{index} candidate{index} {default}")
    wire("queue_lo", 1, "or queued0 queued1")
    wire("queue_hi", 1, "or queued2 queued3")
    wire("found", 1, "or queue_lo queue_hi")
    select("full", 1, "cmd_channel", [f"full{i}" for i in range(4)])
    wire("space", 1, "eq full zero1")
    wire("accept_length", 1, "and valid_length space")
    wire("cmd_ready", 1, "and not_reset accept_length")
    wire("push", 1, "and cmd_valid cmd_ready")

    for state, value in (("idle", "zero2"), ("reading", "one2"),
                         ("response", "two2"), ("writing", "three2")):
        wire(state, 1, f"eq state {value}")
    wire("select_owner", 1, "and idle found")
    wire("rd_valid", 1, "and not_reset reading")
    wire("read_fire", 1, "and rd_valid rd_ready")
    wire("response_fire", 1, "and response rsp_valid")
    wire("wr_valid", 1, "and not_reset writing")
    wire("write_fire", 1, "and wr_valid wr_ready")
    wire("to_read", 2, "mux select_owner one2 state")
    wire("to_response", 2, "mux read_fire two2 to_read")
    wire("to_write", 2, "mux response_fire three2 to_response")
    reg("state", 2, "mux write_fire zero2 to_write")
    reg("owner", 2, "mux select_owner pick0 owner")
    wire("advance", 2, "add owner one2")
    reg("next_channel", 2, "mux write_fire advance next_channel")
    reg("wr_data", 32, "mux response_fire rsp_data wr_data")
    wire("done_channel", 2, "copy owner")

    fields = (("src", 16, "rd_addr", "next_src"), ("dst", 16, "wr_addr", "next_dst"),
              ("words", 8, "active_words", "remaining"))
    for field, width, output, _ in fields:
        for index in range(4):
            wire(f"{field}_head{index}", width,
                 f"mux head{index} {field}{index}_1 {field}{index}_0")
        if onehot:
            zero = wire(f"{field}_zero", width, "const 0")
            for index in range(4):
                wire(f"{field}_masked{index}", width,
                     f"mux owner_is{index} {field}_head{index} {zero}")
            low = wire(f"{field}_low", width, f"or {field}_masked0 {field}_masked1")
            high = wire(f"{field}_high", width, f"or {field}_masked2 {field}_masked3")
            wire(output, width, f"or {low} {high}")
        else:
            select(output, width, "owner", [f"{field}_head{i}" for i in range(4)])
    wire("next_src", 16, "add rd_addr four16")
    wire("next_dst", 16, "add wr_addr four16")
    wire("remaining", 8, "sub active_words one8")
    wire("last_word", 1, "eq active_words one8")
    wire("more_words", 1, "eq last_word zero1")
    wire("done", 1, "and write_fire last_word")

    for index, channel in enumerate(channels):
        wire(f"cmd_to{index}", 1, f"eq cmd_channel {channel}")
        enqueue = wire(f"enqueue{index}", 1, f"and push cmd_to{index}")
        wire(f"owner_is{index}", 1, f"eq owner {channel}")
        active = wire(f"active{index}", 1, f"and write_fire owner_is{index}")
        pop = wire(f"pop{index}", 1, f"and {active} last_word")
        update = wire(f"update{index}", 1, f"and {active} more_words")
        wire(f"grow{index}", 2, f"zext {enqueue}")
        wire(f"shrink{index}", 2, f"zext {pop}")
        wire(f"increased{index}", 2, f"add count{index} grow{index}")
        reg(f"count{index}", 2, f"sub increased{index} shrink{index}")
        reg(f"head{index}", 1, f"xor head{index} {pop}")
        reg(f"tail{index}", 1, f"xor tail{index} {enqueue}")
        for slot in range(2):
            bit = "one1" if slot else "zero1"
            tail = wire(f"tail{index}_{slot}", 1, f"eq tail{index} {bit}")
            head = wire(f"head{index}_{slot}", 1, f"eq head{index} {bit}")
            fill = wire(f"fill{index}_{slot}", 1, f"and {enqueue} {tail}")
            step = wire(f"step{index}_{slot}", 1, f"and {update} {head}")
            for field, width, _, next_value in fields:
                name = f"{field}{index}_{slot}"
                changed = wire(f"changed_{name}", width, f"mux {step} {next_value} {name}")
                reg(name, width, f"mux {fill} cmd_{field} {changed}")
    wire("one1", 1, "const 1")
    return "\n".join(lines + ["end", ""])
