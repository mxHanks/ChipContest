#!/usr/bin/env python3
"""Prepare a small read-only PT106-bit IO observation bundle; never launch EDA."""
import argparse
import hashlib
import json
from pathlib import Path

CATALOG = '96fbf8088cb2b94cc5bd682e09b9ec126762bd6c2dd54aad32caea854fb416ed'
DC = '19779073b505e90de94a9f377f5afc74902ca3f10168c5c4da2833fcf093b290'
MAP = '882b160f2dfde6a9593f63212ae173fc96bb00b6212c56d304a6e6e80ae4e56e'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--fixed-collector', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base = a.baseline.resolve()
    catalog = json.loads((base/'package-files.json').read_text())
    assert sha((base/'package-files.json').read_bytes()) == CATALOG
    assert len(catalog) == 186 and all(sha((base/n).read_bytes()) == h for n, h in catalog.items())
    original = (base/'pt_collect.tcl').read_text()
    fixed = a.fixed_collector.read_text()
    assert fixed == original.replace('xu_capture host-options.rpt {report_host_options} 1',
                                     'xu_capture host-options.rpt {report_host_usage -verbose} 1')
    boundary = '  xu_capture host-options.rpt '
    assert fixed.count(boundary) == original.count(boundary) == 1
    prefix = fixed.split(boundary, 1)[0]
    assert prefix == original.split(boundary, 1)[0] and prefix.endswith('  update_timing -full\n')
    tail = (Path(__file__).parent/'io_observe_tail.tcl').read_text()
    collector = prefix + tail
    runner = (base/'run_once.py').read_text()
    replacements = [
        ("choices=['dc', 'pt'], default='dc'", "choices=['pt'], default='pt'"),
        ("root = Path(__file__).resolve().parent", "bundle = Path(__file__).resolve().parent\n    root = Path(os.environ['XU_IO_BASELINE']).resolve()\n    bundle_files = json.loads((bundle/'package-files.json').read_text())\n    for n, h in bundle_files.items(): check(bundle/n, h)\n    require(sha(root/'package-files.json') == '"+CATALOG+"', 'wrong original1064 N3 catalog')\n    require(sha(root/'execution.json') == '"+DC+"', 'wrong native DC receipt')"),
        ("schema='sysbus32-same-source-' + a.stage + '-execution-v1'", "schema='ingress1064-loader-IO-observation-execution-v1'"),
        ("max_cores=8,\n                  qualification", "max_cores=8, IO_bundle_sha256=sha(bundle/'package-files.json'),\n                  qualification"),
        ("env['XU_MAPPED_SHA256'] = dc_binding['outputs']['mapped.v']['sha256']", "env['XU_MAPPED_SHA256'] = dc_binding['outputs']['mapped.v']['sha256']\n        require(env['XU_MAPPED_SHA256'] == '"+MAP+"', 'wrong fixed mapped.v')"),
        ("out = root / 'pt'", "out = bundle / 'pt'"),
        ("str(root / 'pt_collect.tcl')", "str(bundle / 'io_collect.tcl')"),
        ("marker = 'SYSBUS32_PT_COLLECTION_COMPLETE_NOT_QUALIFIED.txt'", "marker = 'LOADER_IO_OBSERVATION_COMPLETE_NOT_QUALIFIED.txt'"),
        ("    if dc_binding:\n        if sha(root", "    drift += ['IO_bundle/'+n for n, h in bundle_files.items() if not (bundle/n).is_file() or sha(bundle/n) != h]\n    if dc_binding:\n        if sha(root"),
    ]
    for before, after in replacements:
        assert runner.count(before) == 1, before
        runner = runner.replace(before, after)
    begin = runner.index('    required_reports = []\n')
    end = runner.index('    missing = [name for name in required_reports', begin)
    runner = runner[:begin] + "    required_reports = ['loader-io-observations.tsv', 'io-status.txt', 'required-reports.list', 'reports/host-usage.rpt', 'reports/clocks.rpt', 'reports/check_timing.rpt']\n    report_list = out/'required-reports.list'\n    if report_list.is_file(): required_reports += report_list.read_text().splitlines()\n" + runner[end:]
    runner = runner.replace("else 'PT_REPORT_COLLECTION_COMPLETE_NOT_QUALIFIED'", "else 'IO_OBSERVATION_COMPLETE_NOT_QUALIFIED'")
    compile(runner, 'run.py', 'exec')
    binding = dict(schema='ingress1064-loader-IO-observation-preparation-v1', status='SEALED_NOT_EXECUTED',
                   original_catalog_sha256=CATALOG, native_DC_execution_sha256=DC, mapped_v_sha256=MAP,
                   native_fixed_collector_sha256=sha(fixed.encode()), identical_load_prefix_sha256=sha(prefix.encode()),
                   original_SDC_sha256='c15ede0fc2c65771f87e2d6aee763b4ea0d53934868ca807b4785c36182fce7c',
                   method='212 bounded report_timing max_paths1/nworst1 full_clock_expanded reports; keep actual header/numeric counts and minimum returned slack, no unproven timing_path attributes',
                   no_path_policy='Record NO_PATH, missing numeric slack or unparsed output explicitly; none means IO/CDC/STA pass')
    files = {'run.py': runner.encode(), 'io_collect.tcl': collector.encode(),
             'profiles.py': (base/'profiles.py').read_bytes(), 'binding.json': (json.dumps(binding,indent=2)+'\n').encode()}
    a.out.mkdir(mode=0o700, parents=True, exist_ok=False)
    for n, data in files.items():
        (a.out/n).write_bytes(data)
    manifest = {n: sha(data) for n,data in files.items()}
    (a.out/'package-files.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(status='IO_OBSERVATION_SEALED_NOT_EXECUTED', files=manifest,
                         package_files_sha256=sha((a.out/'package-files.json').read_bytes())),indent=2))


if __name__ == '__main__':
    main()
