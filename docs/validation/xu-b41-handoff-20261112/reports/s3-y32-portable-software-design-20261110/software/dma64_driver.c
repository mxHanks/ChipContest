/* Real CPU64 adapter. All tensor layouts and task isolation follow a80dd18.
 * Immutable selected_config.h is generated offline; no online tuning or WFI. */
#include <stdint.h>
#include "targets/dma64_a80dd18.h"
#include "selected_config.h"
#include "rv32_port.h"
#define FFN_WAIT_INLINE static inline __attribute__((always_inline))
#include "ffn_wait.h"
#include "ffn_error_drain.h"

static const struct ffn_wait_config clear_config = FFN_CLEAR_CONFIG;
static const struct ffn_wait_config compute_config = FFN_COMPUTE_CONFIG;

static int failed_wait(int wait_result, int stage_code)
{
    if (wait_result == FFN_WAIT_ERROR &&
        ffn_error_drain(FFN_DRAIN_BUDGET_CYCLES, FFN_DRAIN_POLL_LIMIT))
        return 8; /* Error seen, but BUSY release could not be confirmed. */
    return stage_code;
}

int main(void)
{
    volatile uint32_t *host = (volatile uint32_t *)FFN_HOST_ADDRESS;
    const uint32_t tasks = host[0], rows = host[3], warmup = host[4];
    if (!tasks || tasks > 12u || (rows != 1u && rows != 8u) || warmup > 1u)
        return 2;
    if (!FFN_TARGET_CHECK())
        return 3;
    for (uint32_t call = 0; call < tasks + warmup; ++call) {
        uint32_t polls;
        for (polls = 0; polls < FFN_READY_POLL_LIMIT; ++polls)
            if (host[6] == call + 1u)
                break;
        if (polls == FFN_READY_POLL_LIMIT)
            return 6;
        ffn_fence();
        const uint32_t begin = ffn_read_cycle();
        FFN_TARGET_CLEAR();
        int result = ffn_wait(FFN_CLEAR_DONE, &clear_config);
        if (result)
            return failed_wait(result, 4);
        FFN_TARGET_DESCRIPTORS();
        ffn_fence();
        FFN_TARGET_START(rows);
        result = ffn_wait(FFN_DONE, &compute_config);
        if (result)
            return failed_wait(result, 5);
        ffn_fence();
        host[2] = ffn_read_cycle() - begin;
        host[1] = call + 1u;
        ffn_fence();
    }
    return 1;
}
