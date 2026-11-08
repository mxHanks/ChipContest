#!/usr/bin/env python3
"""Slice original S3 full-SoC waves into separate clear/payload digital SAIF.

This is a postprocessor, not a power, mapping, timing or contest qualifier.
Generic models and partial task sets remain explicitly non-PPA evidence.
"""
import argparse
from decimal import Decimal
from fractions import Fraction
import fnmatch
import importlib.util
import json
from pathlib import Path
import re
import subprocess


def native_probe(binary,out,activity,ppa):
    """Probe units, both boundary events, aliases and X/Z without a DUT run."""
    source=out/'native-probe.vcd';target=out/'native-probe.saif'
    source.write_text('''$timescale 1fs $end
$scope module top $end
$scope module dut $end
$var wire 1 ! clk $end
$var wire 1 ! alias_clk $end
$var reg 1 " q $end
$var reg 1 # at_begin $end
$var reg 1 $ at_end $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
$dumpvars
0!
0"
0#
0$
$end
#2000000
1!
1"
1#
#3000000
0!
x"
#4000000
1!
z"
#5000000
0!
0"
#6000000
1!
1"
1$
#7000000
0!
''')
    command=[str(binary),'-64','-input',str(source),'-output',str(target),
             '-instance','top.dut','-time','2000000','6000000']
    with (out/'native-probe.log').open('w') as log:
        child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
        code=child.wait()
    ppa.require(code==0 and not re.search(r'^Error(?:\s|:)',
                (out/'native-probe.log').read_text(),re.M),'native converter probe failed')
    data=activity.read_saif(target)
    ppa.require(data['timescale_seconds']=='1E-15' and data['duration_ticks']==4000000,
                'native converter time units differ')
    signals={s['path'].split('/')[-1]:s for s in data['signals']}
    expected=dict(clk=(2000000,2000000,0,0,4),alias_clk=(2000000,2000000,0,0,4),
                  q=(1000000,1000000,1000000,1000000,2),
                  at_begin=(0,4000000,0,0,1),at_end=(4000000,0,0,0,0))
    for name,values in expected.items():
        ppa.require(name in signals and tuple(signals[name].get(k,0) for k in ['T0','T1','TX','TZ','TC'])==values,
                    'native converter boundary/alias/unknown semantics differ: '+name)
    result=dict(status='VERIFIED_NATIVE_DIGITAL_SEMANTICS_NOT_PPA',command=command,native_exit=code,
                waitpid_completed=True,binary=dict(path=str(binary),sha256=ppa.sha(binary)),
                source_sha256=ppa.sha(source),observed=data,
                transition_policy='native-vcd2saif: begin-inclusive/end-exclusive; unknown transition TC differs from Python known-only TC; X/Z dwell preserved')
    ppa.write(out/'native-probe.json',result)
    return result


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def canonical_macro_path(path):
    """VCS folds this known generate scope into one dotted INSTANCE atom.

    Keep every other identifier unchanged; callers retain the original path.
    """
    pieces=[]
    for part in path.split('/'):
        match=re.fullmatch(r'macro_storage\.depth_bank\[(\d+)\]\.width_lane\[(\d+)\]\.macro',part)
        if match:pieces.extend(['macro_storage','depth_bank['+match[1]+']','width_lane['+match[2]+']','macro'])
        else:pieces.append(part)
    return '/'.join(pieces)


def phase_windows(item):
    clear=item['activity']['windows']['clear'];payload=item['activity']['windows']['payload']
    bounds=[clear['begin'],clear['end'],payload['begin'],payload['end']]
    if not all(a['tick_fs']<b['tick_fs'] and a['cycle']<b['cycle'] for a,b in zip(bounds,bounds[1:])):
        raise ValueError('clear/gap/payload boundaries must be strictly ordered')
    gap_intervals=payload['begin']['cycle']-clear['end']['cycle']
    if gap_intervals!=int(item['clear']['gap_to_source_request']):
        raise ValueError('ABI/control gap differs from original clear observer')
    gap=dict(begin=dict(clear['end']),end=dict(payload['begin']),period_intervals=gap_intervals,
             duration_fs=payload['begin']['tick_fs']-clear['end']['tick_fs'])
    windows=dict(clear=clear,abi_control_gap=gap,payload=payload)
    for window in windows.values():
        intervals=window['end']['cycle']-window['begin']['cycle']
        duration=window['end']['tick_fs']-window['begin']['tick_fs']
        if abs(Fraction(duration)-Fraction(intervals*20000000,3))>1:
            raise ValueError('activity phase exceeds balanced150 one-fs budget')
    duration=bounds[-1]['tick_fs']-bounds[0]['tick_fs']
    if sum(w['end']['tick_fs']-w['begin']['tick_fs'] for w in windows.values())!=duration:
        raise ValueError('clear/gap/payload physical durations do not partition continuous span')
    return windows,dict(status='HALF_OPEN_CONTIGUOUS_DIGITAL_WINDOWS',begin=bounds[0],end=bounds[-1],
        duration_fs=duration,period_intervals=bounds[-1]['cycle']-bounds[0]['cycle'],
        inclusive_boundary_edges=bounds[-1]['cycle']-bounds[0]['cycle']+1,
        gap_hf_intervals=gap_intervals,partition='[clear.begin,clear.end) U [clear.end,payload.begin) U [payload.begin,payload.end)',
        energy_qualification='NOT_MEASURED',startup_before_first_clear_request='OUTSIDE_REPORTED_SPAN')


def inspect(saif,activity,ppa,profile,window):
    observed=activity.read_saif(saif)
    duration=window['end']['tick_fs']-window['begin']['tick_fs']
    ppa.require(Decimal(observed['duration_seconds'])==Decimal(duration)*Decimal('1e-15'),
                'SAIF duration differs from original phase timestamps')
    prefix='tb_accel_soc/dut'
    signals=observed['signals']
    ppa.require(all(s['path'].startswith(prefix+'/') for s in signals),'activity escaped full SoC scope')
    clocks=[s for s in signals if s['path']==prefix+'/hfextclk']
    ppa.require(len(clocks)==1,'full SoC source clock missing/duplicate')
    expected_edges=Decimal(duration)*Decimal('3e-7')
    ppa.require(clocks[0]['TX']==0 and clocks[0].get('TZ',0)==0 and
                abs(Decimal(clocks[0]['TC'])-expected_edges)<=2,'source clock activity differs from nominal150')
    hardware=ppa.hardware_profile(profile)
    prefixes={name:prefix+'/'+value[0] for name,value in hardware['retained'].items()}
    prefixes.update({name:prefix+'/'+(value[:-2] if value.endswith('/*') else value)
                     for name,value in hardware['scopes'].items()})
    scopes={}
    for name,scope in prefixes.items():
        selected=[s for s in signals if s['path'].startswith(scope+'/')]
        ppa.require(selected,'missing SoC scope: '+name)
        toggles=sum(s['TC'] for s in selected)
        scopes[name]=dict(prefix=scope,signal_bits=len(selected),toggles=sum(s['TC'] for s in selected),
                          unknown_bit_ticks=sum(s['TX']+s.get('TZ',0) for s in selected),
                          observed_activity='TOGGLES_OBSERVED' if toggles else 'NO_TOGGLE_OBSERVED_REVIEW_PENDING')
    clock_paths=[canonical_macro_path(s['path']) for s in signals if s['path'].endswith('/CLK')]
    macro_clocks=[path for path in clock_paths if path.endswith('/macro/CLK')]
    ppa.require(len(macro_clocks)==len(set(macro_clocks)),'native macro canonicalization collision')
    instances={path[:-4] for path in macro_clocks}
    # One lookup per signal keeps this linear in the full SoC pin inventory.
    pins={name:[] for name in instances}
    for signal in signals:
        canonical=canonical_macro_path(signal['path'])
        instance=canonical.rsplit('/',1)[0]
        if instance in pins:
            pins[instance].append(dict(signal,path=canonical,native_path=signal['path']))
    accounted=set();groups={}
    for name,pattern in hardware['scopes'].items():
        found={value for value in instances if fnmatch.fnmatchcase(value,prefix+'/'+pattern)}
        ppa.require(len(found)==hardware['bits'][name]//16384 and not accounted&found,
                    'SAIF macro scope/count differs: '+name)
        accounted.update(found);rows=[]
        for instance in sorted(found):
            selected=pins[instance]
            ppa.require(len({s['path'] for s in selected})==len(selected),'macro pin canonicalization collision')
            pin_names={s['path'].rsplit('/',1)[1] for s in selected}
            for pin,width in [('CLK',1),('CEN',1),('GWEN',1),('RET1N',1),
                              ('A',10),('D',16),('WEN',16),('Q',16),('EMA',3),('EMAW',2)]:
                expected={pin} if width==1 else {pin+'[%d]'%i for i in range(width)}
                ppa.require(expected<=pin_names,'macro pin bits missing: '+instance+'/'+pin)
            rows.append(dict(instance=instance,pins=selected))
        groups[name]=dict(count=len(found),instances=rows,
            interpretation='raw RTL port dwell/toggles; inactive X preserved; not mapped coverage or internal power')
    ppa.require(accounted==instances,'unaccounted full SoC SAIF macro')
    return dict(saif=dict(path=str(saif),sha256=observed['sha256']),duration_fs=duration,
                signal_bits=len(signals),source_clock=clocks[0],scopes=scopes,macro_groups=groups,
                macro_count=len(instances),mapped_coverage='NOT_RUN',internal_power='NOT_MEASURED',
                effective_access_unknown_review='NOT_RUN_REQUIRES_JOINT_CEN_WEN_VALID_Q_TRACE',
                qualification='NOT_QUALIFIED')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',type=Path,required=True)
    parser.add_argument('--campaign-sha256',required=True)
    parser.add_argument('--source-root',type=Path,required=True,help='frozen campaign source root containing tools/scripts')
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--backend',choices=['python-streaming','native-vcd2saif'],default='python-streaming')
    parser.add_argument('--native-converter',type=Path)
    parser.add_argument('--reuse-conversions',type=Path,help='reuse SHA-bound completed phase receipts/SAIF; always rerun coverage audit')
    args=parser.parse_args(argv)
    args.source_root=args.source_root.resolve();args.campaign=args.campaign.resolve()
    ppa=load('_s3_convert_ppa',args.source_root/'tools/scripts/xu_soc_ppa.py')
    activity=load('_s3_convert_activity',args.source_root/'tools/scripts/xu_soc_activity.py')
    ppa.require(ppa.sha(args.campaign)==args.campaign_sha256,'campaign SHA differs')
    record=json.loads(args.campaign.read_text());extension=record['activity_extension']
    ppa.require(record['status']=='DEVELOPMENT_PASS_POLICY_PENDING' and not record['source_drift'],
                'campaign has no completed, unchanged functional proof')
    freeze_path=args.campaign.parent/'source/s3-full-source-freeze.json'
    ppa.require(ppa.sha(freeze_path)==record['original_source_sha256']['s3-full-source-freeze.json'],
                'campaign full-source freeze SHA differs')
    frozen=json.loads(freeze_path.read_text())
    ppa.require(ppa.digest(frozen['source_files'])==extension['source_manifest_sha256'],
                'campaign full-source manifest digest differs')
    for module in (ppa,activity):
        name=Path(module.__file__).relative_to(args.source_root).as_posix()
        ppa.require(ppa.sha(module.__file__)==frozen['source_files'][name]['sha256'],
                    'postprocess helper differs from campaign source freeze: '+name)
    ppa.require(extension['energy_scope']=='full-digital-soc-including-all-srams','campaign scope differs')
    profile=extension['hardware_profile'];ppa.hardware_profile(profile)
    ppa.require(extension['clock_configuration']['profile']=='nominal150-balanced-v1','unsupported physical clock policy')
    tasks=record['task_results'];layers=[item['original_layer'] for item in tasks]
    ppa.require(tasks and len(layers)==len(set(layers)) and all(type(x) is int and x in range(12) for x in layers),
                'activity task set must be nonempty with distinct original layers')
    ppa.require(all(set(item['activity']['windows'])=={'clear','payload'} for item in tasks),
                'every activity task needs exactly clear and payload windows')
    args.out.mkdir(parents=True,exist_ok=False)
    result=dict(schema='s3-full-soc-digital-activity-v1',status='RUNNING',qualification='NOT_QUALIFIED',
        model_kind=extension['model_kind'],macro_model=extension['model'],hardware_profile=profile,
        firmware_schedule=extension['firmware_schedule'],transaction_contract=extension['transaction_contract'],
        campaign=dict(path=str(args.campaign.resolve()),sha256=args.campaign_sha256),
        helpers={str(Path(m.__file__).resolve()):ppa.sha(m.__file__) for m in (ppa,activity)},
        converter_sha256=ppa.sha(__file__),tasks=[],taskset='PARTIAL_DEVELOPMENT_TASKS',
        backend=args.backend,
        limitations=['Digital RTL activity only; generic is non-PPA. No mapped/SDF/formal/STA proof.',
                     'Raw TX/TZ retained. No SRAM Liberty/internal-power or energy result.',
                     'Clear acceptance and FIFO physical-zero policy remain under review.'])
    ppa.write(args.out/'result.json',result)
    try:
        native=None
        if args.backend=='native-vcd2saif':
            ppa.require(args.native_converter is not None,'native backend requires an explicit converter path')
            # Synopsys dispatches this launcher by argv[0]. Resolving its
            # symlink to common_shell_exec loses the vcd2saif command name.
            args.native_converter=args.native_converter.absolute()
            native=native_probe(args.native_converter,args.out,activity,ppa)
            result['native_probe']=native
        for item in tasks:
            phases={};wave=item['activity']['full_soc_vcd']
            windows,continuity=phase_windows(item)
            ppa.require(wave is not None,'campaign has no full SoC VCD')
            path=Path(wave['path']);ppa.require(path.stat().st_size==wave['bytes'],'VCD size differs')
            if native is not None:ppa.require(ppa.sha(path)==wave['sha256'],'native VCD input SHA differs')
            for phase,window in windows.items():
                destination=args.out/('task-%02d-%s.saif'%(item['original_layer'],phase))
                receipt=(args.reuse_conversions/('task-%02d-%s-conversion.json'%(item['original_layer'],phase))
                         if args.reuse_conversions is not None else None)
                if receipt is not None and receipt.exists():
                    ppa.require(native is not None,'phase reuse requires explicitly probed native backend')
                    previous_probe=args.reuse_conversions/'native-probe.json'
                    previous=json.loads(previous_probe.read_text())
                    ppa.require(previous['binary']==native['binary'] and previous['transition_policy']==native['transition_policy'],
                                'reused native converter identity/policy differs')
                    conversion=json.loads(receipt.read_text())
                    ppa.require(conversion['schema']=='s3-native-vcd2saif-v1' and conversion['native_exit']==0 and
                                conversion['waitpid_completed'] and conversion['source_scope']=='tb_accel_soc/dut' and
                                conversion['begin_tick']==window['begin']['tick_fs'] and
                                conversion['end_tick']==window['end']['tick_fs'] and
                                conversion['transition_policy']==native['transition_policy'],'reused conversion window/policy differs')
                    destination=Path(conversion['saif']['path'])
                    logfile=args.reuse_conversions/('task-%02d-%s-native.log'%(item['original_layer'],phase))
                    ppa.require(ppa.sha(destination)==conversion['saif']['sha256'] and
                                ppa.sha(logfile)==conversion['log_sha256'],'reused SAIF/log SHA differs')
                    conversion=dict(conversion,reused_receipt=dict(path=str(receipt),sha256=ppa.sha(receipt),
                        probe_sha256=ppa.sha(previous_probe),coverage='REAUDITED_WITH_CURRENT_HELPER'))
                elif native is None:
                    with path.open('r') as source:
                        conversion=activity.vcd_to_saif(source,destination,window['begin']['tick_fs'],
                                                      window['end']['tick_fs'],'tb_accel_soc/dut')
                else:
                    command=[str(args.native_converter),'-64','-input',str(path),'-output',str(destination),
                             '-instance','tb_accel_soc.dut','-time',str(window['begin']['tick_fs']),str(window['end']['tick_fs'])]
                    logfile=args.out/('task-%02d-%s-native.log'%(item['original_layer'],phase))
                    with logfile.open('w') as log:
                        child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
                        code=child.wait()
                    ppa.require(code==0 and not re.search(r'^Error(?:\s|:)',logfile.read_text(),re.M),
                                'native full SoC conversion failed')
                    conversion=dict(schema='s3-native-vcd2saif-v1',status='CONVERTED_NOT_POWER_QUALIFIED',
                        command=command,native_exit=code,waitpid_completed=True,log_sha256=ppa.sha(logfile),
                        source_sha256=wave['sha256'],source_bytes=wave['bytes'],source_scope='tb_accel_soc/dut',
                        begin_tick=window['begin']['tick_fs'],end_tick=window['end']['tick_fs'],
                        transition_policy=native['transition_policy'],saif=dict(path=str(destination),sha256=ppa.sha(destination)))
                ppa.require(conversion['source_sha256']==wave['sha256'] and
                            conversion['source_bytes']==wave['bytes'],'converted VCD identity differs')
                ppa.write(args.out/('task-%02d-%s-conversion.json'%(item['original_layer'],phase)),conversion)
                phases[phase]=dict(conversion=conversion,
                    audit=inspect(destination,activity,ppa,profile,window))
                ppa.write(args.out/('task-%02d-%s.json'%(item['original_layer'],phase)),phases[phase])
                print('S3_DIGITAL_ACTIVITY_PHASE task=%d phase=%s macros=%d NOT_PPA'%(
                    item['original_layer'],phase,phases[phase]['audit']['macro_count']),flush=True)
            if native is not None:ppa.require(ppa.sha(path)==wave['sha256'],'native VCD changed during conversion')
            result['tasks'].append(dict(original_layer=item['original_layer'],phases=phases,continuity=continuity))
            ppa.write(args.out/'result.json',result)
        layers=[item['original_layer'] for item in result['tasks']]
        if layers==list(range(12)):result['taskset']='FULL_12_FUNCTIONAL_TASKS_NOT_PPA'
        result['status']='DIGITAL_ACTIVITY_EXTRACTED_NOT_POWER_QUALIFIED'
    except Exception as error:
        result['status']='FAIL';result['error']=str(error)
        raise
    finally:
        ppa.write(args.out/'result.json',result)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
