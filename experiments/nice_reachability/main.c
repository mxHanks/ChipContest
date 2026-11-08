/* Independent P0 probe: the existing NICE demo transfers three words. */
#include <stdint.h>

static inline void nice_lbuf(const volatile uint32_t *p) {
    __asm__ volatile (
        ".insn r 0x7b, 2, 1, x0, %0, x0\n\t"
        "fence iorw, iorw"
        :: "r"(p) : "memory");
}

static inline void nice_sbuf(volatile uint32_t *p) {
    __asm__ volatile (
        ".insn r 0x7b, 2, 2, x0, %0, x0\n\t"
        "fence iorw, iorw"
        :: "r"(p) : "memory");
}

int main(void) {
    volatile uint32_t *src = (volatile uint32_t *)0xa0040000u;
    volatile uint32_t *dst0 = (volatile uint32_t *)0xa0040040u;
    volatile uint32_t *dst1 = (volatile uint32_t *)0xa0040080u;
    volatile uint32_t *mmio = (volatile uint32_t *)0x10042000u;
    const uint32_t pattern[3] = {3u, 0x0000a55au, 5u};

    if (mmio[0] != 0xacce2030u || (mmio[3] & 1u)) return 2;
    for (unsigned i = 0; i < 3; ++i) {
        src[i] = pattern[i];
        dst0[i] = 0xdeadbeefu;
        dst1[i] = 0xdeadbeefu;
    }
    __asm__ volatile ("fence iorw, iorw" ::: "memory");

    nice_lbuf(src);
    nice_sbuf(dst0);
    for (unsigned i = 0; i < 3; ++i)
        if (dst0[i] != pattern[i]) return 3;

    /* Only X_ADDR, X_DATA and W_BANK: never CTRL, STATUS or POP writes. */
    nice_sbuf(mmio + 5);
    if (mmio[5] != 3u || mmio[6] != 0xa55au || mmio[7] != 5u) return 4;
    nice_lbuf(mmio + 5);
    nice_sbuf(dst1);
    for (unsigned i = 0; i < 3; ++i)
        if (dst1[i] != pattern[i]) return 5;
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    return 1;
}
