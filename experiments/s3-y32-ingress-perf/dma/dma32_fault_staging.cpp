// Target both halves of32-bit source assembly and terminal Y error retirement.
#define main dma32_original_main
#include <dma32_test.cpp>
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

int main(int argc,char**argv){try{
 Verilated::commandArgs(argc,argv);req(argc==3,"usage vectors_root output_json");Sim s;
 struct Fault {const char *name;uint32_t address;bool read;};
 std::vector<Fault> faults={{"w_low",0xa0008000,true},{"w_high",0xa0008004,true},
  {"bias_low",0xa0018000,true},{"bias_high",0xa0018004,true},{"x",0xa0000000,true},
  {"y_first",0xa0020000,false},{"y_last",0xa0038bfc,false}};
 std::ofstream out(argv[2]);out<<"{\n\"scope\":\"Address-targeted32bit assembly errors and complete new-parameter recovery; no CPU/PPA\",\n\"cases\":[\n";
 unsigned checked=0;
 for(unsigned index=0;index<faults.size();index++){
  auto f=faults[index];fixture(s,argv[1],index);s.clear();s.descriptors();
  s.injectAddress=f.address;s.injectRead=f.read;s.injected=false;s.armed=true;
  s.cfg(false,4,0x802);s.waitIdle(false);req(s.injected,std::string("target not injected ")+f.name);
  req(s.cfg(true,0xc)==1,"first error code");uint64_t after=s.accepts;s.tick(100);
  req(s.accepts==after&&!s.d.debug_done,"automatic retry or completion after error");
  s.injectAddress=0;s.armed=false;
  auto gold=fixture(s,argv[1],index+1);s.clear();s.descriptors();uint64_t a=s.accepts,r=s.retires;
  s.cfg(false,4,0x802);s.waitIdle(true);req(s.accepts-a==40384&&s.retires-r==40384,"new task wrong transactions");
  for(unsigned i=0;i<25344;i++){req(s.host(true,0xa0020000+4*i)==uint32_t(gold[i]),"new task contaminated output");++checked;}
  if(index)out<<",\n";out<<"{\"fault\":\""<<f.name<<"\",\"address\":"<<f.address<<",\"first_error\":1,\"recovery_layer\":"<<index+1<<",\"exact_y32\":25344}";
  out.flush();std::cout<<"DMA32_TARGETED_ERROR_RECOVERY_PASS fault="<<f.name<<" address="<<std::hex<<f.address<<std::dec<<" recovery_layer="<<index+1<<" exact_y32=25344\n"<<std::flush;
 }
 out<<"\n],\n\"exact_recovery_y32\":"<<checked<<",\n\"status\":\"PASS\"\n}\n";
}catch(const std::exception&e){std::cerr<<"FAIL "<<e.what()<<"\n";return 1;}}
