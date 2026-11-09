/* S3 public PACK32 separate clear candidate; frozen main SHA256: 11ea61ea5f4c6f334143954babf79c8ed39d98d68cae4248a19a4d0631e5d3bc */
#define main s3_frozen_task_main
#include "/home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest/build/bias-demand-20261109/full12/source/tests/e203/firmware/main.c"
#undef main

/* No task X/W/bias source is read. Every store uses public 32-bit MMIO. */
static int s3_clear_task_data_and_parameters(void) {
    volatile uint32_t *const reg = (volatile uint32_t *)0x10042000u;
    volatile uint32_t *const host = (volatile uint32_t *)0xa007f000u;
    /* The host descriptor is control, not task input. Reject continuous runs. */
    if (host[0] != 1u) return -1;
    if (reg[0x000 / 4] != 0xacce2030u ||
        reg[0x050 / 4] != 0x58550003u || reg[0x00c / 4] != 0u) return -2;
    const uint32_t bias_capability = reg[0x0ec / 4];
    if (bias_capability != 0u && bias_capability != 0x42530001u) return -3;
    if (reg[0x070 / 4] != 0x58530003u ||
        reg[0x074 / 4] != 0x58500003u) return -4;
    reg[0x040 / 4] = 0u;
    reg[0x054 / 4] = 0u;
    for (unsigned pair = 0; pair < 8192; ++pair)
        reg[0x05c / 4] = 0u;
    if (bias_capability == 0x42530001u) {
        /* ICB completion is withheld until all 768 physical writes finish. */
        reg[0x0e8 / 4] = 1u;
    } else {
        for (unsigned column = 0; column < 256; ++column) {
            reg[0x044 / 4] = column;
            reg[0x048 / 4] = 0u;
            reg[0x04c / 4] = 0u;
        }
    }
    for (unsigned lane = 0; lane < 8; ++lane) {
        reg[0x028 / 4] = lane;
        reg[0x02c / 4] = 0u;
        reg[0x030 / 4] = 0u;
    }
    reg[0x060 / 4] = 0u;
    for (unsigned pair = 0; pair < 32; ++pair)
        reg[0x068 / 4] = 0u;
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    /* Explicit completion proof separates clear from frozen-main ABI reads. */
    if (reg[0x06c / 4] != 0u) return -5;
    if (reg[0x00c / 4] != 0u) return -6;
    return 0;
}

int main(void) {
    __asm__ volatile ("nop");
    if (s3_clear_task_data_and_parameters()) return 17;
    return s3_frozen_task_main();
}
