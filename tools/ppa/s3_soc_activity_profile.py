"""Small full-SoC/macro/activity adapter for the existing S3 CPU campaign.

The original f49 collector is untouched. Generic models never establish PPA.
"""
import fnmatch
import importlib.util
import json
from pathlib import Path
import re
import shutil
from fractions import Fraction


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def once(text,old,new):
    if text.count(old)!=1:raise ValueError('S3 full-SoC adapter anchor differs: '+old[:100])
    return text.replace(old,new,1)


def wrap_testbench(text,preload):
    """Move only the TB external RAM response/preload into the real PPA top."""
    original_assertions=re.findall(r'\$fatal\([^;]*;',text)
    text=once(text,'  reg rsp_valid = 0;','  wire rsp_valid;')
    text=once(text,'  reg [31:0] rsp_rdata = 0;','  wire [31:0] rsp_rdata;\n  wire rsp_err;')
    text=once(text,'  reg [7:0] program_bytes [0:65535];',
              '  reg [7:0] program_bytes [0:65535];\n  reg [63:0] xu_program_words [0:8191];')
    text=once(text,'  assign cmd_ready = (!rsp_valid || rsp_ready) && (cycles % 7 != 0) && !initial_source_block;',
        '\n'.join('  assign %s=dut.ext_sysmem_%s;'%(name,name) for name in
        ['cmd_ready','cmd_valid','cmd_read','cmd_addr','cmd_wdata','cmd_wmask','rsp_ready','rsp_valid','rsp_rdata','rsp_err']))
    text=once(text,'`define CPU dut.u_e203_subsys_top','`define CPU dut.u_soc.u_e203_subsys_top')
    text=once(text,'`define ACCEL dut.u_e203_subsys_top','`define ACCEL dut.u_soc.u_e203_subsys_top')
    text=once(text,'  e203_soc_top #(.EXTERNAL_SYSMEM(1)) dut (','  xu_soc_ppa_top dut (')
    start=text.index('    .ext_sysmem_cmd_valid(cmd_valid),');end=text.index('    .hfxoscen()',start)
    text=text[:start]+text[end:]
    text=once(text,'  task load_layer(input integer index);',preload+'\n  task load_layer(input integer index);')
    text=once(text,'      writes = 0; first_cycle = -1; first_accept_cycle = -1; final_write_pending = 0;',
              '      xu_preload_shared();\n      writes = 0; first_cycle = -1; first_accept_cycle = -1; final_write_pending = 0;')
    text=once(text,'      `ITCM.mem_r[i] = {program_bytes','      xu_program_words[i] = {program_bytes')
    text=once(text,'    ram[HOST/4]=tasks;','    xu_preload_itcm();\n    ram[HOST/4]=tasks;')
    text=once(text,'    for (i=0; i<65536; i=i+1) program_bytes[i]=0;',
              '    #1; // Preload after model time-zero initialization.\n    for (i=0; i<65536; i=i+1) program_bytes[i]=0;')
    text=once(text,'      if (rsp_valid && rsp_ready) rsp_valid <= 0;\n',
              '      if (rsp_valid && rsp_err) $fatal(1,"S3 full-SoC shared endpoint error");\n'
              '      if (cmd_ready !== ((!rsp_valid || rsp_ready) && (cycles%7!=0)))\n'
              '        $fatal(1,"S3 full-SoC shared throttle phase changed");\n')
    text=once(text,'        rsp_valid <= cmd_valid;\n','')
    text=once(text,'            rsp_rdata <= ram[word_index];\n','')
    text=once(text,'        $dumpvars(0,`ACCEL);','        $dumpvars(0,dut);')
    text=once(text,'      end else $dumpvars(0,tb_accel_soc);','      end else $dumpvars(0,dut);')
    if any(assertion not in text for assertion in original_assertions):
        raise ValueError('S3 full-SoC adapter lost an original assertion')
    return text


def balanced_activity_clock(text):
    if re.search(r'^\s*`timescale\b',text,re.M):raise ValueError('unexpected preexisting timescale')
    text='`timescale 1ns/1fs\n'+text
    text=once(text,'  always #2 clk = ~clk;', '''  integer s3_activity_half_index=0;
  real s3_activity_target_ns;
  initial forever begin
    s3_activity_half_index=s3_activity_half_index+1;
    s3_activity_target_ns=s3_activity_half_index*(10.0/3.0);
    #(s3_activity_target_ns-$realtime);clk=~clk;
  end''')
    text=once(text,'  always #33 lfclk = ~lfclk;','  always #15258.7890625 lfclk = ~lfclk;')
    return once(text,'    #120 rst_n=1;','    #(200-$realtime) rst_n=1;')


def activity_hooks(text):
    declarations='''  reg s3_activity_clear_started=0,s3_activity_clear_done=0;
  reg s3_activity_payload_started=0,s3_activity_payload_done=0;
  task s3_activity_clear_observe;
    begin
      if(s3_clear_armed&&!s3_activity_clear_started) begin
        s3_activity_clear_started=1;
        $display("S3_ACTIVITY_CLEAR_BEGIN cycle=%0d tick_fs=%0.0f",cycles,$realtime*1000000.0);
      end
      if(s3_activity_clear_started&&!s3_activity_clear_done&&s3_clear_verified) begin
        s3_activity_clear_done=1;
        $display("S3_ACTIVITY_CLEAR_END cycle=%0d tick_fs=%0.0f",cycles,$realtime*1000000.0);
      end
    end
  endtask
'''
    text=once(text,'  reg s3_payload_phase=0, s3_clear_armed=0;',
              '  reg s3_payload_phase=0, s3_clear_armed=0;\n'+declarations)
    text=once(text,'      if (s3_payload_phase) begin\n',
              '      s3_activity_clear_observe();\n      if (s3_payload_phase) begin\n')
    text=once(text,'      if (in_window) begin\n        perf_active=1;', '''      if (in_window) begin
        if(!s3_activity_payload_started) begin
          if(!s3_activity_clear_done) $fatal(1,"Payload activity preceded verified clear");
          s3_activity_payload_started=1;
          $display("S3_ACTIVITY_PAYLOAD_BEGIN cycle=%0d tick_fs=%0.0f",cycles,$realtime*1000000.0);
        end
        perf_active=1;''')
    text=once(text,'        if (shared_retire && final_write_pending) begin\n          perf_active=0;', '''        if (shared_retire && final_write_pending) begin
          if(!s3_activity_payload_started||s3_activity_payload_done) $fatal(1,"Invalid payload activity end");
          s3_activity_payload_done=1;
          $display("S3_ACTIVITY_PAYLOAD_END cycle=%0d tick_fs=%0.0f",cycles,$realtime*1000000.0);
          perf_active=0;''')
    return text


class S3ActivityExtension:
    EXTRA=['tools/ppa/xu_soc_ppa_verify.py','tools/ppa/xu_soc_ppa_top.sv','tools/ppa/xu_shared_icb_sram.sv',
           'tools/ppa/xu_sirv_sram_adapter.sv','tools/ppa/xu_weight_sram_adapter.sv',
           'tools/ppa/s3_soc_activity_profile.py','tools/ppa/s3_soc_task_activity.py','tools/scripts/xu_soc_ppa.py',
           'tools/ppa/xu_full_soc.sdc']

    def __init__(self,repo,profile,model,model_sha,model_kind,schedule):
        self.repo=Path(repo).resolve();self.profile=profile;self.model=Path(model).resolve()
        self.ppa=load('_s3_activity_ppa',self.repo/'tools/scripts/xu_soc_ppa.py')
        if model_kind not in ('generic-prototype','vendor-rtl-activity'):raise ValueError('explicit model kind required')
        self.model_kind=model_kind;self.schedule=schedule
        if not self.model.is_file() or self.ppa.sha(self.model)!=model_sha:raise ValueError('macro model SHA differs/missing')
        self.model_sha=model_sha
        self.inventory=self.ppa.inventory(self.repo,profile)
        self.freeze=self.ppa.s3_worktree_sources(self.repo)
        self.contract=self.ppa.s3_transaction_contract(self.repo,schedule)
        self.external={str(self.model):model_sha}
        if '`include' in self.model.read_text():
            raise ValueError('macro includes require an explicit support-manifest seam; not yet implemented')
        if model_kind=='generic-prototype' and 'INDEPENDENT GENERIC FUNCTIONAL PROTOTYPE' not in self.model.read_text():
            raise ValueError('generic prototype must use explicitly marked independent model')

    def snapshot(self,repo,source):
        for name in self.EXTRA:
            target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
        if self.model_kind=='generic-prototype':
            self.selected_model=source/'generic_ramsp_non_ppa.sv';shutil.copy2(self.model,self.selected_model)
        else:self.selected_model=self.model
        # Bind bytes that were actually copied, not just a pre-copy observation
        # of a potentially changing worktree. The campaign's later pins guard
        # this frozen stage for the remainder of the native run.
        if self.ppa.s3_worktree_sources(repo)!=self.freeze:
            raise ValueError('S3 source changed while activity inputs were copied')
        for path in source.rglob('*'):
            if not path.is_file():continue
            relative=path.relative_to(source).as_posix()
            if path==self.selected_model:
                if self.ppa.sha(path)!=self.model_sha:raise ValueError('copied macro model SHA differs')
                continue
            if relative=='campaign.py':relative='tools/ppa/s3_task_campaign.py'
            elif relative.startswith('rtl/'):
                relative='third-party/e203_hbirdv2/rtl/e203/'+relative[4:]
            expected=self.freeze['source_files'].get(relative)
            if expected is None or self.ppa.sha(path)!=expected['sha256']:
                raise ValueError('copied activity input differs from full source freeze: '+relative)
        (source/'s3-full-source-freeze.json').write_text(json.dumps(self.freeze,indent=2,sort_keys=True)+'\n')

    def metadata(self,source):
        return dict(model_kind=self.model_kind,qualification='NOT_QUALIFIED',
                    model=dict(path=str(self.selected_model),sha256=self.model_sha),
                    hardware_profile=self.profile,firmware_schedule=self.schedule,transaction_contract=self.contract,
                    source_manifest_sha256=self.ppa.digest(self.freeze['source_files']),
                    macro_count=sum(self.ppa.hardware_profile(self.profile)['bits'].values())//16384,
                    clock_configuration=dict(profile='nominal150-balanced-v1',
                        policy=self.ppa.S3_CLOCK_PROFILES['nominal150-balanced-v1'],reset_release_ns=200,
                        source='absolute HF phase; one-fs bounded window error',timing_qualification='NOT_RUN'),
                    energy_scope='full-digital-soc-including-all-srams',power_area_timing='NOT_MEASURED')

    def testbench(self,text,source,out,args):
        if args.platform_clocks!='development' or args.first_source_stall!=0 or not args.platform_assertions:
            raise ValueError('activity extension owns balanced clocks; requires first-source-stall=0 and all platform assertions')
        base=load('_s3_activity_preload',source/'tools/ppa/xu_soc_ppa_verify.py')
        original=re.findall(r'\$fatal\([^;]*;',text)
        text=activity_hooks(balanced_activity_clock(wrap_testbench(text,base.preload_tasks(True))))
        if any(value not in text for value in original):raise ValueError('activity adapter lost payload/clear assertion')
        return text

    def sources(self,sources,source,out):
        excluded={source/'rtl/general/sirv_sim_ram.v',source/'rtl/perips/mem_1024x16.sv'}
        return [path for path in sources if path not in excluded]+[
            source/'tools/ppa/xu_sirv_sram_adapter.sv',source/'tools/ppa/xu_weight_sram_adapter.sv',
            source/'tools/ppa/xu_soc_ppa_top.sv',source/'tools/ppa/xu_shared_icb_sram.sv',self.selected_model]

    def build_command(self,command):
        if '+define+DISABLE_SV_ASSERTION=1' in command:raise ValueError('activity build disabled original platform assertions')
        return ['-timescale=1ns/1fs' if value=='-timescale=1ns/10ps' else value for value in command]

    def inspect_task(self,log,task,item):
        windows={}
        for phase in ('CLEAR','PAYLOAD'):
            matches=re.findall(r'^S3_ACTIVITY_'+phase+r'_(BEGIN|END) cycle=(\d+) tick_fs=(\d+)$',log,re.M)
            if len(matches)!=2 or [row[0] for row in matches]!=['BEGIN','END']:raise ValueError('activity phase boundary missing/duplicate')
            begin,end=[dict(cycle=int(row[1]),tick_fs=int(row[2])) for row in matches]
            if not begin['cycle']<end['cycle'] or not begin['tick_fs']<end['tick_fs']:raise ValueError('activity phase time reversed')
            cycles=end['cycle']-begin['cycle']+1
            if abs(Fraction(end['tick_fs']-begin['tick_fs'])-Fraction((cycles-1)*20000000,3))>1:
                raise ValueError('activity clock phase exceeds one-fs budget')
            windows[phase.lower()]=dict(begin=begin,end=end,cycles=cycles,duration_fs=end['tick_fs']-begin['tick_fs'])
        payload=windows['payload'];clear=windows['clear']
        if (payload['begin']['cycle']!=item['window']['first_request'] or
            payload['end']['cycle']!=item['window']['final_y_response'] or payload['cycles']!=item['cycles'] or
            clear['cycles']!=int(item['clear']['clear_cycles'])):raise ValueError('activity windows differ from original clear/payload proof')
        macro_review=dict(status='VENDOR_MAPPED_REVIEW_PENDING')
        if self.model_kind=='generic-prototype':
            names=re.findall(r'^S3_GENERIC_NON_PPA_MACRO_INSTANCE (\S+)$',log,re.M)
            if len(names)!=len(set(names)):raise ValueError('duplicate generic macro instance')
            groups=self.ppa.hardware_profile(self.profile)
            matched=set();counts={}
            for name,pattern in groups['scopes'].items():
                prefix='tb_accel_soc/dut/'+pattern
                found={path for path in names if fnmatch.fnmatchcase(path.replace('.','/'),prefix)}
                if len(found)!=groups['bits'][name]//16384 or matched&found:raise ValueError('generic macro scope/count differs: '+name)
                matched.update(found);counts[name]=len(found)
            if matched!=set(names):raise ValueError('unaccounted generic macro')
            macro_review=dict(status='GENERIC_ELABORATED_FUNCTIONAL_ONLY_NOT_PPA',counts=counts,total=len(names))
        wave=task/'tb_accel_soc.vcd'
        return dict(status='GENERIC_NON_PPA_FUNCTIONAL' if self.model_kind=='generic-prototype' else 'RTL_ACTIVITY_REVIEW_PENDING',
                    windows=windows,macro_review=macro_review,
                    full_soc_vcd=dict(path=str(wave),bytes=wave.stat().st_size,sha256=self.ppa.sha(wave)) if wave.exists() else None,
                    saif_status='NOT_COLLECTED',power_area_timing='NOT_MEASURED',qualification='NOT_QUALIFIED')

    def input_drift(self):
        drift=[path for path,digest in self.external.items() if self.ppa.sha(path)!=digest]
        if self.ppa.s3_worktree_sources(self.repo)!=self.freeze:drift.append('S3 complete source worktree changed')
        return drift
