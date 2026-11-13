#include "Vdma32_test_top.h"
#include "verilated.h"
#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

static void req(bool ok,const std::string&s){if(!ok)throw std::runtime_error(s);}
static int64_t sx(uint64_t x,int n){return int64_t(x<<(64-n))>>(64-n);}
static std::vector<int64_t> load(const std::string&p,int bits,size_t n){
 std::ifstream f(p);req(bool(f),"open "+p);std::string s;std::vector<int64_t> v;
 while(f>>s)v.push_back(sx(std::stoull(s,nullptr,16),bits));req(v.size()==n,"size "+p);return v;
}
static uint32_t rne(int64_t x){int64_t q=x/512,r=x%512;if(r<0){--q;r+=512;}if(r>256||(r==256&&(q&1)))++q;return uint32_t(q);}
struct Sim {
 Vdma32_test_top d;uint64_t cycles=0,accepts=0,retires=0,reads=0,writes=0;
 uint64_t first=0,last=0;bool inflight=false,pread=false,stall=false,armed=false,injectRead=true,injected=false;
 bool finalHold=false,finalHeld=false;unsigned holdRemaining=0,heldEdges=0;
 uint32_t paddr=0,injectAddress=0;
 Sim(){d.clk=0;d.rst_n=0;d.cfg_cmd_valid=0;d.cfg_cmd_addr=0;d.cfg_cmd_read=1;d.cfg_cmd_wdata=0;
  d.cfg_cmd_wmask=15;d.cfg_rsp_ready=1;d.cpu_cmd_valid=0;d.cpu_cmd_addr=0;d.cpu_cmd_read=1;
  d.cpu_cmd_wdata=0;d.cpu_cmd_wmask=15;d.cpu_rsp_ready=1;d.response_enable=1;d.inject_error=0;
  tick(4);d.rst_n=1;tick(2);}
 void eval(){d.clk=0;d.eval();}
 void tick(unsigned n=1){for(unsigned i=0;i<n;i++){
  if(finalHold&&!finalHeld&&inflight&&!pread&&paddr==0xa0038bfc){holdRemaining=97;finalHeld=true;}
  bool holding=holdRemaining!=0;
  d.response_enable=(!stall||(cycles%13<8))&&!holding;d.inject_error=0;eval();
  if(holding){req(d.debug_busy&&!d.debug_done,"completion before final write response retirement");--holdRemaining;++heldEdges;}
  if(d.rst_n&&armed&&d.dma_retire&&inflight&&pread==injectRead&&(!injectAddress||paddr==injectAddress)){d.inject_error=1;eval();armed=false;injected=true;}
  if(!d.rst_n){inflight=false;}else{
   if(d.dma_retire){req(inflight,"orphan DMA response");inflight=false;++retires;last=cycles;}
   if(d.dma_accept){req(!inflight,"DMA outstanding >1");inflight=true;pread=d.dma_read;paddr=d.dma_addr;
    if(!first)first=cycles;++accepts;if(pread)++reads;else++writes;}
   if(d.debug_done)req(!inflight&&!d.debug_pending&&!d.debug_locked&&!d.debug_coreactive,"early completion");
  }
  ++cycles;d.clk=1;d.eval();eval();
 }}
 uint32_t cfg(bool rd,uint32_t off,uint32_t data=0,bool error=false){
  d.cfg_cmd_valid=1;d.cfg_cmd_read=rd;d.cfg_cmd_addr=0x10042300+off;d.cfg_cmd_wdata=data;eval();
  unsigned t=0;while(!d.cfg_cmd_ready){tick();req(++t<1000,"cfg accept timeout");}tick();d.cfg_cmd_valid=0;eval();
  t=0;while(!d.cfg_rsp_valid){tick();req(++t<1000,"cfg response timeout");}
  req(bool(d.cfg_rsp_err)==error,"cfg error off="+std::to_string(off));uint32_t value=d.cfg_rsp_rdata;tick();return value;
 }
 uint32_t host(bool rd,uint32_t addr,uint32_t data=0){
  req(!d.debug_busy,"host payload access overlaps DMA task");d.cpu_cmd_valid=1;d.cpu_cmd_read=rd;
  d.cpu_cmd_addr=addr;d.cpu_cmd_wdata=data;eval();unsigned t=0;
  while(!d.cpu_cmd_ready){tick();req(++t<1000,"host accept timeout");}tick();d.cpu_cmd_valid=0;eval();
  t=0;while(!d.cpu_rsp_valid){tick();req(++t<1000,"host response timeout");}
  req(!d.cpu_rsp_err,"host error");uint32_t value=d.cpu_rsp_rdata;tick();return value;
 }
 void waitIdle(bool success){unsigned n=0;while(d.debug_busy){tick();req(++n<2000000,"task timeout state="+std::to_string(d.debug_state));}
  req(!inflight&&!d.debug_pending&&!d.debug_locked,"idle not drained");
  req(bool(d.debug_error)!=success,"wrong task error");req(bool(d.debug_done)==success,"wrong task done");}
 uint32_t clear(){cfg(false,4,1);unsigned n=0;while(d.debug_busy){tick();req(++n<5000,"clear timeout");}
  req(cfg(true,8)==8,"clear status");return cfg(true,0x24);}
 void descriptors(){cfg(false,0x10,0xa0000000);cfg(false,0x14,0xa0008000);
  cfg(false,0x18,0xa0018000);cfg(false,0x1c,0xa0020000);}
};
int main(int argc,char**argv){try{
 Verilated::commandArgs(argc,argv);req(argc>=5,"usage vectors_root tasks rows output_json [faults] [stall] [final_hold]");
 const std::string root=argv[1];unsigned tasks=std::stoul(argv[2]),rows=std::stoul(argv[3]);
 req(tasks>=1&&tasks<=12&&(rows==1||rows==8),"tasks/rows");bool faults=argc>5&&std::stoi(argv[5]);
 Sim s;req(s.cfg(true,0)==0x444d4131,"DMA ID");req(s.cfg(true,0x4c)==0x00082001,"DMA capabilities");
 std::ofstream out(argv[4]);out<<"{\n\"scope\":\"DMA plus original32 arbiter/endpoint over256 functional macros; no CPU/SystemBus, PPA or official whole-task timing\",\n\"layers\":[\n";
 uint64_t total=0,payload=0,totalclear=0,checked=0;
 for(unsigned task=0;task<tasks;task++){
  std::string v=root+"/layer_"+(task<10?"0":"")+std::to_string(task);
  auto x=load(v+"/x.mem",16,6336),w=load(v+"/w.mem",16,16384),b=load(v+"/bias.mem",40,256);
  auto gold=load(v+"/y32.mem",32,25344);
  for(unsigned r=0;r<99;r++)for(unsigned c=0;c<256;c++){
   int64_t expected=b[c];for(unsigned k=0;k<64;k++)expected+=x[r*64+k]*w[k*256+c];
   req(rne(expected)==uint32_t(gold[r*256+c]),"independent tensor oracle");}
  s.stall=false;
  for(unsigned i=0;i<x.size();i++)s.host(false,0xa0000000+4*i,uint32_t(x[i]));
  for(unsigned i=0;i<w.size();i+=2)s.host(false,0xa0008000+2*i,uint32_t(uint16_t(w[i]))|(uint32_t(uint16_t(w[i+1]))<<16));
  for(unsigned i=0;i<b.size();i++){s.host(false,0xa0018000+8*i,uint32_t(b[i]));s.host(false,0xa0018004+8*i,uint32_t(uint64_t(b[i])>>32)&255);}
  for(unsigned i=0;i<25344;i++)s.host(false,0xa0020000+4*i,0xdeadbeef);
  uint32_t clear=s.clear();s.descriptors();uint64_t a=s.accepts,r=s.retires,rd=s.reads,wr=s.writes;
  s.finalHold=argc>7&&std::stoi(argv[7]);s.finalHeld=false;s.holdRemaining=0;
  s.first=0;s.last=0;s.stall=argc>6&&std::stoi(argv[6]);s.cfg(false,4,rows==8?0x802:2);s.waitIdle(true);s.stall=false;
  if(s.finalHold)req(s.finalHeld&&s.holdRemaining==0,"last write response was not held and retired");s.finalHold=false;
  uint32_t cyc=s.cfg(true,0x20),wb=s.cfg(true,0x44),run=s.cfg(true,0x48),mac=s.cfg(true,0x34),pop=s.cfg(true,0x30);
  uint32_t stalls=s.cfg(true,0x3c),rspwait=s.cfg(true,0x40),crwrites=s.cfg(true,0x38);
  req(s.accepts-a==40384&&s.retires-r==40384,"accepted/retired count");
  req(s.reads-rd==15040&&s.writes-wr==25344,"read/write count");
  req(s.cfg(true,0x28)==15040&&s.cfg(true,0x2c)==25344&&pop==3168,"DMA counter count");
  req(mac==(rows==8?26624:202752),"MAC count");req(crwrites==54272,"W/X clear counter");
  uint64_t span=s.last-s.first+1;
  for(unsigned i=0;i<25344;i++)req(s.host(true,0xa0020000+4*i)==uint32_t(gold[i]),"Y32 mismatch layer="+std::to_string(task)+" index="+std::to_string(i));
  total+=clear+cyc;payload+=cyc;totalclear+=clear;checked+=25344;
  if(task)out<<",\n";out<<"{\"task\":"<<task<<",\"clear\":"<<clear<<",\"payload\":"<<cyc<<",\"wb\":"<<wb<<",\"run\":"<<run
   <<",\"source_to_last_write_response\":"<<span<<",\"cmd_stall\":"<<stalls<<",\"response_wait\":"<<rspwait<<",\"exact_y32\":25344,\"reads32\":15040,\"writes32\":25344}";
  out.flush();std::cout<<"DMA32_LAYER_PASS layer="<<task<<" clear="<<clear<<" payload="<<cyc<<" WB="<<wb<<" RUN="<<run<<" total="<<clear+cyc<<" cmdstall="<<stalls<<" rspwait="<<rspwait<<" exact=25344\n"<<std::flush;
 }
 unsigned faultcases=0;
 if(faults){
  for(bool read:{true,false}){
   s.clear();s.descriptors();s.armed=true;s.injectRead=read;s.injected=false;
   s.cfg(false,4,0x802);s.waitIdle(false);req(s.injected,"fault not injected");req(s.cfg(true,0xc)==1,"first error code");
   auto a=s.accepts;s.tick(100);req(s.accepts==a,"automatic retry after error");req(s.cfg(true,8)==4,"error final status");++faultcases;
  }
  for(unsigned phase=0;phase<3;phase++){
   s.clear();s.descriptors();s.cfg(false,4,0x802);unsigned n=0;
   uint64_t oldwrites=s.writes;
   while((phase==0?s.d.debug_state!=2:phase==1?s.d.debug_state!=3:s.writes==oldwrites)){s.tick();req(++n<100000,"reset phase timeout");}
   s.d.rst_n=0;s.tick(3);s.d.rst_n=1;s.tick(8);
   req(!s.d.debug_busy&&!s.d.debug_done&&!s.d.debug_error&&!s.inflight&&!s.d.debug_pending&&!s.d.debug_locked,"reset stale state");
   s.tick(30);req(!s.d.debug_done,"reset generated completion");++faultcases;
  }
 }
 out<<"\n],\n\"rows\":"<<rows<<",\n\"exact_y32\":"<<checked<<",\n\"payload_total\":"<<payload<<",\n\"clear_total\":"<<totalclear
 <<",\n\"principal_cycles\":"<<total<<",\n\"fault_reset_cases\":"<<faultcases<<",\n\"last_y_response_held_edges\":"<<s.heldEdges<<",\n\"status\":\"PASS\"\n}\n";
 std::cout<<"DMA32_CAMPAIGN_PASS tasks="<<tasks<<" exact="<<checked<<" principal="<<total<<" fault_reset_cases="<<faultcases<<"\n";
}catch(const std::exception&e){std::cerr<<"FAIL "<<e.what()<<"\n";return 1;}}
