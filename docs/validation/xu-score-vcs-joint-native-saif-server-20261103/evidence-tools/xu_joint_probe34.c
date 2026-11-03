/* xu independent passive owner/actual-port VPI trace. No DUT writes. */
#include <vpi_user.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
#define MAX_PROBES 16
typedef struct {char *label,*full;int width;vpiHandle handle;s_vpi_value value;s_vpi_time time;s_cb_data cb;} Probe;
static Probe *probes[MAX_PROBES];static unsigned count;static int active,finished;
static uint64_t last_tick,ordinal;
static uint64_t tick(void){s_vpi_time t;memset(&t,0,sizeof(t));t.type=vpiSimTime;vpi_get_time(NULL,&t);return ((uint64_t)t.high<<32)|t.low;}
static char *copy(const char *s){char *p=malloc(strlen(s)+1);if(!p){vpi_control(vpiFinish,1);exit(2);}strcpy(p,s);return p;}
static void fail(const char *s){vpi_printf("XU_PROBE_REJECT %s\n",s);vpi_control(vpiFinish,1);}
static void bits(char *out,p_vpi_vecval v,int width){int i;for(i=0;i<width;i++){unsigned a=(v[0].aval>>i)&1,b=(v[0].bval>>i)&1;out[i]="01zx"[(b<<1)|a];}out[width]=0;}
static void snapshot(Probe *p,const char *kind){s_vpi_value v;char text[33];v.format=vpiVectorVal;vpi_get_value(p->handle,&v);bits(text,v.value.vector,p->width);vpi_printf("XU_PROBE_%s label=%s tick=%"PRIu64" width=%d actual_fullname=%s bits_lsb=%s\n",kind,p->label,tick(),p->width,p->full,text);}
static PLI_INT32 changed(p_cb_data cb){Probe *p=(Probe *)cb->user_data;s_vpi_value v;char delivered[33],current[33];uint64_t t;if(!active)return 0;t=tick();if(t!=last_tick){last_tick=t;ordinal=0;}ordinal++;bits(delivered,cb->value->value.vector,p->width);v.format=vpiVectorVal;vpi_get_value(p->handle,&v);bits(current,v.value.vector,p->width);vpi_printf("XU_PROBE_EVENT label=%s tick=%"PRIu64" ordinal=%"PRIu64" callback_bits_lsb=%s current_bits_lsb=%s\n",p->label,t,ordinal,delivered,current);return 0;}
static PLI_INT32 register_call(PLI_BYTE8 *unused){vpiHandle it=vpi_iterate(vpiArgument,vpi_handle(vpiSysTfCall,NULL)),a;Probe *p;s_vpi_value v;(void)unused;if(active||finished||count==MAX_PROBES){fail("registration phase/count");return 0;}a=vpi_scan(it);if(!a){fail("missing label");return 0;}v.format=vpiStringVal;vpi_get_value(a,&v);p=calloc(1,sizeof(Probe));if(!p){fail("allocation");return 0;}p->label=copy(v.value.str);p->handle=vpi_scan(it);if(!p->handle||vpi_scan(it)){fail("expected one actual signal");return 0;}p->width=vpi_get(vpiSize,p->handle);if(p->width<1||p->width>32){fail("width");return 0;}p->full=copy(vpi_get_str(vpiFullName,p->handle));p->value.format=vpiVectorVal;p->time.type=vpiSimTime;memset(&p->cb,0,sizeof(p->cb));p->cb.reason=cbValueChange;p->cb.cb_rtn=changed;p->cb.obj=p->handle;p->cb.value=&p->value;p->cb.time=&p->time;p->cb.user_data=(PLI_BYTE8 *)p;if(!vpi_register_cb(&p->cb)){fail("callback registration");return 0;}probes[count++]=p;return 0;}
static PLI_INT32 begin_call(PLI_BYTE8 *unused){unsigned i;(void)unused;if(active||finished||count!=8||vpi_get(vpiTimePrecision,NULL)!=-15){fail("begin phase/geometry/precision");return 0;}for(i=0;i<count;i++)snapshot(probes[i],"BEGIN");last_tick=tick();ordinal=0;active=1;return 0;}
static PLI_INT32 end_call(PLI_BYTE8 *unused){unsigned i;(void)unused;if(!active||finished){fail("end phase");return 0;}active=0;finished=1;for(i=0;i<count;i++)snapshot(probes[i],"END");return 0;}
static PLI_INT32 unfinished(p_cb_data cb){(void)cb;if(active)vpi_printf("XU_PROBE_INCOMPLETE active at finish\n");return 0;}
void xu_sram_probe_register_tasks(void){s_vpi_systf_data t;s_cb_data cb;memset(&t,0,sizeof(t));t.type=vpiSysTask;t.tfname="$xu_probe_register";t.calltf=register_call;vpi_register_systf(&t);t.tfname="$xu_probe_begin";t.calltf=begin_call;vpi_register_systf(&t);t.tfname="$xu_probe_end";t.calltf=end_call;vpi_register_systf(&t);memset(&cb,0,sizeof(cb));cb.reason=cbEndOfSimulation;cb.cb_rtn=unfinished;vpi_register_cb(&cb);}
void (*vlog_startup_routines[])(void)={xu_sram_probe_register_tasks,0};
