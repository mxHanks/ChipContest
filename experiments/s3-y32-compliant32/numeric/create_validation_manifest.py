#!/usr/bin/env python3
"""Choose a reproducible local validation-only WAV list; never claims official selection."""
import argparse
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_audio_manifest as exporter


def create(data, count, seed):
    if count < 12:
        raise ValueError('count must be >=12 to cover the 12 label classes')
    buckets = {label: [] for label in exporter.LABELS[1:]}
    for labeldir in sorted(data.iterdir()):
        if not labeldir.is_dir() or labeldir.name.startswith('_') or labeldir.is_symlink():
            continue
        label = labeldir.name if labeldir.name in exporter.WANTED else '_unknown_'
        for wav in sorted(labeldir.glob('*.wav')):
            if wav.is_file() and not wav.is_symlink() and exporter.original_split(wav) == 'validation':
                buckets[label].append(wav)
    rng = random.Random(seed)
    for label in buckets:
        if not buckets[label]:
            raise exporter.kwt.MissingInferenceInput('no validation audio for label ' + label)
        rng.shuffle(buckets[label])
    samples = [dict(sample_id='local-silence-0000', kind='silence_zero', label='_silence_',
                    split='synthetic_silence')]
    # First pass covers each non-silence class. Remaining samples cycle labels
    # without altering the canonical speaker split or numerical configuration.
    counters = {label: 0 for label in buckets}
    while len(samples) < count:
        progressed = False
        for label in exporter.LABELS[1:]:
            if len(samples) == count:
                break
            index = counters[label]
            if index >= len(buckets[label]):
                continue
            wav = buckets[label][index]
            counters[label] += 1
            samples.append(dict(sample_id='local-%s-%04d' % (label.strip('_'), index),
                                kind='wav', label=label, split='validation',
                                path=str(wav.relative_to(data)), sha256=exporter.digest(wav)))
            progressed = True
        if not progressed:
            raise ValueError('requested count exceeds local available unique validation WAVs')
    return dict(schema=exporter.MANIFEST_SCHEMA, purpose='development_validation',
        dataset_root=str(data), dataset=dict(name='speech_commands_v0.02',
            source='locally provided original audio; individual WAV SHA verified; archive origin requires separate receipt'),
        selection=dict(kind='deterministic local validation subset, not official600', seed=seed,
                       no_training_or_test_samples=True, calibration_unchanged=True),
        samples=samples, tasks=[dict(task_id=i, sample_id=samples[i]['sample_id'], layer_id=i) for i in range(12)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--count', type=int, default=12)
    parser.add_argument('--seed', type=int, default=20261113)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must be a new file')
    manifest = create(args.data.resolve(), args.count, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    exporter.write_json(args.output, manifest)
    exporter.validate_manifest(args.output)
    print('LOCAL_VALIDATION_MANIFEST ' + str(args.output.resolve()))


if __name__ == '__main__':
    main()
