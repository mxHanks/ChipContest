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

/* X uses signed16 codes in 32-bit slots; bias uses signed40 in 64-bit slots.
 * W normally uses the same signed16 slots; XU_SHARED_W_PACKED16 instead stores
 * two consecutive signed16 codes in each low/high16 shared word.
 * Y normally receives signed48 in explicit sign-extended low/high32 slots;
 * XU_HARDWARE_Y32 receives row-major signed32 RNE(y48 / 512), one word/result.
 * XU_NICE_DRAIN8 (0x20) uses poll_limit in 1..0x07ffffff, counting
 * retired ROW_STATUS responses. XU_NICE_DRAINN (0x23) uses 1..0x003fffff
 * retired responses per group. XU_NICE_READY (0x24, requires DRAINN, DIRECT
 * and DRAIN8) uses the same 22-bit range but counts READY_WAIT clock edges
 * per group. Every variant checks the returned status code explicitly; -11 rejects the limit and -12 aborts the whole task
 * after a NICE failure, which may include an already-retired POP. */
int accel_linear(const volatile uint32_t *x, const volatile uint32_t *w,
                 const volatile uint32_t *bias, volatile uint32_t *y,
                 uint32_t poll_limit);
#endif
