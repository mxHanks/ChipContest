/* Reference integration: same task protocol and startup as historical Group-y.
 * Successful compilation does not qualify this image on that RTL or on 64 PE. */
#include "group_y_reference.h"
#include "selected_config.h"
#include "rv32_port.h"
#define FFN_WAIT_INLINE static inline __attribute__((always_inline))
#include "ffn_wait.h"

static const struct ffn_wait_config ffn_clear_config = FFN_CLEAR_CONFIG;
static const struct ffn_wait_config ffn_compute_config = FFN_COMPUTE_CONFIG;

#define REG(offset) (*(volatile uint32_t *)(FFN_DMA_BASE + (offset)))

int main(void)
{
    volatile uint32_t *host = (volatile uint32_t *)FFN_HOST_ADDRESS;
    const uint32_t tasks = host[0], dual = host[3], warmup = host[4];
    if (!tasks || tasks > 12u || dual > 1u || warmup > 1u)
        return 2;
    if (REG(0x00) != FFN_DMA_ID)
        return 3;
    for (uint32_t task = 0; task < tasks + warmup; ++task) {
        const uint32_t begin = ffn_read_cycle();
        ffn_fence();
        REG(0x04) = 1u;
        if (ffn_wait(FFN_CLEAR_DONE, &ffn_clear_config))
            return 4;
        REG(0x10) = FFN_X_ADDRESS;
        REG(0x14) = FFN_W_ADDRESS;
        REG(0x18) = FFN_B_ADDRESS;
        REG(0x1c) = FFN_Y_ADDRESS;
        ffn_fence();
        REG(0x04) = 2u | (dual << 8);
        if (ffn_wait(FFN_DONE, &ffn_compute_config))
            return 5;
        ffn_fence();
        host[2] = ffn_read_cycle() - begin;
        host[1] = task + 1u;
        ffn_fence();
    }
    return 1;
}
