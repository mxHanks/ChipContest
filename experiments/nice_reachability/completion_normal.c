#include <stdint.h>
int main(void) {
    volatile uint32_t *reg=(volatile uint32_t*)0x10042000u;
    volatile uint32_t *y=(volatile uint32_t*)0xa0020000u;
    const int32_t raw[8]={256,768,-256,-768,512,-512,1023,-1025};
    const int32_t gold[8]={0,2,0,-2,1,-1,2,-2};
    if(reg[0]!=0xacce2030u || reg[0xe4/4]!=0x59330001u) return 2;
    reg[0x40/4]=0;
    /* Three groups suffice: one drain allows at most three producer groups. */
    for(unsigned k=0;k<64;++k) {
        reg[0x54/4]=k*256;
        for(unsigned pair=0;pair<12;++pair) reg[0x5c/4]=0x00010001u;
    }
    reg[0x60/4]=0;
    for(unsigned pair=0;pair<32;++pair) reg[0x68/4]=0;
    for(unsigned col=0;col<24;++col) {
        int64_t value=(int64_t)raw[col%8]+4096*(col/8);
        reg[0x44/4]=col;
        reg[0x48/4]=(uint32_t)value;
        reg[0x4c/4]=(uint32_t)((uint64_t)value>>32);
    }
    reg[0x40/4]=1;
    reg[0xc0/4]=1;
    uint32_t code, control=100u<<5;
    __asm__ volatile (
        ".insn r 0x7b, 7, 0x20, %0, %1, %2\n\t"
        "fence iorw, iorw"
        : "=r"(code) : "r"(y), "r"(control) : "memory");
#ifdef PROBE_BUS_ERROR
    /* A partial writeback is a whole-task failure: no retry or readback. */
    if(code!=8u) return 3;
#else
    if(code) return 3;
    for(unsigned lane=0;lane<8;++lane) if(y[lane]!=(uint32_t)gold[lane]) return 4;
#endif
    return 1;
}
