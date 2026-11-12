#ifndef FFN_ERROR_DRAIN_H
#define FFN_ERROR_DRAIN_H

/* Called once after ffn_wait has already published the first ERROR code.
 * ERROR is sticky in the target; only BUSY releasing proves accepted work has
 * drained. No new submission, retry, or repeated error publication occurs.
 * The same returned-MMIO and <2^31 cycle-observation assumptions apply as wait.
 */
static inline int ffn_error_drain(uint32_t budget_cycles, uint32_t poll_limit)
{
    const uint32_t begin = FFN_WAIT_READ_CYCLE();
    for (uint32_t poll = 0; poll < poll_limit; ++poll) {
        const uint32_t status = FFN_WAIT_READ_STATUS();
        if (FFN_WAIT_READ_CYCLE() - begin >= budget_cycles)
            return FFN_WAIT_TIMEOUT;
        if ((status & FFN_ERROR) || !(status & FFN_BUSY))
            return FFN_WAIT_OK;
    }
    return FFN_WAIT_POLL_LIMIT;
}

#endif
