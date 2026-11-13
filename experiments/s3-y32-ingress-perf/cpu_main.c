/* Compliant32 development integration. The real RV32 submits every descriptor.
 * Full external timing starts BEFORE input/parameter SystemBus loading.
 * No result calculation, retries, NICE, or retained parameter tasks. */
#include <stdint.h>

#define DMA_BASE 0x10042300u
#define SHARED_BASE 0xa0000000u
#define HOST_OFFSET 0x7f000u
#define REG(off) (*(volatile uint32_t *)(DMA_BASE + (off)))
#define DMA_ID 0x444d4131u
#define STATUS_BUSY 1u
#define STATUS_DONE 2u
#define STATUS_ERROR 4u
#define STATUS_CLEAR_DONE 8u
#define POLL_LIMIT 1000000u

static inline void fence_memory(void) {
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
}

static uint32_t read_cycle(void) {
    uint32_t value;
    __asm__ volatile ("csrr %0, mcycle" : "=r"(value) :: "memory");
    return value;
}

static int wait_status(uint32_t wanted) {
    for (uint32_t poll = 0; poll < POLL_LIMIT; ++poll) {
        uint32_t status = REG(0x08);
        if (status & STATUS_ERROR) {
            volatile uint32_t *host = (volatile uint32_t *)(SHARED_BASE + HOST_OFFSET);
            host[5] = REG(0x0c);
            fence_memory();
            return -1;
        }
        if ((status & wanted) == wanted && !(status & STATUS_BUSY)) return 0;
    }
    return -2;
}

int main(void) {
    volatile uint32_t *host = (volatile uint32_t *)(SHARED_BASE + HOST_OFFSET);
    const uint32_t tasks = host[0], rows = host[3], warmup = host[4];
    if (!tasks || tasks > 12 || (rows != 1 && rows != 8) || warmup > 1) return 2;
    if (REG(0x00) != DMA_ID || REG(0x4c) != 0x00082001u) return 3;
    for (uint32_t call = 0; call < tasks + warmup; ++call) {
        uint32_t polls;
        /* Clear permission follows previous task verification. No tensor is
         * loaded until real CLEAR_DONE is observed and this ACK retires. */
        for (polls = 0; polls < POLL_LIMIT; ++polls)
            if (host[8] == call + 1) break;
        if (polls == POLL_LIMIT) return 6;
        fence_memory();
        uint32_t start = read_cycle();
        REG(0x04) = 1u;
        if (wait_status(STATUS_CLEAR_DONE)) return 4;
        fence_memory();
        host[7] = call + 1;
        fence_memory();
        for (polls = 0; polls < POLL_LIMIT; ++polls)
            if (host[6] == call + 1) break;
        if (polls == POLL_LIMIT) return 7;
        fence_memory();
        REG(0x10) = SHARED_BASE;
        REG(0x14) = SHARED_BASE + 0x08000u;
        REG(0x18) = SHARED_BASE + 0x18000u;
        REG(0x1c) = SHARED_BASE + 0x20000u;
        fence_memory();
        REG(0x04) = rows == 8 ? 0x802u : 2u;
        if (wait_status(STATUS_DONE)) return 5;
        fence_memory();
        host[2] = read_cycle() - start;
        host[1] = call + 1;
        fence_memory();
    }
    return 1;
}
