/* xu bounded read-only VPI string-argument diagnostic. No DUT or power model. */
#include <vpi_user.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define LIMIT 512
static unsigned calls;
static void reject(const char *s) { vpi_printf("XU_STRING_PROBE_REJECT %s\n",s);vpi_control(vpiFinish,1); }
static vpiHandle next(vpiHandle it) { vpiHandle h=vpi_scan(it);if(!h)reject("missing argument");return h; }
static int integer(vpiHandle h) { s_vpi_value v;v.format=vpiIntVal;vpi_get_value(h,&v);return v.value.integer; }
static void snapshot(vpiHandle h,unsigned char *out,size_t *length) {
    s_vpi_value v;size_t i;v.format=vpiStringVal;vpi_get_value(h,&v);
    if(!v.value.str){reject("null string result");*length=0;return;}
    for(i=0;i<LIMIT && v.value.str[i];i++)out[i]=(unsigned char)v.value.str[i];
    if(i==LIMIT){reject("string exceeds diagnostic bound");*length=0;return;}
    *length=i;
}
static void hex(const unsigned char *s,size_t n) { size_t i;for(i=0;i<n;i++)vpi_printf("%02x",(unsigned)s[i]); }
static PLI_INT32 probe(PLI_BYTE8 *data) {
    vpiHandle it=vpi_iterate(vpiArgument,vpi_handle(vpiSysTfCall,NULL)),a,b,c;
    unsigned char first[LIMIT],second[LIMIT];size_t n=0,m=0;int mode=data[0]-'0',ending=data[1]=='e',id;
    if(mode==0){id=integer(next(it));if(!ending){a=next(it);snapshot(a,first,&n);}b=next(it);snapshot(b,second,&m);}
    else {
        c=next(it);a=next(it);b=ending?a:next(it);
        if(mode==1){id=integer(c);if(!ending)snapshot(a,first,&n);snapshot(b,second,&m);}
        else if(mode==2){snapshot(b,second,&m);if(!ending)snapshot(a,first,&n);id=integer(c);}
        else {reject("unknown mode");return 0;}
    }
    if(vpi_scan(it)){reject("extra argument");return 0;}
    calls++;vpi_printf("XU_STRING_PROBE mode=%d id=%d first_bytes=%lu first_hex=",mode,id,(unsigned long)n);hex(first,n);
    vpi_printf(" second_bytes=%lu second_hex=",(unsigned long)m);hex(second,m);vpi_printf("\n");return 0;
}
static PLI_INT32 done(PLI_BYTE8 *unused) { (void)unused;vpi_printf("XU_STRING_PROBE_DONE calls=%u\n",calls);return 0; }
void xu_joint_string_probe_register(void) {
    static char *names[]={"$xu_joint_string_seq","$xu_joint_string_handles","$xu_joint_string_reverse","$xu_joint_end_seq","$xu_joint_end_handles","$xu_joint_end_reverse"};
    static char *flags[]={"0b","1b","2b","0e","1e","2e"};
    s_vpi_systf_data t;unsigned i;memset(&t,0,sizeof(t));t.type=vpiSysTask;t.calltf=probe;
    for(i=0;i<6;i++){t.tfname=names[i];t.user_data=(PLI_BYTE8 *)flags[i];vpi_register_systf(&t);}
    t.user_data=NULL;
    t.tfname="$xu_joint_string_done";t.calltf=done;vpi_register_systf(&t);
}
void (*vlog_startup_routines[])(void)={xu_joint_string_probe_register,0};
