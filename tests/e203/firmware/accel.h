#ifndef E203_ACCEL_H
#define E203_ACCEL_H
#include <stdint.h>

#define ACCEL_BASE 0x10042000u
#define SHARED_BASE 0xa0000000u
#define X_OFFSET 0x00000u
#define W_OFFSET 0x08000u
#define BIAS_OFFSET 0x18000u
#define Y_OFFSET 0x20000u
#define HOST_OFFSET 0x7f000u
#define ROWS 99u
#define INNER 64u
#define COLS 256u

/* x/w use signed16 codes in 32-bit slots, bias uses signed40 in 64-bit slots.
 * y receives signed48 results, sign-extended into explicit low/high32 slots. */
int accel_linear(const volatile uint32_t *x, const volatile uint32_t *w,
                 const volatile uint32_t *bias, volatile uint32_t *y,
                 uint32_t poll_limit);
#endif
