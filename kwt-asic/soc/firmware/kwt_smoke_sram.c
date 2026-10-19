#include <stdint.h>
#include "kwt_accel_regs.h"
#ifndef KWT_TASKS
#define KWT_TASKS 12
#endif
#define MEM_BASE UINT32_C(0xa0000000)
#define HOST_FLAG (*(volatile uint32_t *)(MEM_BASE+0x7ff00))
#define TEST_PHASE (*(volatile uint32_t *)(MEM_BASE+0x7ff08))
#define HOST_FAIL (*(volatile uint32_t *)(MEM_BASE+0x7ff04))
static inline uint32_t reg_read(uint32_t r) { return *(volatile uint32_t *)(KWT_ACCEL_BASE+r); }
static inline void reg_write(uint32_t r,uint32_t v) { *(volatile uint32_t *)(KWT_ACCEL_BASE+r)=v; }
static void fail(uint32_t code) { HOST_FAIL=code; for (;;) { __asm__ volatile("nop"); } }
static void load_tensor(uint32_t kind,uint32_t source,uint32_t count) {
    reg_write(KWT_REG_LOAD_KIND,kind);reg_write(KWT_REG_LOAD_ADDR,0);
    if(kind==KWT_LOAD_BIAS) {
        volatile const uint32_t *p=(volatile const uint32_t *)source;
        for(uint32_t i=0;i<count;i++) {
            reg_write(KWT_REG_LOAD_DATA_LO,p[2*i]);
            reg_write(KWT_REG_LOAD_DATA_HI,p[2*i+1]);
            reg_write(KWT_REG_LOAD_COMMIT,KWT_LOAD_COMMIT_WORD);
        }
    } else {
        // The development shared-bus model returns aligned 32-bit words. Use
        // one word for two signed16 payloads so the CPU never relies on an
        // unverified halfword response convention at an odd byte offset.
        volatile const uint32_t *p=(volatile const uint32_t *)source;
        for(uint32_t i=0;i<count;i+=2) {
            uint32_t packed=p[i/2];
            reg_write(KWT_REG_LOAD_DATA_LO,packed & 0xffffu);
            reg_write(KWT_REG_LOAD_COMMIT,KWT_LOAD_COMMIT_WORD);
            if(i+1<count) {
                reg_write(KWT_REG_LOAD_DATA_LO,packed >> 16);
                reg_write(KWT_REG_LOAD_COMMIT,KWT_LOAD_COMMIT_WORD);
            }
        }
    }
}
int main(void) {
    if(reg_read(KWT_REG_ID)!=KWT_ACCEL_ID) fail(0x101);
    // CPU-driven in-flight abort precheck. TEST_PHASE survives the later
    // external reset; it contains a test phase only, never arithmetic answers.
    if(TEST_PHASE!=0x51u) {
        load_tensor(KWT_LOAD_X,MEM_BASE,KWT_X_COUNT);
        load_tensor(KWT_LOAD_W,MEM_BASE+0x4000,KWT_W_COUNT);
        load_tensor(KWT_LOAD_BIAS,MEM_BASE+0xc000,KWT_BIAS_COUNT);
        reg_write(KWT_REG_CONTROL,KWT_CONTROL_START);
        if(!(reg_read(KWT_REG_STATUS)&KWT_STATUS_BUSY)) fail(0x201);
        reg_write(KWT_REG_CONTROL,4);
        if(reg_read(KWT_REG_STATUS)!=KWT_STATUS_LOAD_READY) fail(0x202);
        if(reg_read(KWT_REG_ERROR) || reg_read(KWT_REG_OUTPUT_COUNT)) fail(0x203);
        __asm__ volatile("fence iorw, iorw" ::: "memory");
        TEST_PHASE=0x51;
    }
    for(uint32_t task=0;task<KWT_TASKS;task++) {
        while(HOST_FLAG!=1) { }
        load_tensor(KWT_LOAD_X,MEM_BASE,KWT_X_COUNT);
        load_tensor(KWT_LOAD_W,MEM_BASE+0x4000,KWT_W_COUNT);
        load_tensor(KWT_LOAD_BIAS,MEM_BASE+0xc000,KWT_BIAS_COUNT);
        if(!(reg_read(KWT_REG_STATUS)&KWT_STATUS_START_READY)) fail(0x102);
        reg_write(KWT_REG_CONTROL,KWT_CONTROL_START);
        volatile uint32_t *output=(volatile uint32_t *)(MEM_BASE+0x10000);
        for(uint32_t i=0;i<KWT_Y_COUNT;i++) {
            while(!(reg_read(KWT_REG_STATUS)&KWT_STATUS_Y_VALID)) { }
            uint32_t index=reg_read(KWT_REG_Y_INDEX);
            if((index&KWT_Y_INDEX_MASK)!=i || !!(index&KWT_Y_LAST)!=(i+1==KWT_Y_COUNT)) fail(0x103);
            uint32_t lo=reg_read(KWT_REG_Y_LO);
            uint32_t hi=reg_read(KWT_REG_Y_HI);
            output[2*i]=lo;output[2*i+1]=hi&0xffff;
        }
        __asm__ volatile("fence iorw, iorw" ::: "memory");
        if(reg_read(KWT_REG_OUTPUT_COUNT)!=KWT_Y_COUNT) fail(0x104);
        if(reg_read(KWT_REG_ERROR)) fail(0x105);
        reg_write(KWT_REG_CONTROL,KWT_CONTROL_WRITEBACK_ACK);
        if(!(reg_read(KWT_REG_STATUS)&KWT_STATUS_SOFTWARE_DONE)) fail(0x106);
        __asm__ volatile("fence iorw, iorw" ::: "memory");
        HOST_FLAG=0x100+task;
    }
    for(;;) { __asm__ volatile("nop"); }
}
