#!/usr/bin/env python3
"""Mutate disposable evidence copies; re-signed false semantic claims must fail."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location('xu64_audit', here / 'audit_local.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cases = []
    for name in ['raw-byte', 'resigned-cycles', 'resigned-direct-work', 'resigned-legacy-variant', 'resigned-boundary-mode']:
        with tempfile.TemporaryDirectory(prefix='xu-pe64-reject-') as temporary:
            raw = Path(temporary) / 'raw'
            shutil.copytree(here / 'raw', raw)
            changed = []
            expected = ''
            if name == 'raw-byte':
                path = raw / 'direct-02/wide64/simulation.log'
                path.write_bytes(path.read_bytes() + b'altered\n')
                expected = 'raw changed'
            elif name == 'resigned-cycles':
                path = raw / 'wide64-real1-02/result.json'
                report = json.loads(path.read_text())
                report['layers'][0]['cycles'] += 1
                path.write_text(json.dumps(report) + '\n')
                changed.append(path)
                expected = 'run identity/counters differ'
            elif name == 'resigned-direct-work':
                path = raw / 'direct-02/compat32/simulation.log'
                path.write_text(path.read_text().replace('lane_macs=53760', 'lane_macs=55296'))
                changed.append(path)
                expected = 'direct physical work differs'
            elif name == 'resigned-legacy-variant':
                path = raw / 'pe64-legacy5-01/accel_compute.log'
                path.write_text(path.read_text().replace('XU_ACCEL_PE64=1', 'XU_ACCEL_PE32=1'))
                report_path = raw / 'pe64-legacy5-01/result.json'
                report = json.loads(report_path.read_text())
                report['log_sha256'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
                report_path.write_text(json.dumps(report) + '\n')
                changed += [path, report_path]
                expected = 'legacy physical64 execution differs'
            else:
                path = raw / 'boundary-01/boundary/simulation.log'
                path.write_text(path.read_text().replace('mode=1 unknown_reads=14', 'mode=2 unknown_reads=14'))
                changed.append(path)
                expected = 'boundary actual coverage incomplete'
            if changed:
                manifest_path = raw / 'manifest.json'
                manifest = json.loads(manifest_path.read_text())
                for path in changed:
                    manifest[str(path.relative_to(raw))] = dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                manifest_path.write_text(json.dumps(manifest) + '\n')
            try:
                module.audit(root, raw)
            except ValueError as error:
                if expected not in str(error):
                    raise
                cases.append(dict(name=name, status='REJECTED_AS_REQUIRED', reason=str(error)))
            else:
                raise AssertionError('corrupted evidence accepted: ' + name)
    result = dict(status='PASS', scope='Five actual mutations of disposable original evidence, four with re-signed SHA metadata', cases=cases)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
