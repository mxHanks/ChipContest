/* xu passive mapped public port adapter + exact original memory preload.
 * vpi_put_value destinations are restricted to TB observation registers and
 * the original 288 ITCM/shared vendor mem words. Never Q or another DUT FF.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include "vpi_user.h"
#include "xu_mapped_expected111.h"
static vpiHandle macro_mod[336], macro_mem[336], macro_words[336][256], source[22], target[22], accel_clk, accel_reset;
static unsigned macro_seen[336], initialized, preload_calls, clock_reset_edges;
static unsigned previous_clk, reset_seen, clock_ready, interface_seen[2];
static int failed;
static vpiHandle clock_callback_handle;
static const char *const port_names[12]={"cmd_valid","cmd_ready","cmd_addr","cmd_read","cmd_wdata","cmd_wmask","rsp_valid","rsp_ready","rsp_rdata","rsp_err","clk","rst_n"};
static const int widths[12]={1,1,32,1,32,4,1,1,32,1,1,1};
static const char *const shared_tb[10]={"cmd_valid","cmd_ready","cmd_addr","cmd_read","cmd_wdata","cmd_wmask","rsp_valid","rsp_ready","rsp_rdata","rsp_err"};
static const char *const accel_tb[12]={"a_cmd_valid","a_cmd_ready","a_cmd_addr","a_cmd_read","a_cmd_wdata","a_cmd_wmask","a_rsp_valid","a_rsp_ready","a_rsp_rdata","a_rsp_err","a_clk","a_rst_n"};
static void reject(const char *why,const char *name) {failed=1;vpi_printf("XU_MAPPED111_ADAPTER_REJECT reason=%s object=%s\n",why,name?name:"<null>");vpi_control(vpiFinish,1);}
static void canonical(const char *in,char *out,size_t size) {size_t n=0;while(*in){unsigned char c=(unsigned char)*in++;if(c=='\\'||isspace(c))continue;if(n+1>=size){reject("overlong_inventory_name",in);break;}out[n++]=(char)c;}out[n]='\0';}
static unsigned scalar(vpiHandle h) {s_vpi_value v;memset(&v,0,sizeof(v));v.format=vpiScalarVal;vpi_get_value(h,&v);return(unsigned)v.value.scalar;}
static void tb_int(const char *name,unsigned n) {char full[256];s_vpi_value v;vpiHandle h;snprintf(full,sizeof(full),"tb_xu_soc_ppa.%s",name);h=vpi_handle_by_name((PLI_BYTE8 *)full,NULL);if(!h){reject("missing_TB_observer_register",full);return;}memset(&v,0,sizeof(v));v.format=vpiIntVal;v.value.integer=(PLI_INT32)n;vpi_put_value(h,&v,NULL,vpiNoDelay);}
static PLI_INT32 clock_callback(p_cb_data unused) {unsigned clk=scalar(accel_clk),rst=scalar(accel_reset);(void)unused;if(clock_ready&&clk!=vpi0&&clk!=vpi1){reject("accelerator_clock_unknown_after_ready","actual_clock");return 0;}if(clk==vpi1&&previous_clk==vpi0){if(rst==vpi0){if(clock_ready)reject("accelerator_reset_reasserted", "actual_clock");reset_seen=1;++clock_reset_edges;}else if(rst==vpi1){if(reset_seen)clock_ready=1;}else if(reset_seen)reject("accelerator_reset_unknown_after_assertion","actual_clock");}previous_clk=clk;return 0;}
static void bind_interface(vpiHandle mod,int accelerator) {unsigned i,count=accelerator?12:10;if(interface_seen[accelerator]++){reject("duplicate_public_interface_module",accelerator?"accelerator":"shared");return;}for(i=0;i<count;++i){char full[256];unsigned index=accelerator?10+i:i;source[index]=vpi_handle_by_name((PLI_BYTE8 *)port_names[i],mod);snprintf(full,sizeof(full),"tb_xu_soc_ppa.%s",accelerator?accel_tb[i]:shared_tb[i]);target[index]=vpi_handle_by_name((PLI_BYTE8 *)full,NULL);if(!source[index]||!target[index]||vpi_get(vpiSize,source[index])!=widths[i]||vpi_get(vpiSize,target[index])!=widths[i])reject("public_port_or_TB_width",full);}if(accelerator){accel_clk=source[20];accel_reset=source[21];}}
/* Every mapped macro is independently checked here. The actual105 primitive
 * is a prerequisite for packing/read/hold behavior, not a substitute for this
 * full-SoC ownership/row proof. Optional metadata is counted when unavailable.
 */
static int geometry(unsigned tag) {
 unsigned r,j,reg_words=0,memory_words=0,index_present=0,parent_present=0,scope_present=0;
 char modname[8192],memname[8192],want[8224],full[8192];const char *text;vpiHandle parent,scope;
 text=vpi_get_str(vpiFullName,macro_mod[tag]);canonical(text?text:"",modname,sizeof(modname));
 text=macro_mem[tag]?vpi_get_str(vpiFullName,macro_mem[tag]):NULL;canonical(text?text:"",memname,sizeof(memname));
 snprintf(want,sizeof(want),"%s.mem",modname);
 if(!macro_mem[tag]||strcmp(modname,xu_expected111[tag].name)!=0||strcmp(want,memname)!=0||vpi_get(vpiSize,macro_mem[tag])!=256||(vpi_get(vpiType,macro_mem[tag])!=vpiMemory&&vpi_get(vpiType,macro_mem[tag])!=vpiRegArray)) {reject("owning_memory_name_type_or_256_rows",modname);return 0;}
 parent=vpi_handle(vpiParent,macro_mem[tag]);scope=vpi_handle(vpiScope,macro_mem[tag]);
 if((parent&&!vpi_compare_objects(parent,macro_mod[tag]))||(scope&&!vpi_compare_objects(scope,macro_mod[tag]))) {reject("owning_memory_parent_or_scope_disagrees",modname);return 0;}
 for(j=0;j<tag;++j)if(macro_mem[j]&&vpi_compare_objects(macro_mem[tag],macro_mem[j])) {reject("macro_memories_alias",modname);return 0;}
 for(r=0;r<256;++r) {
  vpiHandle again,ix;int type;s_vpi_value iv;
  macro_words[tag][r]=vpi_handle_by_index(macro_mem[tag],(PLI_INT32)r);
  if(!macro_words[tag][r]) {reject("indexed_word_missing",modname);return 0;}
  type=vpi_get(vpiType,macro_words[tag][r]);
  if((type!=vpiMemoryWord&&type!=vpiReg)||vpi_get(vpiSize,macro_words[tag][r])!=64) {reject("indexed_word_native_type_or_64_bits",modname);return 0;}
  if(type==vpiReg)++reg_words;else ++memory_words;
  text=vpi_get_str(vpiFullName,macro_words[tag][r]);canonical(text?text:"",full,sizeof(full));snprintf(want,sizeof(want),"%s[%u]",memname,r);
  if(strcmp(full,want)!=0) {reject("indexed_word_not_in_exact_owning_memory",modname);return 0;}
  again=vpi_handle_by_index(macro_mem[tag],(PLI_INT32)r);
  if(!again||!vpi_compare_objects(macro_words[tag][r],again)) {reject("indexed_word_identity_not_repeatable",modname);return 0;}
  for(j=0;j<r;++j)if(vpi_compare_objects(macro_words[tag][r],macro_words[tag][j])) {reject("indexed_word_aliases_another_row",modname);return 0;}
  parent=vpi_handle(vpiParent,macro_words[tag][r]);scope=vpi_handle(vpiScope,macro_words[tag][r]);
  if(parent) {++parent_present;if(!vpi_compare_objects(parent,macro_mem[tag])&&!vpi_compare_objects(parent,macro_mod[tag])) {reject("native_word_parent_disagrees",modname);return 0;}}
  if(scope) {++scope_present;if(!vpi_compare_objects(scope,macro_mod[tag])&&!vpi_compare_objects(scope,macro_mem[tag])) {reject("native_word_scope_disagrees",modname);return 0;}}
  ix=vpi_handle(vpiIndex,macro_words[tag][r]);if(ix) {++index_present;memset(&iv,0,sizeof(iv));iv.format=vpiIntVal;vpi_get_value(ix,&iv);if(iv.value.integer!=(PLI_INT32)r) {reject("native_word_index_disagrees",modname);return 0;}}
 }
 vpi_printf("XU_MAPPED111_GEOMETRY tag=%u role=%d status=PASS rows=256 row_bits=64 unique=256 memory_type=%d reg_words=%u memoryword_words=%u parent_present=%u scope_present=%u index_present=%u name=%s\n",tag,xu_expected111[tag].role,vpi_get(vpiType,macro_mem[tag]),reg_words,memory_words,parent_present,scope_present,index_present,modname);
 return 1;
}

static void walk(vpiHandle mod) {const char *p=vpi_get_str(vpiFullName,mod);char *name=p?strdup(p):NULL;const char *ref=vpi_get_str(vpiDefName,mod);vpiHandle it,child;unsigned i;if(ref&&strcmp(ref,"RAMSP1024X16")==0){char key[8192];unsigned found=0;canonical(name?name:"",key,sizeof(key));for(i=0;i<336;++i)if(strcmp(key,xu_expected111[i].name)==0){++found;++macro_seen[i];macro_mod[i]=mod;macro_mem[i]=vpi_handle_by_name((PLI_BYTE8 *)"mem",mod);}if(found!=1)reject("inventory_macro_bijection",name);}if(name&&strcmp(name,"tb_xu_soc_ppa.dut.u_shared")==0)bind_interface(mod,0);if(name&&strlen(name)>=strlen(".u_accel_icb_slave")&&strcmp(name+strlen(name)-strlen(".u_accel_icb_slave"),".u_accel_icb_slave")==0)bind_interface(mod,1);it=vpi_iterate(vpiModule,mod);if(it)while((child=vpi_scan(it))!=NULL)walk(child);free(name);}
static PLI_INT32 prepare(PLI_BYTE8 *unused) {vpiHandle root;unsigned i;static s_cb_data cb;static s_vpi_time time;static s_vpi_value value;(void)unused;if(initialized++){reject("duplicate_prepare","");return 0;}root=vpi_handle_by_name((PLI_BYTE8 *)"tb_xu_soc_ppa.dut",NULL);if(!root){reject("mapped_root_absent","");return 0;}walk(root);for(i=0;i<336;++i){if(macro_seen[i]!=1)reject("missing_inventory_macro",xu_expected111[i].name);else if(!geometry(i))return 0;}for(i=0;i<22;++i)if(!source[i]||!target[i])reject("public_interface_missing","");if(failed)return 0;previous_clk=scalar(accel_clk);memset(&cb,0,sizeof(cb));memset(&time,0,sizeof(time));memset(&value,0,sizeof(value));time.type=vpiSuppressTime;value.format=vpiSuppressVal;cb.reason=cbValueChange;cb.cb_rtn=clock_callback;cb.obj=accel_clk;cb.time=&time;cb.value=&value;clock_callback_handle=vpi_register_cb(&cb);if(!clock_callback_handle){reject("actual_clock_callback_registration_failed","actual_clock");return 0;}vpi_printf("XU_MAPPED111_ADAPTER_READY macros=336 interface_bits_preserve_4state=1 preload_allowed=288 Q_WRITES=0 OTHER_DUT_FF_WRITES=0\n");return 0;}
static PLI_INT32 sample(PLI_BYTE8 *unused) {unsigned i;(void)unused;if(initialized!=1||failed){reject("sample_before_valid_prepare","");return 0;}for(i=0;i<22;++i){s_vpi_value v;memset(&v,0,sizeof(v));v.format=vpiVectorVal;vpi_get_value(source[i],&v);vpi_put_value(target[i],&v,NULL,vpiNoDelay);}tb_int("a_reset_edges",clock_reset_edges);tb_int("a_reset_seen",reset_seen);tb_int("a_reset_ready",clock_ready);return 0;}
static PLI_INT32 preload(PLI_BYTE8 *unused) {vpiHandle words,ram;unsigned i,r,k,b,count=0;(void)unused;if(initialized!=1||failed||preload_calls++){reject("invalid_or_duplicate_preload","");return 0;}words=vpi_handle_by_name((PLI_BYTE8 *)"tb_xu_soc_ppa.xu_program_words",NULL);ram=vpi_handle_by_name((PLI_BYTE8 *)"tb_xu_soc_ppa.ram",NULL);if(!words||!ram){reject("original_TB_memories_absent","");return 0;}for(i=0;i<336;++i)if(xu_expected111[i].role){++count;for(r=0;r<256;++r){s_vpi_vecval out[2]={{0,0},{0,0}};s_vpi_value value;for(k=0;k<4;++k){unsigned address=(unsigned)xu_expected111[i].bank*1024+4*r+k;vpiHandle word=vpi_handle_by_index(xu_expected111[i].role==1?words:ram,(PLI_INT32)address);if(!word){reject("original_TB_word_absent",xu_expected111[i].name);return 0;}memset(&value,0,sizeof(value));value.format=vpiVectorVal;vpi_get_value(word,&value);for(b=0;b<16;++b){unsigned source_bit=(unsigned)xu_expected111[i].lane*16+b,output_bit=4*b+k,si=source_bit/32,oi=output_bit/32,sp=source_bit%32,op=output_bit%32;if(((uint32_t)value.value.vector[si].aval>>sp)&1u)out[oi].aval|=(PLI_INT32)(UINT32_C(1)<<op);if(((uint32_t)value.value.vector[si].bval>>sp)&1u)out[oi].bval|=(PLI_INT32)(UINT32_C(1)<<op);}}memset(&value,0,sizeof(value));value.format=vpiVectorVal;value.value.vector=out;{vpiHandle destination=vpi_handle_by_index(macro_mem[i],(PLI_INT32)r);s_vpi_value check;unsigned half;if(!destination||!vpi_compare_objects(destination,macro_words[i][r])){reject("native_preload_word_missing",xu_expected111[i].name);return 0;}vpi_put_value(destination,&value,NULL,vpiNoDelay);memset(&check,0,sizeof(check));check.format=vpiVectorVal;vpi_get_value(destination,&check);for(half=0;half<2;++half)if(check.value.vector[half].aval!=out[half].aval||check.value.vector[half].bval!=out[half].bval){reject("native_preload_4state_readback_mismatch",xu_expected111[i].name);return 0;}}}}if(count!=288)reject("original_preload_macro_count","");vpi_printf("XU_MAPPED111_PRELOAD_DONE itcm=32 shared=256 words_per_macro=256 bits_per_row=64 arbitrary_XZ_preserved=1 Q_WRITES=0\n");return 0;}
void xu_mapped_task00_register111(void) {static const char *names[]={"$xu_mapped111_prepare","$xu_mapped111_sample","$xu_mapped111_preload"};PLI_INT32(*calls[])(PLI_BYTE8 *)={prepare,sample,preload};unsigned i;for(i=0;i<3;++i){s_vpi_systf_data d;memset(&d,0,sizeof(d));d.type=vpiSysTask;d.tfname=(PLI_BYTE8 *)names[i];d.calltf=calls[i];vpi_register_systf(&d);}}
void (*vlog_startup_routines[])(void)={xu_mapped_task00_register111,NULL};
