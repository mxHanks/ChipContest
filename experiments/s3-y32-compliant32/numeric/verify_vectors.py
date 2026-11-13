#!/usr/bin/env python3
"""Check arbitrary generic vector manifest identity and exact task math; no inference/RTL."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_audio_manifest as exporter
fixed, s3 = exporter.fixed, exporter.s3


def verify(directory, exact_mac=True):
    directory = Path(directory).resolve()
    path = directory / 'vectors-manifest.json'
    manifest = json.loads(path.read_text())
    if manifest.get('schema') != exporter.VECTOR_SCHEMA or manifest.get('format') != s3.FORMAT_ID:
        raise ValueError('unsupported vectors manifest/profile')
    tasks = manifest.get('tasks')
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 12 or manifest.get('task_count') != len(tasks):
        raise ValueError('task count invalid')
    expected_models = {name: exporter.digest(exporter.ROOT / 'model' / name)
                       for name in ['fixed16_acc48.py', 's3_y32.py']}
    if manifest.get('numerical_models') != expected_models:
        raise ValueError('numerical model identities differ')
    if exporter.digest(directory / 'profile.json') != manifest['transport_profile_sha256']:
        raise ValueError('transport profile SHA mismatch')
    profile = json.loads((directory / 'profile.json').read_text())
    if (profile.get('format') != s3.FORMAT_ID or profile.get('tasks') != len(tasks) or
            profile.get('w', {}).get('layout') != 'row_major_two_signed16_per_word' or
            profile.get('y_bits') != 32 or profile.get('y_exp') != -18 or
            profile.get('output_right_shift') != 9):
        raise ValueError('transport profile does not match canonical packedW/Y32 layout')
    seen_layers = []
    for task_id, task in enumerate(tasks):
        if task['task_id'] != task_id or task['directory'] != 'layer_%02d' % task_id:
            raise ValueError('task order/directory differs')
        if type(task.get('layer_id')) is not int or not 0 <= task['layer_id'] < 12:
            raise ValueError('invalid original model layer identity')
        seen_layers.append(task['layer_id'])
        for name in ('x.mem', 'w.mem', 'bias.mem', 'y.mem', 'y32.mem', 'w_packed16.mem'):
            record = task['files'][name]
            expected_path = task['directory'] + '/' + name
            if record['path'] != expected_path:
                raise ValueError('file path differs from task directory')
            actual = exporter.safe_relative(directory, expected_path)
            if actual.stat().st_size != record['bytes'] or exporter.digest(actual) != record['sha256']:
                raise ValueError('vector byte identity mismatch')
        folder = directory / task['directory']
        x = fixed.read_hex_mem(folder / 'x.mem', 16, 6336)
        w = fixed.read_hex_mem(folder / 'w.mem', 16, 16384)
        bias = fixed.read_hex_mem(folder / 'bias.mem', 40, 256)
        raw = fixed.read_hex_mem(folder / 'y.mem', 48, 25344)
        actual_y = fixed.read_hex_mem(folder / 'y32.mem', 32, 25344)
        if actual_y != [s3.quantize_result(value) for value in raw]:
            raise ValueError('Y32 differs from canonical RNE9')
        packed_raw = [int(value, 16) for value in (folder / 'w_packed16.mem').read_text().splitlines()]
        expected_packed = s3.pack_weight_source([w[row*256:(row+1)*256] for row in range(64)])
        if packed_raw != expected_packed:
            raise ValueError('packed weight bytes differ from original W')
        if exact_mac:
            expected_raw = fixed.linear99x64x256([x[row*64:(row+1)*64] for row in range(99)],
                                               [w[row*256:(row+1)*256] for row in range(64)], bias)
            if raw != [value for row in expected_raw for value in row]:
                raise ValueError('raw output differs from exact task MAC')
    if len(tasks) == 12 and sorted(seen_layers) != list(range(12)):
        raise ValueError('12 tasks do not cover all model layers')
    return dict(status='PASS', tasks=len(tasks), outputs=25344*len(tasks),
                exact_raw_mac_checked=exact_mac, exact_y32_checked=True,
                manifest_sha256=exporter.digest(path), official_acceptance='NOT_CERTIFIED_BY_VECTOR_AUDIT',
                oracle_usage='x/w/bias only for DUT loading; y/y32 checker-only')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vectors', type=Path, required=True)
    parser.add_argument('--identities-and-rne-only', action='store_true',
                        help='Skip canonical MAC replay, retaining SHA/shapes/packedW/RNE checks')
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    result = verify(args.vectors, exact_mac=not args.identities_and_rne_only)
    if args.receipt:
        if args.receipt.exists():
            parser.error('receipt must be a new file')
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        exporter.write_json(args.receipt, result)
    print('GENERIC_Y32_VECTOR_VERIFY ' + json.dumps(result))


if __name__ == '__main__':
    main()
