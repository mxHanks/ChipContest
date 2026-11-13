#!/usr/bin/env python3
"""Freeze a report-only PT API repair; preserve all original sealed inputs."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base = a.baseline.resolve()
    pinned = json.loads((base/'package-files.json').read_text())
    expected = '96fbf8088cb2b94cc5bd682e09b9ec126762bd6c2dd54aad32caea854fb416ed'
    assert sha((base/'package-files.json').read_bytes()) == expected
    assert all(sha((base/n).read_bytes()) == h for n, h in pinned.items())
    old = (base/'pt_collect.tcl').read_bytes()
    before = b'xu_capture host-options.rpt {report_host_options} 1'
    after = b'xu_capture host-options.rpt {report_host_usage -verbose} 1'
    assert old.count(before) == 1
    fixed = old.replace(before, after)
    runner = (base/'run_once.py').read_text()
    runner = runner.replace("choices=['dc', 'pt'], default='dc'", "choices=['pt'], default='pt'")
    runner = runner.replace("root = Path(__file__).resolve().parent", "repair = Path(__file__).resolve().parent\n    root = Path(os.environ['XU_RECOLLECT_BASELINE']).resolve()\n    repair_files = json.loads((repair/'package-files.json').read_text())\n    for n, h in repair_files.items(): check(repair/n, h)\n    require(sha(root/'package-files.json') == '"+expected+"', 'only frozen original1064 N3 package allowed')\n    require(sha(root/'execution.json') == '19779073b505e90de94a9f377f5afc74902ca3f10168c5c4da2833fcf093b290', 'only this fixed DC map allowed')\n    require((repair/'pt_collect.tcl').read_bytes() == (root/'pt_collect.tcl').read_bytes().replace(b'"+before.decode()+"', b'"+after.decode()+"'), 'only native host-report command may differ')")
    runner = runner.replace("schema='sysbus32-same-source-' + a.stage + '-execution-v1'", "schema='ingress1064-same-source-pt-recollection-v1'")
    runner = runner.replace("max_cores=8,\n                  qualification", "max_cores=8, collector_repair=dict(package_files_sha256=sha(repair/'package-files.json'), original_collector_sha256=sha(root/'pt_collect.tcl'), actual_collector_sha256=sha(repair/'pt_collect.tcl'), change='report_host_options to native-proven report_host_usage -verbose; no other collector change', initial_failed_pt_sha256=sha(root/'pt/execution.json')),\n                  qualification")
    runner = runner.replace("out = root / 'pt'", "out = repair / 'pt'")
    runner = runner.replace("str(root / 'pt_collect.tcl')", "str(repair / 'pt_collect.tcl')")
    runner = runner.replace("    if dc_binding:\n        if sha(root", "    drift += ['collector_bundle/'+n for n, h in repair_files.items() if not (repair/n).is_file() or sha(repair/n) != h]\n    if dc_binding:\n        if sha(root")
    compile(runner, 'run.py', 'exec')
    a.out.mkdir(mode=0o700, parents=True, exist_ok=False)
    files = {'run.py': runner.encode(), 'pt_collect.tcl': fixed, 'profiles.py': (base/'profiles.py').read_bytes()}
    for n, b in files.items():
        (a.out/n).write_bytes(b)
    manifest = {n: sha(b) for n, b in files.items()}
    (a.out/'package-files.json').write_text(json.dumps(manifest, indent=2, sort_keys=True)+'\n')
    print(json.dumps(dict(status='REPORT_ONLY_REPAIR_SEALED_NOT_EXECUTED', files=manifest,
        package_files_sha256=sha((a.out/'package-files.json').read_bytes()),
        original_collector_sha256=sha(old), actual_collector_sha256=sha(fixed),
        original_package_files_sha256=expected), sort_keys=True))


if __name__ == '__main__':
    main()
