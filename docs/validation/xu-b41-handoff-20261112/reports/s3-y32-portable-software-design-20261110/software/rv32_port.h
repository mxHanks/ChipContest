#ifndef FFN_RV32_PORT_H
#define FFN_RV32_PORT_H

#include <stdint.h>

/* The selected hardware profile must define these addresses. The reference
 * profile is historical Group-y, not an asserted 64-PE register map. */
static inline void ffn_fence(void)
{
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
}

static inline uint32_t ffn_read_cycle(void)
{
    uint32_t value;
    __asm__ volatile ("csrr %0, mcycle" : "=r"(value) :: "memory");
    return value;
}

static inline void ffn_report_error(void)
{
    const uint32_t value = *(volatile uint32_t *)FFN_ERROR_ADDRESS;
    *(volatile uint32_t *)FFN_ERROR_MAILBOX = value;
    ffn_fence();
}

static inline __attribute__((always_inline)) void ffn_pause(uint32_t nops)
{
    /* Constant fixed/phase configurations let GCC remove unused cases. A
     * backoff configuration keeps multiple blocks; code-size cost is reported. */
#define FFN_NOP_CASE(N) case N: __asm__ volatile (".rept " #N "\n\tnop\n\t.endr" ::: "memory"); break
    switch (nops) {
    case 0: break;
#if FFN_MAX_PAUSE_NOPS >= 8
    FFN_NOP_CASE(8);
#endif
#if FFN_MAX_PAUSE_NOPS >= 16
    FFN_NOP_CASE(16);
#endif
#if FFN_MAX_PAUSE_NOPS >= 32
    FFN_NOP_CASE(32);
#endif
#if FFN_MAX_PAUSE_NOPS >= 64
    FFN_NOP_CASE(64);
#endif
#if FFN_MAX_PAUSE_NOPS >= 128
    FFN_NOP_CASE(128);
#endif
#if FFN_MAX_PAUSE_NOPS >= 256
    FFN_NOP_CASE(256);
#endif
#if FFN_MAX_PAUSE_NOPS >= 512
    FFN_NOP_CASE(512);
#endif
#if FFN_MAX_PAUSE_NOPS >= 1024
    FFN_NOP_CASE(1024);
#endif
    }
#undef FFN_NOP_CASE
}

#define FFN_WAIT_READ_CYCLE() ffn_read_cycle()
#define FFN_WAIT_READ_STATUS() (*(volatile uint32_t *)FFN_STATUS_ADDRESS)
#define FFN_WAIT_REPORT_ERROR() ffn_report_error()
#define FFN_WAIT_PAUSE(nops) ffn_pause(nops)

#endif
