#!/usr/bin/env python3
"""Verify this evidence snapshot; never claims a new simulation or signoff."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def verify(root):
    manifest = json.loads((root / 'package-manifest.json').read_text())
    for name, entry in manifest['files'].items():
        p = root / name
        require(p.is_file() and not p.is_symlink(), 'Missing/nonregular input: ' + name)
        require(p.stat().st_size == entry['bytes'] and digest(p) == entry['sha256'], 'Identity mismatch: ' + name)
    b = root / 'build/compliant32-20261113'
    public_dir = b / 'cpu-public-audio-full12-r1'
    source = public_dir / 'source'
    spec = importlib.util.spec_from_file_location('frozen_cpu_checker', source / 'check_results.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    names = ['cpu-xmacro-task0-r1', 'cpu-public-audio-full12-r1',
             'cpu-xmacro-followups-r1/full12', 'cpu-xmacro-followups-r1/dma-first-wait31',
             'cpu-xmacro-followups-r1/load-first-wait31']
    public = json.loads((public_dir / 'result.json').read_text())
    reports = {}
    for name in names:
        directory = b / name
        result = json.loads((directory / 'result.json').read_text())
        args = result['arguments']
        parsed = checker.check_log((directory / 'simulation.log').read_text(), args['tasks'], args['rows'], args['warmup'], x_macros=True)
        for key, value in parsed.items():
            require(value == result[key], name + ': raw log/result mismatch: ' + key)
        require(result['status'] == 'PASS' and result['source_drift'] == [], name + ': missing PASS/clean source')
        require(result['source_sha256'] == public['source_sha256'], name + ': source differs')
        require(result['simulator_sha256'] == public['simulator_sha256'], name + ': simulator differs')
        require(result['firmware']['elf_sha256'] == public['firmware']['elf_sha256'], name + ': ELF differs')
        for rel, sha in result['source_sha256'].items():
            require(digest(source / rel) == sha, 'Frozen source mismatch: ' + rel)
        vectors = b / ('numeric/public-validation-600-evaluation-r1/vectors' if name == 'cpu-public-audio-full12-r1' else 'numeric/dev-vectors-r1')
        for rel, sha in result['vector_byte_sha256'].items():
            require(digest(vectors / rel) == sha, name + ': vector mismatch: ' + rel)
        require(digest(vectors / 'vectors-manifest.json') == result['vectors_manifest_sha256'], name + ': vector manifest mismatch')
        require(digest(public_dir / 'firmware/dma_day_soc') == result['firmware']['elf_sha256'], name + ': ELF bytes mismatch')
        require(digest(public_dir / 'firmware/dma_day_soc.verilog') == result['firmware']['image_sha256'], name + ': image bytes mismatch')
        reports[name] = {k: result[k] for k in ['outputs', 'total_cycles', 'source_loading_cycles', 'clear_cycles', 'dma_payload_cycles']}
    development = json.loads((b / 'cpu-xmacro-followups-r1/full12/result.json').read_text())
    require(public['total_cycles'] == 3568690 and public['outputs'] == 304128, 'Public full12 total differs')
    require([x['total'] for x in public['layers']] == [x['total'] for x in development['layers']], 'Development/public layer cycles differ')
    for name, field in [('dma-first-wait31', 'forced_wait'), ('load-first-wait31', 'forced_load_wait')]:
        r = json.loads((b / 'cpu-xmacro-followups-r1' / name / 'result.json').read_text())
        require(r['total_cycles'] == 297423 and r['layers'][0]['channel'][field] == 31, 'Wait31 missing: ' + name)
    evaluation_dir = b / 'numeric/public-validation-600-evaluation-r1'
    evaluation = json.loads((evaluation_dir / 'result.json').read_text())
    samples = [json.loads(x) for x in (evaluation_dir / 'samples.jsonl').read_text().splitlines() if x]
    require(len(samples) == 600 and evaluation['sample_count'] == 600 and evaluation['status'] == 'DEVELOPMENT_Y32_PRECISION_PASS', 'Public600 scope/status differs')
    require(sum(x['kind'] == 'wav' for x in evaluation['samples']) == 599, 'WAV count differs')
    require(sum(x['kind'] == 'silence_zero' for x in evaluation['samples']) == 1, 'Synthetic silence count differs')
    independent = json.loads((b / 'numeric/public600-independent-error-replay-r1.json').read_text())
    maximum = 0.0
    max_sample = 0.0
    for i, layer in enumerate(evaluation['layers']):
        entries = [sample['layers'][i] for sample in samples]
        require(all(x['layer_id'] == i for x in entries), 'Layer identity mismatch')
        sse = math.fsum(x['sse'] for x in entries)
        energy = math.fsum(x['reference_energy'] for x in entries)
        require(math.isfinite(sse) and math.isfinite(energy) and energy > 0, 'Invalid raw error record')
        nrmse = math.sqrt(sse / energy)
        require(math.isclose(nrmse, layer['nrmse'], rel_tol=1e-14, abs_tol=1e-18), 'NRMSE aggregation mismatch')
        require(sse == independent['layers'][i]['sse'] and energy == independent['layers'][i]['reference_energy'], 'Independent fsum differs')
        require(layer['count'] == 600 * 25344, 'Compared value count differs')
        require(layer['bias_clips'] == layer['weight_clips'] == layer['x_clips'] == 0, 'Clipping observed')
        require(nrmse <= 0.03, 'Development aggregate precision threshold exceeded')
        for entry in entries:
            n = math.sqrt(entry['sse'] / entry['reference_energy'])
            require(math.isfinite(n) and n <= 0.03, 'Development individual precision threshold exceeded')
            max_sample = max(max_sample, n)
        maximum = max(maximum, nrmse)
    require(maximum == evaluation['max_layer_nrmse'], 'Max aggregate differs')
    return {'status': 'PASS_EXISTING_EVIDENCE_REPLAY_ONLY', 'verified_files': len(manifest['files']),
            'cpu': reports, 'public600_values': 600 * 12 * 25344,
            'max_layer_nrmse_percent': maximum * 100, 'max_sample_layer_nrmse_percent': max_sample * 100,
            'limitations': ['No new simulation or inference executed.', 'No STA, area, mapped equivalence, power or official-sample signoff implied.', 'CPU output equality is the preserved testbench readback result; this parser does not rerun hardware.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path, help='Extracted evidence directory')
    args = parser.parse_args()
    print(json.dumps(verify(args.root.resolve()), ensure_ascii=False, indent=2))
