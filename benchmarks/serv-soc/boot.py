"""Generate a tiny RV32I boot ROM without an external cross-compiler."""
from pathlib import Path


def boot_rom(path, *, serial_overlap=False):
    program = []
    labels = {}

    def i(op, rd, f3, rs, value):
        program.append(((value & 0xfff) << 20) | (rs << 15) | (f3 << 12) | (rd << 7) | op)

    def add(rd, rs, value):
        i(0x13, rd, 0, rs, value)

    def load(rd, base, offset):
        i(0x03, rd, 2, base, offset)

    def store(rs, base, offset):
        off = offset & 0xfff
        program.append(((off >> 5) << 25) | (rs << 20) | (base << 15)
                       | (2 << 12) | ((off & 31) << 7) | 0x23)

    def label(name):
        labels[name] = len(program)

    def branch(a, b, target, unequal=False):
        program.append((a, b, target, int(unequal)))

    program.append(0x100000b7)  # lui x1, 0x10000 (MMIO base)
    add(2, 0, 0x100)            # source
    add(3, 0, 0x300)            # destination
    add(4, 0, 32)               # count
    add(5, 2, 0)                # cursor
    add(6, 4, 0)                # values 32..1
    label("fill")
    store(6, 5, 0)
    add(5, 5, 4)
    add(6, 6, -1)
    branch(6, 0, "fill", True)
    store(2, 1, 0)
    store(3, 1, 4)
    store(4, 1, 8)
    add(7, 0, 1)
    store(7, 1, 12)
    label("dma_wait")
    load(8, 1, 12)
    branch(8, 0, "dma_wait", True)
    label("verify")
    load(8, 3, 0)
    branch(8, 4, "fail", True)
    add(3, 3, 4)
    add(4, 4, -1)
    branch(4, 0, "verify", True)
    add(8, 0, 0x56)
    if serial_overlap:
        add(10, 0, 0xa6)
        store(8, 1, 16)
        store(10, 1, 36)
        add(8, 10, 0)
    else:
        store(8, 1, 16)
        add(8, 0, 0xa6)
        store(8, 1, 36)
    label("spi_wait")
    load(9, 1, 40)
    branch(9, 0, "spi_wait", True)
    load(9, 1, 44)
    branch(8, 9, "fail", True)
    load(8, 1, 24)
    load(9, 1, 24)
    branch(8, 9, "fail")
    add(8, 0, 0x5a)
    store(8, 1, 48)
    program.append(0x6f)
    label("fail")
    add(8, 0, -1)
    store(8, 1, 48)
    program.append(0x6f)

    for position, word in enumerate(program):
        if isinstance(word, tuple):
            a, b, target, f3 = word
            delta = ((labels[target] - position) * 4) & 0x1fff
            program[position] = ((delta >> 12) << 31) | (((delta >> 5) & 63) << 25) | (
                b << 20) | (a << 15) | (f3 << 12) | (((delta >> 1) & 15) << 8) | (
                ((delta >> 11) & 1) << 7) | 0x63
    if len(program) > 64:
        raise ValueError("program exceeds ROM capacity")
    path.write_text("".join(f"{word:08x}\n" for word in program + [0x6f] * (64 - len(program))))


if __name__ == "__main__":
    boot_rom(Path("boot.hex"))
