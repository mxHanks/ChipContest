// Bounded coverage extension. Reuses the frozen R2 driver helpers and RTL model.
#define main dma64_original_main
#include <dma64_test.cpp>
#undef main

static std::vector<int64_t> fixture(Sim &s,const std::string &root,unsigned layer){
 std::string v=root+"/layer_"+(layer<10?"0":"")+std::to_string(layer);
 auto x=load(v+"/x.mem",16,6336),w=load(v+"/w.mem",16,16384),b=load(v+"/bias.mem",40,256);
 auto gold=load(v+"/y32.mem",32,25344);
 for(unsigned r=0;r<99;r++)for(unsigned c=0;c<256;c++){
  int64_t z=b[c];for(unsigned k=0;k<64;k++)z+=x[r*64+k]*w[k*256+c];
  req(rne(z)==uint32_t(gold[r*256+c]),"recovery independent numeric oracle");
 }
 for(unsigned i=0;i<x.size();i++)s.host(false,0xa0000000+4*i,uint32_t(x[i]));
 for(unsigned i=0;i<w.size();i+=2)s.host(false,0xa0008000+2*i,uint32_t(uint16_t(w[i]))|(uint32_t(uint16_t(w[i+1]))<<16));
 for(unsigned i=0;i<b.size();i++){
  s.host(false,0xa0018000+8*i,uint32_t(b[i]));s.host(false,0xa0018004+8*i,uint32_t(uint64_t(b[i])>>32)&255);
 }
 for(unsigned i=0;i<25344;i++)s.host(false,0xa0020000+4*i,0xdeadbeef);
 return gold;
}

int main(int argc,char **argv){try{
 Verilated::commandArgs(argc,argv);req(argc==3,"usage vectors_root output_json");
 Sim s;std::ofstream out(argv[2]);out<<"{\n\"scope\":\"Bounded common-reset recovery; unchanged R2 RTL model; public32 fixtures\",\n\"cases\":[\n";
 unsigned checked=0;
 for(unsigned phase=0;phase<3;phase++){
  // Each cancelled task uses a different parameter identity from its recovery.
  fixture(s,argv[1],phase);s.clear();s.descriptors();s.cfg(false,4,0x802);
  unsigned t=0;uint64_t oldwrites=s.writes;
  while(phase==0?s.d.debug_state!=2:phase==1?!s.d.debug_coreactive:s.writes==oldwrites){
   s.tick();req(++t<100000,"recovery reset phase timeout");
  }
  if(phase==1){s.tick(40);req(s.d.debug_coreactive&&s.d.debug_busy,"active-compute reset phase lost owner");}
  // WB and output reset explicitly cancel an accepted, unretired transaction.
  if(phase!=1){while(!s.inflight){s.tick();req(++t<100000,"reset inflight timeout");}}
  bool hadInflight=s.inflight;uint32_t cancelledAddr=s.paddr;
  s.d.rst_n=0;s.tick(3);s.d.rst_n=1;s.tick(8);
  req(!s.d.debug_busy&&!s.d.debug_done&&!s.d.debug_error&&!s.inflight&&!s.d.debug_pending&&!s.d.debug_locked,"reset retained old owner");
  uint64_t afterResetAccepts=s.accepts;s.tick(30);
  req(!s.d.debug_done&&s.accepts==afterResetAccepts,"old task traffic/completion escaped reset");
  auto gold=fixture(s,argv[1],phase+1);uint32_t clear=s.clear();s.descriptors();
  uint64_t a=s.accepts,r=s.retires,rd=s.reads,wr=s.writes;
  s.cfg(false,4,0x802);s.waitIdle(true);
  req(s.accepts-a==20192&&s.retires-r==20192&&s.reads-rd==7520&&s.writes-wr==12672,"fresh task transaction identity");
  req(s.cfg(true,0x30)==3168&&s.cfg(true,0x34)==26624,"fresh task compute work");
  std::ofstream raw(std::string(argv[2])+".phase"+std::to_string(phase)+".actual-y32.mem");raw<<std::hex<<std::setfill('0');
  for(unsigned i=0;i<25344;i++){
   uint32_t got=s.host(true,0xa0020000+4*i);raw<<std::setw(8)<<got<<"\n";
   req(got==uint32_t(gold[i]),"post-reset old response/wrong new output phase="+std::to_string(phase)+" word="+std::to_string(i));++checked;
  }
  raw.close();uint32_t payload=s.cfg(true,0x20);
  if(phase)out<<",\n";
  out<<"{\"phase\":"<<phase<<",\"cancelled_layer\":"<<phase<<",\"fresh_layer\":"<<phase+1
   <<",\"cancelled_inflight\":"<<(hadInflight?"true":"false")<<",\"cancelled_address\":"<<cancelledAddr
   <<",\"fresh_clear_csr\":"<<clear<<",\"fresh_payload_csr\":"<<payload<<",\"fresh_exact_y32\":25344,\"fresh_accepted\":20192,\"fresh_retired\":20192}";
  out.flush();std::cout<<"DMA64_POSTRESET_FULL_TASK_PASS phase="<<phase<<" cancelled_layer="<<phase<<" fresh_layer="<<phase+1
   <<" old_inflight="<<hadInflight<<" exact_y32=25344 clear="<<clear<<" payload="<<payload<<"\n"<<std::flush;
 }
 out<<"\n],\n\"exact_postreset_y32\":"<<checked<<",\n\"status\":\"PASS\"\n}\n";
 std::cout<<"DMA64_POSTRESET_RECOVERY_PASS cases=3 exact_y32="<<checked<<"\n";
}catch(const std::exception&e){std::cerr<<"FAIL "<<e.what()<<"\n";return 1;}}
