"""Exact source contexts for the eight independent inventory137 candidates."""
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ASSETS = HERE / 'assets'
SCHEDULES = dict(baseline_h1_h2='bias-hw-window', s1_h2_only='bias-dtcm-window',
                 s1_sram_bias='bias-hw-window', s2b='bias-hw-pack32-window',
                 s2d='bias-hw-doublebuf-window', pe32='bias-hw-pe32-autogroup-window',
                 pe64='bias-hw-pe64-autogroup-window', compact32_128='bias-hw-pe32-autogroup-window')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def identity(path):
    path = Path(path).absolute()
    require(path.is_file() and not path.is_symlink(), 'regular non-symlink file required: '+str(path))
    return dict(path=str(path), sha256=sha(path), bytes=path.stat().st_size)


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')
    temporary.replace(path)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(root, *args):
    return subprocess.check_output(['git', '--no-replace-objects']+list(args), cwd=str(root),
                                   stdin=subprocess.DEVNULL).decode().strip()


def tree_identity(root, expected, child_expected=None):
    root = Path(root).resolve()
    require(Path(git(root, 'rev-parse', '--show-toplevel')).resolve()==root, 'source is not its own Git root')
    require(git(root, 'rev-parse', 'HEAD')==expected, 'source HEAD differs from inventory137')
    require(not git(root, 'status', '--porcelain', '--untracked-files=all'), 'source tracked/untracked state is dirty')
    raw = subprocess.check_output(['git', '--no-replace-objects', 'ls-tree', '-rz', 'HEAD'], cwd=str(root))
    records = {}
    for entry in raw.split(b'\0'):
        if not entry:
            continue
        meta, name = entry.split(b'\t', 1)
        mode, kind, oid = meta.decode().split()
        name = os.fsdecode(name); path = root/name
        if mode=='160000':
            require(name=='third-party/e203_hbirdv2' and oid==child_expected, 'unexpected Gitlink')
            records[name] = tree_identity(path, child_expected)
            continue
        require(kind=='blob', 'unexpected tree object: '+name)
        if mode=='120000':
            require(path.is_symlink(), 'source symlink differs: '+name)
            content = os.fsencode(os.readlink(str(path)))
        else:
            require(mode in ('100644','100755') and path.is_file() and not path.is_symlink(), 'source type differs: '+name)
            require(bool(path.stat().st_mode & 0o111)==(mode=='100755'), 'source mode differs: '+name)
            content = path.read_bytes()
        require(hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()==oid,
                'source bytes differ despite Git status: '+name)
        records[name] = dict(mode=mode, sha256=hashlib.sha256(content).hexdigest())
    # Refuse ignored live RTL files as well as ordinary untracked files.
    rtl = root/'rtl/e203'
    if rtl.is_dir():
        actual = {str(p.relative_to(root)) for p in rtl.rglob('*') if p.is_file() and p.suffix in ('.sv','.v','.vh','.svh')}
        require(actual <= set(records), 'untracked or ignored live RTL file present')
    return dict(root=str(root), main_commit=expected, tree=git(root,'rev-parse','HEAD^{tree}'),
                tracked_entries=len(records), bytes_and_modes_sha256=canonical(records))


def asset_identity():
    hashes = json.loads((HERE/'assets.sha256.json').read_text())
    require({p.name for p in ASSETS.iterdir() if p.is_file()}==set(hashes), 'asset file set differs')
    result = []
    for name, digest in sorted(hashes.items()):
        item = identity(ASSETS/name)
        require(item['sha256']==digest, 'frozen asset differs: '+name)
        result.append(item)
    return result


def vendor_model_records():
    """Bind common official models to the original138 freeze, across profiles.

    Only baseline138 listed the1024 model and only compact138 listed128.
    Other candidates reuse those same supplied models; absence in their own
    old producer receipt is not permission to substitute a different model.
    """
    plan = json.loads((HERE/'queue-plan138.snapshot.json').read_text())
    records = {}
    for ref in ('RAMSP1024X16', 'RAMSP128X16'):
        candidates = [r for c in plan['candidates'] for r in c['freeze_inputs']
                      if Path(r['path']).name==ref+'.v' and '/verilog/' in r['path']]
        signatures = {r['sha256'] for r in candidates}
        require(len(signatures)==1, 'single frozen official vendor model required: '+ref)
        sizes = {r['bytes'] for r in candidates if 'bytes' in r}
        require(len(sizes)<=1, 'ambiguous original vendor model size: '+ref)
        records[ref] = dict(sha256=next(iter(signatures)),
                            original_paths=sorted({r['path'] for r in candidates}))
        if sizes:records[ref]['bytes']=next(iter(sizes))
    return records


def check_vendor_model(ref, path):
    require(ref in vendor_model_records(), 'unsupported official vendor model')
    expected = vendor_model_records()[ref]
    actual = identity(path)
    require(all(actual[k]==expected[k] for k in ('sha256','bytes') if k in expected),
            'vendor model differs from original138 supplied bytes: '+ref)
    require(re.search(r'\bmodule\s+'+ref+r'\b',Path(path).read_text()), 'vendor module differs: '+ref)
    return dict(ref_name=ref, selected=actual, original138=expected)


def check_fixture_manifest(manifest, validated):
    """Externally supplied vectors must still be the exact original12 tasks."""
    require([r.get('layer') for r in validated]==list(range(12)), 'original twelve vector layers required')
    required = {'x.mem','w.mem','bias.mem','y.mem'}
    for task in validated:
        require(set(task['sha256'])==required, 'unexpected vector tensor file set')
        for name in sorted(required):
            key='layer_%02d/%s'%(task['layer'],name)
            require(task['sha256'][name]==manifest['files'][key], 'vector differs from original fixture: '+key)


class Context:
    def __init__(self, candidate, root):
        inventory = json.loads((HERE/'inventory137.snapshot.json').read_text())
        matches = [c for c in inventory['candidates'] if c['id']==candidate]
        require(len(matches)==1, 'unknown inventory137 candidate')
        self.candidate = matches[0]; self.id = candidate; self.root = Path(root).resolve()
        plan=json.loads((HERE/'queue-plan138.snapshot.json').read_text())
        self.queue_candidate=next(c for c in plan['candidates'] if c['id']==candidate)
        self.schedule = SCHEDULES[candidate]
        self.variant = 'pe64' if candidate=='pe64' else 'pe32-bank128' if candidate=='compact32_128' else 'pe32' if candidate=='pe32' else 'pe8'
        self.assets = asset_identity()
        self.source = self.source_identity()
        self.contract = load('xu_contract145_'+candidate, self.root/'tools/scripts/xu_firmware_contract.py')
        missing = object()
        saved = {k:sys.modules.get(k, missing) for k in ('xu_firmware_contract','e203_soc')}
        try:
            sys.modules['xu_firmware_contract'] = self.contract
            self.soc = load('xu_soc145_'+candidate, self.root/'tools/scripts/e203_soc.py')
            sys.modules['e203_soc'] = self.soc
            self.base = load('xu_base145_'+candidate, ASSETS/'xu_soc_ppa_verify.py')
        finally:
            for key,value in saved.items():
                if value is missing: sys.modules.pop(key,None)
                else: sys.modules[key]=value
        self.base.TB = self.root/'tests/e203/tb_accel_soc.sv'
        self.base.ROOT = self.root
        self.base.RTL = self.root/'third-party/e203_hbirdv2/rtl/e203'
        self.configuration = self.contract.configuration(self.schedule,'-O2','both-unroll-no-masks')
        self.reader = load('xu_saif145_'+candidate, ASSETS/'xu_soc_activity.py')
        self.alias_helpers = load('xu_alias145_'+candidate, ASSETS/'xu_sram_activity_alias.py')

    def source_identity(self):
        source = self.candidate['source']
        return tree_identity(self.root, source['main_commit'], source['child_commit'])

    def recheck(self):
        require(self.assets==asset_identity(), 'assets changed during run')
        require(self.source==self.source_identity(), 'source changed during run')

    def adoption(self, freeze_path, adoption_path, netlist, constraints):
        frozen = json.loads(Path(freeze_path).read_text())
        adopted = json.loads(Path(adoption_path).read_text())
        require(frozen.get('candidate')==self.id and frozen.get('status')=='FROZEN_REVIEW_PENDING_NOT_QUALIFIED', '138 freeze absent or mismatched')
        require(frozen.get('before')==frozen.get('after') and not frozen.get('errors'), '138 before/after mismatch')
        require(adopted.get('status')=='OWN_FM_ADOPTED_CONDITIONAL_REVIEW_PENDING', '138 ownFM adoption absent')
        planned=self.queue_candidate
        require(len(frozen['after'])==len(planned['freeze_inputs']) and
                [r['path'] for r in frozen['after']]==[r['path'] for r in planned['freeze_inputs']], '138 complete input set differs')
        for actual,expected in zip(frozen['after'],planned['freeze_inputs']):
            require(actual['sha256']==expected['sha256'] and ('bytes' not in expected or actual['bytes']==expected['bytes']),
                    '138 input record differs from fixed queue plan')
        require(frozen['selected_mapped']==adopted['selected_mapped']==planned['selected_mapped'] and
                frozen['ordered_svf_inputs']==adopted['ordered_svf_inputs']==planned['ordered_svf_inputs'], '138 selected mapping/SVF chain differs')
        selected = self.candidate['formal']['mapped']
        require(adopted['selected_mapped']['sha256']==frozen['selected_mapped']['sha256']==selected['sha256']==sha(netlist), 'selected ownFM mapping differs')
        require(sha(constraints)==self.candidate['ppa']['analysis_sdc']['sha256'], 'analysis SDC differs')
        for record in frozen['after']:
            actual=identity(record['path'])
            require(all(actual[k]==record[k] for k in ('path','sha256','bytes')) and record.get('symlink_target') is None,
                    '138 frozen input changed: '+record['path'])
        require(frozen['source']['main_commit']==self.source['main_commit'] and
                frozen['source']['child_commit']==self.candidate['source']['child_commit'] and
                Path(frozen['source']['root']).resolve()==self.root, '138 source binding differs')
        native=Path(planned['formal_log']['path']).read_text(errors='replace')
        require(sha(planned['formal_log']['path'])==planned['formal_log']['sha256']==adopted['log']['sha256'], 'adopted native ownFM log changed')
        require(sum(line.strip()=='Verification SUCCEEDED' for line in native.splitlines())==
                adopted['native_verification_succeeded_count']==1, 'native ownFM success marker differs')
        counts=[int(n) for n in re.findall(r'^\s*(\d+) Passing compare points\s*$',native,re.M)]
        require(counts and counts==adopted['native_passing_counts'] and
                all(n==planned['formal_expected_passing'] for n in counts), 'native ownFM passing count differs')
        return dict(freeze=identity(freeze_path), own_fm=identity(adoption_path), selected_mapped=identity(netlist),
                    analysis_sdc=identity(constraints), original_mapped=self.candidate['ppa']['original_mapped'],
                    ordered_svf_inputs=adopted['ordered_svf_inputs'], sram_internal='BLACK_BOX_NOT_PROVED')
