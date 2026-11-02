#include "accel.h"

enum { ID, SCRATCH, CTRL, STATUS, GROUP, X_ADDR, X_DATA, W_BANK,
       W_ADDR, W_DATA, BIAS_INDEX, BIAS_LO, BIAS_HI,
       RESULT_INDEX, RESULT_LO, RESULT_HI };

enum { CACHE_CTRL = 0x40 / 4, CACHE_ADDR = 0x44 / 4,
       CACHE_LO = 0x48 / 4, CACHE_HI = 0x4c / 4,
       CAPABILITY = 0x50 / 4, RESULT_WINDOW = 0x80 / 4 };

#ifndef XU_HARDWARE_STREAM16
#define XU_HARDWARE_STREAM16 0
#endif
#ifndef XU_HARDWARE_PACK32
#define XU_HARDWARE_PACK32 0
#endif
#if XU_HARDWARE_STREAM16 || XU_HARDWARE_PACK32
enum { W_CURSOR = 0x54 / 4, W_STREAM16 = 0x58 / 4,
       X_CURSOR = 0x60 / 4, X_STREAM16 = 0x64 / 4,
       W_PACK32 = 0x5c / 4, X_PACK32 = 0x68 / 4,
       STREAM_CAPABILITY = 0x70 / 4, PACKED_CAPABILITY = 0x74 / 4 };
#endif

#if XU_FIRMWARE_NO_MASKS
/* Fixed ABI: X/W truncate to 16 bits and BIAS_HI truncates to 8 bits. */
#define XU_LOW16(value) (value)
#define XU_LOW8(value) (value)
#else
#define XU_LOW16(value) ((value) & 0xffffu)
#define XU_LOW8(value) ((value) & 0xffu)
#endif

#if XU_FIRMWARE_BIAS_DTCM
/* Raw low/high words preserve the signed40 MMIO representation in DTCM BSS. */
static uint32_t bias_cache[2 * COLS];
#endif

#if XU_FIRMWARE_BIAS_UNROLL
#define XU_LOAD_BIAS(bank) do { \
    unsigned col = group * 8 + (bank); \
    reg[BIAS_INDEX] = (bank); \
    reg[BIAS_LO] = task_bias[2 * col]; \
    reg[BIAS_HI] = XU_LOW8(task_bias[2 * col + 1]); \
} while (0)
#endif

#if XU_FIRMWARE_RESULT_UNROLL
#if XU_HARDWARE_RESULT_WINDOW
#define XU_READ_RESULT(bank) do { \
    unsigned index = 2 * (row * COLS + group * 8 + (bank)); \
    y[index] = reg[RESULT_WINDOW + 2 * (bank)]; \
    y[index + 1] = (uint32_t)(int32_t)(int16_t)reg[RESULT_WINDOW + 2 * (bank) + 1]; \
} while (0)
#else
#define XU_READ_RESULT(bank) do { \
    unsigned index = 2 * (row * COLS + group * 8 + (bank)); \
    reg[RESULT_INDEX] = (bank); \
    y[index] = reg[RESULT_LO]; \
    y[index + 1] = (uint32_t)(int32_t)(int16_t)reg[RESULT_HI]; \
} while (0)
#endif
#endif

int accel_linear(const volatile uint32_t *x, const volatile uint32_t *w,
                 const volatile uint32_t *bias, volatile uint32_t *y,
                 uint32_t poll_limit) {
    volatile uint32_t *reg = (volatile uint32_t *)ACCEL_BASE;
    if (reg[ID] != 0xacce2030u) return -1;
    if (reg[STATUS] & 1u) return -2;
#if XU_HARDWARE_BIAS_CACHE || XU_HARDWARE_RESULT_WINDOW
    /* Reject old RTL instead of silently accepting writes to absent registers. */
    if (reg[CAPABILITY] != 0x58550003u) return -4;
#endif
#if XU_HARDWARE_PACK32
    if (reg[STREAM_CAPABILITY] != 0x58530003u) return -5;
    uint32_t packed_cap = reg[PACKED_CAPABILITY];
    if ((packed_cap & 0xffff0000u) != 0x58500000u || (packed_cap & 3u) != 3u)
        return -6;
    /* Preserve the original 32-bit shared slots: both high halves are explicitly
     * truncated even when the legacy no-masks experiment is selected. */
    uint32_t first_w0 = w[0];
    uint32_t first_w1 = w[1];
    reg[W_CURSOR] = 0;
    reg[W_PACK32] = (uint32_t)(uint16_t)first_w0 | ((uint32_t)(uint16_t)first_w1 << 16);
    for (unsigned element = 2; element < INNER * COLS; element += 2) {
        uint32_t low = w[element];
        uint32_t high = w[element + 1];
        reg[W_PACK32] = (uint32_t)(uint16_t)low | ((uint32_t)(uint16_t)high << 16);
    }
#elif XU_HARDWARE_STREAM16
    if (reg[STREAM_CAPABILITY] != 0x58530003u) return -5;
    /* Keep initialization inside the first shared-read/final-Y-response window.
     * The source remains one signed16 code per existing 32-bit shared slot. */
    uint32_t first_w = w[0];
    reg[W_CURSOR] = 0;
    reg[W_STREAM16] = first_w;
    for (unsigned element = 1; element < INNER * COLS; ++element)
        reg[W_STREAM16] = w[element];
#else
    for (unsigned bank = 0; bank < 8; ++bank) {
        reg[W_BANK] = bank;
        for (unsigned group = 0; group < 32; ++group)
            for (unsigned k = 0; k < INNER; ++k) {
                reg[W_ADDR] = group * INNER + k;
                reg[W_DATA] = XU_LOW16(w[k * COLS + group * 8 + bank]);
            }
    }
#endif
#if XU_HARDWARE_BIAS_CACHE
    /* Per-task refresh and both mode writes remain inside the timed window. */
    reg[CACHE_CTRL] = 0;
    for (unsigned col = 0; col < COLS; ++col) {
        reg[CACHE_ADDR] = col;
        reg[CACHE_LO] = bias[2 * col];
        reg[CACHE_HI] = XU_LOW8(bias[2 * col + 1]);
    }
    reg[CACHE_CTRL] = 1;
#elif XU_FIRMWARE_BIAS_DTCM
    /* Refresh every task, inside the window after W and before the first X. */
    for (unsigned word = 0; word < 2 * COLS; ++word)
        bias_cache[word] = bias[word];
    const uint32_t *task_bias = bias_cache;
#else
    const volatile uint32_t *task_bias = bias;
#endif
    for (unsigned row = 0; row < ROWS; ++row) {
#if XU_HARDWARE_PACK32
        reg[X_CURSOR] = 0;
        for (unsigned k = 0; k < INNER; k += 2) {
            uint32_t low = x[row * INNER + k];
            uint32_t high = x[row * INNER + k + 1];
            reg[X_PACK32] = (uint32_t)(uint16_t)low | ((uint32_t)(uint16_t)high << 16);
        }
#elif XU_HARDWARE_STREAM16
        reg[X_CURSOR] = 0;
        for (unsigned k = 0; k < INNER; ++k)
            reg[X_STREAM16] = x[row * INNER + k];
#else
        for (unsigned k = 0; k < INNER; ++k) {
            reg[X_ADDR] = k;
            reg[X_DATA] = XU_LOW16(x[row * INNER + k]);
        }
#endif
        for (unsigned group = 0; group < 32; ++group) {
#if XU_HARDWARE_BIAS_CACHE
            /* Chisel selects all eight cached bias values using GROUP. */
#elif XU_FIRMWARE_BIAS_UNROLL
            XU_LOAD_BIAS(0);
            XU_LOAD_BIAS(1);
            XU_LOAD_BIAS(2);
            XU_LOAD_BIAS(3);
            XU_LOAD_BIAS(4);
            XU_LOAD_BIAS(5);
            XU_LOAD_BIAS(6);
            XU_LOAD_BIAS(7);
#else
            for (unsigned bank = 0; bank < 8; ++bank) {
                unsigned col = group * 8 + bank;
                reg[BIAS_INDEX] = bank;
                reg[BIAS_LO] = task_bias[2 * col];
                reg[BIAS_HI] = XU_LOW8(task_bias[2 * col + 1]);
            }
#endif
            reg[GROUP] = group;
            reg[STATUS] = 2; /* W1C, including a previous task's completion. */
            reg[CTRL] = 1;
            unsigned polls = 0;
            while (!(reg[STATUS] & 2u))
                if (++polls >= poll_limit) return -3;
#if XU_FIRMWARE_RESULT_UNROLL
            XU_READ_RESULT(0);
            XU_READ_RESULT(1);
            XU_READ_RESULT(2);
            XU_READ_RESULT(3);
            XU_READ_RESULT(4);
            XU_READ_RESULT(5);
            XU_READ_RESULT(6);
            XU_READ_RESULT(7);
#else
            for (unsigned bank = 0; bank < 8; ++bank) {
                unsigned index = 2 * (row * COLS + group * 8 + bank);
#if XU_HARDWARE_RESULT_WINDOW
                y[index] = reg[RESULT_WINDOW + 2 * bank];
                y[index + 1] = (uint32_t)(int32_t)(int16_t)reg[RESULT_WINDOW + 2 * bank + 1];
#else
                reg[RESULT_INDEX] = bank;
                y[index] = reg[RESULT_LO];
                y[index + 1] = (uint32_t)(int32_t)(int16_t)reg[RESULT_HI];
#endif
            }
#endif
        }
    }
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    return 0;
}
