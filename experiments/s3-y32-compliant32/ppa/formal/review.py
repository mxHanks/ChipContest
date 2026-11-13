#!/usr/bin/env python3
"""Inventory frozen374 RTL/formal inputs. Always offline; there is no --run."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[4]
LIBS = {'standard_cell': 'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723',
        'sram': 'c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f'}


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def history():
    results = []
    for log, marker in [('s2c-fm.log', 'XU_FULL_SOC_FORMALITY_PASS'),
                        ('s2e155-fm.log', 'XU_S2E_TIMING134_FORMALITY_PASS')]:
        path = ROOT / 'docs/handoff-evidence' / log
        text = path.read_text()
        need(re.findall(r'^Verification (?:SUCCEEDED|FAILED)[ \t]*$', text, re.M) == ['Verification SUCCEEDED'],
             'historical native result identity differs')
        need(re.findall('^' + marker + r'[ \t]*$', text, re.M) == [marker], 'historical actual marker differs')
        receipt_path = ROOT / 'docs/handoff-evidence' / ('s2c-fm-state.json' if log == 's2c-fm.log' else 's2e155-state.json')
        receipt = json.loads(receipt_path.read_text())
        run = next(row for row in receipt['runs'] if row.get('candidate') == 's2c') if log == 's2c-fm.log' else receipt['runs'][-1]
        need(run['returncode'] == 0 and run['log']['sha256'] == sha(path) and run['log']['bytes'] == path.stat().st_size,
             'historical log/native receipt binding differs')
        results.append({'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path),
                        'receipt': str(receipt_path), 'receipt_sha256': sha(receipt_path),
                        'native_returncode': run['returncode'],
                        'native_version': re.search(r'Version (\S+)', text)[1],
                        'passing_compare_points': int(re.findall(r'^\s*(\d+) Passing compare points[ \t]*$', text, re.M)[0]),
                        'top': 'xu_soc_ppa_top', 'candidate': 'historical S2 only',
                        'limits': ['SRAM internals blackboxed', 'synopsys_auto_setup assumptions',
                                   'unread/unmatched reference points require review',
                                   'not current S3 RTL-to-mapped evidence']})
    return results


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--package', type=Path, required=True, help='sealed final374 PPA source package')
    p.add_argument('--native', type=Path, help='optional actual same-package374 DC result; never old353')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    package = a.package.resolve()
    need(not a.out.exists(), 'new output required')
    manifest = json.loads((package / 'manifest.json').read_text())
    pinned = json.loads((package / 'package-files.json').read_text())
    need(manifest['hardware_profile'] == 'sysbus32-storage-sram-374' and
         manifest['top'] == 'xu_soc_sysbus32_ppa_top' and
         manifest['expected_internal_macros'] == 54 and manifest['expected_geometry']['total_macros'] == 374,
         'requires final374 source profile')
    for name, digest in pinned.items():
        rel = Path(name)
        need(not rel.is_absolute() and '..' not in rel.parts and '\\' not in name, 'unsafe package input')
        path = package / rel
        need(path.is_file() and not path.is_symlink() and sha(path) == digest, 'source identity differs: ' + name)
    sources = (package / 'rtl.f').read_text().splitlines()
    sm = json.loads((package / 'source-manifest.json').read_text())
    need(sources == [x['path'] for x in sm['ordered_compile_sources']], 'ordered source list differs')
    definitions = json.loads((package / 'defines.json').read_text())
    need(definitions == manifest['defines'] == sm['defines'] and 'XU_MATRIX_STORAGE_SRAM' in definitions,
         'formal reference defines differ')
    includes = sorted({str((package / name).parent) for name in sources})
    toolchain = json.loads((package / 'toolchain.json').read_text())
    need({x['role']: x['sha256'] for x in toolchain['libraries']} == LIBS, 'two frozen libraries differ')
    native = None
    missing = ['Native same374 mapped.v and completed DC receipt',
               'Same374 own default.svf (plus ordered own ECO SVFs if adopted)',
               'Current native Formality launcher bytes/version/2core API confirmation',
               'Native374 RTL-to-mapped full-top match/verify results and assumptions review']
    if a.native:
        folder = a.native.resolve()
        receipt = json.loads((folder / 'execution.json').read_text())
        need(receipt['hardware_profile'] == manifest['hardware_profile'] and
             receipt['manifest_sha256'] == sha(package / 'package-files.json') and
             receipt['top'] == manifest['top'] and receipt['defines'] == definitions,
             'wrong source/profile native result:353 cannot prove374')
        need(receipt['returncode'] == 0 and receipt['completion_marker'] is True and
             receipt['source_drift'] == [] and receipt['native_tool_errors'] == [], 'DC native run incomplete')
        own = {}
        for name in ['mapped.v', 'mapped.ddc', 'default.svf', 'leaf-inventory.tsv']:
            wanted = receipt['outputs'][name]
            need(sha(folder / name) == wanted['sha256'] and (folder / name).stat().st_size == wanted['bytes'],
                 'native formal input differs: ' + name)
            own[name] = wanted
        native = {'execution_sha256': sha(folder / 'execution.json'), 'own_outputs': own}
        missing = missing[2:]
    policy = json.loads((package / 'area-charge-policy.json').read_text())
    known_metadata_difference = []
    if policy.get('conservative_upper_bound', {}).get('internal_SRAM_macros') != 54:
        known_metadata_difference.append('Package area-charge-policy still reports old macro geometry; resolve in a new source package before native run')
    result = {'schema': 'compliant32-final374-formal-input-review-v1',
              'status': 'OFFLINE_INPUT_IDENTITIES_REVIEWED_NOT_FORMALITY_EXECUTED',
              'review_tool_sha256': sha(Path(__file__).resolve()),
              'package': str(package), 'package_files_sha256': sha(package / 'package-files.json'),
              'top': manifest['top'], 'definitions': definitions, 'source_count': len(sources),
              'ordered_compile_sources': sm['ordered_compile_sources'], 'include_directories': includes,
              'libraries': toolchain['libraries'],
              'native': native, 'native_fm_path_hint_only': '/eda/synopsys/fm/fm_2020.09-SP5/bin/fm_shell',
              'expected_macro_geometry': manifest['expected_geometry'],
              'historical_reusable_native_logs': history(), 'known_metadata_difference': known_metadata_difference,
              'missing_or_unverified': missing,
              'prohibited_shortcuts': ['Use old353 map/SVF for374', 'blackbox entire DMA/core/fabric',
                                      'Accept unexpected unresolved modules as blackboxes',
                                      'Hardcode old42338 compare-point counts',
                                      'Read TB/generic RAM memory models as synthesis reference',
                                      'Treat auto-setup or ignore/unread points as automatically reviewed'],
              'scope': 'No EDA, remote access, license/tool/library access, equivalence or qualification claim'}
    need(all(sha(package / name) == digest for name, digest in pinned.items()), 'source drift during review')
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'status': result['status'], 'source_count': len(sources),
                      'native374_inputs_present': bool(native), 'missing_items': len(missing),
                      'known_metadata_difference': known_metadata_difference}))


if __name__ == '__main__':
    main()
