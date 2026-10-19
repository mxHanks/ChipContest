#ifndef CATS_R4_CORE_SERVICE_H
#define CATS_R4_CORE_SERVICE_H

/* ABI3 held completion snapshot. Read only after successful DONE and before
 * the next START. expected_epoch belongs to that transaction; a valid old
 * snapshot is not an acceptable measurement for a new request.
 * Pages 60/61: 64-bit core cycles, first QK acceptance to final PV acceptance.
 * Page 62: epoch[31:16], reserved[15:5], overflow/fault/running/finished/valid.
 */
#include <stdint.h>
#define CATS_R4_CORE_SERVICE_READER_REVISION 1
#define CATS_R4_CORE_SERVICE_ABI3_SIGNATURE UINT32_C(0x43340003)
#define CATS_R4_CORE_SERVICE_PAGE_ABI 47U
#define CATS_R4_CORE_SERVICE_PAGE_CYCLES_LO 60U
#define CATS_R4_CORE_SERVICE_PAGE_CYCLES_HI 61U
#define CATS_R4_CORE_SERVICE_PAGE_META 62U
#define CATS_R4_CORE_SERVICE_VALID (UINT32_C(1) << 0)
#define CATS_R4_CORE_SERVICE_FINISHED (UINT32_C(1) << 1)
#define CATS_R4_CORE_SERVICE_RUNNING (UINT32_C(1) << 2)
#define CATS_R4_CORE_SERVICE_FAULT (UINT32_C(1) << 3)
#define CATS_R4_CORE_SERVICE_OVERFLOW (UINT32_C(1) << 4)

typedef struct {
    uint64_t cycles;
    uint16_t epoch;
    uint8_t valid, finished, running, fault, overflow;
} cats_r4_core_service_snapshot_t;

static int cats_r4_core_service_decode(uint32_t abi, uint32_t lo,
                                      uint32_t hi, uint32_t meta,
                                      cats_r4_core_service_snapshot_t *out)
{
    cats_r4_core_service_snapshot_t value = {0};
    if (out == (cats_r4_core_service_snapshot_t *)0)
        return -1;
    *out = value;
    if (abi != CATS_R4_CORE_SERVICE_ABI3_SIGNATURE)
        return -1;
    /* Require both success bits and reject reserved or failure bits. */
    if ((meta & UINT32_C(0xffff)) != UINT32_C(3) ||
        (meta >> 16) == 0U || (lo == 0U && hi == 0U))
        return -2;
    value.cycles = ((uint64_t)hi << 32) | lo;
    value.epoch = (uint16_t)(meta >> 16);
    value.valid = 1U;
    value.finished = 1U;
    *out = value;
    return 0;
}

typedef uint32_t (*cats_r4_core_service_read_page_fn)(void *user, uint32_t page);

static int cats_r4_core_service_read(cats_r4_core_service_read_page_fn read_page,
                                    void *user, uint16_t expected_epoch,
                                    cats_r4_core_service_snapshot_t *out)
{
    const cats_r4_core_service_snapshot_t empty = {0};
    cats_r4_core_service_snapshot_t decoded;
    uint32_t abi, meta, hi, lo, lo_after, hi_after, meta_after, abi_after;
    int rc;
    if (out == (cats_r4_core_service_snapshot_t *)0)
        return -3;
    *out = empty;
    if (read_page == (cats_r4_core_service_read_page_fn)0 || expected_epoch == 0U)
        return -3;
    abi = read_page(user, CATS_R4_CORE_SERVICE_PAGE_ABI);
    if (abi != CATS_R4_CORE_SERVICE_ABI3_SIGNATURE)
        return -1;
    meta = read_page(user, CATS_R4_CORE_SERVICE_PAGE_META);
    hi = read_page(user, CATS_R4_CORE_SERVICE_PAGE_CYCLES_HI);
    lo = read_page(user, CATS_R4_CORE_SERVICE_PAGE_CYCLES_LO);
    lo_after = read_page(user, CATS_R4_CORE_SERVICE_PAGE_CYCLES_LO);
    hi_after = read_page(user, CATS_R4_CORE_SERVICE_PAGE_CYCLES_HI);
    meta_after = read_page(user, CATS_R4_CORE_SERVICE_PAGE_META);
    abi_after = read_page(user, CATS_R4_CORE_SERVICE_PAGE_ABI);
    if (abi != abi_after || meta != meta_after || hi != hi_after || lo != lo_after)
        return -4;
    rc = cats_r4_core_service_decode(abi, lo, hi, meta, &decoded);
    if (rc != 0)
        return rc;
    if (decoded.epoch != expected_epoch)
        return -5;
    *out = decoded;
    return 0;
}
#endif
