#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "cats_r4_core_service.h"

/* Literal page and flag values keep this MMIO model independent of the
 * implementation constants. It models a held snapshot changing during reads,
 * not an FPGA bus or a physical CDC proof. */
typedef struct {
    uint32_t abi, lo, hi, meta;
    unsigned low_reads, high_reads, meta_reads, reads;
    unsigned change_epoch, change_high;
} fake_snapshot_t;

static uint32_t read_page(void *user, uint32_t page)
{
    fake_snapshot_t *f = (fake_snapshot_t *)user;
    ++f->reads;
    switch (page) {
    case 47: return f->abi;
    case 60:
        ++f->low_reads;
        if (f->change_epoch) f->meta = (10U << 16) | 3U;
        return f->lo;
    case 61:
        ++f->high_reads;
        return f->hi + ((f->change_high && f->high_reads > 1U) ? 1U : 0U);
    case 62: ++f->meta_reads; return f->meta;
    default: return 0xf24f0000U | page;
    }
}

static fake_snapshot_t fresh(void)
{
    fake_snapshot_t f = {0x43340003U, 0x89abcdefU, 0x12345678U,
                         (9U << 16) | 3U, 0, 0, 0, 0, 0, 0};
    return f;
}

static int read_expected(fake_snapshot_t *f, uint16_t expected,
                         cats_r4_core_service_snapshot_t *out)
{
#ifdef CATS_R4_CORE_SERVICE_READER_REVISION
    return cats_r4_core_service_read(read_page, f, expected, out);
#else
    /* Allows execution against the saved original implementation. The old
     * API cannot receive the expected transaction; this is the defect. */
    (void)expected;
    return cats_r4_core_service_read(read_page, f, out);
#endif
}

static int empty(const cats_r4_core_service_snapshot_t *s)
{
    return s->cycles == 0 && s->epoch == 0 && !s->valid && !s->finished &&
           !s->running && !s->fault && !s->overflow;
}

#define REQUIRE(condition, code, message) do { \
    if (!(condition)) { puts("FAIL " message); return code; } \
} while (0)

static int regression(const char *name)
{
    fake_snapshot_t f = fresh();
    cats_r4_core_service_snapshot_t s = {1, 1, 1, 1, 0, 0, 0};
    if (!strcmp(name, "stale")) {
        REQUIRE(read_expected(&f, 10, &s) != 0, 21, "STALE_EPOCH_ACCEPTED");
        REQUIRE(empty(&s), 31, "STALE_FAILURE_RETAINED_OUTPUT");
    } else if (!strcmp(name, "metadata")) {
        f.change_epoch = 1;
        REQUIRE(read_expected(&f, 9, &s) != 0, 22, "TORN_METADATA_ACCEPTED");
        REQUIRE(empty(&s), 32, "TORN_METADATA_RETAINED_OUTPUT");
    } else if (!strcmp(name, "retained")) {
        REQUIRE(read_expected(&f, 9, &s) == 0 && s.valid, 40, "SEED_READ_FAILED");
        f.abi = 0x43340002U;
        REQUIRE(read_expected(&f, 9, &s) != 0, 41, "OLD_ABI_ACCEPTED");
        REQUIRE(empty(&s), 23, "FAILED_READ_RETAINED_VALID_DATA");
    } else if (!strcmp(name, "cycles")) {
        f.change_high = 1;
        REQUIRE(read_expected(&f, 9, &s) != 0, 24, "CHANGING_CYCLES_ACCEPTED");
        REQUIRE(empty(&s), 34, "CHANGING_CYCLES_RETAINED_OUTPUT");
    } else {
        puts("FAIL unknown regression case");
        return 90;
    }
    return 0;
}

int main(int argc, char **argv)
{
    unsigned cases = 0;
    const char *names[] = {"stale", "metadata", "retained", "cycles"};
    if (argc == 2 && strcmp(argv[1], "all")) {
        int rc = regression(argv[1]);
        if (rc) return rc;
        printf("PASS CORE_SERVICE_COHERENCE case=%s\n", argv[1]);
        return 0;
    }
    for (unsigned i = 0; i < 4; ++i) {
        int rc = regression(names[i]);
        if (rc) return rc;
        ++cases;
    }
    fake_snapshot_t f = fresh();
    cats_r4_core_service_snapshot_t s;
    REQUIRE(read_expected(&f, 9, &s) == 0 &&
            s.cycles == UINT64_C(0x1234567889abcdef) && s.epoch == 9,
            42, "STABLE_64BIT_SNAPSHOT_REJECTED_OR_TRUNCATED");
    ++cases;
    f = fresh(); f.meta = (65535U << 16) | 3U;
    REQUIRE(read_expected(&f, 65535, &s) == 0 && s.epoch == 65535,
            43, "LAST_VALID_EPOCH_REJECTED");
    ++cases;
    f = fresh();
    REQUIRE(read_expected(&f, 0, &s) != 0 && empty(&s) && f.reads == 0,
            44, "ZERO_EXPECTED_EPOCH_READ_OR_ACCEPTED");
    ++cases;
    /* Each metadata failure is isolated with a nonzero full-width value and
     * matching epoch. Missing valid/finished, running, fault, overflow, and
     * unknown reserved metadata must each be rejected. */
    const uint32_t flags[] = {2U, 1U, 7U, 11U, 19U, 35U};
    for (unsigned i = 0; i < sizeof(flags)/sizeof(flags[0]); ++i) {
        f = fresh(); f.meta = (9U << 16) | flags[i];
        REQUIRE(read_expected(&f, 9, &s) != 0 && empty(&s),
                45, "INVALID_FLAGS_ACCEPTED_OR_OUTPUT_RETAINED");
        ++cases;
    }
    f = fresh(); f.lo = 0; f.hi = 0;
    REQUIRE(read_expected(&f, 9, &s) != 0 && empty(&s), 46, "ZERO_CYCLES_ACCEPTED");
    ++cases;
    f = fresh();
    REQUIRE(read_expected(&f, 9, (cats_r4_core_service_snapshot_t *)0) != 0 && f.reads == 0,
            47, "NULL_OUTPUT_READ_REGISTERS");
    ++cases;
#ifdef CATS_R4_CORE_SERVICE_READER_REVISION
    s.cycles = 99; s.valid = 1;
    REQUIRE(cats_r4_core_service_read((cats_r4_core_service_read_page_fn)0, &f, 9, &s) != 0 && empty(&s),
            48, "NULL_READER_RETAINED_OUTPUT");
    ++cases;
#endif
    printf("PASS CORE_SERVICE_COHERENCE cases=%u\n", cases);
    return 0;
}
