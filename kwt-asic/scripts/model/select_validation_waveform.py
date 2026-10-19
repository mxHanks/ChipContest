#!/usr/bin/env python3
"""Select one recorded validation WAV for a smoke export, without tuning scales."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace
import wave
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=ROOT/'data/speech-commands-v0.02')
    parser.add_argument('--word', choices='yes no up down left right on off stop go'.split(), default='yes')
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = ROOT/'vendor/kwt1-237e4097/kws_streaming/data/input_data.py'
    function = next(n for n in ast.parse(source.read_text()).body
                    if isinstance(n, ast.FunctionDef) and n.name == 'which_set')
    ns = dict(os=os, re=re, hashlib=hashlib, MAX_NUM_WAVS_PER_CLASS=2**27-1,
              compat=SimpleNamespace(as_bytes=lambda s: s.encode('utf-8')))
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), ns)
    candidates = sorted(p for p in (args.data/args.word).glob('*.wav')
                        if ns['which_set'](str(p), 10, 10) == 'validation')
    if not 0 <= args.offset < len(candidates):
        raise ValueError('offset outside validation candidates')
    selected = candidates[args.offset]
    prep = json.loads((args.data/'preparation.json').read_text())
    inventory_path = args.data/'source-files.json'
    if prep['status'] != 'PASS' or sha(inventory_path) != prep['inventory']['sha256']:
        raise ValueError('dataset provenance mismatch')
    inventory = json.loads(inventory_path.read_text())
    item = next(r for r in inventory if r['path'] == selected.relative_to(args.data).as_posix())
    if sha(selected) != item['sha256']:
        raise ValueError('selected WAV bytes differ from archive inventory')
    with wave.open(str(selected), 'rb') as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (1,2,16000,'NONE'):
            raise ValueError('expected mono PCM16 at 16 kHz')
        raw = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2')
    audio = np.zeros(16000, dtype=np.float32)
    count = min(len(raw), 16000)
    audio[:count] = raw[:count].astype(np.float32) / 32768.0
    args.output.mkdir(parents=True, exist_ok=False)
    path = args.output/'waveform.npy'
    np.save(str(path), audio, allow_pickle=False)
    report = {'status':'PASS', 'scope':'one deterministic validation waveform smoke, not validation-set accuracy',
              'partition':'validation', 'word':args.word, 'selection':'lexicographic order within fixed upstream which_set validation partition',
              'offset':args.offset, 'source_wav':str(selected.resolve()), 'source_wav_sha256':item['sha256'],
              'original_samples':len(raw), 'zero_pad_to':16000, 'waveform':str(path.resolve()),
              'waveform_sha256':sha(path), 'upstream_split_code_sha256':sha(source),
              'implementation_sha256':sha(Path(__file__)), 'scales_tuned_on_sample':False,
              'archive_sha256':prep['archive_sha256']}
    (args.output/'selection.json').write_text(json.dumps(report, indent=2)+'\n')
    print('VALIDATION_WAVEFORM_SELECTED '+str(path.resolve()))


if __name__ == '__main__':
    main()
