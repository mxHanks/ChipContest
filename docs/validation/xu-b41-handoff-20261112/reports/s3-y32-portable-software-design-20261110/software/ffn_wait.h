#ifndef FFN_WAIT_H
#define FFN_WAIT_H

#include <stdint.h>

/* The adapter supplies four static operations. Status is normalized to these
 * bits; its MMIO ordering and error publication remain the adapter's contract. */
enum { FFN_BUSY = 1u, FFN_DONE = 2u, FFN_ERROR = 4u, FFN_CLEAR_DONE = 8u };
enum { FFN_WAIT_OK = 0, FFN_WAIT_ERROR = -1, FFN_WAIT_TIMEOUT = -2,
       FFN_WAIT_POLL_LIMIT = -3 };
enum { FFN_POLL_TIGHT, FFN_POLL_FIXED, FFN_POLL_PHASED, FFN_POLL_BACKOFF };

struct ffn_wait_config {
    uint32_t budget_cycles;
    uint32_t poll_limit;
    uint32_t initial_nops;
    uint32_t max_nops;
    uint32_t fast_reads;
    unsigned policy;
};

/* Valid immutable configs are created by the offline tools. budget_cycles and
 * the interval between clock observations must stay below 2^31 cycles.
 *
 * The deadline is checked after each returned status read. ERROR takes priority
 * even at the deadline; a late DONE is a timeout. A blocked MMIO operation or a
 * pause can overrun the budget before the next observation. This is not an
 * independent watchdog and makes no unconditional wall-clock-return guarantee.
 *
 * No state is retained across calls. The caller performs the completion fence
 * before consuming outputs or publishing completion. */
#ifndef FFN_WAIT_INLINE
#define FFN_WAIT_INLINE static inline
#endif
FFN_WAIT_INLINE int ffn_wait(uint32_t wanted, const struct ffn_wait_config *config)
{
    const uint32_t begin = FFN_WAIT_READ_CYCLE();
    uint32_t pause = config->initial_nops;
    for (uint32_t poll = 0; poll < config->poll_limit; ++poll) {
        const uint32_t status = FFN_WAIT_READ_STATUS();
        if (status & FFN_ERROR) {
            FFN_WAIT_REPORT_ERROR();
            return FFN_WAIT_ERROR;
        }
        const uint32_t elapsed = FFN_WAIT_READ_CYCLE() - begin;
        if (elapsed >= config->budget_cycles)
            return FFN_WAIT_TIMEOUT;
        if ((status & wanted) == wanted && !(status & FFN_BUSY))
            return FFN_WAIT_OK;
        if (config->policy == FFN_POLL_TIGHT ||
            (config->policy != FFN_POLL_FIXED && poll < config->fast_reads))
            continue;
        FFN_WAIT_PAUSE(pause);
        if (config->policy == FFN_POLL_BACKOFF && pause < config->max_nops)
            pause = pause > config->max_nops / 2u ? config->max_nops : pause * 2u;
    }
    return FFN_WAIT_POLL_LIMIT;
}

#endif
