#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include "../xu_mapped_task00_vpi111.c"
void vpi_get_value(vpiHandle h,p_vpi_value v){v->value.scalar=*(PLI_INT32 *)h;}
PLI_INT32 vpi_printf(const char *fmt,...){PLI_INT32 r;va_list ap;va_start(ap,fmt);r=vprintf(fmt,ap);va_end(ap);return r;}
void vpi_control(PLI_INT32 operation,...){(void)operation;}
int main(int argc,char **argv){
 unsigned n;int mode=argc>1?atoi(argv[1]):0;PLI_INT32 clock=vpi0,reset=vpi0;
 accel_clk=(vpiHandle)&clock;accel_reset=(vpiHandle)&reset;previous_clk=vpi0;
 if(mode==5){clock=vpiX;clock_callback(NULL);clock=vpi0;clock_callback(NULL);}
 for(n=0;n<4594;++n){clock=vpi1;clock_callback(NULL);clock=vpi0;clock_callback(NULL);}
 reset=vpi1;clock=vpi1;clock_callback(NULL);clock=vpi0;clock_callback(NULL);
 if(clock_reset_edges!=4594||clock_ready!=1||failed)return 2;
 if(mode==1){clock=vpiX;}if(mode==2){clock=vpiZ;}
 if(mode==3){reset=vpiX;}if(mode==4){reset=vpi0;}
 if(mode>=1&&mode<=4){if(mode>=3)clock=vpi1;clock_callback(NULL);}
 printf("REVIEW111_CLOCK mode=%d reset_edges=%u ready=%u rejected=%d NO_NATIVE_VCS_EVENT_PROOF\n",mode,clock_reset_edges,clock_ready,failed);
 return (failed!=((mode>=1&&mode<=4)?1:0));
}
