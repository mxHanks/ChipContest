#!/usr/bin/env python3
"""Import the original KWT and restore every model variable, without audio/training."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import traceback
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SOURCE = Path('/home/mxhanks/Projects/migration-v0.2/vendor/kwt1-237e4097')
RUNTIME = ROOT / 'build/compliant32-20261113/numeric/runtime'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    if hasattr(os, 'sched_getaffinity'):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    for key in ('TF_NUM_INTRAOP_THREADS', 'TF_NUM_INTEROP_THREADS', 'OMP_NUM_THREADS',
                'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[key] = '1'
    os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
    sys.path[:0] = [str(ROOT), str(ROOT / 'tools/model')]
    import export_kwt as kwt
    report = dict(schema='s3-compliant32-legacy-runtime-check-v1',
                  created_utc=datetime.now(timezone.utc).isoformat(),
                  audio_inference_executed=False, numerical_inference_executed=False,
                  training_executed=False, dataset_downloaded=False,
                  official_600='UNAVAILABLE_MANIFEST_NOT_CERTIFIED')
    RUNTIME.mkdir(parents=True, exist_ok=True)
    try:
        provenance = kwt.source_inventory(args.source)
        np, tf = kwt.load_inference_dependencies()
        tf.config.threading.set_intra_op_parallelism_threads(1)
        tf.config.threading.set_inter_op_parallelism_threads(1)
        report['environment'] = kwt.environment_record()
        report['source'] = {k: v for k, v in provenance.items() if k != 'files'}
        report['source']['verified_files'] = len(provenance['files'])
        sys.path.insert(0, str(args.source))
        # Import the same modules and original input graph required by the
        # existing audio-manifest entry point. This does not enumerate data.
        from kws_streaming.models import models
        from kws_streaming.models.transformer_utils import KWSTransformer
        from kws_streaming.data import input_data
        from kws_streaming.layers.speech_features import SpeechFeatures
        report['original_module_imports'] = dict(models=models.__file__,
            input_data=input_data.__file__, speech_features=SpeechFeatures.__module__)
        flags = json.loads((args.source / kwt.MODEL_SUBDIR / 'flags.json').read_text())
        kwt.validate_flags(flags)
        for key, value in [('distill_teacher_json', ''), ('prenorm', False), ('approximate_gelu', False)]:
            flags.setdefault(key, value)
        flags.update(training=False, train=0, batch_size=1, use_spec_augment=0, use_spec_cutout=0,
                     sp_time_shift_ms=0.0, sp_resample=0.0, time_shift_ms=0.0, resample=0.0,
                     volume_resample=0.0, background_frequency=0.0, background_volume=0.0,
                     data_url='', data_dir='')
        reader = tf.train.load_checkpoint(str(args.source / kwt.MODEL_SUBDIR / 'best_weights'))
        layers = kwt.select_checkpoint_layers(reader.get_variable_to_shape_map())
        warnings = kwt.WarningCapture()
        tf.get_logger().addHandler(warnings)
        try:
            model = models.MODELS['kws_transformer'](SimpleNamespace(**flags))
            status = model.load_weights(str(args.source / kwt.MODEL_SUBDIR / 'best_weights'))
            status.assert_existing_objects_matched()
            status.expect_partial()
            restoration = kwt.verify_all_model_values(model, reader, tf, np, RUNTIME)
        finally:
            tf.get_logger().removeHandler(warnings)
        transformers = [layer for layer in model.layers if isinstance(layer, KWSTransformer)]
        if len(transformers) != 1 or len(transformers[0].enc_layers) != 12 or len(layers) != 12:
            raise ValueError('expected exactly one original 12-layer KWT transformer')
        restoration['warnings'] = warnings.messages
        report.update(status='PASS_RUNTIME_AND_ORIGINAL_CHECKPOINT_RESTORATION',
                      checkpoint_restoration=restoration, original_transformer_layers=12,
                      cpu_affinity=sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None,
                      remaining=['real Speech Commands V2 WAV validation', 'official sample manifest/600 certification'])
    except Exception as exc:
        report.update(status='FAIL_RUNTIME_CHECK', error=str(exc), traceback=traceback.format_exc())
    output = RUNTIME / 'runtime-check.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + '\n')
    print(json.dumps({key: report[key] for key in ('status', 'audio_inference_executed',
                     'training_executed')}))
    print(output)
    if report['status'].startswith('FAIL'):
        print(report['traceback'], file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
