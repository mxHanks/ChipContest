#!/usr/bin/env python3
"""Strict saved-evidence comparison: unchanged packed-MMIO clear + READY payload.

Reuses the SHA-pinned packed-clear verifier's complete artifact/raw-log loader.
Only the externally reviewed eight-PE MacPE RTL SHA may change.
No source, native artifact, campaign result, or measured value is modified.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import sys

# Verification may import frozen local helpers but must never add bytecode to
# immutable measured source directories or corruption fixtures.
sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
CORE = 'rtl/perips/MacPE.sv'
LOADER_SHA = '2554944714fafb04370570b66ab217be283d4e2dd18306bfae22e06ef5567af2'
BASELINE_RESULT_SHA = '6c60c5cda7a0740b5169077936aa150366aec79e2f59e368e8549679af3bfce1'
BASELINE_MAP_SHA = '3104c0ea8d2183c6bf57be8aaa0243c75b1749101242f52cf60689ad253da61b'
BASELINE_CORE_SHA = '74321ca1a17f355f71ecea27807078d42c9be423564d453b2f1de097ffa2ae70'
CANDIDATE_CORE_SHA = '1b8eefc0910663a6996cb7f282def3f6a0b9656e016a18bb5a8b711f5c14a8d1'
SOURCE_COUNT = 171


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def find_inherited_loader():
    relative=Path('docs/validation/s3-y32-packed-clear-20261109/summaries/packed_clear_compare.py')
    # Supports both build/.../verification and docs/validation/.../verification
    # without embedding the developer checkout root. A standalone evidence
    # extraction may include the two SHA-pinned files in the local fallback.
    paths=[parent/relative for parent in (HERE,*HERE.parents)]
    paths.append(HERE/'inherited-packed-clear-verifier/packed_clear_compare.py')
    for path in paths:
        if path.is_file() and not path.is_symlink() and digest(path)==LOADER_SHA:
            return path
    raise ValueError('SHA-pinned inherited loader not found in ancestor repo or local evidence fallback')


LOADER_PATH=find_inherited_loader()
if digest(LOADER_PATH) != LOADER_SHA:
    raise ValueError('complete inherited loader SHA differs')
_spec = importlib.util.spec_from_file_location('bias_demand_pinned_packed_loader', LOADER_PATH)
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)
require = V.require
read_json = V.read_json


def baseline_pins():
    path = HERE/'baseline-sources.json'
    require(digest(path) == BASELINE_MAP_SHA, 'fixed packed-full12 source map file differs')
    pins = read_json(path)
    require(len(pins) == SOURCE_COUNT and pins.get(CORE) == BASELINE_CORE_SHA,
            'fixed 171-source baseline identity differs')
    return pins


def candidate_pins(pairs, identity=False):
    pins = baseline_pins()
    if identity:
        require(pairs == {}, 'identity validation accepts no source changes')
        return pins
    require(set(pairs) == {CORE}, 'only one reviewed MacPE.sv SHA pair is allowed')
    pair = pairs[CORE]
    require(pair == [BASELINE_CORE_SHA, CANDIDATE_CORE_SHA],
            'reviewed changed-core SHA pair is invalid')
    pins[CORE] = pair[1]
    return pins


def load_campaign(path, pins):
    """Select the exact reviewed core pin, retaining every inherited check.

    The inherited loader hardcodes its prior PE8 core SHA. No function is
    monkeypatched; the sole pin is temporarily replaced by the reviewed map
    entry, then restored. The full map equality and all 171 artifact hashes
    remain mandatory. Both profiles are the same eight-PE packed/READY mode.
    """
    require(len(pins) == SOURCE_COUNT and set(pins) == set(baseline_pins()),
            'source map membership/count differs')
    prior = V.PE8_CORE_SHA
    try:
        V.PE8_CORE_SHA = pins['rtl/perips/LinearAutoGroupCore.sv']
        return V.load_campaign(path, 'ready32-packed', pins)
    finally:
        V.PE8_CORE_SHA = prior


def normalized_elf_file_symbol(campaign):
    """Canonicalize one nonloaded local ABS FILE symbol's GCC random suffix.

    No code, PT_LOAD bytes, attributes, headers, section layout, other symbol,
    or other metadata byte may differ. GCC's final link embeds its temporary
    start.S object basename ccXXXXXX.o in a local STT_FILE symbol; only these
    six random characters may vary across otherwise identical native builds.
    """
    path=V.artifact(Path(campaign['result_path']).parent,'accel_soc',campaign['firmware_elf_sha256'])
    data=path.read_bytes();header=struct.unpack_from('<16sHHIIIIIHHHHHH',data)
    shoff,shentsize,shnum,shstrndx=header[6],header[11],header[12],header[13]
    require(shentsize==40 and 0<shnum<65535 and shstrndx<shnum and
            shoff+shnum*shentsize<=len(data),'ELF section table invalid')
    sections=[struct.unpack_from('<IIIIIIIIII',data,shoff+i*40) for i in range(shnum)]
    strings=sections[shstrndx];require(strings[1]==3 and strings[4]+strings[5]<=len(data),'ELF section names invalid')
    def cstring(offset,limit):
        end=data.find(b'\0',offset,limit);require(end>=offset,'ELF string not terminated')
        return data[offset:end]
    matches=[]
    for section in sections:
        if section[1]!=2:continue
        require(section[2]==0 and section[9]==16 and section[5]%16==0 and
                section[4]+section[5]<=len(data) and section[6]<shnum,'ELF symbol table invalid')
        table=sections[section[6]]
        require(table[1]==3 and table[2]==0 and table[4]+table[5]<=len(data),'ELF symbol strings invalid')
        require(cstring(strings[4]+section[0],strings[4]+strings[5])==b'.symtab' and
                cstring(strings[4]+table[0],strings[4]+strings[5])==b'.strtab','ELF symbol section names differ')
        # The string normalization is provably outside every file-backed load.
        for index in range(header[10]):
            ph=struct.unpack_from('<IIIIIIII',data,header[5]+index*32)
            require(ph[0]!=1 or table[4]+table[5]<=ph[1] or table[4]>=ph[1]+ph[4],
                    'ELF symbol strings overlap loaded bytes')
        for index in range(section[5]//16):
            name,value,size,info,other,ndx=struct.unpack_from('<IIIBBH',data,section[4]+index*16)
            require(name<table[5],'ELF symbol name outside string table')
            label=cstring(table[4]+name,table[4]+table[5])
            if info==4 and re.fullmatch(rb'cc[A-Za-z0-9]{6}\.o',label):
                require(value==size==other==0 and ndx==0xfff1,'GCC temp symbol semantics differ')
                require(data.count(label+b'\0')==1,'GCC temp symbol string not unique')
                matches.append((table[4]+name,label))
    require(len(matches)==1,'requires exactly one GCC local ABS temporary-object FILE symbol')
    offset,label=matches[0];canonical=data[:offset]+b'cc@@@@@@.o'+data[offset+len(label):]
    return dict(normalized_sha256=hashlib.sha256(canonical).hexdigest(),
        normalization='only six alphanumeric random characters in one nonloaded local ABS STT_FILE ccXXXXXX.o string',
        original_file_symbol=label.decode(),file_offset=offset)


def compare(before, after, pairs, identity=False):
    require(before['postflow_profile'] == after['postflow_profile'] == 'ready32-packed',
            'both sides require identical READY packed-clear profiles')
    # Unlike the older scalar -> packed comparison, remove no conditions,
    # helper identities, recipes, macros, work counts or firmware selectors.
    require(before['conditions'] == after['conditions'],
            'conditions differ; only exact campaign/repository path normalization is allowed')
    bs, cs = before['source_sha256'], after['source_sha256']
    observed = {p: [bs.get(p), cs.get(p)] for p in set(bs)|set(cs) if bs.get(p) != cs.get(p)}
    require(observed == pairs, 'source changes differ from exact reviewed SHA pair')
    require((identity and not observed) or (not identity and set(observed) == {CORE}),
            'exactly the one reviewed core must change in a performance comparison')
    require(len(bs) == len(cs) == SOURCE_COUNT, 'source count differs')
    require(before['generated_clear_c_identity'] == after['generated_clear_c_identity'],
            'generated C differs beyond the one exact frozen-main include path')
    require(before['generated_tb_sha256'] == after['generated_tb_sha256'], 'generated testbench differs')
    require(before['firmware_loaded_elf'] == after['firmware_loaded_elf'], 'loaded ELF contract differs')
    require(before['firmware_image_sha256'] == after['firmware_image_sha256'], 'loaded firmware image differs')
    elf_normalization=dict(baseline=normalized_elf_file_symbol(before),candidate=normalized_elf_file_symbol(after))
    require(elf_normalization['baseline']['normalized_sha256']==elf_normalization['candidate']['normalized_sha256'],
            'ELF differs beyond one exact nonloaded GCC temporary-object FILE symbol')
    require(before['original_layer_coverage'] == list(range(12)), 'baseline must retain full12 identity')
    require(len(before['rows']) == len(after['rows']) and before['rows'], 'layer count differs')
    layers = []
    for b, a in zip(before['rows'], after['rows']):
        require(b['original_layer'] == a['original_layer'], 'layer order differs')
        for key in ('vectors', 'vector_profile', 'profile_source_sha256', 'measured_clocks'):
            require(b[key] == a[key], 'input/model/clock differs: '+key)
        require(V.startup_signature(b['startup_observations']) == V.startup_signature(a['startup_observations']),
                'external reset semantics differ')
        # Physical clear protocol and observed work must match in every field
        # except the actually observed timing; timing deltas remain explicit.
        clear_timing = {'clear_cycles', 'response_end_cycle', 'gap_to_source_request'}
        require({k:v for k,v in b['clear'].items() if k not in clear_timing} ==
                {k:v for k,v in a['clear'].items() if k not in clear_timing},
                'physical clear protocol/work/policy differs')
        work = ('mac_fire', 'mmio_reads', 'mmio_writes', 'shared_reads', 'shared_writes', 'starts', 'dones')
        require({k:b['bus_counters'][k] for k in work} == {k:a['bus_counters'][k] for k in work},
                'compute or bus transaction work differs')
        require(b['nice'] == a['nice'] and b['transport'] == a['transport'], 'NICE/direct work differs')
        require({k:b['auto'][k] for k in ('rows','pops_retired')} ==
                {k:a['auto'][k] for k in ('rows','pops_retired')}, 'autogroup work differs')
        # checked_cycles is measured, while PE work is fixed independently.
        require({k:v for k,v in b['physical'].items() if k != 'checked_cycles'} ==
                {k:v for k,v in a['physical'].items() if k != 'checked_cycles'}, 'physical PE work differs')
        for marker in ('stream_activity','ready_activity'):
            timing = {'ready_wait_cycles'}
            bm, am = (row['additional_markers'][marker] for row in (b,a))
            require({k:v for k,v in bm.items() if k not in timing} ==
                    {k:v for k,v in am.items() if k not in timing}, 'stream/READY work differs')
        bt, at = V.totals([b]), V.totals([a])
        require(bt == at, 'per-layer 41-bit timing and work totals differ')
        require(b['window'] == a['window'], 'per-layer request/final-response window differs')
        require(b['clear'] == a['clear'], 'per-layer physical-clear timing or work differs')
        layers.append(dict(original_layer=b['original_layer'], baseline=bt, candidate=at,
            delta=V.differences(bt, at), physical=dict(baseline=b['physical'],candidate=a['physical']),
            additional_markers=dict(baseline=b['additional_markers'],candidate=a['additional_markers']),
            windows=dict(baseline=b['window'],candidate=a['window']),
            clear_markers=dict(baseline=b['clear'],candidate=a['clear']),
            startup_observations=dict(baseline=b['startup_observations'],candidate=a['startup_observations'])))
    bt, at = V.totals(before['rows']), V.totals(after['rows'])
    require(bt == at, '41-bit candidate must preserve every measured work, phase and timing total')
    if identity:
        require(before['result_sha256'] == after['result_sha256'] == BASELINE_RESULT_SHA,
                'identity check must compare pinned baseline to itself')
        require(bt == at, 'identity totals differ')
    return dict(schema='s3-acc41-strict-comparison-v1',
        status='IDENTITY_VALIDATION_NONPERFORMANCE' if identity else 'ACC41_SAVED_CAMPAIGNS_COMPARED',
        scope='read-only development saved-evidence verification; no synthesis, PPA or official qualification',
        performance_claim_allowed=False, accumulator_scope='Only eight ACC registers narrow48->41; external48 result and protocol preserved; no PPA claim',
        metric='payload request-to-final-Y-response plus separately observed physical clear cycles',
        delta_convention='candidate minus baseline; negative measured cycle delta is an improvement',
        timing_semantics='measured phases/stalls/READY_WAIT retained; no padding or phase adjustment',
        gap_semantics='clear-to-source gap reported separately, excluded from principal total',
        numerical_semantics='unchanged SHA-pinned TB compares all 25344 Y32 values per layer; exact raw TASK_PASS/SOC_PASS required',
        proof_limits=dict(clear_policy='REVIEW_PENDING',fifo_payload_physical_zero='UNPROVEN',
            simulator='Verilator two-state; retained Chisel assertions; no STA/PPA claim'),
        verifier=dict(path=str(Path(__file__).resolve()),sha256=digest(__file__),
            inherited_loader_path=str(LOADER_PATH),inherited_loader_sha256=LOADER_SHA,
            baseline_source_map_sha256=BASELINE_MAP_SHA,source_count=SOURCE_COUNT,
            reviewed_core_pin_only=True,condition_normalizations=['exact saved campaign/repository path prefixes']),
        source_changes={k:dict(baseline_sha256=v[0],candidate_sha256=v[1]) for k,v in observed.items()},
        firmware_identity=dict(raw_elf_sha256_equal=before['firmware_elf_sha256']==after['firmware_elf_sha256'],
            strict_nonloaded_elf_normalization=elf_normalization,loaded_image_sha256_equal=True,
            elf_load_contract_equal=True,loaded_firmware_change_allowed=False,
            independent_load_verification=dict(baseline=V.verify_loaded_image(before),candidate=V.verify_loaded_image(after))),
        baseline_identity={k:v for k,v in before.items() if k != 'rows'},
        candidate_identity={k:v for k,v in after.items() if k != 'rows'},
        layer_selection=dict(baseline_original=before['original_layer_coverage'],
            candidate_original=after['original_layer_coverage'],compared=[r['original_layer'] for r in before['rows']],
            mode=before['selection_mode'],original_results_unmodified=True),
        layers=layers,totals=dict(baseline=bt,candidate=at,delta=V.differences(bt,at)))


def verify(baseline, candidate, pairs, layers=None, identity=False):
    require(digest(baseline) == BASELINE_RESULT_SHA, 'baseline is not pinned packed-full12 result')
    before = load_campaign(baseline, baseline_pins())
    after = load_campaign(candidate, candidate_pins(pairs,identity))
    require([r['original_layer'] for r in before['rows']] == list(range(12)), 'baseline is not full12')
    candidate_layers = [r['original_layer'] for r in after['rows']]
    selected = list(range(12)) if layers is None else layers
    require(candidate_layers == selected, 'candidate must cover every selected original layer in order')
    mode = 'full12-to-full12' if layers is None else 'explicit-common-layer-projection'
    before = V.project_layers(before,selected,mode)
    after = V.project_layers(after,selected,mode)
    return compare(before,after,pairs,identity)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline',type=Path)
    parser.add_argument('candidate',type=Path)
    parser.add_argument('--source-pairs',type=Path,required=True)
    parser.add_argument('--layers',type=V.parse_layers)
    parser.add_argument('--identity',action='store_true',help='baseline-to-itself validation; makes no performance claim')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    try:
        result=verify(args.baseline,args.candidate,read_json(args.source_pairs),args.layers,args.identity)
        with args.out.open('x') as stream:
            json.dump(result,stream,sort_keys=True,indent=2);stream.write('\n')
        print(result['status'])
        for key in ('payload_cycles','clear_cycles','payload_plus_clear_cycles','clear_to_source_gap'):
            print(key,result['totals']['baseline'][key],result['totals']['candidate'][key],result['totals']['delta'][key])
        return 0
    except (OSError,ValueError,KeyError,TypeError,StopIteration,AttributeError) as error:
        print('BIAS_DEMAND_COMPARISON_REJECTED:',error,file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
