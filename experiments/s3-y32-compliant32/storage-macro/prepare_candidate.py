#!/usr/bin/env python3
"""Freeze an opt-in scalar-result storage-macro overlay; no production edits."""
import argparse, hashlib, json, shutil
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PERIPS=ROOT/'third-party/e203_hbirdv2/rtl/e203/perips'
BASE=ROOT/'build/compliant32-20261113/x-macro/candidate-r2/rtl'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def repl(t,a,b,n=1):
    if t.count(a)!=n:raise ValueError('seam differs: '+a)
    return t.replace(a,b)

def prepare(out):
    out=out.resolve();out.mkdir(parents=True,exist_ok=False);rtl=out/'rtl';rtl.mkdir()
    origins={}
    for p in sorted(BASE.glob('*.sv')):
        origins[str(p.relative_to(ROOT))]=sha(p);shutil.copy2(p,rtl/p.name)
    old=(rtl/'LinearTileDmaCore.sv').read_text()
    start=old.index('module MacPE_Acc41(');end=old.index('endmodule',start)+len('endmodule')
    pe=old[:end]
    core=(HERE/'StorageMacroCore.sv').read_text()
    select=('`ifdef XU_MATRIX_DMA_SYSBUS32\n`ifdef XU_MATRIX_X_SRAM\n`ifdef XU_MATRIX_STORAGE_SRAM\n'
            '`define C32_STORAGE_SELECTED\n`endif\n`endif\n`endif\n')
    finish='\n`endif\n`ifdef C32_STORAGE_SELECTED\n`undef C32_STORAGE_SELECTED\n`endif\n'
    (rtl/'LinearTileDmaCore.sv').write_text(select+'`ifdef C32_STORAGE_SELECTED\n'+pe+'\n'+core+'\n`else\n'+old+finish)
    old_dma=(PERIPS/'xu_matrix_dma_sysbus32.sv').read_text();t=old_dma
    t=repl(t,'  reg [255:0] y_payload;\n','')
    t=repl(t,'  reg [31:0] y_address;\n','')
    t=repl(t,'  reg [3:0] y_issue;\n','')
    t=repl(t,'  wire [2:0] core_out_row;','  wire [2:0] core_out_row,core_out_column;\n  wire core_clear_result;')
    t=repl(t,'if(y_active&&y_issue<8)begin\n        want=1;want_kind=KY;want_index={10\'b0,y_issue};want_read=0;\n        want_addr=y_address+{26\'b0,y_issue,2\'b0};want_data=y_payload[32*y_issue+:32];',
       "if(core_out_valid&&!y_active)begin\n        want=1;want_kind=KY;want_index={11'b0,core_out_column};want_read=0;\n        want_addr=run_y+(({25'b0,run_row}+{29'b0,core_out_row})<<10)+{22'b0,core_out_group,5'b0}+{27'b0,core_out_column,2'b0};\n        want_data=rne(core_out[0]);")
    t=repl(t,'wire core_pop=state==RUN&&!aborting&&!fault&&!y_active&&core_out_valid;',
       'wire core_pop=state==RUN&&load_ok&&pending_kind==KY;')
    t=repl(t,'.io_outGroup(core_out_group),.io_outRow(core_out_row),',
       '.io_outGroup(core_out_group),.io_outRow(core_out_row),.io_outColumn(core_out_column),')
    t=repl(t,'.io_clearWeightWrite(core_clear_w),.io_clearXWrite(core_clear_x)',
       '.io_clearWeightWrite(core_clear_w),.io_clearXWrite(core_clear_x),.io_clearResultWrite(core_clear_result)')
    t=repl(t,'      y_active<=0;y_payload<=0;y_address<=0;y_issue<=0;', '      y_active<=0;')
    t=repl(t,'+(core_clear_x?32\'d16:0);', "+(core_clear_x?32'd16:0)+(core_clear_result?32'd3:0);")
    t=repl(t,'          KY:y_issue<=y_issue+1;', '          KY:y_active<=1;')
    t=repl(t,'        KY:if(pending_index==7)y_active<=0;', '        KY:y_active<=0;')
    t=repl(t,'      if(core_pop)begin\n        for(lane=0;lane<8;lane=lane+1)y_payload[32*lane+:32]<=rne(core_out[lane]);\n        y_active<=1;y_issue<=0;pop_count<=pop_count+1;\n        y_address<=run_y+(({25\'b0,run_row}+{29\'b0,core_out_row})<<10)+{22\'b0,core_out_group,5\'b0};\n      end',
       '      if(core_pop&&core_out_column==7)pop_count<=pop_count+1;')
    t=repl(t,'y_active<=0;y_payload<=0;bias_data<=0;', 'y_active<=0;bias_data<=0;')
    t=repl(t,'pending_kind<=0;pending_index<=0;y_address<=0;y_issue<=0;', 'pending_kind<=0;pending_index<=0;')
    if any(x in t for x in ['y_payload','y_address','y_issue']):raise ValueError('obsolete result staging retained')
    (rtl/'xu_matrix_dma_sysbus32.sv').write_text(select+'`ifdef C32_STORAGE_SELECTED\n'+t+'\n`else\n'+old_dma+finish)
    origins[str((PERIPS/'xu_matrix_dma_sysbus32.sv').relative_to(ROOT))]=sha(PERIPS/'xu_matrix_dma_sysbus32.sv')
    for p in [HERE/'StorageMacroCore.sv',Path(__file__)]:origins[str(p.relative_to(ROOT))]=sha(p)
    manifest=dict(schema='compliant32_storage_macro_v1',status='PREPARED_NOT_VERIFIED',
      required_defines=['XU_MATRIX_DMA_SYSBUS32','XU_MATRIX_X_SRAM','XU_MATRIX_STORAGE_SRAM'],
      origins=origins,files={p.name:sha(p) for p in sorted(rtl.glob('*.sv'))},
      arithmetic='MacPE_Acc41 reused byte-identically; signed16 multiply, signed40 bias init, signed41 ACC, RNE9 Y32',
      storage=dict(weight_macros=16,bias_macros=1,x_macros=16,result_macros=3,internal_macros=36,full_soc_macros=356,
        result_logical_bits=5248,result_physical_bits=49152,bias_reusable_cache_bits=0,result_register_copy_bits=0,dma_group_payload_bits=0),
      clear=dict(weight_writes=16384,bias_writes=768,x_writes=16384,result_writes=3072,total16bit_writes=36608,
        mmio_W_X_result_writes=35840,parallel_address_steps=1024),
      payload_state=dict(host_bias_transaction_bits=40,bias_read_low_assembly_bits=32,scalar_bus_lock_data_bits=32,
        note='Single in-flight transaction/operand assembly state retained and disclosed; no reusable parameter slots or result group/row arrays.'),
      result_contract='Scalar result Q repeatedly reads identical macro address until its successful Y write response retires; single-port store/read arbitration, 2 packet slots. Original external MMIO ABI/counters retained.',
      fallback='Without XU_MATRIX_STORAGE_SRAM both original installed X-macro core and original sysbus32 DMA bytes retained verbatim.',
      scope='Isolated experiment, generic functional models; no synthesis, STA, power, contest qualification or CPU claim')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');return manifest
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    m=prepare(a.out);print(json.dumps(dict(status=m['status'],out=str(a.out.resolve()))))
