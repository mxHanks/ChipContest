#!/usr/bin/env python3
"""Apply reviewed development ICB/shared-memory wiring to a pinned local copy.

The fork checkout itself is never modified. This open E203 development platform
is not asserted to be the competition's released platform or physical macros.
"""
from pathlib import Path
import argparse,hashlib,json
ROOT=Path(__file__).resolve().parents[2]

def replace_once(text,old,new):
    if text.count(old)!=1:raise ValueError('source context differs; refusing patch: '+old[:70])
    return text.replace(old,new)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=ROOT/'integration/ChipContest/third-party/e203_hbirdv2');a=p.parse_args();base=a.root.resolve()
    manifest=[]
    perips=base/'rtl/e203/subsys/e203_subsys_perips.v';old=perips.read_text()
    if 'u_kwt_accel' in old:raise ValueError('fusion already applied; use recorded patched copy')
    text=replace_once(old,'.O15_BASE_REGION_LSB (3)','.O15_BASE_REGION_LSB (12)')
    text=replace_once(text,'   //  *      \n    .o15_icb_enable     (1\'b0),', '   // KWT development accelerator at 0x10042000..0x10042fff.\n    .o15_icb_enable     (1\'b1),')
    start=text.index('    .o15_icb_enable');end=text.index('\n    .clk',start)
    block=text[start:end]
    portmap={'cmd_valid':'valid','cmd_ready':'ready','cmd_addr':'addr','cmd_read':'read','cmd_wdata':'wdata','cmd_wmask':'wmask','rsp_valid':'rsp_valid','rsp_ready':'rsp_ready','rsp_err':'rsp_err','rsp_rdata':'rdata'}
    import re
    for port,wire in portmap.items():
        pat=r'(\.o15_icb_'+port+r'\s*\()[^)]*(\))'
        block,count=re.subn(pat,r'\g<1>kwt_'+wire+r'\2',block)
        if count!=1:raise ValueError('missing o15 port '+port)
    text=text[:start]+block+text[end:]
    wires='''
  // Added development adapter; original fork remains byte-identical outside
  // this prepared working copy. 32-bit ICB, one pending response.
  wire kwt_valid, kwt_ready, kwt_read, kwt_rsp_valid, kwt_rsp_ready, kwt_rsp_err;
  wire [31:0] kwt_addr, kwt_wdata, kwt_rdata;
  wire [3:0] kwt_wmask;
  kwt_icb_slave u_kwt_accel (
    .clk(clk), .rst_n(bus_rst_n),
    .icb_cmd_valid(kwt_valid), .icb_cmd_ready(kwt_ready),
    .icb_cmd_addr(kwt_addr), .icb_cmd_read(kwt_read),
    .icb_cmd_wdata(kwt_wdata), .icb_cmd_wmask(kwt_wmask),
    .icb_rsp_valid(kwt_rsp_valid), .icb_rsp_ready(kwt_rsp_ready),
    .icb_rsp_err(kwt_rsp_err), .icb_rsp_rdata(kwt_rdata)
  );
'''
    pos=text.rfind('endmodule');text=text[:pos]+wires+text[pos:]
    perips.write_text(text);manifest.append({'path':str(perips),'original_sha256':hashlib.sha256(old.encode()).hexdigest(),'patched_sha256':hashlib.sha256(text.encode()).hexdigest()})
    soc=base/'rtl/e203/soc/e203_soc_top.v';old=soc.read_text();text=old
    text=replace_once(text,' wire sysmem_icb_cmd_ready;', ''' wire sysmem_icb_cmd_ready;
 wire sysmem_read, sysmem_rsp_valid, sysmem_rsp_ready, sysmem_rsp_err;
 wire [31:0] sysmem_addr, sysmem_wdata, sysmem_rdata;
 wire [3:0] sysmem_wmask;
 // Development-only shared 512 KiB transaction model. Never synthesize this
 // model as a designated SRAM macro or count it as zero physical power.
 kwt_shared512_model u_kwt_shared (
   .clk(u_e203_subsys_top.u_e203_subsys_main.hfclk),
   .rst_n(io_pads_aon_erst_n_i_ival),
   .cmd_valid(sysmem_icb_cmd_valid), .cmd_ready(sysmem_icb_cmd_ready),
   .cmd_addr(sysmem_addr), .cmd_read(sysmem_read),
   .cmd_wdata(sysmem_wdata), .cmd_wmask(sysmem_wmask),
   .rsp_valid(sysmem_rsp_valid), .rsp_ready(sysmem_rsp_ready),
   .rsp_err(sysmem_rsp_err), .rsp_rdata(sysmem_rdata)
 );''')
    for port,oldarg,newarg in [('cmd_read','','sysmem_read'),('cmd_addr','','sysmem_addr'),('cmd_wdata','','sysmem_wdata'),('cmd_wmask','','sysmem_wmask'),('rsp_valid','sysmem_icb_cmd_valid','sysmem_rsp_valid'),('rsp_ready','sysmem_icb_cmd_ready','sysmem_rsp_ready'),('rsp_err',"1'b0",'sysmem_rsp_err'),('rsp_rdata',"32'b0",'sysmem_rdata')]:
        pattern=r'(\.sysmem_icb_'+port+r'\s*\()'+re.escape(oldarg)+r'\s*(\))'
        text,count=re.subn(pattern,r'\g<1>'+newarg+r'\2',text)
        if count!=1:raise ValueError('missing sysmem port '+port)
    soc.write_text(text);manifest.append({'path':str(soc),'original_sha256':hashlib.sha256(old.encode()).hexdigest(),'patched_sha256':hashlib.sha256(text.encode()).hexdigest()})
    target=ROOT/'artifacts/integration/20261017-teammate/e203-fusion-patches.json';target.write_text(json.dumps(manifest,indent=2)+'\n');print(target)

if __name__=='__main__':main()
