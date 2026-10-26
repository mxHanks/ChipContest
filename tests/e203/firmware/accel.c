#include "accel.h"

enum { ID, SCRATCH, CTRL, STATUS, GROUP, X_ADDR, X_DATA, W_BANK,
       W_ADDR, W_DATA, BIAS_INDEX, BIAS_LO, BIAS_HI,
       RESULT_INDEX, RESULT_LO, RESULT_HI };

int accel_linear(const volatile uint32_t *x, const volatile uint32_t *w,
                 const volatile uint32_t *bias, volatile uint32_t *y,
                 uint32_t poll_limit) {
    volatile uint32_t *reg = (volatile uint32_t *)ACCEL_BASE;
    if (reg[ID] != 0xacce2030u) return -1;
    if (reg[STATUS] & 1u) return -2;
    for (unsigned bank = 0; bank < 8; ++bank) {
        reg[W_BANK] = bank;
        for (unsigned group = 0; group < 32; ++group)
            for (unsigned k = 0; k < INNER; ++k) {
                reg[W_ADDR] = group * INNER + k;
                reg[W_DATA] = w[k * COLS + group * 8 + bank] & 0xffffu;
            }
    }
    for (unsigned row = 0; row < ROWS; ++row) {
        for (unsigned k = 0; k < INNER; ++k) {
            reg[X_ADDR] = k;
            reg[X_DATA] = x[row * INNER + k] & 0xffffu;
        }
        for (unsigned group = 0; group < 32; ++group) {
            for (unsigned bank = 0; bank < 8; ++bank) {
                unsigned col = group * 8 + bank;
                reg[BIAS_INDEX] = bank;
                reg[BIAS_LO] = bias[2 * col];
                reg[BIAS_HI] = bias[2 * col + 1] & 0xffu;
            }
            reg[GROUP] = group;
            reg[STATUS] = 2; /* W1C, including a previous task's completion. */
            reg[CTRL] = 1;
            unsigned polls = 0;
            while (!(reg[STATUS] & 2u))
                if (++polls >= poll_limit) return -3;
            for (unsigned bank = 0; bank < 8; ++bank) {
                unsigned index = 2 * (row * COLS + group * 8 + bank);
                reg[RESULT_INDEX] = bank;
                y[index] = reg[RESULT_LO];
                y[index + 1] = (uint32_t)(int32_t)(int16_t)reg[RESULT_HI];
            }
        }
    }
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    return 0;
}
