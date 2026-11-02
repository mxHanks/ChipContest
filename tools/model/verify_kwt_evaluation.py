#!/usr/bin/env python3
"""Independently recompute isolated FFN1 validation error from recorded sums.

Standard library only. No inference, quantization, runtime model or EDA module is
imported. This verifies evidence arithmetic and identities, not that software
outputs were produced by RTL or that the development split is official input.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import sys

LAYER_COUNT = 12
ELEMENTS = 99 * 256
FLOOR = 1e-8


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(path.read_text())


def close(actual, expected, name):
    require(isinstance(actual, (int, float)) and not isinstance(actual, bool) and
            math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-15),
            'independently calculated value differs: ' + name)


def finite_nonnegative(value, name):
    require(isinstance(value, (int, float)) and not isinstance(value, bool) and
            math.isfinite(value) and value >= 0, 'invalid finite nonnegative value: ' + name)
    return value


def nrmse(sse, reference_energy, count):
    require(type(count) is int and count > 0, 'empty error population')
    return math.sqrt(sse / count) / max(math.sqrt(reference_energy / count), FLOOR)


def validate(result, sampling, rows):
    """Validate complete immutable per-sample records and derive all twelve layers."""
    require(result['evaluation_completed'] is True and result['exit_code'] in (0, 1), 'evaluation is incomplete')
    samples = result['dataset']['evaluated_samples']
    require(type(samples) is int and samples > 1 and len(rows) == samples, 'complete multi-sample evidence is required')
    require(len(sampling['validation']) == result['dataset']['full_validation_samples'] >= samples,
            'validation population differs from sampling identity')
    require(len(result['layers']) == LAYER_COUNT and
            [layer['layer_id'] for layer in result['layers']] == list(range(LAYER_COUNT)),
            'missing/duplicate/misordered layer summary')
    values = [dict(sse=[], energy=[], per_sample=[]) for _ in range(LAYER_COUNT)]
    labels = Counter()
    for index, row in enumerate(rows):
        entry = sampling['validation'][index]
        require(row['sample_index'] == entry['index'] == index and
                row['label_index'] == entry['label_index'], 'sample index/label differs')
        require(re.fullmatch(r'[0-9a-f]{64}', row['waveform_float32_sha256']) is not None,
                'preprocessed waveform identity is malformed')
        if entry.get('input_kind') == 'exact_zero_16000_no_wav_decode':
            require(row['waveform_float32_sha256'] == hashlib.sha256(bytes(16000 * 4)).hexdigest(),
                    'silence waveform is not the documented exact float32 zero input')
        require(len(row['layers']) == LAYER_COUNT and
                [layer['layer_id'] for layer in row['layers']] == list(range(LAYER_COUNT)),
                'sample has missing/duplicate/misordered layers')
        labels[row['label_index']] += 1
        for layer in row['layers']:
            number = layer['layer_id']
            sse = finite_nonnegative(layer['sse'], 'sample SSE')
            energy = finite_nonnegative(layer['reference_energy'], 'sample reference energy')
            error = nrmse(sse, energy, ELEMENTS)
            close(layer['nrmse'], error, 'sample NRMSE')
            finite_nonnegative(layer['peak_absolute_error'], 'peak absolute error')
            finite_nonnegative(layer['peak_reference'], 'peak reference magnitude')
            values[number]['sse'].append(sse)
            values[number]['energy'].append(energy)
            values[number]['per_sample'].append(error)
    require({str(key): value for key, value in labels.items()} == result['dataset']['label_counts'],
            'label population differs from complete sample stream')
    derived = []
    for number, (record, sums) in enumerate(zip(result['layers'], values)):
        count = samples * ELEMENTS
        sse, energy = math.fsum(sums['sse']), math.fsum(sums['energy'])
        error = nrmse(sse, energy, count)
        worst = max(range(samples), key=lambda index: sums['per_sample'][index])
        require(record['count'] == count and record['samples'] == samples, 'layer population differs')
        for key, value in [('sum_error_sq', sse), ('sum_reference_sq', energy), ('nrmse', error),
                           ('max_sample_nrmse', sums['per_sample'][worst])]:
            close(record[key], value, 'layer ' + str(number) + ' ' + key)
        require(record['worst_sample_index'] == worst, 'worst sample identity differs')
        require(record['x_clips'] == record['weight_clips'] == record['bias_clips'] == 0,
                'frozen quantization clipped validation inputs/parameters')
        require(record['scales'] == dict(x_exp=-11, w_exp=-16, y_exp=-27), 'fixed numerical scales changed')
        derived.append(dict(layer_id=number, samples=samples, elements=count, sum_error_sq=sse,
                            sum_reference_sq=energy, nrmse_ratio=error, nrmse_percent=error * 100,
                            max_sample_nrmse_ratio=sums['per_sample'][worst], worst_sample_index=worst))
    maximum = max(layer['nrmse_ratio'] for layer in derived)
    maximum_sample = max(layer['max_sample_nrmse_ratio'] for layer in derived)
    close(result['max_layer_nrmse'], maximum, 'maximum layer NRMSE')
    close(result['max_sample_layer_nrmse'], maximum_sample, 'maximum sample-layer NRMSE')
    gate = 'PASS' if maximum <= .03 and maximum_sample <= .03 else 'FAIL'
    require(result['status'] == result['development_3_percent_gate'] == gate and
            result['exit_code'] == (0 if gate == 'PASS' else 1), 'development precision decision differs')
    require(result['official_600_task_acceptance'] == result['rtl_full_validation'] == result['soc_ppa'] == 'NOT_RUN',
            'development software evaluation has overclaimed its acceptance scope')
    return dict(status='PASS', development_precision_gate=gate, samples=samples, layers=derived,
                total_output_values=samples * LAYER_COUNT * ELEMENTS,
                max_layer_nrmse_ratio=maximum, max_layer_nrmse_percent=maximum * 100,
                max_sample_layer_nrmse_ratio=maximum_sample, max_sample_layer_nrmse_percent=maximum_sample * 100,
                scope='independent arithmetic audit of recorded isolated FFN1 software sums; not official600 or RTL output validation')


def audit(directory, repo=None, source=None):
    result = read(directory / 'result.json')
    identities = []
    for key in ['samples', 'sampling', 'consumed_files']:
        identity = result['samples'] if key == 'samples' else result['dataset'][key]
        path = Path(identity['path'])
        require(not path.is_absolute() and '..' not in path.parts, 'unsafe result evidence path')
        original = directory / path
        require(original.is_file() and original.stat().st_size == identity['bytes'] and sha(original) == identity['sha256'],
                'raw evaluation evidence bytes/hash differ: ' + str(path))
        identities.append(dict(path=path.as_posix(), bytes=identity['bytes'], sha256=identity['sha256']))
    sampling = read(directory / result['dataset']['sampling']['path'])
    consumed = read(directory / result['dataset']['consumed_files']['path'])
    require(len(consumed) == len({item['path'] for item in consumed}), 'duplicate consumed source identity')
    source_files = {item['path']: item for item in consumed}
    for entry in sampling['validation']:
        require(entry['file'] in source_files and source_files[entry['file']]['sha256'] == entry['file_sha256'],
                'sample source identity differs from verified consumed data inventory')
    rows = [json.loads(line) for line in (directory / result['samples']['path']).read_text().splitlines()]
    output = validate(result, sampling, rows)
    output['original_evidence_files'] = identities
    output['result_sha256'] = sha(directory / 'result.json')
    output['source_commit'] = result['source']['commit']
    if source is not None:
        for identity in result['source']['files']:
            path = Path(identity['path'])
            require(not path.is_absolute() and '..' not in path.parts, 'unsafe source path')
            original = source / path
            require(original.is_file() and original.stat().st_size == identity['bytes'] and sha(original) == identity['sha256'],
                    'external checkpoint/source bytes differ: ' + str(path))
        output['external_source_files_locally_verified'] = len(result['source']['files'])
    if repo is not None:
        for identity in result['implementation']:
            path = Path(identity['path'])
            require(not path.is_absolute() and '..' not in path.parts and sha(repo / path) == identity['sha256'],
                    'executed model implementation differs: ' + str(path))
        identity = result['static_scale_contract']
        require(sha(repo / identity['path']) == identity['sha256'], 'frozen scale contract bytes differ')
        output['implementation_and_scale_contract_locally_verified'] = True
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evaluation', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True, help='new JSON output file')
    parser.add_argument('--repo', type=Path)
    parser.add_argument('--source', type=Path)
    args = parser.parse_args(argv)
    result = audit(args.evaluation, args.repo, args.source)
    result['verifier_sha256'] = sha(Path(__file__))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n')
    print('PASS: {} samples, 12 layers, maximum layer NRMSE {:.8f}%'.format(
        result['samples'], result['max_layer_nrmse_percent']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
