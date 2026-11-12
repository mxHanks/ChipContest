/* The real wait and error-drain functions under scripted, returned MMIO. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint32_t model_status(void), cycle(void);
static void report(void);
#define FFN_WAIT_READ_STATUS() model_status()
#define FFN_WAIT_READ_CYCLE() cycle()
#define FFN_WAIT_REPORT_ERROR() report()
#define FFN_WAIT_PAUSE(n) ((void)(n))
#include "ffn_wait.h"
#include "ffn_error_drain.h"

static struct {
    uint32_t script[4], now, origin, cost, reads, clocks, reports, error_code, published;
    unsigned count;
} model;
static unsigned cases;
#define CHECK(v) do { if (!(v)) { fprintf(stderr,"DRAIN_FAIL line=%d check=%s\n",__LINE__,#v); exit(1); } } while (0)
static uint32_t model_status(void)
{
    uint32_t i=model.reads++;
    return model.script[i<model.count?i:model.count-1];
}
static uint32_t cycle(void)
{
    model.clocks++;
    model.now+=model.cost;
    return model.origin+model.now;
}
static void report(void) { model.reports++; model.published=model.error_code; }
static void reset(void)
{
    memset(&model,0,sizeof(model));
    model.cost=1;model.count=3;model.error_code=0x71;
    model.script[0]=model.script[1]=FFN_ERROR|FFN_BUSY;
    model.script[2]=FFN_ERROR;
}
int main(void)
{
    const struct ffn_wait_config wait={32,16,0,0,0,FFN_POLL_TIGHT};
    reset();
    CHECK(ffn_wait(FFN_DONE,&wait)==FFN_WAIT_ERROR);
    CHECK(ffn_error_drain(32,16)==FFN_WAIT_OK);
    CHECK(model.reads==3 && model.reports==1 && model.published==0x71);cases++;

    reset();model.script[0]=FFN_ERROR|FFN_DONE;model.script[1]=FFN_ERROR|FFN_DONE;
    CHECK(ffn_wait(FFN_DONE,&wait)==FFN_WAIT_ERROR);
    CHECK(ffn_error_drain(32,16)==FFN_WAIT_OK);
    CHECK(model.reads==2 && model.reports==1);cases++;

    reset();model.error_code=0;
    CHECK(ffn_wait(FFN_CLEAR_DONE,&wait)==FFN_WAIT_ERROR);
    CHECK(ffn_error_drain(32,16)==FFN_WAIT_OK);
    CHECK(model.reports==1 && model.published==0);cases++;

    reset();model.count=1;
    CHECK(ffn_wait(FFN_DONE,&wait)==FFN_WAIT_ERROR);
    CHECK(ffn_error_drain(4,16)==FFN_WAIT_TIMEOUT);
    CHECK(model.reports==1 && model.reads>1);cases++;

    reset();model.count=1;model.cost=0;
    CHECK(ffn_wait(FFN_DONE,&wait)==FFN_WAIT_ERROR);
    CHECK(ffn_error_drain(32,7)==FFN_WAIT_POLL_LIMIT);
    CHECK(model.reads==8 && model.reports==1);cases++;

    reset();model.origin=UINT32_MAX-3u;
    CHECK(ffn_wait(FFN_DONE,&wait)==FFN_WAIT_ERROR);
    CHECK(ffn_error_drain(32,16)==FFN_WAIT_OK);
    CHECK(model.reports==1 && model.origin+model.now<model.origin);cases++;

    reset();model.script[1]=FFN_ERROR|FFN_DONE|FFN_BUSY;
    CHECK(ffn_wait(FFN_DONE,&wait)==FFN_WAIT_ERROR);
    CHECK(ffn_error_drain(32,16)==FFN_WAIT_OK);
    CHECK(model.reads==3 && model.reports==1);cases++;

    reset();model.count=2;model.script[1]=FFN_ERROR;
    CHECK(ffn_wait(FFN_DONE,&wait)==FFN_WAIT_ERROR);
    CHECK(ffn_error_drain(1,16)==FFN_WAIT_TIMEOUT);
    CHECK(model.reports==1);cases++;

    reset();model.error_code=0x99;
    CHECK(ffn_wait(FFN_DONE,&wait)==FFN_WAIT_ERROR);
    CHECK(ffn_error_drain(32,16)==FFN_WAIT_OK);
    CHECK(model.published==0x99 && model.reports==1);cases++;
    puts("DRAIN_CONTRACT_PASS cases=9");
    return 0;
}
