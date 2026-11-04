/* xu explicit clear candidate; original main SHA256: 11ea61ea5f4c6f334143954babf79c8ed39d98d68cae4248a19a4d0631e5d3bc */
#define main xu_frozen_task_main
#include "/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/ChipContest-s2c-02/tests/e203/firmware/main.c"
#undef main

/* Fresh-process TASKS=1 only. No task X/W/bias pointer is accessed here. */
static int xu_clear_task_data_and_parameters(void) {
    volatile uint32_t *const reg = (volatile uint32_t *)0x10042000u;
    if (reg[0x000 / 4] != 0xacce2030u ||
        reg[0x050 / 4] != 0x58550003u || (reg[0x00c / 4] & 1u)) return -1;
    reg[0x040 / 4] = 0; /* cache disabled throughout clearing */
    for (unsigned bank = 0; bank < 8; ++bank) {
        reg[0x01c / 4] = bank;
        for (unsigned address = 0; address < 2048; ++address) {
            reg[0x020 / 4] = address;
            reg[0x024 / 4] = 0;
        }
    }
    for (unsigned column = 0; column < 256; ++column) {
        reg[0x044 / 4] = column;
        reg[0x048 / 4] = 0;
        reg[0x04c / 4] = 0;
    }
    for (unsigned lane = 0; lane < 8; ++lane) {
        reg[0x028 / 4] = lane;
        reg[0x02c / 4] = 0;
        reg[0x030 / 4] = 0;
    }
    for (unsigned address = 0; address < 64; ++address) {
        reg[0x014 / 4] = address;
        reg[0x018 / 4] = 0;
    }
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    return 0;
}

int main(void) {
    if (xu_clear_task_data_and_parameters()) return 17;
    return xu_frozen_task_main();
}
