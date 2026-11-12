/* Actual ffn_wait() under deterministic status/clock/pause adapters.
 * The synthetic clock charges adapter operations only, not CPU instructions. */
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint32_t read_cycle(void);
static uint32_t read_status(void);
static void report_error(void);
static void pause_nops(uint32_t count);
#define FFN_WAIT_READ_CYCLE() read_cycle()
#define FFN_WAIT_READ_STATUS() read_status()
#define FFN_WAIT_REPORT_ERROR() report_error()
#define FFN_WAIT_PAUSE(count) pause_nops(count)
#include "ffn_wait.h"

static struct {
    uint64_t time, done_at, error_at, total_nops;
    uint32_t origin, status_cost, cycle_cost, nop_cost;
    uint32_t reads, clocks, reports, error_reads, pauses, max_pause, first_pause;
    uint32_t error_code, published_error, done_mask;
    uint32_t script[8], script_length;
    int frozen_clock;
} model;

static void reset(void)
{
    memset(&model, 0, sizeof(model));
    model.done_at = model.error_at = UINT64_MAX;
    model.status_cost = 4;
    model.cycle_cost = model.nop_cost = 1;
    model.error_code = 0x71u;
    model.done_mask = FFN_DONE;
}

static uint32_t read_cycle(void)
{
    ++model.clocks;
    model.time += model.cycle_cost;
    return model.origin + (model.frozen_clock ? 0u : (uint32_t)model.time);
}

static uint32_t read_status(void)
{
    const uint32_t index = model.reads++;
    model.time += model.status_cost;
    if (model.script_length)
        return model.script[index < model.script_length ? index : model.script_length - 1u];
    uint32_t status = model.time >= model.done_at ? model.done_mask : FFN_BUSY;
    if (model.time >= model.error_at)
        status |= FFN_ERROR;
    return status;
}

static void report_error(void)
{
    ++model.error_reads;
    ++model.reports;
    model.published_error = model.error_code;
}

static void pause_nops(uint32_t count)
{
    if (!model.pauses)
        model.first_pause = count;
    ++model.pauses;
    model.total_nops += count;
    if (count > model.max_pause)
        model.max_pause = count;
    model.time += (uint64_t)count * model.nop_cost;
}

static unsigned cases;
#define CHECK(value) do { if (!(value)) { \
    fprintf(stderr, "CONTRACT_FAIL line=%d expression=%s\n", __LINE__, #value); exit(1); \
} } while (0)
#define CASE_DONE() (++cases)

static void contracts(void)
{
    const struct ffn_wait_config configs[] = {
        {10000, 1000, 0, 0, 0, FFN_POLL_TIGHT},
        {10000, 1000, 64, 64, 0, FFN_POLL_FIXED},
        {10000, 1000, 64, 64, 4, FFN_POLL_PHASED},
        {10000, 1000, 8, 256, 4, FFN_POLL_BACKOFF}
    };
    for (unsigned mode = 0; mode < sizeof(configs)/sizeof(configs[0]); ++mode) {
        struct ffn_wait_config cfg = configs[mode];
        reset(); model.script_length = 1;
        model.script[0] = FFN_ERROR | FFN_DONE | FFN_BUSY;
        CHECK(ffn_wait(FFN_DONE, &cfg) == FFN_WAIT_ERROR);
        CHECK(model.reads == 1 && model.reports == 1 && model.error_reads == 1 &&
              model.published_error == 0x71u && model.pauses == 0); CASE_DONE();

        reset(); model.error_at = 0; model.error_code = 0;
        CHECK(ffn_wait(FFN_DONE, &cfg) == FFN_WAIT_ERROR);
        CHECK(model.reports == 1 && model.published_error == 0); CASE_DONE();

        reset(); model.done_at = 0;
        CHECK(ffn_wait(FFN_DONE, &cfg) == FFN_WAIT_OK);
        CHECK(model.reads == 1 && model.pauses == 0 && model.reports == 0); CASE_DONE();

        reset(); model.script_length = 2;
        model.script[0] = FFN_BUSY | FFN_DONE; model.script[1] = FFN_DONE;
        CHECK(ffn_wait(FFN_DONE, &cfg) == FFN_WAIT_OK);
        CHECK(model.reads == 2); CASE_DONE();

        reset(); model.script_length = 3;
        model.script[0] = model.script[1] = FFN_DONE; model.script[2] = FFN_CLEAR_DONE;
        CHECK(ffn_wait(FFN_CLEAR_DONE, &cfg) == FFN_WAIT_OK);
        CHECK(model.reads == 3); CASE_DONE();

        reset(); model.origin = UINT32_MAX - 32u; model.done_at = 80;
        CHECK(ffn_wait(FFN_DONE, &cfg) == FFN_WAIT_OK);
        CHECK(model.time >= 80 && model.time < cfg.budget_cycles); CASE_DONE();

        reset(); cfg.budget_cycles = 32;
        CHECK(ffn_wait(FFN_DONE, &cfg) == FFN_WAIT_TIMEOUT);
        CHECK(model.time >= 32 && model.reports == 0); CASE_DONE();

        reset(); cfg = configs[mode]; cfg.poll_limit = 7; model.frozen_clock = 1;
        CHECK(ffn_wait(FFN_DONE, &cfg) == FFN_WAIT_POLL_LIMIT);
        CHECK(model.reads == 7); CASE_DONE();

        reset(); cfg = configs[mode]; cfg.budget_cycles = 5; model.done_at = 0;
        CHECK(ffn_wait(FFN_DONE, &cfg) == FFN_WAIT_TIMEOUT); CASE_DONE();

        reset(); cfg = configs[mode]; cfg.budget_cycles = 5; model.error_at = 0;
        CHECK(ffn_wait(FFN_DONE, &cfg) == FFN_WAIT_ERROR);
        CHECK(model.reports == 1); CASE_DONE();

        reset(); cfg = configs[mode]; cfg.budget_cycles = 32;
        model.script_length = 1; model.script[0] = FFN_BUSY | FFN_DONE;
        CHECK(ffn_wait(FFN_DONE, &cfg) == FFN_WAIT_TIMEOUT); CASE_DONE();

        reset(); cfg = configs[mode]; model.done_at = 2000;
        CHECK(ffn_wait(FFN_DONE, &cfg) == FFN_WAIT_OK);
        CHECK(model.max_pause <= cfg.max_nops);
        CHECK((mode == 0 && model.pauses == 0) ||
              (mode != 0 && model.pauses > 0 && model.first_pause == cfg.initial_nops)); CASE_DONE();

        /* A second task cannot inherit the previous backoff phase. */
        reset(); model.done_at = 2000;
        CHECK(ffn_wait(FFN_DONE, &cfg) == FFN_WAIT_OK);
        if (mode != 0) CHECK(model.first_pause == cfg.initial_nops); CASE_DONE();

        reset(); cfg = configs[mode]; cfg.poll_limit = 7;
        CHECK(ffn_wait(FFN_DONE, &cfg) == FFN_WAIT_POLL_LIMIT);
        CHECK(model.reads == 7); CASE_DONE();

        reset(); cfg = configs[mode]; model.error_at = 200;
        CHECK(ffn_wait(FFN_DONE, &cfg) == FFN_WAIT_ERROR);
        CHECK(model.reports == 1 && model.reads > 1); CASE_DONE();

        reset(); model.script_length = 2;
        model.script[0] = FFN_DONE; model.script[1] = FFN_DONE | FFN_CLEAR_DONE;
        CHECK(ffn_wait(FFN_DONE | FFN_CLEAR_DONE, &cfg) == FFN_WAIT_OK);
        CHECK(model.reads == 2); CASE_DONE();

        /* The budget is observed after MMIO returns, not by a watchdog. */
        reset(); cfg = configs[mode]; cfg.budget_cycles = 32; model.status_cost = 320;
        CHECK(ffn_wait(FFN_DONE, &cfg) == FFN_WAIT_TIMEOUT);
        CHECK(model.time > cfg.budget_cycles && model.reads == 1); CASE_DONE();

        reset(); cfg = configs[mode]; model.origin = UINT32_MAX - 10u;
        model.error_at = 200;
        CHECK(ffn_wait(FFN_DONE, &cfg) == FFN_WAIT_ERROR);
        CHECK(model.published_error == 0x71u); CASE_DONE();
    }
    printf("CONTRACT_PASS cases=%u policies=4\n", cases);
}

static void screen(void)
{
    unsigned policy, initial, maximum, fast, budget, limit, status_cost, cycle_cost, nop_cost;
    uint64_t completion;
    while (scanf("%u %u %u %u %u %u %" SCNu64 " %u %u %u", &policy, &initial,
                 &maximum, &fast, &budget, &limit, &completion, &status_cost,
                 &cycle_cost, &nop_cost) == 10) {
        reset();
        model.done_at = completion;
        model.status_cost = status_cost;
        model.cycle_cost = cycle_cost;
        model.nop_cost = nop_cost;
        const struct ffn_wait_config cfg = {budget, limit, initial, maximum, fast, policy};
        const int result = ffn_wait(FFN_DONE, &cfg);
        printf("%d %" PRIu64 " %u %u %" PRIu64 " %u\n", result, model.time,
               model.reads, model.clocks, model.total_nops, model.max_pause);
    }
}

int main(int argc, char **argv)
{
    if (argc == 2 && strcmp(argv[1], "--screen") == 0)
        screen();
    else
        contracts();
    return 0;
}
