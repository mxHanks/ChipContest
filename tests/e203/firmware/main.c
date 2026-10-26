#include "accel.h"

int main(void) {
    volatile uint32_t *host = (volatile uint32_t *)(SHARED_BASE + HOST_OFFSET);
    const unsigned tasks = host[0];
    if (!tasks || tasks > 12) return 2;
    for (unsigned layer = 0; layer < tasks; ++layer) {
        uint32_t start, end;
        __asm__ volatile ("csrr %0, mcycle" : "=r"(start) :: "memory");
        int result = accel_linear(
            (volatile uint32_t *)(SHARED_BASE + X_OFFSET),
            (volatile uint32_t *)(SHARED_BASE + W_OFFSET),
            (volatile uint32_t *)(SHARED_BASE + BIAS_OFFSET),
            (volatile uint32_t *)(SHARED_BASE + Y_OFFSET), 100000);
        if (result) return 10 - result;
        __asm__ volatile ("csrr %0, mcycle" : "=r"(end) :: "memory");
        host[2] = end - start;
        host[1] = layer + 1; /* Host loads the next layer after verified writeback. */
        __asm__ volatile ("fence iorw, iorw" ::: "memory");
    }
    return 1;
}
