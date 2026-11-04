/* xu read-only RAMSP1024X16 joint activity recorder, new producer only.
 * No vpi_put_value, force, DUT writes, SAIF rewriting or power calculation.
 * Callback ordinal is observation order, not a simulator delta-cycle claim.
 */
#include <vpi_user.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>

#define PORTS 10
#define BITS 67
#define PROJS 34
#define MAX_MACROS 1024
/* 0,1,X,Z; little bit order within each real vector port. */
static const int widths[PORTS]={10,1,1,16,3,2,1,16,1,16};
static const int offsets[PORTS]={0,10,11,12,28,31,33,34,50,51};
static const char *port_names[PORTS]={"A","CEN","CLK","D","EMA","EMAW","GWEN","Q","RET1N","WEN"};
static const int controls[8]={50,10,33,30,29,28,32,31};

typedef struct { uint64_t key,value; unsigned used; } Entry;
typedef struct { Entry *items; size_t capacity,size; } Counts;
typedef struct { uint64_t ordinal; unsigned port; char old_value[17],new_value[17]; } Event;
typedef struct Macro Macro;
typedef struct { Macro *macro; int port; s_vpi_value value; s_vpi_time time; s_cb_data callback; } Port;
struct Macro {
    char *name; vpiHandle handles[PORTS]; Port ports[PORTS]; unsigned char state[BITS];
    uint64_t pin_last[BITS],pin_dwell[BITS][4],pin_trans[BITS][16];
    uint64_t proj_last[PROJS],proj_key[PROJS]; Counts dwell,transitions;
    uint64_t pending_tick; unsigned pending_valid,has_control,has_toggling;
    unsigned char pending_state[BITS]; Event *pending; size_t pending_size,pending_capacity;
    uint64_t callback_events;
};
static Macro *macros[MAX_MACROS]; static unsigned macro_count;
static int active,finished,task_id;
static uint64_t start_tick,end_tick,last_ordinal_tick,ordinal,begin_ordinal,end_ordinal,sidecar_records;
static FILE *stats,*sidecar;
static char *begin_identity;
static int numeric_transaction;
static uint32_t source_cycle;

static void fail(const char *message) { vpi_printf("XU_JOINT_REJECT %s\n",message); vpi_control(vpiFinish,1); }
static void *allocate(size_t n) { void *p=calloc(1,n); if(!p){fail("allocation failed");exit(2);} return p; }
static uint64_t now_tick(void) { s_vpi_time t; memset(&t,0,sizeof(t));t.type=vpiSimTime;vpi_get_time(NULL,&t);return ((uint64_t)t.high<<32)|t.low; }
static uint64_t next_ordinal(uint64_t tick) { if(tick!=last_ordinal_tick){last_ordinal_tick=tick;ordinal=0;}return ++ordinal; }
static void json_string(FILE *f,const char *s) { const unsigned char *p=(const unsigned char *)s;fputc('"',f);for(;*p;p++){if(*p=='"'||*p=='\\')fputc('\\',f);if(*p<32)fprintf(f,"\\u%04x",*p);else fputc(*p,f);}fputc('"',f); }
static uint64_t hash_key(uint64_t k) { k^=k>>30;k*=UINT64_C(0xbf58476d1ce4e5b9);k^=k>>27;k*=UINT64_C(0x94d049bb133111eb);return k^(k>>31); }
static void add(Counts *c,uint64_t key,uint64_t value);
static void grow(Counts *c) { size_t i,n=c->capacity;Entry *old=c->items;c->capacity=n?n*2:128;c->size=0;c->items=allocate(c->capacity*sizeof(Entry));for(i=0;i<n;i++)if(old[i].used)add(c,old[i].key,old[i].value);free(old); }
static void add(Counts *c,uint64_t key,uint64_t value) { size_t i;if(!value)return;if(!c->capacity||c->size*10>=c->capacity*7)grow(c);i=hash_key(key)&(c->capacity-1);while(c->items[i].used&&c->items[i].key!=key)i=(i+1)&(c->capacity-1);if(!c->items[i].used){c->items[i].used=1;c->items[i].key=key;c->size++;}if(UINT64_MAX-c->items[i].value<value){fail("counter overflow");return;}c->items[i].value+=value; }
static uint64_t projection(Macro *m,int p) {
    uint64_t k=0;int i;
    if(p==0){for(i=0;i<8;i++)k|=(uint64_t)m->state[controls[i]]<<(2*i);}
    else if(p==1){k=m->proj_key[0]|((uint64_t)m->state[11]<<16);}
    else if(p<18){i=p-2;k=m->state[51+i]|((uint64_t)m->state[33]<<2)|((uint64_t)m->state[12+i]<<4);}
    else {i=p-18;k=m->state[50]|((uint64_t)m->state[33]<<2)|((uint64_t)m->state[34+i]<<4);}
    return k;
}
/* Projection IDs: 0 control tuple; 1 control+CLK; 2..17 WEN/GWEN/D;
 * 18..33 RET1N/GWEN/Q. RET1N/CEN is derived from tuple 0 plus raw pin edges.
 * Dedicated RET transition evidence is kept in projection 0 transitions.
 * Keys: projection ID above bit 40; transition previous key above bit 20.
 */
static void touch(Macro *m,int p,uint64_t t) {
    uint64_t old=m->proj_key[p],fresh=projection(m,p);
    if(t<m->proj_last[p]){fail("time reversed");return;}
    add(&m->dwell,((uint64_t)p<<40)|old,t-m->proj_last[p]);
    if(fresh!=old)add(&m->transitions,((uint64_t)p<<40)|(old<<20)|fresh,1);
    m->proj_key[p]=fresh;m->proj_last[p]=t;
}
static void state_string(FILE *f,const unsigned char *s,int n) { int i;fputc('"',f);for(i=0;i<n;i++)fputc("01xz"[s[i]],f);fputc('"',f); }
static void port_string(char *s,const unsigned char *state,int port) { int i;for(i=0;i<widths[port];i++)s[i]="01xz"[state[offsets[port]+i]];s[i]=0; }
static void flush_pending(Macro *m,int boundary) {
    size_t i;if(!m->pending_valid)return;
    if((m->has_control&&m->has_toggling)||boundary){
        fprintf(sidecar,"{\"macro\":");json_string(sidecar,m->name);
        fprintf(sidecar,",\"tick\":%"PRIu64",\"boundary\":%s,\"pre_state_lsb_ports\":",m->pending_tick,boundary?"true":"false");state_string(sidecar,m->pending_state,BITS);
        fprintf(sidecar,",\"events\":[");for(i=0;i<m->pending_size;i++){Event *e=&m->pending[i];if(i)fputc(',',sidecar);fprintf(sidecar,"{\"callback_ordinal\":%"PRIu64",\"port\":",e->ordinal);json_string(sidecar,port_names[e->port]);fprintf(sidecar,",\"old\":");json_string(sidecar,e->old_value);fprintf(sidecar,",\"new\":");json_string(sidecar,e->new_value);fputc('}',sidecar);}fprintf(sidecar,"]}\n");sidecar_records++;
    }
    m->pending_valid=0;m->pending_size=0;m->has_control=0;m->has_toggling=0;
}
static void snapshot_port(Macro *m,int port,unsigned char *target) { s_vpi_value v;int i;v.format=vpiVectorVal;vpi_get_value(m->handles[port],&v);for(i=0;i<widths[port];i++){unsigned a=(v.value.vector[0].aval>>i)&1,b=(v.value.vector[0].bval>>i)&1;target[offsets[port]+i]=(unsigned char)(b?(a?2:3):a);} }
static PLI_INT32 changed(p_cb_data cb) {
    Port *p=(Port *)cb->user_data;Macro *m=p->macro;unsigned char fresh[BITS];uint64_t t,o;int i,bit,changed_any=0,affected[PROJS]={0};Event *e;
    if(!active)return 0;
    memcpy(fresh,m->state,BITS);
    /* cb value is the delivered event value, never a read of other live ports. */
    for(i=0;i<widths[p->port];i++){unsigned a=(cb->value->value.vector[0].aval>>i)&1,b=(cb->value->value.vector[0].bval>>i)&1;fresh[offsets[p->port]+i]=(unsigned char)(b?(a?2:3):a);if(fresh[offsets[p->port]+i]!=m->state[offsets[p->port]+i])changed_any=1;}
    if(!changed_any)return 0;
    t=now_tick();o=next_ordinal(t);m->callback_events++;
    if(m->pending_valid&&m->pending_tick!=t)flush_pending(m,m->pending_tick==start_tick);
    if(!m->pending_valid){m->pending_valid=1;m->pending_tick=t;memcpy(m->pending_state,m->state,BITS);}
    if(m->pending_size==m->pending_capacity){size_t n=m->pending_capacity?m->pending_capacity*2:8;Event *v=realloc(m->pending,n*sizeof(Event));if(!v){fail("event allocation failed");return 0;}m->pending=v;m->pending_capacity=n;}
    e=&m->pending[m->pending_size++];e->ordinal=o;e->port=p->port;port_string(e->old_value,m->state,p->port);port_string(e->new_value,fresh,p->port);
    if(p->port==1||p->port==4||p->port==5||p->port==6||p->port==8||p->port==9)m->has_control=1;
    if(p->port==2||p->port==3||p->port==7||p->port==8)m->has_toggling=1;
    for(i=0;i<widths[p->port];i++){
        bit=offsets[p->port]+i;if(fresh[bit]==m->state[bit])continue;
        m->pin_dwell[bit][m->state[bit]]+=t-m->pin_last[bit];m->pin_last[bit]=t;m->pin_trans[bit][m->state[bit]*4+fresh[bit]]++;
        if(p->port==3)affected[2+i]=1;
        if(p->port==7)affected[18+i]=1;
        if(p->port==9)affected[2+i]=1;
    }
    if(p->port==1||p->port==4||p->port==5||p->port==6||p->port==8)affected[0]=affected[1]=1;
    if(p->port==2)affected[1]=1;
    if(p->port==6){for(i=2;i<PROJS;i++)affected[i]=1;}
    if(p->port==8){for(i=18;i<PROJS;i++)affected[i]=1;}
    memcpy(m->state,fresh,BITS);for(i=0;i<PROJS;i++)if(affected[i])touch(m,i,t);
    return 0;
}
static vpiHandle argument(vpiHandle iterator) { vpiHandle p=vpi_scan(iterator);if(!p)fail("missing system-task argument");return p; }
static int integer_argument(vpiHandle h) { s_vpi_value v;v.format=vpiIntVal;vpi_get_value(h,&v);return v.value.integer; }
static char *string_argument(vpiHandle h) { s_vpi_value v;char *s;v.format=vpiStringVal;vpi_get_value(h,&v);if(!v.value.str){fail("null string argument");return NULL;}s=allocate(strlen(v.value.str)+1);strcpy(s,v.value.str);return s; }
/* Copy each four-state value before any further VPI call. Numeric transaction
 * identities do not retain simulator-owned string buffers or SV expressions. */
static int known_u32_arguments(vpiHandle it,uint32_t *out,unsigned count) {
    unsigned i;for(i=0;i<count;i++){
        vpiHandle h=vpi_scan(it);s_vpi_value v;int width;
        if(!h){fail("missing numeric transaction argument");return 0;}
        width=vpi_get(vpiSize,h);if(width<1||width>32){fail("numeric transaction argument width differs");return 0;}
        v.format=vpiVectorVal;vpi_get_value(h,&v);
        if(!v.value.vector||v.value.vector[0].bval){fail("numeric transaction argument contains X/Z");return 0;}
        out[i]=(uint32_t)v.value.vector[0].aval;
    }
    if(vpi_scan(it)){fail("extra numeric transaction argument");return 0;}return 1;
}
static PLI_INT32 register_call(PLI_BYTE8 *unused) {
    vpiHandle call=vpi_handle(vpiSysTfCall,NULL),it=vpi_iterate(vpiArgument,call);Macro *m;int p;unsigned i;(void)unused;
    if(active||finished||macro_count==MAX_MACROS){fail("invalid registration phase/count");return 0;}
    m=allocate(sizeof(Macro));m->name=string_argument(argument(it));for(i=0;i<macro_count;i++)if(!strcmp(macros[i]->name,m->name)){fail("duplicate macro name");return 0;}
    for(p=0;p<PORTS;p++){
        m->handles[p]=argument(it);if(vpi_get(vpiSize,m->handles[p])!=widths[p]){fail("actual macro port width differs");return 0;}
        {
            vpiHandle scope=vpi_handle(vpiScope,m->handles[p]);
            char scope_name[4096];
            const char *scope_value=scope?vpi_get_str(vpiFullName,scope):NULL;
            if(!scope_value||strlen(scope_value)>=sizeof(scope_name)){fail("invalid actual macro scope");return 0;}
            strcpy(scope_name,scope_value);
            const char *pin_name=vpi_get_str(vpiName,m->handles[p]);
            if(strcmp(scope_name,m->name)||!pin_name||strcmp(pin_name,port_names[p])) {
                fail("register arguments must be the named actual macro ports in one exact scope");return 0;
            }
        }
        snapshot_port(m,p,m->state);
        m->ports[p].macro=m;m->ports[p].port=p;m->ports[p].value.format=vpiVectorVal;
        m->ports[p].time.type=vpiSimTime;
        memset(&m->ports[p].callback,0,sizeof(s_cb_data));m->ports[p].callback.reason=cbValueChange;m->ports[p].callback.cb_rtn=changed;
        m->ports[p].callback.obj=m->handles[p];m->ports[p].callback.value=&m->ports[p].value;m->ports[p].callback.time=&m->ports[p].time;m->ports[p].callback.user_data=(PLI_BYTE8 *)&m->ports[p];
        if(!vpi_register_cb(&m->ports[p].callback)){fail("value-change callback registration failed");return 0;}
    }
    if(vpi_scan(it)){fail("extra register argument");return 0;}macros[macro_count++]=m;return 0;
}
static PLI_INT32 begin_window(int supplied,const char *prefix,const char *identity) {
    char *name;unsigned i;int p;size_t n;
    if(active||finished||!macro_count||vpi_get(vpiTimePrecision,NULL)!=-15){fail("begin requires registered macros, fresh process, global 1fs precision");return 0;}
    task_id=supplied;if(task_id<0||task_id>11||!prefix||!identity){fail("invalid begin task/arguments");return 0;}
    begin_identity=allocate(strlen(identity)+1);strcpy(begin_identity,identity);
    n=strlen(prefix)+64;name=allocate(n);snprintf(name,n,"%s.stats.jsonl",prefix);stats=fopen(name,"wx");snprintf(name,n,"%s.simultaneous.jsonl",prefix);sidecar=fopen(name,"wx");free(name);
    if(!stats||!sidecar){fail("output already exists or cannot be created");return 0;}
    start_tick=now_tick();begin_ordinal=next_ordinal(start_tick);
    for(i=0;i<macro_count;i++){Macro *m=macros[i];for(p=0;p<PORTS;p++)snapshot_port(m,p,m->state);for(p=0;p<BITS;p++)m->pin_last[p]=start_tick;for(p=0;p<PROJS;p++){m->proj_last[p]=start_tick;m->proj_key[p]=projection(m,p);}fprintf(sidecar,"{\"macro\":");json_string(sidecar,m->name);fprintf(sidecar,",\"begin_tick\":%"PRIu64",\"callback_ordinal\":%"PRIu64",\"initial_state_lsb_ports\":",start_tick,begin_ordinal);state_string(sidecar,m->state,BITS);fprintf(sidecar,"}\n");}
    active=1;vpi_printf("XU_JOINT_BEGIN task=%d tick=%"PRIu64" macros=%u callback_ordinal=%"PRIu64"\n",task_id,start_tick,macro_count,begin_ordinal);return 0;
}
static PLI_INT32 begin_call(PLI_BYTE8 *unused) {
    vpiHandle it=vpi_iterate(vpiArgument,vpi_handle(vpiSysTfCall,NULL));char *prefix,*identity;int supplied;(void)unused;
    supplied=integer_argument(argument(it));prefix=string_argument(argument(it));identity=string_argument(argument(it));
    if(vpi_scan(it)){fail("extra begin argument");return 0;}numeric_transaction=0;
    begin_window(supplied,prefix,identity);free(prefix);free(identity);return 0;
}
static PLI_INT32 begin_transaction_call(PLI_BYTE8 *unused) {
    vpiHandle it=vpi_iterate(vpiArgument,vpi_handle(vpiSysTfCall,NULL));uint32_t a[6];char identity[192];(void)unused;
    if(!known_u32_arguments(it,a,6))return 0;
    if(a[0]>11||a[1]>INT32_MAX||a[2]<UINT32_C(0xa0000000)||a[2]>=UINT32_C(0xa0018800)||a[3]!=1||a[4]!=1||a[5]>1){fail("source REQUEST numeric identity differs");return 0;}
    snprintf(identity,sizeof(identity),"source_request cycle=%"PRIu32" addr=%08"PRIx32" read=1 valid=1 accept=%"PRIu32,a[1],a[2],a[5]);
    numeric_transaction=1;source_cycle=a[1];return begin_window((int)a[0],"task-joint",identity);
}
static int compare_entries(const void *a,const void *b){const Entry *x=a,*y=b;return x->key<y->key?-1:x->key>y->key;}
static void print_counts(FILE *f,Counts *c) { size_t i,j=0;Entry *a=allocate(c->size*sizeof(Entry));for(i=0;i<c->capacity;i++)if(c->items[i].used)a[j++]=c->items[i];qsort(a,j,sizeof(Entry),compare_entries);fputc('[',f);for(i=0;i<j;i++){if(i)fputc(',',f);fprintf(f,"[%"PRIu64",%"PRIu64"]",a[i].key,a[i].value);}fputc(']',f);free(a); }
static PLI_INT32 end_window(int supplied,const char *identity) {
    int p,s;unsigned i;
    if(!active||finished){fail("end outside active window");return 0;}
    if(supplied!=task_id||!identity){fail("end task/arguments differ");return 0;}
    end_tick=now_tick();end_ordinal=next_ordinal(end_tick);if(end_tick<=start_tick){fail("nonpositive activity duration");return 0;}active=0;finished=1;
    fprintf(stats,"{\"schema\":\"xu-sram-joint-projections-v1\",\"status\":\"CAPTURED_CALLBACK_ORDER_REQUIRES_SIMULATOR_AND_SAIF_CALIBRATION_NOT_QUALIFIED\",\"task_id\":%d,\"start_tick\":%"PRIu64",\"end_tick\":%"PRIu64",\"duration_ticks\":%"PRIu64",\"timescale_fs\":1,\"begin_callback_ordinal\":%"PRIu64",\"end_callback_ordinal\":%"PRIu64",\"begin_transaction\":",task_id,start_tick,end_tick,end_tick-start_tick,begin_ordinal,end_ordinal);json_string(stats,begin_identity);fprintf(stats,",\"end_transaction\":");json_string(stats,identity);fprintf(stats,",\"transaction_argument_encoding\":\"%s\",\"macro_count\":%u,\"pin_bits_per_macro\":67,\"liberty_arc_count\":121}\n",numeric_transaction?"known-uint32-v1":"legacy-vpi-string",macro_count);
    for(i=0;i<macro_count;i++){
        Macro *m=macros[i];for(p=0;p<BITS;p++)m->pin_dwell[p][m->state[p]]+=end_tick-m->pin_last[p];for(p=0;p<PROJS;p++)touch(m,p,end_tick);flush_pending(m,m->pending_tick==end_tick||m->pending_tick==start_tick);
        fprintf(stats,"{\"macro\":");json_string(stats,m->name);fprintf(stats,",\"callback_events\":%"PRIu64",\"final_state_lsb_ports\":",m->callback_events);state_string(stats,m->state,BITS);
        fprintf(stats,",\"pin_dwell\":[");for(p=0;p<BITS;p++){if(p)fputc(',',stats);fputc('[',stats);for(s=0;s<4;s++){if(s)fputc(',',stats);fprintf(stats,"%"PRIu64,m->pin_dwell[p][s]);}fputc(']',stats);}fprintf(stats,"],\"pin_transitions\":[");for(p=0;p<BITS;p++){if(p)fputc(',',stats);fputc('[',stats);for(s=0;s<16;s++){if(s)fputc(',',stats);fprintf(stats,"%"PRIu64,m->pin_trans[p][s]);}fputc(']',stats);}fprintf(stats,"],\"projection_dwell\":");print_counts(stats,&m->dwell);fprintf(stats,",\"projection_transitions\":");print_counts(stats,&m->transitions);fprintf(stats,"}\n");
        fprintf(sidecar,"{\"macro\":");json_string(sidecar,m->name);fprintf(sidecar,",\"end_tick\":%"PRIu64",\"callback_ordinal\":%"PRIu64",\"final_state_lsb_ports\":",end_tick,end_ordinal);state_string(sidecar,m->state,BITS);fprintf(sidecar,"}\n");
    }
    fprintf(stats,"{\"complete\":true,\"macro_count\":%u,\"simultaneous_records\":%"PRIu64"}\n",macro_count,sidecar_records);
    if(fclose(stats)||fclose(sidecar)){fail("output close failed");return 0;}
    vpi_printf("XU_JOINT_COMPLETE task=%d tick=%"PRIu64" duration_ticks=%"PRIu64" macros=%u simultaneous_records=%"PRIu64" NOT_QUALIFIED\n",task_id,end_tick,end_tick-start_tick,macro_count,sidecar_records);free(begin_identity);begin_identity=NULL;return 0;
}
static PLI_INT32 end_call(PLI_BYTE8 *unused) {
    vpiHandle it=vpi_iterate(vpiArgument,vpi_handle(vpiSysTfCall,NULL));int supplied;char *identity;(void)unused;
    supplied=integer_argument(argument(it));identity=string_argument(argument(it));
    if(vpi_scan(it)||numeric_transaction){fail("end task/arguments differ");return 0;}
    end_window(supplied,identity);free(identity);return 0;
}
static PLI_INT32 end_transaction_call(PLI_BYTE8 *unused) {
    vpiHandle it=vpi_iterate(vpiArgument,vpi_handle(vpiSysTfCall,NULL));uint32_t a[7];char identity[256];(void)unused;
    if(!known_u32_arguments(it,a,7))return 0;
    if(!numeric_transaction||a[0]>11||a[1]>INT32_MAX||a[2]<source_cycle||a[2]>=a[1]||a[3]!=UINT32_C(0xa00517fc)||a[4]!=1||a[5]!=1||a[6]!=50688){fail("final RETIRE numeric identity differs");return 0;}
    snprintf(identity,sizeof(identity),"final_y_retire cycle=%"PRIu32" request_cycle=%"PRIu32" addr=%08"PRIx32" response_valid=1 response_ready=1 writes=50688",a[1],a[2],a[3]);
    return end_window((int)a[0],identity);
}
static PLI_INT32 unfinished(p_cb_data cb){(void)cb;if(active) vpi_printf("XU_JOINT_INCOMPLETE active window at end of simulation; outputs have no completion footer\n");return 0;}
void xu_sram_joint_register_tasks(void) {
    s_vpi_systf_data t;s_cb_data c;memset(&t,0,sizeof(t));t.type=vpiSysTask;t.tfname="$xu_sram_joint_register";t.calltf=register_call;vpi_register_systf(&t);t.tfname="$xu_sram_joint_begin";t.calltf=begin_call;vpi_register_systf(&t);t.tfname="$xu_sram_joint_end";t.calltf=end_call;vpi_register_systf(&t);t.tfname="$xu_sram_joint_begin_transaction";t.calltf=begin_transaction_call;vpi_register_systf(&t);t.tfname="$xu_sram_joint_end_transaction";t.calltf=end_transaction_call;vpi_register_systf(&t);memset(&c,0,sizeof(c));c.reason=cbEndOfSimulation;c.cb_rtn=unfinished;vpi_register_cb(&c);
}
void (*vlog_startup_routines[])(void)={xu_sram_joint_register_tasks,0};
