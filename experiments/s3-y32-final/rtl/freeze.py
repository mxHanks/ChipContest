#!/usr/bin/env python3
"""Record and check the exact installed DMA4/storage21 integration sources."""
import hashlib,json,re,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
CHILD=ROOT/'third-party/e203_hbirdv2'
PERIPS=CHILD/'rtl/e203/perips'
BASE='5470c5650f2d11d16e7c52cc96626d21030a3973'
FROZEN=ROOT/'docs/validation/s3-y32-compliant32-storage-20261113/wide-candidate-r2'
OUT=Path(__file__).resolve().parent
DEFINES=['XU_MATRIX_DMA_SYSBUS32','XU_MATRIX_X_SRAM','XU_MATRIX_STORAGE_SRAM']
FILES=['DmaBiasSramPrefetch.sv','LinearTileDmaCore.sv','MacController.sv','Sram1024x16.sv','TileWeightBank.sv','TileWeightBankArray.sv','TileXMacroRowBuffer.sv','TileXRowBuffer.sv','mem_1024x16.sv','xu_matrix_dma_sysbus32.sv']
def sha(data):return hashlib.sha256(data).hexdigest()
def old(name):return subprocess.check_output(['git','-C',str(CHILD),'show',BASE+':rtl/e203/perips/'+name])
def tokens(path,defines):
    raw=subprocess.check_output(['verilator','-E',*['-D'+d for d in defines],str(path)],text=True)
    raw=re.sub(r'^`line[^\n]*','',raw,flags=re.M)
    raw=re.sub(r'/\*.*?\*/|//[^\n]*','',raw,flags=re.S)
    return re.findall(r'"(?:\\.|[^"\\])*"|\\\S+|[A-Za-z_$][A-Za-z0-9_$]*|\d+\x27[sS]?[bBoOdDhH][\dxXzZ?_a-fA-F]+|\d+|[^\s]',raw)
def main():
    origins={name:sha((FROZEN/'rtl'/name).read_bytes()) for name in FILES if name!='xu_matrix_dma_sysbus32.sv'}
    core=(PERIPS/'LinearTileDmaCore.sv').read_text()
    stripped=core.replace(' // Issue selection is independent of response retirement. Both read the held macro Q row.\n input [2:0] io_outIssueColumn,output [47:0] io_outIssueResult,\n','').replace(' wire [40:0] resultIssueRaw=resultRowQ[41*io_outIssueColumn+:41];\n','').replace(' assign io_outIssueResult={{7{resultIssueRaw[40]}},resultIssueRaw};\n','')
    assert stripped==(FROZEN/'rtl/LinearTileDmaCore.sv').read_text(),'more than disclosed combinational core interface change'
    mac=re.compile(r'module MacPE_Acc41\(.*?\nendmodule',re.S)
    assert mac.findall(core)==mac.findall((FROZEN/'rtl/LinearTileDmaCore.sv').read_text()),'arithmetic source drift'
    fallback=[]
    with tempfile.TemporaryDirectory(prefix='final-rtl-projection-') as td:
      for name in ['xu_matrix_dma_sysbus32.sv','LinearTileDmaCore.sv']:
        p=Path(td)/name;p.write_bytes(old(name))
        for mask in range(7):
          defines=[d for i,d in enumerate(DEFINES) if mask&(1<<i)]
          actual=tokens(PERIPS/name,defines);base=tokens(p,defines)
          assert actual==base,(name,defines,'fallback token difference')
          fallback.append(dict(file=name,defines=defines,tokens=len(actual),sha256=sha(json.dumps(actual).encode()),same_as_5470=True))
    ingress=CHILD/'rtl/e203/subsys/xu_systembus_ingress32.v'
    assert ingress.read_bytes()==subprocess.check_output(['git','-C',str(CHILD),'show',BASE+':rtl/e203/subsys/xu_systembus_ingress32.v'])
    changed=subprocess.check_output(['git','-C',str(CHILD),'diff','--name-only',BASE,'--','rtl'],text=True).splitlines()
    allowed=['rtl/e203/perips/'+n for n in ['LinearTileDmaCore.sv','mem_1024x16.sv','xu_matrix_dma_sysbus32.sv']]
    assert sorted(changed)==sorted(allowed),('unexpected RTL change',changed)
    rec=dict(schema='s3_y32_final_dma4_storage21_sources_v1',source_base_child=BASE,installed_child_commit=subprocess.check_output(['git','-C',str(CHILD),'rev-parse','HEAD'],text=True).strip(),
      required_production_defines=DEFINES,production_test_loader=False,
      installed_sources={str((PERIPS/n).relative_to(ROOT)):sha((PERIPS/n).read_bytes()) for n in FILES},
      simulation_only_models={'tools/ppa/generic_ramsp_non_ppa.sv':sha((ROOT/'tools/ppa/generic_ramsp_non_ppa.sv').read_bytes())},
      storage21_source_manifest_sha256=sha((FROZEN/'manifest.json').read_bytes()),storage21_source_files=origins,
      arithmetic_macpe_acc41_sha256=[sha(v.encode()) for v in mac.findall(core)],
      core_noncombinational_bytes_equal_storage21=True,
      preserved_ingress_sha256=sha(ingress.read_bytes()),unchanged_cpu_fabric=True,changed_rtl=changed,
      fallback_projection=fallback,
      storage=dict(W=16,bias=1,X=16,result=21,internal_macros=54,expected_full_soc_macros=374,
        internal_physical_bytes=110592,result_physical_bytes=43008,result_logical_bits=5248),
      clear=dict(W=16384,bias=768,X=16384,result=21504,total_physical16=55040,mmio_W_X_result=54272,address_steps=1024),
      metadata=dict(request_depth=4,request_kind_bits=12,request_index_bits=56,read_write_pointer_bits=4,pending_count_bits=3,
        y_issue_bits=4,y_retire_bits=3,comment='No payload stored in the ordered descriptor queue; locked command includes one32bit payload for ICB stability.'),
      assembly_state=[dict(name='dma.w_low',bits=32,lifetime='even W response until following odd W response physical load'),
        dict(name='dma.bias_low',bits=32,lifetime='low bias response until high response assembled'),
        dict(name='dma.bias_data',bits=40,lifetime='one bias host write; no second bias pair while bias_busy'),
        dict(name='core.hostData',bits=40,lifetime='accepted bias write during three physical16bit writes'),
        dict(name='core.biasLow',bits=32,lifetime='two synchronous bias macro slices until same lane ACC init'),
        dict(name='dma.lock_data',bits=32,lifetime='one locked ICB scalar while command VALID waits READY')],
      compute_accumulator=dict(count=64,bits_each=41),
      forbidden_copies=dict(dma_y_payload_bits=0,result_register_fifo_bits=0,raw_result_snapshot_bits=0,bias_prefetch_slots=0),
      scope='Source merge identity and fallback projection only. Macros are expected until independently counted in actual simulation/mapped hierarchy. No timing/area/power qualification.')
    (OUT/'manifest.json').write_text(json.dumps(rec,indent=2)+'\n')
    print('FINAL_RTL_SOURCE_IDENTITY_PASS')
if __name__=='__main__':main()
