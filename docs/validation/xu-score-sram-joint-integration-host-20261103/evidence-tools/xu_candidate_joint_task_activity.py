#!/usr/bin/env python3
"""Independent frozen S2c SAIF + continuous SRAM joint activity producer.

The old candidate collector, baseline helpers and their guards are unchanged.
All outputs remain experimental; neither capture nor integer invariants qualify
VCS scheduling, SAIF/PT conditional semantics, STA, power, energy or contest use.
"""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import re
import shlex
import shutil
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import xu_candidate_joint_context as context
import xu_candidate_task_activity as original

JOINT=HERE/'xu_joint_activity'
SCOPE=original.SCOPE
require,identity,sha=context.require,context.identity,context.sha
write_json=original.write_json
common_collector=original.common_collector
compile_firmware=original.compile_firmware
checked_log=original.checked_log
unchanged=original.unchanged

SRAM_DB_SHA='c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f'
STD_DB_SHA='f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723'
# This producer is deliberately limited to the measured S2c implementation.
# Equal macro names alone would also accept the baseline or another candidate.
S2C_MAPPED_SHA='9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892'


def check_frozen(records):
    for record in records:
        require(identity(record['path'])==record,'joint frozen file bytes/type/mode changed: '+record['path'])


def check_raw_inventory_table(path,actual):
    rows=Path(path).read_text().splitlines()
    require(rows and rows[0]=='kind\tcell\tref_or_pin\tlibcell_or_direction',
        'actual PT macro/pin table header differs')
    seen=set();macros=set();pins=set()
    for line in rows[1:]:
        fields=line.split('\t')
        require(len(fields)==4 and tuple(fields) not in seen,'actual PT duplicate/malformed table row')
        seen.add(tuple(fields));kind,cell,third,fourth=fields
        require(kind in ('MACRO','PIN'),'actual PT unknown table row kind')
        (macros if kind=='MACRO' else pins).add((cell,third,fourth))
    expected_macros={(name,record['ref_name'],record['lib_cell']) for name,record in actual.items()}
    expected_pins={(name,pin['full_name'],pin['direction']) for name,record in actual.items() for pin in record['pins']}
    require(macros==expected_macros and pins==expected_pins,
        'actual PT raw table/JSON macro, library, pin or direction differs')
    return dict(status='ACTUAL_PT_RAW_TABLE_JSON_EXACT_MATCH_NOT_ACTIVITY_OR_EQUIVALENCE_QUALIFIED',
        raw_table=identity(path),macros=len(macros),pin_bits=len(pins))


def joint_binding(ctx,mapping,inventory_path,netlist_path,constraints_path,out):
    bridge=context.load('xu_joint_exact_inventory_bridge',HERE/'xu_saif_mapped_macros.py')
    inventory,actual,comparison=bridge.inventory_macros(inventory_path)
    netlist=identity(netlist_path)
    require(netlist['sha256']==S2C_MAPPED_SHA,
        'joint collector requires exact measured S2c netlist; equal macro names are insufficient')
    require(inventory['netlist']['sha256']==netlist['sha256'] and
        Path(inventory['netlist']['path']).resolve()==Path(netlist['path']).resolve(),
        'joint mapped inventory belongs to a different exact netlist')
    libraries=[]
    for record in inventory['libraries']:
        current=identity(record['path'])
        require(current['sha256']==record['sha256'] and
            ('bytes' not in record or current['bytes']==record['bytes']),'inventory actual library identity changed')
        libraries.append(current)
    require(len(libraries)==2 and {SRAM_DB_SHA,STD_DB_SHA} == {v['sha256'] for v in libraries},
        'joint collector requires actual same-server 1024x16 SS and SMIC SS libraries')
    require(all(r['lib_cell']=='RAMSP1024X16_ss_0p99v_0p99v_125c/RAMSP1024X16' for r in actual.values()),
        'joint 121-arc ledger does not describe actual mapped macro library')
    require(inventory.get('design')=='xu_soc_ppa_top','actual inventory linked design differs')
    bridge.declared_identity(inventory.get('constraints'),'inventory.constraints')
    constraints=identity(constraints_path)
    require(constraints['sha256']==inventory['constraints']['sha256'] and
        Path(constraints['path']).resolve()==Path(inventory['constraints']['path']).resolve(),
        'actual inventory/collector analysis SDC identity differs')
    canonical={}
    for record in mapping['macros']:
        full=record['instance']
        require(full.startswith(SCOPE+'.'),'joint RTL macro outside exact DUT')
        key=full[len(SCOPE)+1:].replace('.','/')
        require(key not in canonical,'joint RTL macro duplicate/collision')
        canonical[key]=record
    require(len(actual)==mapping['macro_count']==336 and set(canonical)==set(comparison),
        'joint exact S2c actual mapped/RTL macro bijection missing/extra')
    pairs=[dict(rtl_instance=canonical[k]['instance'],group=canonical[k]['group'],mapped_instance=comparison[k],
        actual_lib_cell=actual[comparison[k]]['lib_cell']) for k in sorted(canonical)]
    frozen=[identity(inventory_path),netlist,constraints]+libraries
    # Any declared file provenance is verified rather than copied as authority.
    def provenance_files(value):
        if isinstance(value,dict):
            if isinstance(value.get('path'),str) and isinstance(value.get('sha256'),str):
                current=identity(value['path'])
                require(current['sha256']==value['sha256'] and
                    ('bytes' not in value or (type(value['bytes']) is int and current['bytes']==value['bytes'])),
                    'inventory provenance file changed or declared size differs')
                frozen.append(current)
            for child in value.values():provenance_files(child)
        elif isinstance(value,list):
            for child in value:provenance_files(child)
    provenance_files(inventory['provenance'])
    provenance=inventory['provenance']
    before,after=provenance.get('input_sha256_before'),provenance.get('input_sha256_after')
    require(isinstance(before,dict) and before and before==after,
        'actual inventory export input before/after hashes missing or changed')
    exported_inputs={}
    for path,digest in before.items():
        require(isinstance(path,str) and Path(path).is_absolute() and isinstance(digest,str) and
            re.fullmatch(r'[0-9a-f]{64}',digest),'actual inventory input hash map malformed')
        current=identity(path);canonical_path=str(Path(path).resolve())
        require(canonical_path not in exported_inputs,'actual inventory input path alias collision')
        require(current['sha256']==digest,'actual inventory export input changed after export')
        exported_inputs[canonical_path]=digest;frozen.append(current)
    for record in [netlist,constraints]+libraries:
        require(exported_inputs.get(str(Path(record['path']).resolve()))==record['sha256'],
            'actual inventory before/after does not cover exact netlist/SDC/library input')
    require(isinstance(provenance.get('raw_tsv'),dict) and isinstance(provenance.get('script'),dict),
        'actual inventory raw table/script provenance missing')
    table=check_raw_inventory_table(provenance['raw_tsv']['path'],actual)
    script=Path(provenance['script']['path']).read_text()
    reads=re.findall(r'^\s*read_verilog\s+\{([^\n{}]+)\}\s*$',script,re.M)
    require(len(reads)==1 and Path(reads[0]).resolve()==Path(netlist['path']).resolve(),
        'actual inventory Tcl read_verilog does not identify exact S2c netlist')
    links=re.findall(r'^\s*set_app_var\s+link_path\s+\[list\s+\*\s*((?:\{[^{}\n]+\}\s*)+)\]\s*$',script,re.M)
    require(len(links)==1,'actual inventory Tcl library link command missing/ambiguous')
    link_paths=[str(Path(p).resolve()) for p in re.findall(r'\{([^{}\n]+)\}',links[0])]
    require(len(link_paths)==len(set(link_paths))==2 and
        set(link_paths)=={str(Path(r['path']).resolve()) for r in libraries},
        'actual inventory Tcl linked libraries differ')
    result=dict(schema='xu-s2c-joint-mapped-binding-v1',status='EXACT_NAME_PIN_LIBRARY_INPUT_BIJECTION_NOT_EQUIVALENCE_OR_ENERGY_QUALIFIED',
        source_context=ctx.source,tool_context=ctx.joint_tool,inventory=identity(inventory_path),
        inventory_netlist=inventory['netlist'],inventory_provenance=inventory['provenance'],netlist=netlist,
        libraries=libraries,constraints=constraints,raw_table_comparison=table,
        macro_count=336,pin_bit_count=22512,pairs=pairs,frozen_files=frozen,
        expected_s2c_netlist_sha256=S2C_MAPPED_SHA,
        name_policy='dot/slash comparison only over complete validated finite macro inventories; actual mapped instance strings remain unchanged')
    write_json(out,result);result['binding_file']=identity(out);result['frozen_files'].append(result['binding_file'])
    return result


def generate_tb(ctx,mapping):
    text=original.generate_tb(ctx)
    registration=['  integer xu_joint_final_request_cycle=-1;',
        '  reg [31:0] xu_joint_final_request_addr;',
        '  // xu passive C/VPI registration outside DUT, no drivers/force.',
        '  initial begin : xu_joint_register_all_actual_macro_ports']
    for record in mapping['macros']:
        instance=record['instance']
        require(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$]*(?:\[\d+\])?(?:\.[A-Za-z_][A-Za-z0-9_$]*(?:\[\d+\])?)*',instance),
            'joint registration requires exact ordinary source hierarchy')
        registration.append('    $xu_sram_joint_register("%s",%s);'%(instance,','.join(instance+'.'+pin for pin in ('A','CEN','CLK','D','EMA','EMAW','GWEN','Q','RET1N','WEN'))))
    registration.append('  end\n')
    text=ctx.base.once(text,'  // Observation only: these counters never drive','\n'.join(registration)+'\n  // Observation only: these counters never drive')
    text=ctx.base.once(text,'        $toggle_start();','''        $toggle_start();
        $xu_sram_joint_begin(xu_global_task,"task-joint",
          $sformatf("source_request cycle=%0d addr=%08h read=1 valid=1 accept=%b",cycles,cmd_addr,cmd_ready));''')
    text=ctx.base.once(text,'          $toggle_stop();','''          if (!shared_retire || !final_write_pending || writes!=50688 ||
              xu_joint_final_request_cycle<xu_request_cycle || xu_joint_final_request_cycle>=cycles ||
              xu_joint_final_request_addr!==BASE+YOFF+50687*4)
            $fatal(1,"XU_JOINT_REJECT final response transaction identity differs");
          $toggle_stop();
          $xu_sram_joint_end(xu_global_task,
            $sformatf("final_y_retire cycle=%0d request_cycle=%0d addr=%08h response_valid=1 response_ready=1 writes=50688",cycles,xu_joint_final_request_cycle,xu_joint_final_request_addr));''')
    text=ctx.base.once(text,'              if (writes==50688) final_write_pending=1;','''              if (writes==50688) begin
                final_write_pending=1;
                xu_joint_final_request_cycle=cycles;
                xu_joint_final_request_addr=cmd_addr;
              end''')
    require(text.count('$xu_sram_joint_register(')==336 and text.count('$xu_sram_joint_begin(')==text.count('$xu_sram_joint_end(')==1,
        'joint API generation count differs')
    return text


def compile_vpi(ctx,build,cc,include,timeout):
    executable=shutil.which(cc);require(executable,'joint C compiler unavailable')
    compiler=identity(Path(executable).resolve());header=identity((include.resolve()/'vpi_user.h'))
    source=identity(JOINT/'xu_sram_joint_vpi.c');library=build/'xu_sram_joint_vpi.so';deps=build/'joint-vpi-dependencies.d'
    command=[compiler['path'],'-std=c99','-D_POSIX_C_SOURCE=200809L','-fPIC','-shared','-Wall','-Wextra','-Wshadow',
        '-Wstrict-prototypes','-Werror','-O2','-I'+str(include.resolve()),'-MD','-MF',str(deps),source['path'],'-o',str(library)]
    ctx.soc.run([compiler['path'],'--version'],build,build/'joint-cc-version.log',timeout)
    ctx.soc.run(command,build,build/'joint-vpi-build.log',timeout)
    require(library.is_file() and library.stat().st_size>0,'joint VPI compile did not produce library')
    data=deps.read_text().replace('\\\n',' ');require(':' in data,'C dependency manifest malformed')
    paths=shlex.split(data.split(':',1)[1]);require(paths,'C dependency manifest empty')
    dependencies=[identity(Path(p).resolve()) for p in sorted(set(paths))]
    require(any(r['sha256']==header['sha256'] and r['path']==header['path'] for r in dependencies),'actual requested VPI header not compiled')
    record=dict(status='COMPILED_NOT_VCS_OR_VENDOR_CALIBRATED',command=command,compiler=compiler,header=header,source=source,
        library=identity(library),dependency_manifest=identity(deps),dependencies=dependencies,
        version=identity(build/'joint-cc-version.log'),build_log=identity(build/'joint-vpi-build.log'),
        entry_point='xu_sram_joint_register_tasks')
    record['frozen_files']=dependencies+[compiler,source,record['library'],record['dependency_manifest'],record['version'],record['build_log']]
    return record


def actual_vcs_header_guard(vcs,include):
    executable=vcs.resolve();header=(include.resolve()/'vpi_user.h').resolve()
    installation=executable.parent.parent
    require(installation in header.parents and 'iverilog' not in str(header).lower(),
        'actual run VPI header must be inside same selected VCS installation; host stand-in allowed only in prepare')


def check_boundary_sidecar(joint,sidecar):
    """Cross-check observed boundary states and sparse simultaneous events.

    The sidecar omits ordinary single-port timestamps. It cannot reconstruct a
    full event trace, but its boundary identities, callback ordering and observed
    transitions must agree with the independently recorded direct pin totals.
    """
    auditor=context.load('xu_joint_boundary_integer_audit',JOINT/'xu_sram_joint_audit.py')
    rows=[json.loads(line,object_pairs_hook=auditor.unique_json) for line in Path(sidecar).read_text().splitlines()]
    begin={r['macro']:r['initial_state_lsb_ports'] for r in rows if 'begin_tick' in r}
    end={r['macro']:r['final_state_lsb_ports'] for r in rows if 'end_tick' in r}
    macros={r['macro']:r for r in joint['macros']};window=joint['window']
    require(set(begin)==set(end)==set(macros),'joint sidecar boundary macro membership differs')
    seen_ordinals=set();last_tick={};event_counts={name:0 for name in macros}
    projected={name:{p:[0]*16 for p in auditor.PINS} for name in macros}
    offsets={};start=0
    for port,width in auditor.PORTS:offsets[port]=(start,width);start+=width
    for row in rows:
        if 'tick' not in row:continue
        name,tick=row['macro'],row['tick'];state=list(row['pre_state_lsb_ports'])
        boundary=tick in (window['start_tick'],window['end_tick'])
        require(type(row.get('boundary')) is bool and row['boundary']==boundary,'sidecar boundary flag differs')
        require(tick>last_tick.get(name,-1),'sidecar macro timestamps not strictly increasing')
        last_tick[name]=tick
        if tick==window['start_tick']:
            require(''.join(state)==begin[name],'sidecar begin state/event chain differs')
        controls=toggling=False
        for event in row['events']:
            ordinal=event['callback_ordinal']
            require((tick,ordinal) not in seen_ordinals,'sidecar duplicate global callback ordinal')
            seen_ordinals.add((tick,ordinal))
            require(tick!=window['start_tick'] or ordinal>window['begin_callback_ordinal'],
                'sidecar event precedes begin callback')
            require(tick!=window['end_tick'] or ordinal<window['end_callback_ordinal'],
                'sidecar event follows end callback')
            port=event['port'];offset,width=offsets[port]
            controls|=port in ('CEN','EMA','EMAW','GWEN','RET1N','WEN')
            toggling|=port in ('CLK','D','Q','RET1N')
            require(''.join(state[offset:offset+width])==event['old'],'sidecar event replay differs')
            for bit,(old,new) in enumerate(zip(event['old'],event['new'])):
                if old==new:continue
                pin=port if width==1 else '%s[%d]'%(port,bit)
                projected[name][pin]['01xz'.index(old)*4+'01xz'.index(new)]+=1
            state[offset:offset+width]=event['new'];event_counts[name]+=1
        require(row['events'] and (boundary or (controls and toggling)),
            'sidecar row is neither boundary nor simultaneous control/toggling')
        if tick==window['end_tick']:
            require(''.join(state)==end[name],'sidecar end state/event chain differs')
    for name,macro in macros.items():
        for i,pin in enumerate(auditor.PINS):
            direct=macro['pin_transitions'][pin]
            require(all(x<=y for x,y in zip(projected[name][pin],direct)),
                'sidecar transitions exceed independently recorded direct pin totals '+name+'/'+pin)
            for state in range(4):
                incoming=sum(direct[previous*4+state] for previous in range(4))
                outgoing=sum(direct[state*4+following] for following in range(4))
                expected=int(end[name][i]=='01xz'[state])-int(begin[name][i]=='01xz'[state])
                require(incoming-outgoing==expected,'direct transitions disagree with begin/end state '+name+'/'+pin)
    return dict(status='BOUNDARY_STATE_BALANCE_AND_SPARSE_EVENT_SUBSET_PASS_NOT_FULL_TRACE_OR_SIMULATOR_CALIBRATION',
        checked_macros=len(macros),checked_pin_bits=len(macros)*67,sidecar_events=sum(event_counts.values()),
        policy='integer direct pin transition flow conserves measured begin/end states; sparse sidecar events are a subset, not a complete callback trace')


def inspect_joint(ctx,log,destination,task_id,window,binding):
    require(not re.search(r'XU_JOINT_(?:REJECT|INCOMPLETE)',log),'VPI joint rejection/incomplete marker')
    begin=re.findall(r'^XU_JOINT_BEGIN task=(\d+) tick=(\d+) macros=(\d+) callback_ordinal=(\d+)$',log,re.M)
    end=re.findall(r'^XU_JOINT_COMPLETE task=(\d+) tick=(\d+) duration_ticks=(\d+) macros=(\d+) simultaneous_records=(\d+) NOT_QUALIFIED$',log,re.M)
    require(len(begin)==len(end)==1,'joint actual complete window markers missing/duplicate')
    require(list(map(int,begin[0][:3]))==[task_id,window['begin']['tick'],336] and
        list(map(int,end[0][:4]))==[task_id,window['end']['tick'],window['duration_ticks'],336],
        'joint/SAIF source REQUEST/final RETIRE boundary or mapped count differs')
    auditor=context.load('xu_candidate_joint_integer_audit',JOINT/'xu_sram_joint_audit.py')
    stats=destination/'task-joint.stats.jsonl';sidecar=destination/'task-joint.simultaneous.jsonl'
    result=auditor.audit(stats,sidecar)
    require({r['macro'] for r in result['macros']}=={r['rtl_instance'] for r in binding['pairs']},'actual VPI macro set differs from exact RTL/mapped binding')
    header=result['window']
    require(header['task_id']==task_id and header['start_tick']==window['begin']['tick'] and header['end_tick']==window['end']['tick'] and
        header['duration_ticks']==window['duration_ticks'] and header['begin_callback_ordinal']==int(begin[0][3]) and
        header['end_callback_ordinal']>0 and result['simultaneous_records']==int(end[0][4]),'joint header/window/log differs')
    source=re.fullmatch(r'source_request cycle=(\d+) addr=([0-9a-f]{8}) read=1 valid=1 accept=([01])',header['begin_transaction'])
    final=re.fullmatch(r'final_y_retire cycle=(\d+) request_cycle=(\d+) addr=([0-9a-f]{8}) response_valid=1 response_ready=1 writes=50688',header['end_transaction'])
    require(source and final,'joint actual transaction identities missing')
    require(int(source[1])==window['begin']['cycle'] and 0xa0000000<=int(source[2],16)<0xa0018800 and
        int(final[1])==window['end']['cycle'] and int(source[1])<=int(final[2])<int(final[1]) and
        int(final[3],16)==0xa00517fc,'joint captured source/final transaction identity differs')
    require(header['begin_callback_ordinal']==int(begin[0][3]),'joint begin callback ordinal differs')
    result.update(boundary_crosscheck=check_boundary_sidecar(result,sidecar),
        raw_statistics=identity(stats),simultaneous_sidecar=identity(sidecar),binding_sha256=context.canonical(binding),
        status='CAPTURED_INTEGER_INVARIANTS_PASS_CALLBACK_SAIF_PT_AND_ENERGY_REVIEW_PENDING_NOT_QUALIFIED')
    return result


def compare_saif_joint(ctx,path,joint,binding):
    # This is an explicitly labelled field comparison, not a calibration rule.
    # TB/IG and X/Z edge semantics are retained independently, never converted.
    observed=ctx.activity.read_saif(path);index={}
    require(observed['duration_ticks']==joint['window']['duration_ticks'] and
        Decimal(observed['timescale_seconds'])==Decimal('1e-15'),
        'same-window joint/normalized SAIF duration or precision differs')
    for row in observed['signals']:
        index.setdefault(row['path'],[]).append(row)
    rows=[];different=0
    for macro in joint['macros']:
        for pin,dwell in sorted(macro['pin_dwell'].items()):
            name=macro['macro'].replace('.','/')+'/'+pin
            found=index.get(name,[]);require(found,'normalized same-task SAIF missing actual joint pin '+name)
            fields=[{k:r.get(k,0) for k in ('T0','T1','TX','TZ','TB','TC','IG')} for r in found]
            require(all(r==fields[0] for r in fields),'normalized SAIF NET/PORT activity differs '+name)
            values=fields[0];delta=[dwell[i]-values[k] for i,k in enumerate(('T0','T1','TX','TZ'))]
            different+=bool(any(delta) or values['TB'])
            rows.append(dict(pin=name,vpi_dwell_0_1_x_z=dwell,saif_fields=values,
                field_difference_vpi_minus_saif_0_1_x_z=delta,vpi_transition_16=macro['pin_transitions'][pin]))
    require(len(rows)==binding['pin_bit_count'],'joint/SAIF pin comparison count differs')
    return dict(status='EXACT_INTEGER_FIELDS_OBSERVED_DEFINITIONS_NOT_CALIBRATED' if different==0 else 'FIELD_DIFFERENCES_REVIEW_PENDING_NOT_QUALIFIED',
        pin_bit_count=len(rows),different_or_tb_pin_bits=different,rows=rows,
        policy='same-window raw field comparison only; no assumed SAIF X/Z/TB/TC/IG event equivalence or PT state_condition use')


def joint_summary(joint):
    unknown=sum(sum(m['pin_dwell'][p][2:]) for m in joint['macros'] for p in m['pin_dwell'])
    q_true_unknown=sum(sum(a['pin_joint_dwell'][1][2:]) for m in joint['macros'] for a in m['arcs'] if a['toggling_pin'] and a['toggling_pin'].startswith('Q['))
    return dict(status=joint['status'],macro_count=joint['macro_count'],pin_bit_count=joint['macro_count']*67,
        arc_count_per_macro=121,simultaneous_records=joint['simultaneous_records'],raw_unknown_bit_ticks=unknown,
        q_true_condition_unknown_bit_ticks=q_true_unknown,saif_field_comparison_status=joint['saif_raw_dwell_comparison']['status'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', '--root', dest='root', required=True, type=Path, help='exact frozen S2c source root')
    parser.add_argument('--tool-root', type=Path, default=context.TOOL_ROOT, help='must identify this producer checkout')
    parser.add_argument('--profile', choices=[context.PROFILE], default=context.PROFILE)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--vendor-model', required=True, type=Path)
    parser.add_argument('--netlist', required=True, type=Path, help='supplied target identity; equivalence is not asserted')
    parser.add_argument('--constraints', required=True, type=Path)
    parser.add_argument('--vectors', type=Path)
    parser.add_argument('--vcs', default='vcs')
    parser.add_argument('--mapped-inventory',required=True,type=Path)
    parser.add_argument('--vpi-include',required=True,type=Path,help='actual VCS include directory; host prepare may use explicitly recorded stand-in')
    parser.add_argument('--cc',default='gcc')
    parser.add_argument('--calibration-receipt',type=Path,help='optional raw actual VCS calibration identity; presence alone is not qualification')
    parser.add_argument('--cross-prefix', default='riscv64-unknown-elf-')
    parser.add_argument('--max-cycles', type=int, default=4000000)
    parser.add_argument('--build-timeout', type=int, default=1800)
    parser.add_argument('--run-timeout', type=int, default=7200)
    parser.add_argument('--initialize-vendor-memory', action='store_true')
    parser.add_argument('--task-ids', default='0,1,2,3,4,5,6,7,8,9,10,11')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args(argv)
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(schema='xu-s2c-isolated-joint-task-activity-v1', status='RUNNING', tasks=[], limitations=[
        'RTL activity only; no equivalence, STA, power, energy or contest qualification result',
        'supplied netlist identity does not establish source/netlist equivalence',
        'mapped PT coverage and SRAM Liberty/internal-power remain REVIEW_PENDING',
        'FIFO payload registers are not physically reset: reset/clear establishes empty logical ownership; all 3168 groups are produced/read/retired afresh',
        'new VPI callback joint statistics are experimental: VCS cell visibility, callback ordering, SAIF/PT state_condition and energy remain NOT_QUALIFIED'])
    try:
        require(args.tool_root.resolve() == context.TOOL_ROOT, 'explicit tool root differs from this producer')
        ctx = context.Context(args.root)
        common = common_collector()
        task_ids = common.parse_task_ids(args.task_ids)
        require(args.max_cycles > 0 and args.build_timeout > 0 and args.run_timeout > 0, 'positive limits required')
        vendor = identity(args.vendor_model)
        require(re.search(r'reg\s*\[63:0\]\s*mem\s*\[0:255\]', Path(vendor['path']).read_text()), 'vendor preload geometry differs')
        report.update(source_context=ctx.source, tool_context=ctx.tool, requested_task_ids=task_ids,
                      taskset_complete=task_ids == list(range(12)))
        vectors = args.vectors.resolve() if args.vectors else args.out / 'original-vectors'
        if args.vectors is None:
            report['fixture'] = ctx.soc.load_fixture(vectors, 12)
        validated = ctx.soc.check_vectors(vectors, 12)
        report['original_task_vectors'] = validated
        fixture_sources = [identity(ctx.soc.TESTS / ('vectors/kwt-silence-v1.' + suffix)) for suffix in ('tar.gz','json')] if args.vectors is None else []
        firmware_dir = args.out / 'firmware'
        firmware_dir.mkdir()
        firmware, firmware_record = compile_firmware(ctx, firmware_dir, args.cross_prefix)
        report['firmware_build'] = firmware_record
        build = args.out / 'simulator'
        build.mkdir()
        tb = build / 'tb_xu_s2c_joint_task_activity.sv'
        excluded = {ctx.base.RTL / 'general/sirv_sim_ram.v', ctx.base.RTL / 'perips/mem_1024x16.sv'}
        sources = sorted(p for p in ctx.base.RTL.rglob('*') if p.suffix in ('.v', '.sv') and p not in excluded)
        sources += [HERE / name for name in ('xu_sirv_sram_adapter.sv', 'xu_weight_sram_adapter.sv',
                                              'xu_shared_icb_sram.sv', 'xu_soc_ppa_top.sv')]
        sources += [Path(vendor['path']), tb]
        import xu_candidate_sram_activity_alias as aliases
        alias_dir = build / 'sram-pin-alias'
        mapping = aliases.generate(ctx.root, alias_dir)
        mapping_path = alias_dir / 'xu_candidate_sram_activity_alias.mapping.json'
        checked, pairs = aliases.validate_mapping(mapping_path)
        require(checked == mapping and len(pairs) == 22512, 'candidate SRAM pin mapping differs')
        sources.append(Path(mapping['observer_source']['path']))
        binding=joint_binding(ctx,mapping,args.mapped_inventory,args.netlist,args.constraints,build/'joint-binding.json')
        tb.write_text(generate_tb(ctx,mapping))
        vpi=compile_vpi(ctx,build,args.cc,args.vpi_include,args.build_timeout)
        calibration=identity(args.calibration_receipt) if args.calibration_receipt else None
        defines = ['ARM_UD_MODEL', 'DISABLE_SV_ASSERTION=1']
        if args.initialize_vendor_memory:
            defines.append('INITIALIZE_MEMORY')
        config = dict(source_context=ctx.source, tool_context=ctx.tool,
                      producer_sources=[identity(p) for p in (Path(__file__), Path(context.__file__), Path(original.__file__),Path(aliases.__file__),
                                        HERE / 'xu_candidate_activity_context.py',HERE / 'xu_saif_mapped_macros.py',HERE / 'xu_s2c_activity_observer.svh',
                                        JOINT / 'xu_sram_joint_vpi.c',JOINT / 'xu_sram_joint_audit.py',JOINT / 'xu_sram1024x16_arc_ledger.json')],
                      rtl_sources=[identity(p) for p in sources], original_tb=identity(ctx.base.TB),
                      candidate_contract=identity(ctx.contract.__file__), candidate_soc_helper=identity(ctx.soc.__file__),
                      fixture_sources=fixture_sources, firmware=firmware_record, firmware_build=identity(firmware_dir / 'firmware-build.json'),
                      netlist=identity(args.netlist), constraints=identity(args.constraints),
                      nominal_hz=150000000, lf_hz=32768, precision_fs=1, numeric_format='signed16/40/48',
                      activity_scope=SCOPE, monitoring_policy='rtl_on', simulator_defines=defines,
                      process_policy='one fresh process, TASKS=1 and one source-REQUEST/final-Y-response-RETIRE window per real task',
                      clear_policy='33697 CPU legacy actual-zero writes; all W/X/bias commits checked; no pre-source candidate setup writes',
                      reset_policy='actual accelerator clock must sample reset before internal bus_rst_n release; startup excludes only reset interval with no accelerator/source request; first ready checks all known/FIFO assertions; later reset/X rejected',
                      sram_alias=mapping, sram_alias_mapping=identity(mapping_path),
                      joint_tool_context=ctx.joint_tool,joint_binding=binding,vpi_build=vpi,calibration_receipt=calibration,
                      joint_policy='passive actual macro VPI vector callbacks; same SAIF first REQUEST/final Y RETIRE window; integer fs/four-state projections; no independence/unknown-zero/energy inference')
        frozen = {}
        for item in config['rtl_sources'] + config['producer_sources'] + ctx.tool['frozen_common_tools'] + firmware_record['inputs'] + firmware_record['toolchain'] + fixture_sources:
            frozen[item['path']] = item['sha256']
        for item in (config['original_tb'], config['candidate_contract'], config['candidate_soc_helper'], config['netlist'],
                     config['constraints'], config['firmware_build'], firmware_record['elf'], firmware_record['image'],
                     firmware_record['compiler_version'], config['sram_alias_mapping']):
            frozen[item['path']] = item['sha256']
        for item in binding['frozen_files']+vpi['frozen_files']+([calibration] if calibration else []):
            frozen[item['path']]=item['sha256']
        report['configuration'] = config
        report['configuration_sha256'] = context.canonical(config)
        tasks = []
        for task_id in task_ids:
            destination = args.out / ('task_%02d' % task_id)
            destination.mkdir()
            inputs = common.materialize_task(vectors, destination / 'vectors', task_id, validated[task_id])
            tasks.append((task_id, destination, inputs))
            for record in inputs['files']:
                for kind in ('original', 'materialized'):
                    frozen[record[kind]['path']] = record[kind]['sha256']
            receipt = identity(destination / 'vectors/input-manifest.json')
            frozen[receipt['path']] = receipt['sha256']
        report['taskset_inputs_sha256'] = context.canonical({str(i): inputs for i, _, inputs in tasks})
        filelist = build / 'rtl.f'
        filelist.write_text('\n'.join(str(p) for p in sources) + '\n')
        frozen[str(filelist)] = sha(filelist)
        frozen_records=[identity(path) for path in sorted(frozen)]
        require(all(record['sha256']==frozen[record['path']] for record in frozen_records),
            'joint input changed while sealing complete input manifest')
        freeze_path=args.out/'input-freeze.json'
        write_json(freeze_path,dict(schema='xu-joint-complete-file-freeze-v1',
            files=frozen_records,source_context=ctx.source,tool_context=ctx.joint_tool))
        frozen_records.append(identity(freeze_path))
        report['input_freeze']=identity(freeze_path)
        command = ctx.base.build_command('vcs', 'macro', build, filelist, True, 'nominal150')
        command[0] = args.vcs
        command.insert(1, '-debug_region+cell')
        command[1:1]=['-load',vpi['library']['path']+':xu_sram_joint_register_tasks']
        if args.initialize_vendor_memory:
            command.insert(1, '+define+INITIALIZE_MEMORY')
        report['build_command'] = command
        ctx.recheck(); check_frozen(frozen_records)
        if args.prepare_only:
            report['tasks'] = [dict(task_id=i, input_manifest=identity(d / 'vectors/input-manifest.json')) for i, d, _ in tasks]
            report['status'] = 'PREPARED_NOT_SIMULATED' if report['taskset_complete'] else 'PARTIAL_PREPARED_NOT_SIMULATED'
        else:
            vcs = shutil.which(args.vcs)
            require(vcs, 'VCS executable unavailable: ' + args.vcs)
            actual_vcs_header_guard(Path(vcs),args.vpi_include)
            report['vcs_executable'] = identity(vcs)
            frozen[report['vcs_executable']['path']] = report['vcs_executable']['sha256']
            frozen_records.append(report['vcs_executable'])
            ctx.soc.run([args.vcs, '-ID'], build, build / 'vcs-version.log', args.build_timeout)
            log = ctx.soc.run(command, build, build / 'build.log', args.build_timeout)
            require(not re.search(r'Error-\[|undefined system task|unknown system task', log, re.I), 'VCS build diagnostic failure')
            ctx.recheck(); check_frozen(frozen_records)
            binary = build / 'soc'
            report['binary'] = identity(binary)
            frozen[str(binary)] = sha(binary)
            frozen_records.append(report['binary'])
            for task_id, destination, _ in tasks:
                ctx.recheck(); check_frozen(frozen_records); aliases.validate_mapping(mapping_path)
                run = [str(binary), '+TESTCASE=' + str(firmware), '+VECTORS=' + str(destination / 'vectors'),
                       '+TASKS=1', '+XU_GLOBAL_TASK=' + str(task_id), '+MAX_CYCLES=' + str(args.max_cycles), '+DUMPWAVE=0']
                log = ctx.soc.run(run, destination, destination / 'simulation.log', args.run_timeout)
                ctx.recheck(); check_frozen(frozen_records)
                layer, window, auto = checked_log(ctx, log, task_id)
                joint=inspect_joint(ctx,log,destination,task_id,window,binding)
                raw = identity(destination / 'task.saif')
                receipt = aliases.normalize(destination / 'task.saif', mapping_path,
                                            destination / 'task-normalized.saif', destination / 'task-normalization.json')
                require(identity(raw['path']) == raw, 'raw candidate SAIF changed')
                saif = common.inspect_activity(destination / 'task-normalized.saif', window, common.STATIC_SCOPE_DECLARATIONS)
                joint['saif_raw_dwell_comparison']=compare_saif_joint(ctx,destination/'task-normalized.saif',joint,binding)
                joint_record=destination/'joint-result.json'
                write_json(joint_record,joint)
                joint_identity=identity(joint_record)
                ctx.recheck(); check_frozen(frozen_records)
                result = dict(task_id=task_id, status='COLLECTED_REVIEW_PENDING', configuration_sha256=report['configuration_sha256'],
                              layer=layer, autogroup=auto, activity_window=window, run_command=run,
                              input_manifest=identity(destination / 'vectors/input-manifest.json'),
                              boundary_log=identity(destination / 'simulation.log'), raw_saif=raw,
                              saif=saif, normalization=receipt,joint_activity=joint_identity,joint_summary=joint_summary(joint),cache_policy=dict(fresh_process=True,
                                  physical_zero_clear_observed=True, all_fixture_commits_inside_window=True,
                                  fifo_ownership_reset_and_fresh_production_observed=True, cross_task_reuse=False))
                write_json(destination / 'result.json', result)
                report['tasks'].append(result)
                write_json(args.out / 'result.json', report)
                print('COLLECTED_CANDIDATE_JOINT task=%d duration_fs=%d' % (task_id, window['duration_ticks']), flush=True)
            report['status'] = 'COLLECTED_12_TASKS_REVIEW_PENDING' if report['taskset_complete'] else 'PARTIAL_COLLECTED_REVIEW_PENDING'
    except Exception as error:
        report.update(status='FAIL', error=str(error))
        print('FAIL: ' + str(error), file=sys.stderr)
    write_json(args.out / 'result.json', report)
    print(report['status'] + ': ' + str(args.out / 'result.json'), flush=True)
    return 1 if report['status'] == 'FAIL' else 0


if __name__ == '__main__':
    sys.exit(main())
