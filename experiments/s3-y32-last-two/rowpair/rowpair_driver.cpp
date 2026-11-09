#include "VLinearRowPairPrototype.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

static void require(bool ok, const std::string &s) { if (!ok) throw std::runtime_error(s); }
static int64_t sx(uint64_t value, int bits) { return (int64_t)(value << (64-bits)) >> (64-bits); }
static std::vector<int64_t> readhex(const std::string &p, int bits, size_t n) {
  std::ifstream f(p); require(bool(f), "open " + p); std::string s; std::vector<int64_t> v;
  while (f >> s) v.push_back(sx(std::stoull(s, nullptr, 16), bits));
  require(v.size()==n, "size " + p); return v;
}
static uint32_t rne(int64_t x) {
  int64_t q=x/512, rem=x%512; if (rem<0) {--q; rem+=512;}
  if (rem>256 || (rem==256 && (q&1))) ++q;
  return (uint32_t)q;
}
struct Counts { uint64_t clocks=0,starts=0,weight=0,mac=0,full=0,wclear=0,xclear=0; };
struct Test {
  VLinearRowPairPrototype d;
  Counts c;
  uint64_t clearCount=0,clearCycles=0,clearW=0,clearX=0;
  Test() {
    d.clock=0; d.reset=1; d.io_start=0; d.io_secondRow=0;
    d.io_xLoadWen=0; d.io_xLoadRow=0; d.io_xLoadAddr=0; d.io_xLoadData=0;
    d.io_wLoadWen=0; d.io_wLoadBank=0; d.io_wLoadAddr=0; d.io_wLoadData=0;
    d.io_biasHostValid=0; d.io_biasHostAddr=0; d.io_biasHostData=0;
    d.io_clearValid=0; d.io_outPop=0; tick(3); d.reset=0; tick();
  }
  void eval() {d.clock=0;d.eval();}
  void tick(unsigned n=1) {for(unsigned i=0;i<n;i++) {
    eval(); ++c.clocks; c.starts+=d.io_computeStart; c.weight+=d.io_weightRead;
    c.mac+=d.io_macStep; c.full+=d.io_fifoFullWait;
    c.wclear+=d.io_clearWeightWrite; c.xclear+=2*d.io_clearXWrite;
    d.clock=1;d.eval();eval();
  }}
  std::array<uint64_t,8> output() {return {d.io_outResult_0,d.io_outResult_1,d.io_outResult_2,d.io_outResult_3,
    d.io_outResult_4,d.io_outResult_5,d.io_outResult_6,d.io_outResult_7};}
  void clear() {
    eval(); unsigned t=0;while(!d.io_clearReady){tick();require(++t<20000,"clear ready timeout");}
    uint64_t wc=c.wclear,xc=c.xclear,begin=c.clocks;
    d.io_clearValid=1;tick();d.io_clearValid=0;
    t=0;while(!d.io_clearDone){tick();require(++t<20000,"clear done timeout");}
    require(c.wclear-wc==16384,"physical W clear count");
    require(c.xclear-xc==128,"physical X clear count");
    require(!d.io_outValid&&!d.io_active,"clear exposed stale work");tick();
    ++clearCount;clearCycles+=c.clocks-begin;clearW+=c.wclear-wc;clearX+=c.xclear-xc;
    std::cout<<"CLEAR physical_writes_w="<<c.wclear-wc<<" physical_writes_x="<<c.xclear-xc
      <<" cycles="<<c.clocks-begin<<"\n";
  }
  void load(const std::vector<int64_t>&w,const std::vector<int64_t>&b) {
    for(int g=0;g<32;g++)for(int lane=0;lane<8;lane++)for(int k=0;k<64;k++) {
      d.io_wLoadWen=1;d.io_wLoadBank=lane;d.io_wLoadAddr=g*64+k;d.io_wLoadData=w[k*256+g*8+lane];tick();
    }d.io_wLoadWen=0;
    for(int j=0;j<256;j++) {
      d.io_biasHostValid=1;d.io_biasHostAddr=j;d.io_biasHostData=(uint64_t)b[j]&((1ULL<<40)-1);
      eval(); unsigned t=0;while(!d.io_biasHostReady){tick();require(++t<100,"bias ready timeout");}
      tick();d.io_biasHostValid=0;eval();t=0;
      while(!d.io_biasRspValid){tick();require(++t<100,"bias response timeout");}
      require(!d.io_biasRspError,"bias response error");tick();
    }
  }
  void loadx(const std::vector<int64_t>&x,int row,int rows) {
    for(int r=0;r<rows;r++)for(int k=0;k<64;k++) {
      d.io_xLoadWen=1;d.io_xLoadRow=r;d.io_xLoadAddr=k;d.io_xLoadData=x[(row+r)*64+k];tick();
    }d.io_xLoadWen=0;eval();
  }
  uint64_t row(int first,int rows,const std::vector<int64_t>&gold,const std::vector<int64_t>&y32,
               unsigned stall,unsigned&checked,std::vector<int64_t>*measured=nullptr) {
    uint64_t begin=c.clocks;d.io_secondRow=rows==2;d.io_start=1;tick();d.io_start=0;
    unsigned bundles=0,wait=0;eval();
    while(d.io_active) {
      if(!d.io_outValid){tick();require(++wait<100000,"row stalled");continue;}
      unsigned group=d.io_outGroup,sel=d.io_outSecond;
      require(group==bundles/rows && sel==bundles%rows,"bundle order/group/tail mask");
      auto held=output();
      for(unsigned s=0;s<stall;s++) {
        tick(); require(d.io_outValid&&d.io_outGroup==group&&d.io_outSecond==sel&&output()==held,
                        "bundle changed under consumer backpressure");
      }
      for(int lane=0;lane<8;lane++) {
        unsigned i=(first+sel)*256+group*8+lane;
        require(sx(held[lane],48)==gold[i],"raw48 mismatch output "+std::to_string(i));
        require(rne(sx(held[lane],48))==(uint32_t)y32[i],"Y32 mismatch output "+std::to_string(i));
        if(measured)(*measured)[i]=sx(held[lane],48);
        ++checked;
      }
      d.io_outPop=1;tick();d.io_outPop=0;++bundles;eval();
    }
    require(bundles==32*(unsigned)rows,"row bundle count");
    return c.clocks-begin;
  }
  void resetphase(int phase,const std::vector<int64_t>&x) {
    loadx(x,0,2);d.io_secondRow=1;d.io_start=1;tick();d.io_start=0;
    if(phase==0){tick(3);}else{
      unsigned t=0;while(!d.io_outValid){tick();require(++t<1000,"reset result timeout");}
      if(phase==2){d.io_outPop=1;tick();d.io_outPop=0;require(d.io_outSecond,"reset second bundle phase");}
      tick(5);
    }
    d.reset=1;tick(3);d.reset=0;tick(4);
    require(!d.io_active&&!d.io_outValid&&!d.io_computeStart,"reset stale work");
  }
};
int main(int argc,char**argv) {
  try {
    Verilated::commandArgs(argc,argv);require(argc==5,"usage: driver vectors rows stall json");
    std::string v=argv[1]; int rows=std::stoi(argv[2]);unsigned stall=std::stoul(argv[3]);
    require(rows==1||rows==2,"rows");
    auto x=readhex(v+"/x.mem",16,6336),w=readhex(v+"/w.mem",16,16384),b=readhex(v+"/bias.mem",40,256);
    auto y=readhex(v+"/y.mem",48,25344),y32=readhex(v+"/y32.mem",32,25344);
    for(int r=0;r<99;r++)for(int j=0;j<256;j++) {
      int64_t expected=b[j];for(int k=0;k<64;k++)expected+=x[r*64+k]*w[k*256+j];
      require(expected==y[r*256+j],"independent tensor oracle raw48");
      require(rne(expected)==(uint32_t)y32[r*256+j],"independent tensor oracle Y32");
    }
    Test t;uint64_t clearBegin=t.c.clocks;t.clear();uint64_t initialClearCycles=t.c.clocks-clearBegin;
    uint64_t paramsBegin=t.c.clocks;t.load(w,b);uint64_t parameterLoadCycles=t.c.clocks-paramsBegin;
    Counts before=t.c;uint64_t active=0,xload=0;unsigned checked=0,pairs=0;
    std::vector<int64_t> measured(25344);
    for(int r=0;r<99;r+=rows) {
      int n=std::min(rows,99-r);uint64_t xb=t.c.clocks;t.loadx(x,r,n);xload+=t.c.clocks-xb;
      active+=t.row(r,n,y,y32,stall,checked,&measured);++pairs;
    }
    require(checked==25344,"output count");
    uint64_t starts=t.c.starts-before.starts,wr=t.c.weight-before.weight,mac=t.c.mac-before.mac,full=t.c.full-before.full;
    require(starts==(uint64_t)pairs*32 && wr==starts*64 && mac==starts*64,"physical compute/read work");
    std::ofstream raw(std::string(argv[4])+".actual-raw48.mem"),quant(std::string(argv[4])+".cpp-rne-y32.mem");
    raw<<std::hex<<std::setfill('0');quant<<std::hex<<std::setfill('0');
    for(auto result:measured) {raw<<std::setw(12)<<((uint64_t)result&((1ULL<<48)-1))<<"\n";
      quant<<std::setw(8)<<rne(result)<<"\n";}
    raw.close();quant.close();
    // Both shared-weight engines exercise full signed inputs and 40-bit bias.
    // These are raw48 datapath tests; the C++ quantizer is not RTL rounding.
    std::vector<int64_t> extremeX(6336,0),extremeW(16384,0),extremeBias(256,0);
    std::vector<int64_t> extremeY(25344,0),extreme32(25344,0);
    for(int k=0;k<64;k++) {extremeX[k]=-32768;extremeX[64+k]=32767;}
    for(int j=0;j<256;j++) {
      extremeBias[j]=(j%2)?-(1LL<<39):(1LL<<39)-1;
      for(int k=0;k<64;k++) extremeW[k*256+j]=(j%2)?32767:-32768;
      for(int r=0;r<2;r++) {
        int64_t z=extremeBias[j];for(int k=0;k<64;k++)z+=extremeX[r*64+k]*extremeW[k*256+j];
        extremeY[r*256+j]=z;extreme32[r*256+j]=rne(z);
      }
    }
    require(extremeY[0]==618475290623LL&&extremeY[1]==-618473193472LL,"legal endpoint oracle");
    t.load(extremeW,extremeBias);t.loadx(extremeX,0,2);unsigned extremeChecked=0;
    t.row(0,2,extremeY,extreme32,31,extremeChecked);require(extremeChecked==512,"endpoint raw48 results");
    // Three reset boundaries: computation, stalled row0 output, stalled row1 output.
    for(int phase=0;phase<3;phase++)t.resetphase(phase,x);
    // A new launch after reset must not reuse a cancelled bundle.
    t.load(w,b);t.loadx(x,0,2);unsigned resetChecked=0;
    t.row(0,2,y,y32,17,resetChecked);require(resetChecked==512,"reset recovery count");
    // Public writes dirty every W/X/bias address before physical clear.
    constexpr int64_t dirtyBias=0x0101010101LL;
    std::vector<int64_t> nonzeroW(16384,1),nonzeroBias(256,dirtyBias),nonzeroX(6336,1);
    std::vector<int64_t> nonzeroY(25344,dirtyBias+64),nonzero32(25344,rne(dirtyBias+64));
    t.load(nonzeroW,nonzeroBias);t.loadx(nonzeroX,0,2);unsigned dirtyChecked=0;
    t.row(0,2,nonzeroY,nonzero32,17,dirtyChecked);
    require(dirtyChecked==512,"dirty pre-clear outputs");
    t.clear();
    std::vector<int64_t> zeroY(25344,0),zero32(25344,0);unsigned zeroChecked=0;
    t.row(0,2,zeroY,zero32,3,zeroChecked);require(zeroChecked==512,"physical clear zero result count");
    std::ofstream out(argv[4]);out<<"{\n\"schema\":\"rowpair_module_screen_v1\",\n\"rows\":"<<rows
      <<",\n\"consumer_stall_edges_per_bundle\":"<<stall<<",\n\"active_cycles\":"<<active
      <<",\n\"x_load_cycles\":"<<xload<<",\n\"active_plus_x_load_cycles\":"<<active+xload
      <<",\n\"initial_physical_clear_cycles\":"<<initialClearCycles
      <<",\n\"parameter_load_cycles\":"<<parameterLoadCycles
      <<",\n\"clear_parameter_x_compute_consume_window_cycles\":"<<initialClearCycles+parameterLoadCycles+xload+active
      <<",\n\"compute_starts\":"<<starts<<",\n\"weight_array_read_requests\":"<<wr
      <<",\n\"weight_16bit_macro_reads\":"<<wr*8<<",\n\"mac_steps_per_active_engine\":"<<mac
      <<",\n\"fifo_full_wait_edges\":"<<full<<",\n\"outputs_exact_raw48\":"<<checked
      <<",\n\"outputs_exact_cpp_rne_y32\":"<<checked<<",\n\"reset_boundaries\":3,\n\"reset_recovery_outputs\":"<<resetChecked
      <<",\n\"public_nonzero_before_clear_outputs\":"<<dirtyChecked
      <<",\n\"legal_endpoint_raw48_outputs\":"<<extremeChecked
      <<",\n\"physical_clear_calls\":"<<t.clearCount<<",\n\"physical_clear_observed_cycles\":"<<t.clearCycles
      <<",\n\"physical_clear_weight_writes\":"<<t.clearW<<",\n\"physical_clear_x_writes\":"<<t.clearX
      <<",\n\"post_clear_zero_outputs\":"<<zeroChecked<<",\n\"scope\":\"actual Verilator module RTL; C++ sink and Y32 RNE; not CPU or SoC cycles\"\n}\n";
    std::cout<<"ROWPAIR_PASS rows="<<rows<<" stall="<<stall<<" active="<<active<<" xload="<<xload
      <<" starts="<<starts<<" array_reads="<<wr<<" macro_reads="<<wr*8<<" exact="<<checked<<"\n";
  }catch(const std::exception&e){std::cerr<<"FAIL "<<e.what()<<"\n";return 1;}
}
