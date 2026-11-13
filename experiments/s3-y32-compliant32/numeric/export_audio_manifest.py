#!/usr/bin/env python3
"""Pinned KWT WAV-manifest -> exact S3 Y32 model/precision/CPU-vector export.

Never changes calibration/scales, downloads data, trains, or runs RTL/EDA.
TensorFlow inference uses the separately installed pinned Python 3.8 environment.
The manifest may be a development validation list or the later official list.
An input's claimed official origin is recorded, never authenticated by this tool.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
import traceback
import wave
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools/model'))
from model import fixed16_acc48 as fixed
from model import s3_y32 as s3
import export_kwt as kwt
import evaluate_kwt_dataset as evaluate
import export_s3_vectors as transport

MANIFEST_SCHEMA = 's3-compliant32-audio-manifest-v1'
VECTOR_SCHEMA = 's3-compliant32-audio-vectors-v1'
WANTED = ['yes', 'no', 'up', 'down', 'left', 'right', 'on', 'off', 'stop', 'go']
LABELS = ['_silence_', '_unknown_'] + WANTED


def digest(path):
    return kwt.sha256(path)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False,
                                    sort_keys=True, allow_nan=False) + '\n')


def file_record(path, base):
    path = Path(path)
    return dict(path=str(path.relative_to(base)), sha256=digest(path), bytes=path.stat().st_size)


def original_split(filename, validation_percentage=10, testing_percentage=10):
    """Literal pinned input_data.which_set algorithm; checked against upstream at runtime."""
    stem = re.sub(r'_nohash_.*$', '', Path(filename).name)
    maximum = 2**27 - 1
    value = int(hashlib.sha1(stem.encode('utf-8')).hexdigest(), 16)
    percentage = (value % (maximum + 1)) * (100.0 / maximum)
    return ('validation' if percentage < validation_percentage else
            'testing' if percentage < validation_percentage + testing_percentage else 'training')


def safe_relative(base, name):
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts or not relative.parts:
        raise ValueError('WAV path must be a safe relative path')
    path = base / relative
    # No symlink may swap samples outside the declared input root.
    for part in [path] + list(path.parents):
        if part == base.parent:
            break
        if part.is_symlink():
            raise ValueError('symlink in WAV path')
    if base.resolve() not in path.resolve().parents:
        raise ValueError('WAV path escapes dataset root')
    return path


def validate_manifest(path, dataset_root=None, require_files=True):
    """Validate structure, deterministic identities/split, task-to-sample mapping."""
    path = Path(path).resolve()
    data = json.loads(path.read_text())
    if data.get('schema') != MANIFEST_SCHEMA or data.get('purpose') not in (
            'development_validation', 'official_evaluation'):
        raise ValueError('unsupported manifest schema/purpose')
    base = Path(dataset_root or data.get('dataset_root', '')).expanduser()
    if not base.is_absolute():
        raise ValueError('dataset_root must be explicit and absolute')
    base = base.resolve()
    samples = data.get('samples')
    tasks = data.get('tasks')
    if not isinstance(samples, list) or not samples:
        raise ValueError('nonempty samples required')
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 12:
        raise ValueError('tasks must contain 1..12 entries')
    normalized, known = [], set()
    for item in samples:
        identity = item.get('sample_id')
        if not isinstance(identity, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', identity) or identity in known:
            raise ValueError('sample_id invalid or duplicate')
        known.add(identity)
        kind, label = item.get('kind'), item.get('label')
        if label not in LABELS or kind not in ('wav', 'silence_zero'):
            raise ValueError('unsupported label/kind')
        record = dict(item)
        record['label_index'] = LABELS.index(label)
        if kind == 'silence_zero':
            if label != '_silence_' or item.get('split') != 'synthetic_silence':
                raise ValueError('silence must be explicitly zero, not relabeled WAV')
            if any(key in item for key in ('path', 'sha256')):
                raise ValueError('synthetic silence has no decoded source WAV')
        else:
            if label == '_silence_' or not isinstance(item.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', item['sha256']):
                raise ValueError('WAV label/SHA invalid')
            relative = Path(item['path'])
            if relative.suffix.lower() != '.wav':
                raise ValueError('sample must be a WAV')
            source_label = relative.parts[0] if len(relative.parts) >= 2 else ''
            expected_label = source_label if source_label in WANTED else '_unknown_'
            if not source_label or source_label == '_background_noise_' or label != expected_label:
                raise ValueError('label must follow Speech Commands directory label mapping')
            actual_split = original_split(relative)
            if item.get('split') != actual_split:
                raise ValueError('declared split differs from pinned speaker-hash split')
            if data['purpose'] == 'development_validation' and actual_split != 'validation':
                raise ValueError('development evaluation may only consume validation WAVs')
            wav = safe_relative(base, item['path'])
            if require_files:
                if not wav.is_file():
                    raise kwt.MissingInferenceInput('missing manifest WAV: ' + str(wav))
                if digest(wav) != item['sha256']:
                    raise ValueError('manifest WAV SHA mismatch: ' + item['path'])
                with wave.open(str(wav), 'rb') as stream:
                    if (stream.getframerate(), stream.getnchannels(), stream.getsampwidth(), stream.getcomptype()) != (16000, 1, 2, 'NONE'):
                        raise ValueError('requires original 16kHz mono PCM16 Speech Commands WAV')
                    if stream.getnframes() <= 0:
                        raise ValueError('empty WAV')
                    record['original_frames'] = stream.getnframes()
                record['bytes'] = wav.stat().st_size
        normalized.append(record)
    for index, task in enumerate(tasks):
        if (type(task.get('task_id')) is not int or task['task_id'] != index or
                type(task.get('layer_id')) is not int or not 0 <= task['layer_id'] < 12 or
                task.get('sample_id') not in known):
            raise ValueError('task IDs must be consecutive, layers valid, samples declared')
    if len(tasks) == 12 and sorted(task['layer_id'] for task in tasks) != list(range(12)):
        raise ValueError('12-task export must cover all 12 layer parameters exactly once')
    if not any(item['kind'] == 'wav' for item in normalized):
        raise ValueError('manifest must include at least one real non-silence WAV')
    task_samples = {task['sample_id'] for task in tasks}
    if not any(item['kind'] == 'wav' and item['sample_id'] in task_samples for item in normalized):
        raise ValueError('CPU task list must not consist only of silence')
    return data, base, normalized


def integer_y32(raw, np):
    """Vectorized exact floor-divmod/ties-even, independently checked with s3 model."""
    if raw.dtype != np.int64 or np.any(raw < s3.Y48_MIN) or np.any(raw > s3.Y48_MAX):
        raise ValueError('raw integer outside full signed16/signed40 MAC domain')
    quotient, remainder = np.divmod(raw, 512)
    result = quotient + ((remainder > 256) | ((remainder == 256) & ((quotient & 1) != 0))).astype(np.int64)
    if np.any(result < -(1 << 31)) or np.any(result >= (1 << 31)):
        raise ValueError('Y32 overflow')
    return result


def check_rne_without_dependencies():
    """Canonical S3 test used in preflight; no fabricated speech/precision claim."""
    from fractions import Fraction
    values = [s3.Y48_MIN, s3.Y48_MAX]
    values += [512 * q + rem for q in range(-7, 8) for rem in (0, 1, 255, 256, 257, 511)]
    for value in values:
        if s3.quantize_result(value) != round(Fraction(value, 512)):
            raise ValueError('canonical S3 RNE identity mismatch')
    return dict(status='PASS', values=len(values), scope='canonical Y32 arithmetic only; no audio inference')


def implementation_record():
    paths = [Path(__file__).resolve(), ROOT / 'model/s3_y32.py', ROOT / 'model/fixed16_acc48.py',
             ROOT / 'tools/model/export_kwt.py', ROOT / 'tools/model/evaluate_kwt_dataset.py',
             ROOT / 'tools/model/export_s3_vectors.py', ROOT / 'model/kwt-static-scales.json']
    return [file_record(path, ROOT) for path in paths]


def evaluate_manifest(args, report):
    data, base, samples = validate_manifest(args.manifest, args.data_root)
    provenance = kwt.source_inventory(args.source)
    original_implementations = implementation_record()
    report.update(input_manifest=dict(path=str(args.manifest), sha256=digest(args.manifest)),
                  manifest_purpose=data['purpose'], declared_dataset=data.get('dataset'),
                  dataset_root=str(base), samples=samples, source=provenance,
                  implementation=original_implementations,
                  arithmetic_preflight=check_rne_without_dependencies(),
                  python_executable=sys.executable, python_version=sys.version,
                  official_acceptance='NOT_RUN_OR_CERTIFIED', calibration='UNCHANGED_PARAMETER_ONLY_STATIC_SCALES')
    if args.preflight_only:
        report.update(status='PREFLIGHT_PASS_NOT_INFERENCE', evaluation_completed=False,
                      inference_environment_available=sys.version_info[:3] == (3, 8, 20))
        return report
    # Thread limits precede TF/NumPy imports. This tool does not create processes or use a GPU.
    for key, value in [('TF_NUM_INTRAOP_THREADS', str(args.threads)), ('TF_NUM_INTEROP_THREADS', '1'),
                       ('OMP_NUM_THREADS', str(args.threads)), ('OPENBLAS_NUM_THREADS', str(args.threads)),
                       ('MKL_NUM_THREADS', str(args.threads)), ('CUDA_VISIBLE_DEVICES', '-1')]:
        os.environ[key] = value
    np, tf = kwt.load_inference_dependencies()
    tf.config.threading.set_intra_op_parallelism_threads(args.threads)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    sys.path.insert(0, str(args.source))
    from kws_streaming.models import models
    from kws_streaming.models.transformer_utils import KWSTransformer
    from kws_streaming.data import input_data
    from kws_streaming.layers.speech_features import SpeechFeatures
    for sample in samples:
        if sample['kind'] == 'wav' and input_data.which_set(sample['path'], 10, 10) != sample['split']:
            raise ValueError('local split implementation differs from pinned original')
    flags = json.loads((args.source / kwt.MODEL_SUBDIR / 'flags.json').read_text())
    kwt.validate_flags(flags)
    for key, value in [('distill_teacher_json', ''), ('prenorm', False), ('approximate_gelu', False)]:
        flags.setdefault(key, value)
    flags.update(training=False, train=0, batch_size=args.batch_size, use_spec_augment=0, use_spec_cutout=0,
                 sp_time_shift_ms=0.0, sp_resample=0.0, time_shift_ms=0.0, resample=0.0, volume_resample=0.0,
                 background_frequency=0.0, background_volume=0.0, data_url='', data_dir=str(base))
    namespace = SimpleNamespace(**flags)
    reader = tf.train.load_checkpoint(str(args.source / kwt.MODEL_SUBDIR / 'best_weights'))
    keys = kwt.select_checkpoint_layers(reader.get_variable_to_shape_map())
    capture_warnings = kwt.WarningCapture()
    tf.get_logger().addHandler(capture_warnings)
    try:
        model = models.MODELS['kws_transformer'](namespace)
        status = model.load_weights(str(args.source / kwt.MODEL_SUBDIR / 'best_weights'))
        status.assert_existing_objects_matched()
        status.expect_partial()
        restoration = kwt.verify_all_model_values(model, reader, tf, np, args.output)
    finally:
        tf.get_logger().removeHandler(capture_warnings)
    restoration['warnings'] = capture_warnings.messages
    transformers = [layer for layer in model.layers if isinstance(layer, KWSTransformer)]
    if len(transformers) != 1 or len(transformers[0].enc_layers) != 12:
        raise ValueError('expected one pinned 12-layer transformer')
    transformer = transformers[0]
    parameters, layer_reports = [], []
    for layer_id, layer_keys in enumerate(keys):
        block = transformer.enc_layers[layer_id]
        w, bias, gamma, beta = tf.keras.backend.batch_get_value([
            block.ffn.layers[0].kernel, block.ffn.layers[0].bias, block.layernorm1.gamma, block.layernorm1.beta])
        for name, value in [('kernel', w), ('bias', bias), ('gamma', gamma), ('beta', beta)]:
            if not np.array_equal(value, reader.get_tensor(layer_keys[name])):
                raise ValueError('checkpoint parameter differs')
        x_bound, w_bound = kwt.layernorm_bound(gamma, beta), float(np.max(np.abs(w)))
        scales = fixed.Fixed16Scales(kwt.choose_scale_exp(x_bound), kwt.choose_scale_exp(w_bound))
        kwt.validate_static_scales(layer_id, scales.x_exp, scales.w_exp, x_bound, w_bound)
        if scales.y_exp + s3.RIGHT_SHIFT != s3.OUTPUT_EXP:
            raise ValueError('frozen Y32 output exponent does not match this layer')
        wi, wc = evaluate.quantize_float32(w, 16, scales.w_exp)
        bi, bc = evaluate.quantize_float32(bias, 40, scales.y_exp)
        if wc or bc:
            raise ValueError('frozen parameter scales clipped weights or bias')
        parameters.append((w, bias, wi, bi, scales))
        layer_reports.append(dict(layer_id=layer_id, checkpoint_keys=layer_keys,
            scales=dict(x_exp=scales.x_exp, w_exp=scales.w_exp, bias_exp=scales.y_exp,
                        raw48_exp=scales.y_exp, output_y32_exp=s3.OUTPUT_EXP, output_right_shift=9),
            sample_independent_scales=True, weight_clips=wc, bias_clips=bc,
            x_clips=0, sum_error_sq=0.0, sum_reference_sq=0.0, sample_nrmse=[]))
    # Use the ORIGINAL unaugmented decode/crop/pad/resample graph, without the
    # constructor's full-dataset enumeration, so arbitrary official lists work.
    processor = input_data.AudioProcessor.__new__(input_data.AudioProcessor)
    processor.prepare_processing_graph(namespace)
    captured, originals = {}, []
    audio = tf.compat.v1.placeholder(tf.float32, (args.batch_size, 16000), name='manifest_waveform')
    for layer_id, block in enumerate(transformer.enc_layers):
        dense, old_call = block.ffn.layers[0], block.ffn.layers[0].call
        def capture(inputs, *positional, _id=layer_id, _call=old_call, **keywords):
            result = _call(inputs, *positional, **keywords)
            if _id in captured:
                raise ValueError('FFN hook executed twice')
            captured[_id] = (inputs, result)
            return result
        originals.append((dense, old_call))
        dense.call = capture
    try:
        logits = model(audio, training=False)
    finally:
        for dense, old_call in originals:
            dense.call = old_call
    if isinstance(logits, (list, tuple)):
        if len(logits) != 1:
            raise ValueError('wrong classifier outputs')
        logits = logits[0]
    if set(captured) != set(range(12)):
        raise ValueError('missing real-model FFN1 activation')
    feature_layers = [layer for layer in model.layers if isinstance(layer, SpeechFeatures)]
    if len(feature_layers) != 1:
        raise ValueError('requires one original MFCC feature layer')
    mfcc = feature_layers[0](audio, training=False)
    fetches = [value for layer in range(12) for value in captured[layer]] + [mfcc, logits]
    session = tf.compat.v1.keras.backend.get_session()
    graph_ops = len(session.graph.get_operations())
    vectors = args.output / 'vectors'
    vectors.mkdir()
    task_records = {}
    sums_by_layer = [( [], [] ) for _ in range(12)]
    sample_records, correct = [], 0
    with (args.output / 'samples.jsonl').open('w') as sample_log:
        for offset in range(0, len(samples), args.batch_size):
            selected = samples[offset:offset + args.batch_size]
            waveforms = np.zeros((args.batch_size, 16000), dtype=np.float32)
            for index, sample in enumerate(selected):
                if sample['kind'] == 'wav':
                    value = processor.get_features_for_wav(str(base / sample['path']), namespace, session)[0]
                    if value.shape != (16000,) or not np.isfinite(value).all():
                        raise ValueError('upstream WAV decode must yield finite 16000 samples')
                    waveforms[index] = value
                    if not np.any(value):
                        raise ValueError('non-silence manifest WAV decoded to all zero')
            tensors = session.run(fetches, feed_dict={audio: waveforms})
            predictions = tensors[-1][:len(selected)]
            mfcc_values = tensors[-2][:len(selected)]
            if mfcc_values.shape != (len(selected), 98, 40) or not np.isfinite(mfcc_values).all():
                raise ValueError('original MFCC must be finite [batch,98,40]')
            if predictions.shape != (len(selected), 12) or not np.isfinite(predictions).all():
                raise ValueError('bad FP32 classifier output')
            records = [dict(sample_id=sample['sample_id'], label=sample['label'],
                            waveform_float32_sha256=hashlib.sha256(waveforms[index].tobytes()).hexdigest(),
                            mfcc_float32_sha256=hashlib.sha256(mfcc_values[index].tobytes()).hexdigest(),
                            float_reference_label=int(np.argmax(predictions[index])), layers=[])
                       for index, sample in enumerate(selected)]
            correct += sum(record['float_reference_label'] == sample['label_index']
                           for record, sample in zip(records, selected))
            for layer_id, (w, bias, wi, bi, scales) in enumerate(parameters):
                x, ref = tensors[2 * layer_id][:len(selected)], tensors[2 * layer_id + 1][:len(selected)]
                if (x.shape != (len(selected), 99, 64) or ref.shape != (len(selected), 99, 256) or
                        x.dtype != np.float32 or ref.dtype != np.float32):
                    raise ValueError('FFN1 shape differs from required task')
                xi, clips = evaluate.quantize_float32(x, 16, scales.x_exp)
                if clips:
                    raise ValueError('frozen X scales clipped manifest activations')
                raw = evaluate.integer_linear(xi, wi, bi)
                y32 = integer_y32(raw, np)
                decoded = np.ldexp(y32.astype(np.float64), s3.OUTPUT_EXP)
                sums = evaluate.error_sums(decoded, ref)
                sums_by_layer[layer_id][0].extend(sums['sse'].tolist())
                sums_by_layer[layer_id][1].extend(sums['reference_energy'].tolist())
                for local, sample in enumerate(selected):
                    records[local]['layers'].append(dict(layer_id=layer_id,
                        **{key: float(values[local]) for key, values in sums.items()}))
                    for task in data['tasks']:
                        if task['sample_id'] != sample['sample_id'] or task['layer_id'] != layer_id:
                            continue
                        task_id = task['task_id']
                        target = vectors / ('layer_%02d' % task_id)
                        target.mkdir()
                        x_list, w_list, bias_list = xi[local].tolist(), wi.tolist(), bi.tolist()
                        expected_raw = fixed.linear99x64x256(x_list, w_list, bias_list)
                        expected_y32 = s3.quantize_output(expected_raw)
                        if not np.array_equal(raw[local], expected_raw) or not np.array_equal(y32[local], expected_y32):
                            raise ValueError('exported task differs from exact canonical raw/Y32 model')
                        for name, values, bits in [
                                ('x', xi[local].flat, 16), ('w', wi.flat, 16), ('bias', bi.flat, 40),
                                ('y', raw[local].flat, 48)]:
                            fixed.write_hex_mem(target / (name + '.mem'), [int(v) for v in values], bits)
                        np.savez(str(target / 'float-reference.npz'), x_float=x[local], y_float=ref[local],
                                 waveform=waveforms[local], mfcc=mfcc_values[local], decoded_y32=decoded[local])
                        task_records[task_id] = dict(task, directory='layer_%02d' % task_id,
                            sample=sample, output_values=25344, nrmse=float(sums['nrmse'][local]),
                            exact_model_crosscheck='PASS_RAW48_AND_Y32_ALL_25344')
            for record in records:
                sample_log.write(json.dumps(record, separators=(',', ':'), allow_nan=False) + '\n')
                sample_records.append(record)
            sample_log.flush()
            print('Y32_AUDIO_PROGRESS ' + json.dumps(dict(done=offset + len(selected), total=len(samples))), flush=True)
    if set(task_records) != set(range(len(data['tasks']))):
        raise ValueError('not all requested tasks were exported')
    if len(session.graph.get_operations()) != graph_ops:
        raise ValueError('inference graph grew across samples')
    for layer_id, layer in enumerate(layer_reports):
        layer.update(evaluate.aggregate(*sums_by_layer[layer_id], len(samples)))
        layer['max_sample_nrmse'] = max(record['layers'][layer_id]['nrmse'] for record in sample_records)
        layer.pop('sample_nrmse')
    profile = transport.add_s3_files(vectors, len(data['tasks']), shared_w_packed=True)
    ordered_tasks = [task_records[i] for i in range(len(data['tasks']))]
    for task in ordered_tasks:
        target = vectors / task['directory']
        task['files'] = {path.name: file_record(path, vectors) for path in sorted(target.iterdir()) if path.is_file()}
    vector_manifest = dict(schema=VECTOR_SCHEMA, format=s3.FORMAT_ID, tasks=ordered_tasks,
        task_count=len(ordered_tasks), audio_manifest_sha256=digest(args.manifest),
        source=provenance, quantization_static_scales_sha256=digest(kwt.SCALE_CONTRACT),
        numerical_models={name: digest(ROOT / 'model' / name) for name in ['fixed16_acc48.py', 's3_y32.py']},
        transport_profile_sha256=digest(vectors / 'profile.json'), implementations=original_implementations,
        official_600_acceptance='NOT_RUN_OR_CERTIFIED', loader='real platform 32-bit System Bus only; reference files never enter DUT')
    write_json(vectors / 'vectors-manifest.json', vector_manifest)
    # Rehash exact input sources and all implementations after inference/export.
    final_data, final_base, final_samples = validate_manifest(args.manifest, args.data_root)
    if final_samples != samples or final_data != data or final_base != base:
        raise ValueError('audio inputs or manifest changed during inference')
    if kwt.source_inventory(args.source) != provenance or implementation_record() != original_implementations:
        raise ValueError('source/checkpoint/config/model changed during inference')
    maximum = max(layer['nrmse'] for layer in layer_reports)
    max_sample = max(layer['max_sample_nrmse'] for layer in layer_reports)
    task_max = max(task['nrmse'] for task in ordered_tasks)
    gate = 'PASS' if maximum <= 0.03 and task_max <= 0.03 else 'FAIL'
    report.update(status='DEVELOPMENT_Y32_PRECISION_' + gate, evaluation_completed=True,
        format=s3.FORMAT_ID, output_y32_exp=s3.OUTPUT_EXP, restoration=restoration,
        inference_flags=flags, environment=kwt.environment_record(), layers=layer_reports,
        max_layer_nrmse=maximum, max_sample_layer_nrmse=max_sample, max_exported_task_nrmse=task_max,
        reference_classifier_accuracy=correct / len(samples), reference_classifier_only=True,
        sample_count=len(samples), sample_label_counts=dict(Counter(item['label'] for item in samples)),
        vectors=file_record(vectors / 'vectors-manifest.json', args.output),
        samples_log=file_record(args.output / 'samples.jsonl', args.output),
        all_exported_task_output_values=25344 * len(ordered_tasks), input_rehash='PASS',
        limitations=['Local manifest precision does not establish official 600 sample acceptance.',
                     'Isolated FFN1 uses true FP32 activations of each layer, not quantized full encoder inference.',
                     'TF 2.4.0 release is the recorded fallback for unavailable 2.4.0rc1.',
                     'No RTL/SoC simulation, timing/area/power or official resource claims from this tool.'])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--data-root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--batch-size', type=int, default=8)
    parser.add_argument('--threads', type=int, choices=(1, 2), default=1)
    parser.add_argument('--preflight-only', action='store_true')
    args = parser.parse_args(argv)
    if not 1 <= args.batch_size <= 32:
        parser.error('batch-size must be 1..32')
    for key in ('source', 'manifest', 'output'):
        setattr(args, key, getattr(args, key).resolve())
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(schema='s3-compliant32-audio-evaluation-v1', status='FAIL',
                  created_utc=datetime.now(timezone.utc).isoformat(), command=[sys.executable] + sys.argv,
                  evaluation_completed=False, official_acceptance='NOT_RUN_OR_CERTIFIED')
    try:
        report = evaluate_manifest(args, report)
        code = 1 if report['status'].endswith('_FAIL') else 0
    except Exception as exc:
        blocked = isinstance(exc, kwt.MissingInferenceInput)
        report.update(status='BLOCKED' if blocked else 'FAIL', error_type=type(exc).__name__,
                      error=str(exc), traceback=traceback.format_exc())
        code = 2 if blocked else 1
        traceback.print_exc()
    report['exit_code'] = code
    write_json(args.output / 'result.json', report)
    print('Y32_AUDIO_EVALUATION ' + json.dumps(dict(status=report['status'], output=str(args.output))), flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
