#include <stdint.h>
int main(void) {
    uint32_t code;
#ifdef PROBE_UNSUPPORTED
    const uint32_t destination = 0xa0020000u;
    const uint32_t expected_code = 1u; /* Unsupported near-miss: no memory traffic. */
#elif defined(PROBE_MMIO_TIMEOUT)
    const uint32_t destination = 0xa0020000u;
    const uint32_t expected_code = 5u; /* One real empty-ROW_STATUS poll. */
#else
    const uint32_t destination = 0xa0020004u; /* Intentionally misaligned. */
    const uint32_t expected_code = 2u;
#endif
    const uint32_t control = 1u << 5;
    __asm__ volatile (
#ifdef PROBE_UNSUPPORTED
        ".insn r 0x7b, 7, 0x00, %0, %1, %2\n\t"
#else
        ".insn r 0x7b, 7, 0x20, %0, %1, %2\n\t"
#endif
        "fence iorw, iorw"
        : "=r"(code) : "r"(destination), "r"(control) : "memory");
    return code == expected_code ? 1 : 2;
}
