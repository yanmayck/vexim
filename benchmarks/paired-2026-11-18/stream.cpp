#include "Vmem_controller.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>

constexpr std::uint64_t bytes = 1ULL << 30;
constexpr std::uint64_t base = 0x8040000000ULL;
constexpr unsigned max_beats = 255;

static std::uint64_t pattern(std::uint64_t addr) {
    return (addr + 0x9e3779b97f4a7c15ULL) * 0xbf58476d1ce4e5b9ULL;
}

static void require(bool valid, const char* message, std::uint64_t addr) {
    if (!valid) {
        std::fprintf(stderr, "%s at 0x%llx\n", message,
                     static_cast<unsigned long long>(addr));
        std::exit(1);
    }
}

static void tick(Vmem_controller& dut) {
    dut.clk = 1;
    dut.eval();
    dut.clk = 0;
    dut.eval();
}

static void transfer(Vmem_controller& dut, bool writing, std::uint64_t addr,
                     unsigned count, std::array<std::uint64_t, max_beats>& storage) {
    unsigned host = 0, memory = 0, burst = 0;
    dut.cmd_valid = 1;
    dut.cmd_write = writing;
    dut.cmd_addr = addr;
    dut.cmd_beats = count;
    dut.eval();
    require(dut.cmd_ready, "host not ready", addr);
    tick(dut);
    dut.cmd_valid = 0;

    for (unsigned cycle = 0; cycle < 4096; ++cycle) {
        const auto current = addr + 8ULL * memory;
        dut.w_valid = writing && host < count;
        dut.w_data = pattern(addr + 8ULL * host);
        dut.mem_r_valid = !writing && burst != 0;
        dut.mem_r_data = memory < count ? storage[memory] : 0;
        dut.eval();
        const bool descriptor = dut.mem_valid && dut.mem_ready;
        const bool host_beat = writing ? dut.w_valid && dut.w_ready : dut.r_valid && dut.r_ready;
        const bool memory_beat = writing ? dut.mem_w_valid && dut.mem_w_ready :
                                          dut.mem_r_valid && dut.mem_r_ready;
        if (descriptor) {
            const auto expected = std::min({16U, count - memory,
                                            (4096U - unsigned(current & 4095U)) / 8U});
            require(burst == 0 && !memory_beat && expected != 0 &&
                    dut.mem_addr == current && dut.mem_beats == expected &&
                    dut.mem_write == writing, "bad descriptor", current);
            burst = expected;
        }
        if (memory_beat) {
            require(burst != 0 && memory < count, "unexpected memory beat", current);
            if (writing) {
                require(dut.mem_w_strb == 255 && dut.mem_w_data == pattern(current),
                        "corrupt write", current);
                storage[memory] = dut.mem_w_data;
            }
            --burst;
            ++memory;
        }
        if (host_beat) {
            require(host < count, "extra host beat", addr);
            if (!writing) {
                const auto expected_addr = addr + 8ULL * host;
                require(dut.r_data == pattern(expected_addr) &&
                        dut.r_last == (host + 1 == count), "corrupt read", expected_addr);
            }
            ++host;
        }
        const bool complete = host == count && memory == count;
        require(bool(dut.done) == complete, "bad completion", addr);
        tick(dut);
        if (complete) return;
    }
    require(false, "watchdog expired", addr);
}

int main() {
    Vmem_controller dut;
    dut.clk = 0;
    dut.rst = 1;
    dut.cmd_valid = 0;
    dut.w_valid = 0;
    dut.mem_r_valid = 0;
    dut.mem_ready = 1;
    dut.mem_w_ready = 1;
    dut.r_ready = 1;
    dut.w_strb = 255;
    dut.eval();
    tick(dut);
    dut.rst = 0;
    std::array<std::uint64_t, max_beats> storage{};
    for (std::uint64_t offset = 0; offset < bytes;) {
        const auto count = static_cast<unsigned>(std::min<std::uint64_t>(max_beats,
                                                                        (bytes - offset) / 8));
        transfer(dut, true, base + offset, count, storage);
        transfer(dut, false, base + offset, count, storage);
        offset += 8ULL * count;
    }
    std::puts("PASS: 1073741824 bytes written and read back, each beat checked");
}
