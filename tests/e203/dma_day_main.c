/* Independent peripheral-DMA candidate: real RV32 CPU submits descriptors.
 * No NICE instructions, result shortcuts, retries, or retained task parameters. */
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
    uint32_t result;
    __asm__ volatile ("csrr %0, mcycle" : "=r"(result) :: "memory");
    return result;
}

static int wait_status(uint32_t wanted) {
    for (uint32_t poll = 0; poll < POLL_LIMIT; ++poll) {
        uint32_t status = REG(0x08);
        if (status & STATUS_ERROR) {
            /* Preserve the first error code; never retry a partial descriptor. */
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
    const uint32_t tasks = host[0];
    const uint32_t dual = host[3];
    const uint32_t warmup = host[4];
    if (!tasks || tasks > 12 || dual > 1 || warmup > 1) return 2;
    if (REG(0x00) != DMA_ID) return 3;

    for (uint32_t layer = 0; layer < tasks + warmup; ++layer) {
        uint32_t start = read_cycle();
        /* Each task clears physical state and reloads its own complete tensors. */
        fence_memory();
        REG(0x04) = 1u;
        if (wait_status(STATUS_CLEAR_DONE)) return 4;
        REG(0x10) = SHARED_BASE;
        REG(0x14) = SHARED_BASE + 0x08000u;
        REG(0x18) = SHARED_BASE + 0x18000u;
        REG(0x1c) = SHARED_BASE + 0x20000u;
        fence_memory();
        REG(0x04) = 2u | (dual << 8);
        if (wait_status(STATUS_DONE)) return 5;
        fence_memory();
        host[2] = read_cycle() - start;
        /* The endpoint loads the next task only after proving this task retired. */
        host[1] = layer + 1;
        fence_memory();
    }
    return 1;
}
