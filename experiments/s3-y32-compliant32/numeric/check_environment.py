#!/usr/bin/env python3
"""Read-only local numerical prerequisite audit; does not install/download anything."""
import argparse
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_audio_manifest as audio


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--data', type=Path)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must be new')
    report = dict(schema='s3-compliant32-numeric-environment-v1', created_utc=datetime.now(timezone.utc).isoformat(),
                  python_version=sys.version, executable=sys.executable,
                  required_environment='Python3.8.20 / tensorflow-cpu2.4.0 / numpy1.19.5',
                  installs_or_downloads=False, numerical_inference_executed=False,
                  canonical_rne=audio.check_rne_without_dependencies(), missing=[])
    try:
        report['kwt_source'] = audio.kwt.source_inventory(args.source)
    except Exception as exc:
        report['missing'].append(dict(kind='pinned_source', error=str(exc)))
    if sys.version_info[:3] != (3, 8, 20):
        report['missing'].append(dict(kind='legacy_python', error='current interpreter does not meet frozen TensorFlow environment'))
    else:
        try:
            np, tf = audio.kwt.load_inference_dependencies()
            report['environment_versions'] = dict(numpy=np.__version__, tensorflow=tf.__version__)
        except Exception as exc:
            report['missing'].append(dict(kind='inference_dependencies', error=str(exc)))
    if args.manifest:
        try:
            _, base, samples = audio.validate_manifest(args.manifest, args.data)
            report['audio'] = dict(manifest_sha256=audio.digest(args.manifest), root=str(base), samples=len(samples))
        except Exception as exc:
            report['missing'].append(dict(kind='audio_manifest_or_wavs', error=str(exc)))
    elif args.data and args.data.is_dir():
        report['data_directory'] = str(args.data.resolve())
        report['missing'].append(dict(kind='sample_manifest', error='WAV selection manifest not provided'))
    else:
        report['missing'].append(dict(kind='speech_commands_audio', error='local SpeechCommandsV2 audio and sample manifest absent',
            requested_root=None if args.data is None else str(args.data)))
    report['status'] = 'BLOCKED_INPUTS_OR_ENV' if report['missing'] else 'PRECONDITIONS_PRESENT_NOT_INFERENCE'
    report['official_600'] = 'UNAVAILABLE_MANIFEST_NOT_CERTIFIED'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    audio.write_json(args.output, report)
    print(report['status'] + ' ' + str(args.output.resolve()))
    return 2 if report['missing'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
