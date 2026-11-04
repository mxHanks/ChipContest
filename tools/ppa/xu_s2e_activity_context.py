#!/usr/bin/env python3
"""Explicit source/tool contexts for the frozen S2e activity candidate.

No baseline source/guard is changed. Private module instances compose the
frozen generator with the separately hash-checked candidate TB and contracts.
Python 3.6+, standard library only.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

TOOL_ROOT = Path(__file__).resolve().parents[2]
PROFILE = 's2e-paired-hi'
MAIN_COMMIT = '5bf123bfead8f2a37f97f3234d4e40ce8201aae9'
SCHEDULE = 'bias-hw-autogroup-paired-hi-window'
FROZEN_TOOLS = {
    'tools/ppa/xu_sirv_sram_adapter.sv': 'b2b2baaa1e105ed794382886439cd2c16fd280a0f29b54c4d925351e6f90a0c5',
    'tools/ppa/xu_weight_sram_adapter.sv': '86b49e6279e9e9ac2c91467028608be8e3ca1caadb811ddd09d379311730d707',
    'tools/ppa/xu_shared_icb_sram.sv': '2ebad6ec1870806cb4b770610213aa4d3318e272f6433bf68e6175b15fa25e9d',
    'tools/ppa/xu_soc_ppa_top.sv': '8d0e5fd38f2425e7ea8041dd5b8c3a8fd4ce7fa171afb1bf0ebeb6f53446f28a',
    'tools/ppa/xu_soc_task_activity.py': '84bd2ac43621fcee46b3e8c336d0ccb0142ec0d1180fc7926ee2af5cef676511',
    'tools/ppa/xu_soc_ppa_verify.py': 'feeb24d171bc251e7020b77ed1b29d6e2a30da4d9037269f4e7c06b150252967',
    'tools/ppa/xu_task_clear_protocol.py': '467e51abbaefa1ef40e3c2d5cfbc18376be351886b212f7667f0a44934488ee8',
    'tools/ppa/xu_sram_activity_alias.py': '5e36356860aae2e6c1993a9dafbce884534c657eec7b1bb0be1b7420a0153c7c',
    'tools/scripts/e203_soc.py': '573d0d1830069cf99ea73bcf2553b175bc77f6f5ecbe7595036453a193970e2b',
    'tools/scripts/xu_firmware_contract.py': 'a0602663237aec93e52f1ea38ff7982ceb21f603f334899cbc48fd6a51c30b96',
    'tools/scripts/xu_soc_activity.py': '8a10bde83fb1a622b01f6b9a014e9b65b286f1f76a3a214c62f6c6d6a784c942',
    'tools/scripts/xu_soc_ppa.py': 'cccbee4288193254f0ec0ca50c741bfe8836593a4cf67b26b4fdcd9b6f732c73',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity(path):
    path = Path(path).absolute()
    require(path.is_file() and not path.is_symlink(), 'regular non-symlink file required: ' + str(path))
    return dict(path=str(path), sha256=sha(path))


def git(root, *arguments):
    return subprocess.check_output(['git', '--no-replace-objects'] + list(arguments),
                                   cwd=str(root), stdin=subprocess.DEVNULL).decode().strip()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def source_identity(root):
    """Verify every tracked main blob, gitlink, mode and complete child tree.

    Independent blob hashing also rejects assume-unchanged/skip-worktree edits.
    Nonignored untracked files in the source root are rejected. The approved
    child profile separately rejects ignored/untracked live RTL sources.
    """
    root = Path(root).resolve()
    require(Path(git(root, 'rev-parse', '--show-toplevel')).resolve() == root,
            'candidate source must be its own repository root')
    require(git(root, 'rev-parse', 'HEAD') == MAIN_COMMIT, 'candidate main commit differs from frozen S2e')
    require(not git(root, 'status', '--porcelain', '--untracked-files=all'), 'candidate main/child is dirty or untracked')
    raw = subprocess.check_output(['git', '--no-replace-objects', 'ls-tree', '-rz', 'HEAD'], cwd=str(root))
    records = {}
    for entry in raw.split(b'\0'):
        if not entry:
            continue
        meta, raw_name = entry.split(b'\t', 1)
        mode, kind, oid = meta.decode('ascii').split()
        name = os.fsdecode(raw_name)
        path = root / name
        if mode == '160000':
            require(name == 'third-party/e203_hbirdv2' and git(path, 'rev-parse', 'HEAD') == oid,
                    'unexpected/uninitialized/mismatched candidate gitlink: ' + name)
            records[name] = dict(mode=mode, commit=oid)
            continue
        require(kind == 'blob', 'unsupported main tree entry: ' + name)
        if mode == '120000':
            require(path.is_symlink(), 'main tree symlink differs: ' + name)
            content = os.fsencode(os.readlink(str(path)))
        else:
            require(mode in ('100644', '100755') and path.is_file() and not path.is_symlink(),
                    'main tree file missing/type differs: ' + name)
            require(bool(path.stat().st_mode & 0o111) == (mode == '100755'), 'main file mode differs: ' + name)
            content = path.read_bytes()
        actual = hashlib.sha1(b'blob ' + str(len(content)).encode('ascii') + b'\0' + content).hexdigest()
        require(actual == oid, 'main worktree bytes differ from frozen S2e: ' + name)
        records[name] = dict(mode=mode, sha256=hashlib.sha256(content).hexdigest())
    # This independent approved-profile guard checks child commit, full fixed
    # platform delta, every tracked byte/mode and untracked/ignored live RTL.
    ppa = load('xu_candidate_profile_guard', TOOL_ROOT / 'tools/scripts/xu_soc_ppa.py')
    child = ppa.source_profile_identity(root, PROFILE)
    return dict(root=str(root), main_commit=MAIN_COMMIT, main_tree=git(root, 'rev-parse', 'HEAD^{tree}'),
                main_worktree_manifest_sha256=canonical(records), main_tracked_entries=len(records),
                source_profile=child)


def tool_identity():
    records = []
    for name, expected in sorted(FROZEN_TOOLS.items()):
        record = identity(TOOL_ROOT / name)
        require(record['sha256'] == expected, 'frozen baseline/common tool bytes differ: ' + name)
        records.append(record)
    require(Path(git(TOOL_ROOT, 'rev-parse', '--show-toplevel')).resolve() == TOOL_ROOT, 'tool root is not repository root')
    require(not git(TOOL_ROOT, 'status', '--porcelain', '--untracked-files=all'), 'tool checkout must be clean and committed')
    for name in ('xu_s2e_activity_context.py','xu_s2e_task_activity.py',
                 'xu_s2e_sram_activity_alias.py','xu_s2e_activity_observer.svh','xu_s2e_activity_server.py'):
        relative='tools/ppa/'+name
        data=(TOOL_ROOT/relative).read_bytes()
        expected=git(TOOL_ROOT,'rev-parse','HEAD:'+relative)
        actual=hashlib.sha1(b'blob '+str(len(data)).encode('ascii')+b'\0'+data).hexdigest()
        require(actual==expected,'S2e producer worktree differs from committed source: '+relative)
        records.append(identity(TOOL_ROOT/relative))
    return dict(root=str(TOOL_ROOT), main_commit=git(TOOL_ROOT, 'rev-parse', 'HEAD'),
                main_tree=git(TOOL_ROOT, 'rev-parse', 'HEAD^{tree}'), frozen_common_tools=records,
                baseline_tools_policy='S2e explicitly pins current PPA profile guard; every other common asset is unchanged. Old S2c producer/context is untouched.')


def checked_mapped_context(root,ppa_root):
    """Bind actual completed S2e89 synthesis/FМ, never an arbitrary/S2c netlist."""
    root,ppa_root=Path(root).resolve(),Path(ppa_root).resolve()
    ppa=load('xu_s2e_mapping_profile_guard',TOOL_ROOT/'tools/scripts/xu_soc_ppa.py')
    source=ppa.source_profile_identity(root,PROFILE)
    state_path=ppa_root/'state.json';state=json.loads(state_path.read_text())
    require(state.get('status')=='EXECUTED_NOT_QUALIFIED','completed S2e89 DC/Formality/PT context required')
    require(state.get('source_before')==state.get('source_after')==source,'mapped S2e source freeze differs')
    require(state.get('inputs_before') and state.get('inputs_before')==state.get('inputs_after'),'mapped tool/library freeze differs')
    require(state.get('formality',{}).get('status')=='VERIFIED_FULL_SOC_REVIEW_PENDING_NOT_QUALIFIED',
            'own S2e full-SoC Formality completion required')
    prepared_path=ppa_root/'ppa/prepared.json';prepared=json.loads(prepared_path.read_text())
    ppa.verify_prepared(root,ppa_root/'ppa',prepared)
    impl=prepared['implementation']
    require(impl.get('source_profile')==PROFILE and impl.get('source_freeze',{}).get('main_commit')==MAIN_COMMIT and
            impl.get('source_freeze',{}).get('profile')==source,'prepared S2e source profile differs')
    require(impl.get('defines')==['SYNTHESIS','DISABLE_SV_ASSERTION=1'] and
            sum(g['count'] for g in impl['memory_groups'])==336 and
            all(g['macro_ref']=='RAMSP1024X16' for g in impl['memory_groups']), 'mapped SRAM geometry/defines differ')
    netlist=identity(ppa_root/'ppa/mapped.v');constraints=identity(ppa_root/'ppa/constraints.sdc')
    require(netlist['sha256']==state.get('netlist',{}).get('sha256'),'actual own mapped netlist identity differs')
    require(constraints['sha256']=='404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98',
            'original nominal150MHz constraints differ')
    require(identity(ppa_root/'ppa/default.svf')['sha256']==state.get('own_svf',{}).get('sha256'),
            'actual own synthesis SVF identity differs')
    # An equal pair of receipt dictionaries is not an on-disk freeze check.
    # Rehash the actual original tool/library/RTL/SVF files, and re-read the
    # own proof's terminal state and log. No S2c filename/hash is substituted.
    frozen=checked_frozen_records(state['inputs_before'],'actual S2e89 tool/library inputs')
    formal_path=ppa_root/'formality/state.json'
    formal=json.loads(formal_path.read_text())
    require(formal==state['formality'],'actual own Formality state differs from campaign state')
    require(formal.get('frozen_before') and formal['frozen_before']==formal.get('frozen_after'),
            'actual own Formality input freeze differs')
    frozen+=checked_frozen_records(formal['frozen_before'],'actual own Formality inputs')
    proof_paths={str(ppa_root/'ppa'/name) for name in ('mapped.v','default.svf','rtl.f')}
    proof_paths|={str(Path(item['path'])) for item in impl['libraries']}
    proof_paths|={str(p) for p in (ppa_root/'ppa/rtl').rglob('*') if p.is_file()}
    proof_paths.add(str(ppa_root/'formality/verify.tcl'))
    require(set(formal['frozen_before'])==proof_paths,'actual own Formality complete input set differs')
    formal_log=ppa_root/'formality/fm.log'
    require(formal.get('returncode')==0 and
            checked_record(formal.get('log',{}),'actual own Formality log')==identity(formal_log),
            'actual own Formality log identity/return code differs')
    proof_text=formal_log.read_text(errors='replace')
    require('Version R-2020.09-SP5' in proof_text and
            re.findall(r'^XU_S2E_FULL_SOC_FORMALITY_PASS\s*$',proof_text,re.M)==['XU_S2E_FULL_SOC_FORMALITY_PASS'] and
            not re.search(r'^\s*(?:Error:|Fatal:|XU_S2E_FULL_SOC_FORMALITY_(?:FAIL|SCRIPT_ERROR))',proof_text,re.M),
            'actual own full-SoC Formality completion missing/failed')
    execution_path=ppa_root/'ppa/execution.json'
    execution=json.loads(execution_path.read_text())
    require(execution.get('status') in ('EXECUTED_NOT_QUALIFIED','DC_EXECUTED_PT_INCOMPLETE_NOT_QUALIFIED') and
            execution.get('netlist_sha256')==netlist['sha256'] and
            execution.get('analysis_sdc_sha256')==constraints['sha256'] and
            execution.get('sdc_sha256')==sha(ppa_root/'ppa/mapped.sdc') and
            execution.get('dc')==state.get('dc') and execution.get('formality')==formal,
            'actual own DC/execution/SVF proof context differs')
    dc_log=ppa_root/'ppa/dc.log'
    require(state.get('dc',{}).get('returncode')==0 and
            state['dc'].get('log_sha256')==sha(dc_log),'actual own DC log identity/return code differs')
    dc_text=dc_log.read_text(errors='replace')
    require('Version T-2022.03-SP5-5' in dc_text and
            re.findall(r'^XU_SOC_SYNTHESIS_COMPLETE_NOT_QUALIFIED[ \t]*$',dc_text,re.M)==['XU_SOC_SYNTHESIS_COMPLETE_NOT_QUALIFIED'] and
            not re.search(r'^\s*(?:Error:|Fatal:|FATAL:|XU_FATAL:)',dc_text,re.M),
            'actual own DC completion missing/failed')
    for name,record in prepared['source_files'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts,'unsafe prepared source path')
        require(sha(ppa_root/'ppa'/name)==record['sha256'],'prepared mapping RTL bytes differ: '+name)
    identities=[identity(p) for p in (state_path,prepared_path,execution_path,formal_path,formal_log,
                                    ppa_root/'ppa/default.svf',ppa_root/'ppa/mapped.sdc',dc_log)]+frozen
    identities=list({item['path']:item for item in identities}.values())
    return dict(schema='xu-s2e-actual-mapped-context-v1',source_profile=source,netlist=netlist,constraints=constraints,
                inputs=identities,limitations='Identity and prior own-SVF full proof only; no timing or power qualification')


def checked_record(record,label):
    """Verify a native PPA record without silently dropping its byte count."""
    require(isinstance(record,dict) and set(record)=={'path','bytes','sha256'},label+' record schema differs')
    path=Path(record['path'])
    require(path.is_absolute(),label+' must identify an absolute file')
    actual=identity(path)
    require(record['bytes']==path.stat().st_size and record['sha256']==actual['sha256'],
            label+' actual bytes/hash differ: '+str(path))
    return actual


def checked_frozen_records(records,label):
    require(isinstance(records,dict) and records,label+' missing')
    result=[]
    for path,record in sorted(records.items()):
        require(isinstance(record,dict) and record.get('path')==path,label+' key/path differs')
        result.append(checked_record(record,label))
    return result


class Context:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.tool = tool_identity()
        self.source = source_identity(self.root)
        # Explicitly select the frozen candidate contracts. Temporary import
        # bindings are restored; shared baseline module objects are never edited.
        self.contract = load('xu_s2c_frozen_contract', self.root / 'tools/scripts/xu_firmware_contract.py')
        missing = object()
        saved = {name: sys.modules.get(name, missing) for name in ('xu_firmware_contract', 'e203_soc')}
        try:
            sys.modules['xu_firmware_contract'] = self.contract
            self.soc = load('xu_s2c_frozen_soc', self.root / 'tools/scripts/e203_soc.py')
            sys.modules['e203_soc'] = self.soc
            self.base = load('xu_candidate_private_generator', TOOL_ROOT / 'tools/ppa/xu_soc_ppa_verify.py')
        finally:
            for name, value in saved.items():
                if value is missing:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = value
        self.base.TB = self.root / 'tests/e203/tb_accel_soc.sv'
        self.base.RTL = self.root / 'third-party/e203_hbirdv2/rtl/e203'
        self.base.ROOT = self.root
        self.clear = load('xu_candidate_frozen_clear', TOOL_ROOT / 'tools/ppa/xu_task_clear_protocol.py')
        self.activity = load('xu_candidate_frozen_saif', TOOL_ROOT / 'tools/scripts/xu_soc_activity.py')
        self.configuration = self.contract.configuration(SCHEDULE, '-O2', 'both-unroll-no-masks')

    def recheck(self):
        require(self.tool == tool_identity(), 'tool identity changed during collection')
        require(self.source == source_identity(self.root), 'candidate identity changed during collection')
