#!/usr/bin/env python3
"""Prepare isolated DC/exact-PT replay; --run explicitly executes installed tools.

Original evidence stays unchanged. All RTL inputs are checked against the
original manifests, then copied into new per-case directories. New DC mapped.v /
mapped.sdc feed the new exact-STA audit. No manual or vectorless power probe runs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

BASELINE_E203 = 'e36d34a52e6eef93fd0bdfed1b13009e1056bea3'
CANDIDATE_E203 = 'f49a5fc914971426bd4530db39e270a84b41139f'
DEFAULT_FROZEN_BASE = '/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa'
DEFAULT_LC_ROOT = '/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5'


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checked_subset(root):
    manifest = {}
    for line in (root/'SHA256SUMS').read_text().splitlines():
        require(re.fullmatch(r'[0-9a-f]{64}  [^\r\n]+', line), 'bad subset SHA256SUMS')
        digest, name = line.split('  ', 1)
        require(name not in manifest and not Path(name).is_absolute() and '..' not in Path(name).parts,
                'unsafe or duplicate subset path')
        manifest[name] = digest
    actual = {path.relative_to(root).as_posix() for path in root.rglob('*')
              if path.is_file() and path.name != 'SHA256SUMS'}
    require(actual == set(manifest), 'subset manifest file set differs')
    for name, digest in manifest.items():
        require(not (root/name).is_symlink() and sha256(root/name) == digest, 'subset hash differs: '+name)
    derived = json.loads((root/'derived-subset-manifest.json').read_text())
    original = json.loads((root/'ppa-transfer-manifest.json').read_text())
    require(derived['source_archive']['sha256'] ==
            '8fc6a127069934bb21227b865918c45aeb74f4f7739b7c24b34b32ee5a4c31f3' and
            len(original['files']) == 113 and len(derived['included_originals']) == 104 and
            len(derived['omitted_originals']) == 9, 'subset provenance differs')
    require(sha256(root/'ppa-transfer-manifest.json') == derived['original_transfer_manifest']['sha256'],
            'original transfer manifest differs')
    require(set(derived['included_originals']) | set(derived['omitted_originals']) == set(original['files']) and
            not (set(derived['included_originals']) & set(derived['omitted_originals'])),
            'included / omitted original partition differs')
    for name, record in derived['included_originals'].items():
        require(record == original['files'][name] and sha256(root/name) == record['sha256'] and
                (root/name).stat().st_size == record['bytes'], 'subset original bytes differ: '+name)
    return derived


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--subset-root', required=True, help='expanded xu-ppa-reproducibility archive root')
    parser.add_argument('--out', required=True, help='new replay root; existing directories are refused')
    parser.add_argument('--frozen-base', default=DEFAULT_FROZEN_BASE,
                        help='server PPA root containing frozen-fw-rtl and frozen-hw-rtl-02')
    parser.add_argument('--old-submodule', help='recover baseline RTL from exact old E203 Git objects instead')
    parser.add_argument('--new-submodule', help='recover candidate RTL from exact new E203 Git objects instead')
    parser.add_argument('--lc-root', default=DEFAULT_LC_ROOT)
    parser.add_argument('--dc-shell', default='dc_shell')
    parser.add_argument('--pt-shell', default='pt_shell')
    parser.add_argument('--run', action='store_true', help='execute DC and exact PT sequentially after preparing')
    args = parser.parse_args()
    subset, out = Path(args.subset_root).resolve(), Path(args.out).resolve()
    require(not out.exists(), 'refusing to reuse replay output directory')
    require(bool(args.old_submodule) == bool(args.new_submodule), 'both exact-Git source repositories are required')
    checked_subset(subset)
    cases = [('baseline', 'baseline-ss-01', 'frozen-fw-rtl', BASELINE_E203, args.old_submodule),
             ('candidate', 'candidate-ss-02', 'frozen-hw-rtl-02', CANDIDATE_E203, args.new_submodule)]
    prepared = []
    dependencies = None
    for name, original_case, frozen_name, revision, submodule in cases:
        original = subset/'ppa'/original_case
        source_manifest = json.loads((original/'manifest.json').read_text())
        if dependencies is None:
            dependencies = source_manifest['libraries']
        require(dependencies == source_manifest['libraries'], 'paired library identities differ')
        constraints = (original/'constraints.sdc').read_bytes()
        source_bytes, origins = {}, {}
        for filename, digest in source_manifest['source_sha256'].items():
            if filename == 'xu-sram-adapter.sv':
                path = subset/'ppa/frozen-fw-rtl'/filename
                payload = path.read_bytes()
                origin = dict(kind='original subset adapter', path=str(path))
            elif submodule:
                entry = revision+':rtl/e203/perips/'+filename
                payload = subprocess.check_output(['git', 'show', entry], cwd=str(Path(submodule).resolve()))
                origin = dict(kind='exact Git object', repository=str(Path(submodule).resolve()), entry=entry)
            else:
                path = Path(args.frozen_base).resolve()/frozen_name/filename
                payload = path.read_bytes()
                origin = dict(kind='frozen server source file', path=str(path))
            require(hashlib.sha256(payload).hexdigest() == digest, 'source bytes differ: '+name+'/'+filename)
            source_bytes[filename], origins[filename] = payload, origin
        synth = (original/'synth.tcl').read_text()
        inputs = re.findall(r'analyze -format sverilog \{([^}]+)\}', synth)
        require(len(inputs) == len(source_bytes) and {Path(path).name for path in inputs} == set(source_bytes),
                'DC analysis source set differs')
        here = out/name
        for path in inputs:
            synth = synth.replace('{'+path+'}', '{'+str(here/'rtl'/Path(path).name)+'}')
        audit = (subset/'ppa/paired-exact-audit-01'/name/'audit.tcl').read_text()
        audit, netlists = re.subn(r'read_verilog \{[^}]+\}', 'read_verilog {'+str(here/'mapped.v')+'}', audit)
        audit, sdcs = re.subn(r'read_sdc \{[^}]+\}', 'read_sdc {'+str(here/'mapped.sdc')+'}', audit)
        require(netlists == sdcs == 1 and 'man read_' not in audit and 'update_power' not in audit,
                'exact audit does not isolate the new netlist / SDC / STA scope')
        for command in [synth, audit]:
            require(not re.search(r'>\s+[/~]', command), 'replay Tcl has an absolute output redirection')
        prepared.append(dict(name=name, source_manifest=source_manifest, constraints=constraints,
                             source_bytes=source_bytes, source_origins=origins, synth=synth, audit=audit))
    require(prepared[0]['constraints'] == prepared[1]['constraints'], 'paired constraint bytes differ')
    libraries = {}
    for filename, expected in dependencies.items():
        path = Path(filename)
        available = path.is_file()
        record = dict(expected, available=available)
        if available:
            record['actual_sha256'] = sha256(path)
            require(record['actual_sha256'] == expected['sha256'] and path.stat().st_size == expected['bytes'],
                    'installed dependency differs: '+filename)
        libraries[filename] = record
    lc_root = Path(args.lc_root).resolve()
    environment = dict(os.environ, SYNOPSYS_LC_ROOT=str(lc_root))
    environment['PATH'] = str(lc_root/'bin')+os.pathsep+environment.get('PATH', '')
    tools = {name: shutil.which(command, path=environment['PATH']) for name, command in
             [('dc_shell', args.dc_shell), ('pt_shell', args.pt_shell)]}
    ready = all(row['available'] for row in libraries.values()) and all(tools.values()) and lc_root.is_dir()
    if args.run:
        require(ready, '--run requires exact installed libraries, DC/PT executables and Library Compiler root')
    out.mkdir(parents=True, exist_ok=False)
    report = dict(schema='xu-isolated-ppa-replay-v1', status='PREPARED_NOT_RUN',
                  scope='new complete-wrapper synthesis and exact STA only; no power/manual/signoff claim',
                  libraries=libraries, tools=tools, library_compiler_root=str(lc_root),
                  dependencies_ready_for_execution=ready, cases=[])
    def save():
        (out/'replay-manifest.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    for record in prepared:
        here = out/record['name']
        (here/'rtl').mkdir(parents=True)
        for filename, payload in record['source_bytes'].items():
            (here/'rtl'/filename).write_bytes(payload)
        (here/'constraints.sdc').write_bytes(record['constraints'])
        (here/'synth.tcl').write_text(record['synth'])
        (here/'audit.tcl').write_text(record['audit'])
        report['cases'].append(dict(name=record['name'], status='PREPARED_NOT_RUN', cwd=str(here),
            frozen_source_commit=record['source_manifest']['source_commit'],
            source_origins=record['source_origins'], source_sha256=record['source_manifest']['source_sha256'],
            constraints_sha256=sha256(here/'constraints.sdc'), synth_sha256=sha256(here/'synth.tcl'),
            audit_sha256=sha256(here/'audit.tcl'),
            commands=[[tools['dc_shell'] or args.dc_shell, '-64bit', '-f', 'synth.tcl'],
                      [tools['pt_shell'] or args.pt_shell, '-f', 'audit.tcl']]))
    save()
    if args.run:
        report['status'] = 'RUNNING'
        save()
        try:
            for record in report['cases']:
                for stage, command, marker in [('dc', record['commands'][0], 'XU_DC_BASELINE_PASS'),
                                                ('pt', record['commands'][1], 'XU_EXACT_AUDIT_PASS')]:
                    log = Path(record['cwd'])/(stage+'.log')
                    start = time.monotonic()
                    with log.open('x') as stream:
                        completed = subprocess.run(command, cwd=record['cwd'], env=environment,
                                                   stdout=stream, stderr=subprocess.STDOUT, timeout=7200)
                    text = log.read_text(errors='replace')
                    record[stage] = dict(returncode=completed.returncode,
                        elapsed_seconds=time.monotonic()-start, log_sha256=sha256(log))
                    require(completed.returncode == 0 and not re.search(r'^Error:', text, re.M) and
                            marker in text.splitlines(), 'replay '+record['name']+'/'+stage+' failed; original new logs retained')
                    save()
                record['status'] = 'PASS'
            report['status'] = 'PASS'
        except Exception as error:
            report.update(status='FAIL', error=str(error))
            raise
        finally:
            save()
    print(json.dumps(dict(status=report['status'], output=str(out),
                          dependencies_ready_for_execution=ready, commands_executed=bool(args.run)), indent=2))


if __name__ == '__main__':
    main()
