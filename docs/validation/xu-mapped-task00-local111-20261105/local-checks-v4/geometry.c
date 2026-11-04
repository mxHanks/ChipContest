#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include "../xu_mapped_task00_vpi111.c"
typedef struct {int kind,index;} Obj;
static Obj module_object={0,0},memory_object={1,0},words[256],indices[256],different={2,255};
static int mode,reads255;
static Obj *obj(vpiHandle h){return(Obj*)h;}
void vpi_get_value(vpiHandle h,p_vpi_value v){v->value.integer=obj(h)->index;}
PLI_INT32 vpi_printf(const char *fmt,...){PLI_INT32 r;va_list ap;va_start(ap,fmt);r=vprintf(fmt,ap);va_end(ap);return r;}
void vpi_control(PLI_INT32 operation,...){(void)operation;}
PLI_INT32 vpi_get(PLI_INT32 property,vpiHandle h){Obj*o=obj(h);if(property==vpiType){if(o->kind==0)return vpiModule;if(o->kind==1)return mode==1?vpiMemory:vpiRegArray;return mode==1?vpiMemoryWord:mode==4&&o->index==255?vpiNet:vpiReg;}if(property==vpiSize)return o->kind==1?256:mode==3&&o->index==255?63:64;return -1;}
PLI_BYTE8 *vpi_get_str(PLI_INT32 property,vpiHandle h){static char buffers[8][8300];static unsigned next;char *out=buffers[(next++)%8];Obj *o=obj(h);if(property!=vpiFullName)return NULL;if(o->kind==0)snprintf(out,8300,"%s",xu_expected111[0].name);else if(o->kind==1)snprintf(out,8300,"%s.%s",xu_expected111[0].name,mode==5?"wrong":"mem");else snprintf(out,8300,"%s.mem[%d]",xu_expected111[0].name,o->index);return(PLI_BYTE8*)out;}
vpiHandle vpi_handle_by_index(vpiHandle h,PLI_INT32 row){if(h!=(vpiHandle)&memory_object||row<0||row>255)return NULL;if(row==255){++reads255;if(mode==2)return NULL;if(mode==6)return(vpiHandle)&words[0];if(mode==7&&reads255>1)return(vpiHandle)&different;}return(vpiHandle)&words[row];}
vpiHandle vpi_handle(PLI_INT32 relation,vpiHandle h){Obj*o=obj(h);if(relation==vpiParent){if(o->kind==1)return(vpiHandle)&module_object;if(o->kind==2)return mode==8&&o->index==255?(vpiHandle)&words[1]:(vpiHandle)&memory_object;}if(relation==vpiScope)return(vpiHandle)&module_object;if(relation==vpiIndex&&o->kind==2){if(mode==9&&o->index==255)return(vpiHandle)&indices[254];return(vpiHandle)&indices[o->index];}return NULL;}
PLI_INT32 vpi_compare_objects(vpiHandle a,vpiHandle b){return a==b;}
int main(int argc,char **argv){unsigned i;mode=argc>1?atoi(argv[1]):0;for(i=0;i<256;++i){words[i].kind=2;words[i].index=(int)i;indices[i].kind=3;indices[i].index=(int)i;}macro_mod[0]=(vpiHandle)&module_object;macro_mem[0]=(vpiHandle)&memory_object;int ok=geometry(0);printf("REVIEW111_GEOMETRY mode=%d accepted=%d rejected=%d row255_lookups=%d MECHANISM_ONLY_NOT_NATIVE_VCS\n",mode,ok,failed,reads255);return (mode<=1)?!(ok&&!failed):(ok||!failed);}
