/* xu read-only mapped elaboration probe. No signal or memory writes. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include "vpi_user.h"
#include "xu_expected_macros74.h"
static unsigned xu_seen[XU_EXPECTED_MACROS];
static unsigned xu_macros, xu_pins, xu_modules, xu_shared, xu_accel, xu_preload;
static int xu_failed;
static void xu_error(const char *why, const char *name) {
  vpi_printf("XU_MAPPED_PROBE_ERROR reason=%s object=%s\n", why, name ? name : "<null>");
  xu_failed=1;
}
static void xu_canonical(const char *in, char *out, size_t size) {
  size_t n=0;
  while (*in) {
    unsigned char c=(unsigned char)*in++;
    if (c=='\\' || isspace(c)) continue;
    if (n+1>=size) { xu_error("overlong_canonical_path", "path"); break; }
    out[n++]=(char)c;
  }
  out[n]='\0';
}
static void xu_port(vpiHandle mod, const char *role, const char *name, int width) {
  vpiHandle local=vpi_handle_by_name((PLI_BYTE8 *)name,mod);
  vpi_printf("XU_MAPPED_INTERFACE role=%s name=%s width=%d local_named_net=%d\n",role,name,local?vpi_get(vpiSize,local):-1,local!=NULL);
  if (!local || vpi_get(vpiSize,local)!=width) xu_error("named_interface_net_width_or_absence",name);
}
static void xu_interface(vpiHandle mod, const char *role) {
  static const char *names[]={"cmd_valid","cmd_ready","cmd_addr","cmd_read","cmd_wdata","cmd_wmask","rsp_valid","rsp_ready","rsp_rdata","rsp_err","clk","rst_n"};
  static const int widths[]={1,1,32,1,32,4,1,1,32,1,1,1};
  unsigned j;
  for (j=0;j<sizeof(widths)/sizeof(widths[0]);++j) xu_port(mod,role,names[j],widths[j]);
}
static void xu_macro(vpiHandle mod, const char *full) {
  char canonical[8192];
  unsigned i, match=0, bits=0, ports=0;
  vpiHandle port,mem,word;
  static const char *port_names[]={"A","CEN","CLK","D","EMA","EMAW","GWEN","Q","RET1N","WEN"};
  static const int port_widths[]={10,1,1,16,3,2,1,16,1,16};
  xu_canonical(full,canonical,sizeof(canonical));
  for (i=0;i<XU_EXPECTED_MACROS;++i) if (strcmp(canonical,xu_expected_macros[i])==0) {
    ++match; ++xu_seen[i];
    if (strstr(xu_expected_macros[i],".u_shared.") || strstr(xu_expected_macros[i],".u_e203_itcm_ram.")) ++xu_preload;
  }
  if (match!=1) xu_error("native_inventory_bijection",full);
  for (i=0;i<sizeof(port_widths)/sizeof(port_widths[0]);++i) {
    port=vpi_handle_by_name((PLI_BYTE8 *)port_names[i],mod);
    if (!port || vpi_get(vpiSize,port)!=port_widths[i]) xu_error("macro_named_port_width",port_names[i]);
    if (port) { bits+=(unsigned)vpi_get(vpiSize,port); ++ports; }
  }
  mem=vpi_handle_by_name((PLI_BYTE8 *)"mem",mod);
  word=mem ? vpi_handle_by_index(mem,0) : NULL;
  if (bits!=67 || !mem || !word || vpi_get(vpiSize,word)!=64 || vpi_get(vpiSize,mem)!=256) xu_error("vendor_67pin_or_256x64_mem_shape",full);
  vpi_printf("XU_MAPPED_MACRO name=%s ports=%u signal_bits=%u mem_words=%d word_bits=%d\n",full,ports,bits,mem?vpi_get(vpiSize,mem):-1,word?vpi_get(vpiSize,word):-1);
  ++xu_macros; xu_pins+=bits;
}
static void xu_walk(vpiHandle mod) {
  const char *value=vpi_get_str(vpiFullName,mod);
  char *full=value?strdup(value):NULL;
  const char *ref=vpi_get_str(vpiDefName,mod);
  vpiHandle it,child;
  ++xu_modules;
  if (ref && strcmp(ref,"RAMSP1024X16")==0) xu_macro(mod,full?full:"");
  if (full && strcmp(full,"tb_xu_soc_ppa.dut.u_shared")==0) { ++xu_shared; xu_interface(mod,"shared"); }
  if (full && strlen(full)>=strlen(".u_accel_icb_slave") && strcmp(full+strlen(full)-strlen(".u_accel_icb_slave"),".u_accel_icb_slave")==0) { ++xu_accel; xu_interface(mod,"accelerator"); }
  it=vpi_iterate(vpiModule,mod);
  if (it) while ((child=vpi_scan(it))!=NULL) xu_walk(child);
  free(full);
}
static PLI_INT32 xu_call(PLI_BYTE8 *unused) {
  vpiHandle top=vpi_handle_by_name((PLI_BYTE8 *)"tb_xu_soc_ppa.dut",NULL);
  unsigned i;
  (void)unused;
  if (!top) xu_error("mapped_top_absent","tb_xu_soc_ppa.dut"); else xu_walk(top);
  for (i=0;i<XU_EXPECTED_MACROS;++i) if (xu_seen[i]!=1) xu_error("missing_or_duplicate_macro",xu_expected_macros[i]);
  if (xu_macros!=336 || xu_pins!=22512 || xu_preload!=288 || xu_shared!=1 || xu_accel!=1) xu_error("required_scope_or_inventory_count","summary");
  vpi_printf("XU_MAPPED_INVENTORY_RESULT macros=%u pin_bits=%u preload_macros=%u shared_interfaces=%u accelerator_interfaces=%u modules=%u status=%s NOT_FUNCTIONAL_OR_ACTIVITY_OR_ENERGY_PROOF\n",xu_macros,xu_pins,xu_preload,xu_shared,xu_accel,xu_modules,xu_failed?"FAIL":"PASS");
  if (xu_failed) vpi_control(vpiFinish,1);
  return 0;
}
void xu_mapped_probe_register(void) {
  s_vpi_systf_data record;
  memset(&record,0,sizeof(record));
  record.type=vpiSysTask; record.tfname=(PLI_BYTE8 *)"$xu_mapped_inventory74"; record.calltf=xu_call;
  vpi_register_systf(&record);
}
void (*vlog_startup_routines[])(void)={xu_mapped_probe_register,NULL};
