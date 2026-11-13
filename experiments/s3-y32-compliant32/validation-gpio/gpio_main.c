/* Production-N2 CPU loader over existing GPIO pads. No third SystemBus source.
 * Tensor words enter only as real GPIO inputs, then CPU loads/stores through
 * original GPIO/PPI/LSU/BIU/SystemBus paths. No retries after error. */
#include <stdint.h>
#define DMA_BASE 0x10042300u
#define BASE 0xa0000000u
#define HOST 0xa007f000u
#define REG(o) (*(volatile uint32_t *)(DMA_BASE+(o)))
#define GA(o) (*(volatile uint32_t *)(0x10012000u+(o)))
#define GB(o) (*(volatile uint32_t *)(0x10040000u+(o)))
#define ACK (1u<<21)
#define READY (1u<<22)
#define ERROR (1u<<23)
#define POLLS 2000000u
static uint32_t req_level;
static uint32_t gpio_shadow;
static inline void fence_memory(void) { __asm__ volatile("fence iorw, iorw" ::: "memory"); }
static inline uint32_t cycle(void) { uint32_t x; __asm__ volatile("csrr %0, mcycle":"=r"(x)::"memory"); return x; }
static int failure(uint32_t code) {
    GA(8)=ERROR|(req_level?ACK:0u);fence_memory();
    *(volatile uint32_t *)(HOST+20)=code;fence_memory();return 0;
}
static int receive(uint32_t *value, volatile uint32_t *destination) {
    gpio_shadow=READY|(req_level?ACK:0u);GA(8)=gpio_shadow;fence_memory();
    uint32_t polls;
    for(polls=0;polls<POLLS;++polls)if(((GA(4)>>20)&1u)!=req_level)break;
    if(polls==POLLS)return failure(0x100u);
    *value=GB(4);
    if(destination)*destination=*value;
    fence_memory(); /* Actual shared response retirement precedes GPIO ACK. */
    req_level^=1u;gpio_shadow=READY|(req_level?ACK:0u);GA(8)=gpio_shadow;fence_memory();
    return 1;
}
static int status(uint32_t wanted) {
    for(uint32_t i=0;i<POLLS;++i){uint32_t s=REG(8);if(s&4u)return failure(REG(12)|0x200u);if(!(s&1u)&&(s&wanted)==wanted)return 1;}
    return failure(0x201u);
}
int main(void) {
    volatile uint32_t *host=(volatile uint32_t *)HOST;
    GA(0x1c)=0;GB(0x1c)=0;GA(0x0c)=0;GB(0x0c)=0;GA(8)=0;GA(0)=ACK|READY|ERROR;GB(0)=0;fence_memory();
    uint32_t tasks,rows,warmup,tmp;
    if(!receive(&tasks,0)||!receive(&rows,0)||!receive(&warmup,0))return 2;
    if(!tasks||tasks>12||(rows!=1&&rows!=8)||warmup>1)return failure(0x300u);
    if(REG(0)!=0x444d4131u||REG(0x4c)!=0x00082001u)return failure(0x301u);
    for(uint32_t call=0;call<tasks+warmup;++call){
        if(!receive(&tmp,0)||tmp!=call+1)return failure(0x302u);
        GA(8)=req_level?ACK:0u;fence_memory();
        volatile uint32_t *y=(volatile uint32_t *)(BASE+0x20000u);
        for(uint32_t i=0;i<25344;++i)y[i]=0xdeadbeefu;
        fence_memory();uint32_t begin=cycle();
        REG(4)=1;if(!status(8u))return 4;fence_memory();
        host[7]=call+1;fence_memory();
        const uint32_t bases[3]={BASE,BASE+0x8000u,BASE+0x18000u};
        const uint32_t sizes[3]={6336u,8192u,512u};
        for(uint32_t region=0;region<3;++region)
            for(uint32_t i=0;i<sizes[region];++i)
                if(!receive(&tmp,(volatile uint32_t *)(bases[region]+4*i)))return 7;
        GA(8)=req_level?ACK:0u;fence_memory();
        REG(0x10)=BASE;REG(0x14)=BASE+0x8000u;REG(0x18)=BASE+0x18000u;REG(0x1c)=BASE+0x20000u;fence_memory();
        REG(4)=rows==8?0x802u:2u;if(!status(2u))return 5;fence_memory();
        host[2]=cycle()-begin;fence_memory();
        uint32_t checksum=0;
        for(uint32_t i=0;i<25344;++i)checksum^=y[i];
        fence_memory();host[9]=checksum;fence_memory();
        host[1]=call+1;fence_memory();
    }
    return 1;
}
