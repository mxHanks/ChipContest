#!/usr/bin/env python3
"""Explicit development fallback: existing integer vectors -> generic loader contract.

No frozen sample SHA whitelist. All shapes, source files, exact raw MAC outputs,
Y32 ties-even outputs and packed W are checked. This provides protocol test data,
never WAV/precision or official-sample evidence. The --dev acknowledgement is
mandatory; official audio goes through export_audio_manifest.py instead.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_audio_manifest as exporter
fixed, s3, transport = exporter.fixed, exporter.s3, exporter.transport


def convert(source, output, count, dev, source_manifest=None):
    if not dev:
        raise ValueError('--dev is required: integer fixtures cannot establish audio/model precision')
    if not 1 <= count <= 12:
        raise ValueError('task count must be 1..12')
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('output must be a new directory')
    raw_specs = {'x.mem': (16, 6336), 'w.mem': (16, 16384),
                 'bias.mem': (40, 256), 'y.mem': (48, 25344)}
    checked = []
    for task in range(count):
        folder = source / ('layer_%02d' % task)
        arrays, identities = {}, {}
        for name, (bits, words) in raw_specs.items():
            path = folder / name
            if path.is_symlink():
                raise ValueError('symlink in fixture')
            arrays[name] = fixed.read_hex_mem(path, bits, words)
            identities[name] = exporter.file_record(path, source)
        x = [arrays['x.mem'][row*64:(row+1)*64] for row in range(99)]
        w = [arrays['w.mem'][row*256:(row+1)*256] for row in range(64)]
        actual = [value for row in fixed.linear99x64x256(x, w, arrays['bias.mem']) for value in row]
        if actual != arrays['y.mem']:
            raise ValueError('raw MAC oracle mismatch task %d' % task)
        y32 = [s3.quantize_result(value) for value in actual]
        if (folder / 'y32.mem').exists() and fixed.read_hex_mem(folder / 'y32.mem', 32, 25344) != y32:
            raise ValueError('Y32 oracle mismatch task %d' % task)
        checked.append((identities, y32))
    output.mkdir(parents=True)
    tasks = []
    for task, (identities, _) in enumerate(checked):
        target = output / ('layer_%02d' % task)
        target.mkdir()
        for name in raw_specs:
            src = source / ('layer_%02d' % task) / name
            if exporter.digest(src) != identities[name]['sha256']:
                raise ValueError('source changed during conversion')
            shutil.copyfile(str(src), str(target / name))
        tasks.append(dict(task_id=task, layer_id=task, directory=target.name,
                          sample_id='development-fixture-%02d' % task,
                          exact_model_crosscheck='PASS_RAW48_AND_Y32_ALL_25344',
                          output_values=25344, nrmse=None, audio_source='NOT_PROVIDED'))
    profile = transport.add_s3_files(output, count, shared_w_packed=True)
    for task in tasks:
        target = output / task['directory']
        task['files'] = {path.name: exporter.file_record(path, output) for path in sorted(target.iterdir()) if path.is_file()}
    manifest = dict(schema=exporter.VECTOR_SCHEMA, format=s3.FORMAT_ID,
        created_utc=datetime.now(timezone.utc).isoformat(), task_count=count, tasks=tasks,
        source=dict(kind='explicit_development_integer_fixture', directory=str(source),
                    input_files=[item[0] for item in checked],
                    source_manifest=None if source_manifest is None else dict(path=str(source_manifest),
                        sha256=exporter.digest(source_manifest))),
        numerical_models={name: exporter.digest(exporter.ROOT / 'model' / name)
                          for name in ['fixed16_acc48.py', 's3_y32.py']},
        transport_profile_sha256=exporter.digest(output / 'profile.json'),
        official_600_acceptance='NOT_RUN_OR_CERTIFIED', precision='NOT_MEASURED_NO_FLOAT_REFERENCE',
        scope='development protocol/RTL vectors only; never audio precision evidence',
        loader='real platform 32-bit System Bus only; y/y32 are checker-only and never DUT source')
    exporter.write_json(output / 'vectors-manifest.json', manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--source-manifest', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tasks', type=int, default=12)
    parser.add_argument('--dev', action='store_true')
    args = parser.parse_args()
    manifest = convert(args.source, args.output, args.tasks, args.dev, args.source_manifest)
    print('DEV_INTEGER_VECTOR_IMPORT ' + json.dumps(dict(status='PASS', tasks=manifest['task_count'],
        official_acceptance='NOT_RUN', precision='NOT_MEASURED')))


if __name__ == '__main__':
    main()
