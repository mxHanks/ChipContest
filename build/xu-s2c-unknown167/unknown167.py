#!/usr/bin/env python3
"""xu167: unchanged original S2c147 checks plus passive unknown-fatal observations."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
FROZEN147 = {
 'xu_private147.py':'5ee323cec482d465ccf3a641b18a31186e9d7ed5173caccbcdf7c446f2685743',
 'private147-runtime.c.in':'2c9044aeff474fd336195f81b4527385caabba6bee754325e01bc599feb4e282',
 'support111.py':'2a740fb35d8f6db7da3295031f4e7e66f1505d30c9ccf030a5cb1862cb8caa6d',
 'frozen111-vpi.c':'2403e25ee5ab453d017b6686da89df7553b79bcd89d70ca35be96281d5d8e7c7',
 'actual133-inventory.json':'14a0aec91b4ceca013861ce7f4703142e90a8c762fe8c6da632f28a13ccdabb9',
 'frozen-s2c-accel.v':'1a088c873c5e5de84ca92fdc74d693a326e430cc6191128979f573fe4e64ad45'}
EIGHT = [('w_commit','xu147_o_048',1),('x_commit','xu147_o_051',1),('bias_commit','xu147_o_043',1),
         ('row_active','xu147_o_016',1),('row_count','xu147_o_017',2),('row_running','xu147_o_023',1),
         ('row_produced','xu147_o_020',6),('row_retired','xu147_o_022',6)]
ACCEL = 'tb_xu_soc_ppa.dut.u_soc.u_e203_subsys_top.u_e203_subsys_main.u_e203_subsys_perips.u_accel_icb_slave.u_linear_compute_core'
FIFO = 'tb_xu_soc_ppa.dut.u_soc.u_e203_subsys_top.u_e203_subsys_main.u_e203_subsys_mems.u_sirv_mem_fab.u_sirv_gnrl_icb_buffer.u_sirv_gnrl_rsp_fifo'
TARGET = FIFO + '.dp_gt0.vec_31_dfflr.qout_r_reg[0]'
NATIVE = ['io_wLoadWen','io_xLoadWen','io_cacheWriteEnable','io_rowActive',
          'io_rowCount','io_rowRunning','io_rowProduced','io_rowRetired']
SHARED = ['clk','rst_n','cmd_valid','cmd_ready','cmd_read','cmd_addr','cmd_wdata',
          'cmd_wmask','rsp_valid','rsp_ready','rsp_rdata','rsp_err']
WINDOW = (9359300000000, 9359500000000)
FATAL = 'XU_CANDIDATE_REJECT unknown commit/FIFO ownership state'
COLLECTED = 'COLLECTED_ORIGINAL_UNKNOWN_FATAL167_NOT_QUALIFIED'
FAIL = 'FAIL_OBSERVATION167_NOT_QUALIFIED'
PREPARED = 'PREPARED_UNCHANGED147_PASSIVE_UNKNOWN167_NOT_QUALIFIED'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load147(root):
    root = Path(root).resolve()
    for name, digest in FROZEN147.items():
        need(sha(root / name) == digest, 'frozen147 file differs: ' + name)
    need('support111' not in sys.modules, 'support111 already loaded; use separate foreground process')
    sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location('xu_frozen147_for167', str(root / 'xu_private147.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def tb_instrument(text):
    original = '        $fatal(1,"' + FATAL + '");'
    need(text.count(original) == 1, 'unique original unknown fatal differs')
    fields = ' '.join(name + '=%b' for name, _, _ in EIGHT)
    args = ','.join(name if name.endswith('_commit') else target for name,target,_ in EIGHT)
    addition = 'begin\n        $display("XU_UNKNOWN167_TRIGGER tick_fs=%0.0f ' + fields + '",$realtime*1000000.0,' + args + ');\n        $xu_unknown167_snapshot();\n' + original + '\n      end'
    result = text.replace(original, addition, 1)
    prepare = '    $xu_private147_prepare();'
    need(result.count(prepare) == 1, 'original prepare boundary differs')
    result = result.replace(prepare, prepare + '\n    $xu_unknown167_prepare();', 1)
    need(result.replace(addition, original, 1).replace(prepare+'\n    $xu_unknown167_prepare();',prepare,1)==text,
         'instrumentation is not exactly reversible to original147')
    return result


def c_instrument(text):
    start = 'void xu_private147_register(void){'
    need(text.count(start) == 1, 'original147 registration boundary differs')
    result = text.replace(start, (HERE/'observer167.c.in').read_text()+'\n'+start+'\n xu167_register();',1)
    need(result.replace((HERE/'observer167.c.in').read_text()+'\n'+start+'\n xu167_register();',start,1)==text,
         'C observer is not exactly reversible to original147')
    return result


def observer_bindings(text):
    need(not re.search(r"^XU_UNKNOWN167_\w*REJECT\b",text,re.M), "passive observer reported a rejection")
    ready=re.findall(r'^XU_UNKNOWN167_READY native_operands=8 tb_operands=8 scopes=1,1,1,1 observed_nodes=(\d+) failed=0 start_fs=(\d+) stop_fs=(\d+) new_DUT_writes=0 new_TB_writes=0 forces=0 timing_controls_changed=0 NOT_QUALIFIED$',text,re.M)
    need(len(ready)==1 and tuple(int(x) for x in ready[0][1:])==WINDOW, 'passive observer binding incomplete')
    observer_binds=re.findall(r'^XU_UNKNOWN167_BIND role=(\S+) bits=(\d+) type=(\d+) name=(\S+)$',text,re.M)
    need(observer_binds and len({b[3] for b in observer_binds})==len(observer_binds), 'observer binding names missing or duplicated')
    need(int(ready[0][0])==len(observer_binds), 'observer ready count differs from exact binding names')
    need(all(1<=int(b[1])<=64 and int(b[2]) in [36,44,48] for b in observer_binds), 'observer binding geometry/type differs')
    by_name={b[3]:b for b in observer_binds}
    required={ACCEL+'.'+native:(logical,width) for (logical,_,width),native in zip(EIGHT,NATIVE)}
    required.update({'tb_xu_soc_ppa.'+target:('tb_fatal_operand',width) for _,target,width in EIGHT})
    required.update({TARGET+'.'+pin:('fifo_'+pin,1) for pin in ['CK','D','Q','NOTIFIER']})
    for name,(role,width) in required.items():
        need(name in by_name and by_name[name][:2]==(role,str(width)), 'required exact passive binding missing: '+name)
    for name in SHARED:
        need('tb_xu_soc_ppa.dut.u_shared.'+name in by_name and
             by_name['tb_xu_soc_ppa.dut.u_shared.'+name][0]=='shared_port', 'shared pin binding missing: '+name)
    scopes=re.findall(r'^XU_UNKNOWN167_SCOPE index=(\d+) definition=(\S+) name=(\S+)$',text,re.M)
    need(sorted((int(s[0]),s[2]) for s in scopes)==list(enumerate([ACCEL,FIFO,TARGET,'tb_xu_soc_ppa.dut.u_shared'])) and
         all(s[1]!='ABSENT' for s in scopes), 'exact four observer scopes missing')
    return observer_binds,by_name


def classify_unknown(raw, code, tb_path, bindings):
    text=raw.decode('utf-8',errors='replace')
    trigger=list(re.finditer(r'^XU_UNKNOWN167_TRIGGER tick_fs=(\d+) (.*)$',text,re.M))
    need(len(trigger)==1 and text.count(FATAL)==1, 'unique original unknown rejection/167 trigger missing')
    values=dict(re.findall(r'(\w+)=([01xz]+)',trigger[0].group(2)))
    need(set(values)=={name for name,_,_ in EIGHT}, 'exact eight fatal operands missing')
    need(all(len(values[name])==width for name,_,width in EIGHT), 'fatal operand widths differ')
    unknown=[name for name,_,_ in EIGHT if re.search('[xz]',values[name])]
    need(unknown, 'original unknown fatal lacks unknown operand')
    need('SOC_PASS' not in text and 'XU_PRIVATE147_ADAPTER_REJECT' not in text and
         'XU_UNKNOWN167_BIND_REJECT' not in text and
         not re.search(r'^\s*(?:Error:|Error-|FATAL:)',text,re.M), 'unexpected native error/rejection/pass')
    for marker in [
        'XU_PRIVATE147_ADAPTER_READY logical_references=72 private_references=60 native_bindings=84 original_preload_macros=288 Q_WRITES=0 OTHER_DUT_FF_WRITES=0',
        'XU_PRIVATE147_PRELOAD_ROLE_DONE role=1 macros=32 rows=256 bits=64 arbitrary_XZ_preserved=1 Q_WRITES=0',
        'XU_PRIVATE147_PRELOAD_ROLE_DONE role=2 macros=256 rows=256 bits=64 arbitrary_XZ_preserved=1 Q_WRITES=0']:
        need(text.count(marker)==1 and text.index(marker)<trigger[0].start(), 'original native binding/preload marker missing or late')
    bind_lines=re.findall(r'^XU_PRIVATE147_BIND (.*)$',text,re.M)
    need(len(bind_lines)==len(bindings)==84, 'original84 native bindings missing')
    for tag,b in enumerate(bindings):
        target='tb_xu_soc_ppa.'+b['target']+('[%d]'%b['lane'] if b['lane']>=0 else '')
        expected='tag=%d logical=%s lane=%d width=%d sources=%d phase_mask=%d source=%s.%s target=%s source_type=' % (
            tag,b['logical'],b['lane'],b['width'],b['parts'],b['phases'],b['scope'],b['names'][0],target)
        matches=[line[len(expected):] for line in bind_lines if line.startswith(expected)]
        need(len(matches)==1 and matches[0] in ['36','44','48'], 'original binding identity/type differs at tag='+str(tag))
    observer_binds,by_name=observer_bindings(text)
    done=re.findall(r'^XU_UNKNOWN167_SNAPSHOT_DONE nodes=(\d+) failed=(\d+) tick_fs=(\d+) original_fatal_retained=1 NOT_QUALIFIED$',text,re.M)
    need(len(done)==1 and done[0][1]=='0' and done[0][2]==trigger[0].group(1),'unique same-tick passive snapshot missing')
    events=re.findall(r'^XU_UNKNOWN167_EVENT serial=(\d+) tick_fs=(\d+) reason=(\S+) role=(\S+) bits=(\d+) aval=([0-9a-f]{16}) bval=([0-9a-f]{16}) name=(\S+)$',text,re.M)
    need([int(e[0])for e in events]==list(range(1,len(events)+1)), 'observer event serial gaps')
    need([int(e[1])for e in events]==sorted(int(e[1])for e in events), 'observer event simulation ticks go backwards')
    snapshot=[e for e in events if e[2]=='before_original_unknown_fatal']
    need(len(snapshot)==int(done[0][0])==len(observer_binds) and {e[7]for e in snapshot}==set(by_name),'complete unique fatal snapshot missing')
    need(all(e[2] in ['before_original_unknown_fatal','value_change','first_observed_window_event'] and
             e[7] in by_name and (e[3],e[4])==by_name[e[7]][:2] for e in events), 'event identity/type differs from binding')
    need(all(e[1]==trigger[0].group(1) for e in snapshot), 'snapshot changed simulation tick')
    need(all(WINDOW[0]<=int(e[1])<=WINDOW[1] for e in events if e[2]!='before_original_unknown_fatal'), 'callback event outside frozen window')
    need(sum(e[3]=='tb_fatal_operand' for e in snapshot)==8, 'eight TB VPI snapshots missing')
    for name,_,_ in EIGHT:
        need(sum(e[3]==name for e in snapshot)==1, 'native operand snapshot missing '+name)
    def four_state(event):
        width=int(event[4]);aval=int(event[5],16);bval=int(event[6],16)
        return ''.join(('x' if (aval>>bit)&1 else 'z') if (bval>>bit)&1 else
                       ('1' if (aval>>bit)&1 else '0') for bit in range(width-1,-1,-1))
    native_values={name:four_state(next(e for e in snapshot if e[3]==name)) for name,_,_ in EIGHT}
    tb_values={name:four_state(next(e for e in snapshot if e[7]=='tb_xu_soc_ppa.'+target))
               for name,target,_ in EIGHT}
    need(tb_values==values, 'fatal local values differ from same-call TB VPI snapshots')
    need(text.index('XU_UNKNOWN167_TRIGGER') < text.index('XU_UNKNOWN167_SNAPSHOT_DONE') < text.index(FATAL),
         'diagnostics must precede the retained original fatal')
    source=Path(tb_path).read_text().splitlines()
    lines=[i for i,s in enumerate(source,1)if '$fatal(1,"'+FATAL+'")' in s]
    fatal_blocks=re.findall(r'^Fatal: "([^"\n]+)", (\d+): ([^\n]+): at time (\d+) fs\n([^\n]+)\n'
                           r'\$finish called from file "([^"\n]+)", line (\d+)\.\n'
                           r'\$finish at simulation time\s+(\d+)\n',text,re.M)
    need(len(lines)==len(fatal_blocks)==1 and len(re.findall(r'^(?:Fatal|FATAL):',text,re.M))==1, 'unique native original fatal block missing')
    f=fatal_blocks[0]
    need(f[0]==f[5]==str(tb_path.resolve()) and int(f[1])==int(f[6])==lines[0] and f[4]==FATAL and
         f[3]==f[7]==trigger[0].group(1), 'native fatal source/line/message/time differs')
    return dict(status=COLLECTED,qualification='NOT_QUALIFIED',original_worker_verdict='FAIL_PRIVATE147_NOT_QUALIFIED',
                original_mandatory_fatal=FATAL,original_unknown_values=values,unknown_operands=unknown,
                native_values_at_original_fatal=native_values,tb_values_at_original_fatal=tb_values,
                current_native_vs_sampled_differences=[name for name,_,_ in EIGHT if native_values[name]!=tb_values[name]],
                trigger_tick_fs=int(trigger[0].group(1)),native_simulation_returncode=code,
                passive_snapshot_nodes=len(snapshot),private_qualification_gates_discharged=0,
                original_checks_preserved=True,notifier_causality='NOT_PROVEN',new_dut_writes=0,
                observation_window_fs=list(WINDOW),window_covers_fatal=WINDOW[0]<=int(trigger[0].group(1))<=WINDOW[1],
                passive_value_change_events=sum(e[2]=='value_change' for e in events),
                callback_serial_semantics='CALLBACK_DISPATCH_ORDER_ONLY_NOT_CAUSALITY_OR_VPI_SCHEDULER_PHASE',
                observed_events=[dict(serial=int(e[0]),tick_fs=int(e[1]),reason=e[2],role=e[3],bits=int(e[4]),
                                      aval=e[5],bval=e[6],name=e[7]) for e in events])


def install(module):
    original_tb=module.generated_tb; original_c=module.generate_c; original_classify=module.classify; original_work=module.work
    def generate(original, records):
        for (logical,target,width),native in zip(EIGHT,NATIVE):
            matches=[r for r in records if r['observation']==target]
            need(len(matches)==1 and matches[0]['width_each']==width and matches[0]['lanes']==1 and
                 len(matches[0]['endpoint_lookups'])==1 and
                 'tb_xu_soc_ppa.dut.'+matches[0]['endpoint_lookups'][0]['path']==ACCEL+'.'+native,
                 'frozen147 fatal/native operand mapping differs: '+logical)
        text,review=original_tb(original,records)
        result=tb_instrument(text)
        review.update(passive_unknown167=True,original147_reversible=True,original_unknown_fatal_retained=True)
        return result,review
    module.generated_tb=generate
    module.generate_c=lambda:c_instrument(original_c())
    def classify(raw,code,tb_path,bindings,inventory):
        if FATAL in raw.decode('utf-8',errors='replace'):
            return classify_unknown(raw,code,tb_path,bindings)
        result=original_classify(raw,code,tb_path,bindings,inventory)
        observer_binds,_=observer_bindings(raw.decode("utf-8",errors="replace"))
        result.update(original_worker_verdict='ORIGINAL_TB_EXU_HALT_REACHED_FINAL_QUALIFICATION_GATE_PENDING_NOT_QUALIFIED',
                      unknown_fatal_reproduced=False,qualification='NOT_QUALIFIED',
                      passive_observer_bindings=len(observer_binds),passive_observer_binding_check='COMPLETE_NOT_QUALIFIED')
        return result
    module.classify=classify
    def work(args,run):
        run.freeze(Path(__file__));run.freeze(HERE/'observer167.c.in')
        for name in FROZEN147:
            run.freeze(module.HERE/name)
        original_work(args,run)
        if not args.run:
            run.state.update(status=PREPARED,qualification='NOT_QUALIFIED')
        run.state.update(scope='S2C147_UNCHANGED_CHECKS_PASSIVE_UNKNOWN167',adapter167='PASSIVE_ONLY_NO_DUT_WRITES_OR_TIMING_SUPPRESSION')
        run.save()
    module.work=work
    module.base.FAIL_STATUS=FAIL


def contract():
    return dict(schema='xu-unknown167-contract-v1',foreground=True,python_minimum='3.6',
        cli='unknown167.py',result_file='state.json',collected_status=COLLECTED,failure_status=FAIL,
        prepared_status=PREPARED,diagnostic_terminal_statuses=[COLLECTED,
            'ORIGINAL_TB_EXU_HALT_REACHED_FINAL_QUALIFICATION_GATE_PENDING_NOT_QUALIFIED'],
        expected_cli_exit=0,expected_simulator_exit='RECORDED_VERBATIM_VCS_MAY_RETURN_ZERO_ON_ORIGINAL_FATAL',
        original147_files=FROZEN147,qualification='NOT_QUALIFIED',new_dut_writes=0,new_tb_writes=0,
        original147_tb_fatals_preserved=87,original_always_blocks=3,original_sampling_calls=3,
        observation_window_fs=list(WINDOW),unknown_operands=[dict(logical=n,tb=t,width=w,native=ACCEL+'.'+p)
            for (n,t,w),p in zip(EIGHT,NATIVE)],target_fifo_scope=FIFO,target_notifier_scope=TARGET,
        callback_serial_semantics='CALLBACK_DISPATCH_ORDER_ONLY_NOT_CAUSALITY_OR_VPI_SCHEDULER_PHASE',
        usage='unknown167.py --adapter147 ORIGINAL_FROZEN147 [original147 args including --out FRESH --run]')


def main():
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--adapter147',type=Path,default=HERE.parent/'xu-campaign-batch154/private147')
    parser.add_argument('--describe167','--describe',dest='describe167',action='store_true')
    args,remaining=parser.parse_known_args()
    if args.describe167:
        print(json.dumps(contract(),sort_keys=True,indent=2));return 0
    module=load147(args.adapter147);install(module)
    sys.argv=[str(Path(__file__).resolve())]+remaining
    return module.main()


if __name__=='__main__':
    sys.exit(main())
