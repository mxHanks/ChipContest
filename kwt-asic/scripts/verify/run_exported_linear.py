#!/usr/bin/env python3
"""Validate exported KWT vectors before bounded, bit-exact RTL replay."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import time
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_linear as LINEAR

COMMON = LINEAR.COMMON
FORMAT = "fixed16_acc48_v1"
SHAPE = {"x": [99, 64], "w": [64, 256], "bias": [256], "y": [99, 256]}
MEMORY_SPECS = {"x": (16, 6336), "w": (16, 16384), "bias": (40, 256), "y": (48, 25344)}
PINNED_COMMIT = "237e4097afd4f6851e0b82f0a8d65c2dfe8eae30"


def relative_file(root, name):
    """Export members must be regular files contained in their export folder."""
    if not isinstance(name, str) or not name:
        raise ValueError("export member path must be a nonempty string")
    relative = PurePosixPath(name)
    if relative.is_absolute() or ".." in relative.parts or "\\" in name:
        raise ValueError("unsafe export member path: " + name)
    root = Path(root).resolve()
    path = root.joinpath(*relative.parts)
    if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
        raise ValueError("missing, linked or outside export member: " + name)
    return path.resolve()


def verify_record(path, metadata):
    """Return actual bytes only when they match the declared SHA-256."""
    digest = metadata.get("sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("missing/invalid SHA-256 for " + str(path))
    payload = Path(path).read_bytes()
    if hashlib.sha256(payload).hexdigest() != digest:
        raise ValueError("SHA-256 mismatch: " + str(path))
    if "bytes" in metadata and metadata["bytes"] != len(payload):
        raise ValueError("byte count mismatch: " + str(path))
    if "size_bytes" in metadata and metadata["size_bytes"] != len(payload):
        raise ValueError("byte count mismatch: " + str(path))
    return payload


def read_memory(root, metadata, role):
    bits, count = MEMORY_SPECS[role]
    if metadata.get("bits") != bits or metadata.get("count") != count:
        raise ValueError(f"incorrect {role} bit width or word count")
    path = relative_file(root, metadata.get("path"))
    payload = verify_record(path, metadata)
    try:
        lines = payload.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("memory image is not ASCII: " + str(path)) from exc
    if len(lines) != count:
        raise ValueError("actual memory word count mismatch: " + str(path))
    digits = bits // 4
    if not all(re.fullmatch(rf"[0-9a-fA-F]{{{digits}}}", line) for line in lines):
        raise ValueError("memory words must be fixed-width known hex: " + str(path))
    values = [int(line, 16) for line in lines]
    values = [value - (1 << bits) if value & (1 << (bits-1)) else value for value in values]
    return values, LINEAR.file_record(path), payload


def verify_layer_golden(arrays, model, layer_id):
    x = [arrays["x"][start:start+64] for start in range(0, 6336, 64)]
    w = [arrays["w"][start:start+256] for start in range(0, 16384, 256)]
    expected = [v for row in model.linear99x64x256(x, w, arrays["bias"]) for v in row]
    for index, (actual, golden) in enumerate(zip(arrays["y"], expected)):
        if actual != golden:
            raise ValueError(f"exported golden mismatch layer={layer_id} index={index} exported={actual} recalculated={golden}")
    if len(arrays["y"]) != len(expected):
        raise ValueError("exported golden size mismatch")


def validate_manifest_structure(manifest):
    if manifest.get("schema") != "kwt_ffn_export_v1" or manifest.get("status") != "PASS":
        raise ValueError("require a successful kwt_ffn_export_v1 export manifest")
    if manifest.get("format") != FORMAT or manifest.get("shape") != SHAPE:
        raise ValueError("export shape or numeric format mismatch")
    if manifest.get("end_marker") != "KWT_EXPORT_COMPLETED" or manifest.get("restoration", {}).get("status") != "PASS":
        raise ValueError("export must have completed with verified checkpoint restoration")
    layers = manifest.get("layers")
    if not isinstance(layers, list) or len(layers) != 12:
        raise ValueError("export must contain all twelve encoder layers")
    for index, layer in enumerate(layers):
        if type(layer.get("layer_id")) is not int or layer["layer_id"] != index:
            raise ValueError("layers must appear exactly once in order 0..11")
        if layer.get("shape") != SHAPE:
            raise ValueError("per-layer shape mismatch")
        if set(layer.get("files", {})) != set(MEMORY_SPECS):
            raise ValueError("each layer must identify x/w/bias/y memory images")
        scales = layer.get("scales", {})
        if set(scales) != {"x_exp", "w_exp", "bias_exp", "y_exp"} or any(type(v) is not int for v in scales.values()):
            raise ValueError("each layer must supply integer tensor scale exponents")
        if scales["bias_exp"] != scales["x_exp"] + scales["w_exp"] or scales["y_exp"] != scales["bias_exp"]:
            raise ValueError("bias/output scale must equal the product scale")
        keys = layer.get("checkpoint_keys", {})
        if set(keys) != {"kernel", "bias", "gamma", "beta"} or not all(isinstance(v, str) and v for v in keys.values()):
            raise ValueError("each layer must identify its checkpoint tensors")
        if not isinstance(layer.get("float_tensors"), dict):
            raise ValueError("each layer must bind exported floating-point tensors")
    source = manifest.get("source", {})
    if source.get("commit") != PINNED_COMMIT:
        raise ValueError("source commit is not the competition-pinned KWT version")
    sample = manifest.get("input", {})
    if sample.get("kind") not in {"synthetic_zero_silence_smoke", "user_supplied_waveform_smoke"}:
        raise ValueError("unsupported or absent source sample kind")
    if (sample.get("sample_rate"), sample.get("channels"), sample.get("samples")) != (16000, 1, 16000):
        raise ValueError("input must identify one 16 kHz mono one-second sample")
    if not isinstance(manifest.get("scope"), str) or not manifest["scope"]:
        raise ValueError("export scope must be recorded")
    return layers


def provenance_records(root, value):
    """Resolve and verify exporter provenance records, retaining exact hashes.

    Export-local relative records and explicit project-relative/absolute source
    records are distinct so moving an export cannot silently select a new file.
    """
    records = []
    if isinstance(value, dict):
        if "sha256" in value and ("path" in value or "project_relative_path" in value):
            if "project_relative_path" in value:
                path = relative_file(ROOT, value["project_relative_path"])
            else:
                name = value["path"]
                if not isinstance(name, str):
                    raise ValueError("provenance path must be a string")
                path = Path(name)
                if path.is_absolute():
                    if not path.is_file() or path.is_symlink():
                        raise ValueError("missing/linked provenance file: " + name)
                else:
                    path = relative_file(root, name)
            verify_record(path, value)
            records.append(LINEAR.file_record(path))
        for child in value.values():
            records.extend(provenance_records(root, child))
    elif isinstance(value, list):
        for child in value:
            records.extend(provenance_records(root, child))
    return records


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def validate_source(manifest, source_root=None):
    """Verify the pinned bytes at the recorded or explicitly relocated root."""
    source = manifest["source"]
    source_root = Path(source["source_directory"] if source_root is None else source_root)
    if not source_root.is_absolute() or not source_root.is_dir():
        raise ValueError("source_directory must identify an existing absolute source directory")
    inventory = source.get("files")
    if not isinstance(inventory, list) or not inventory or canonical_hash(inventory) != source.get("inventory_sha256"):
        raise ValueError("source inventory hash mismatch or empty inventory")
    paths = [item["path"] for item in inventory]
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate source inventory paths")
    checkpoint_names = {"models_data_v2_12_labels/kwt1/best_weights.index",
                        "models_data_v2_12_labels/kwt1/best_weights.data-00000-of-00001"}
    checkpoint = source.get("checkpoint", [])
    if {item["path"] for item in checkpoint} != checkpoint_names or len(checkpoint) != 2:
        raise ValueError("require both pinned best_weights checkpoint files")
    by_path = {item["path"]: item for item in inventory}
    if any(item != by_path.get(item["path"]) for item in checkpoint):
        raise ValueError("checkpoint identities do not match source inventory")
    provenance = ROOT / "docs/runs/kwt-source-manifest.json"
    verify_record(provenance, {"sha256": source["provenance_manifest_sha256"]})
    downloaded = json.loads(provenance.read_text())
    if downloaded.get("status") != "PASS" or downloaded.get("commit") != PINNED_COMMIT:
        raise ValueError("pinned source acquisition provenance is not PASS")
    expected = {}
    for item in downloaded["files"]:
        prefix, separator, relative = item["path"].partition(PINNED_COMMIT + "/")
        if not separator or relative in expected:
            raise ValueError("invalid/duplicate acquisition provenance paths")
        expected[relative] = {"path": relative, "sha256": item["sha256"], "bytes": item["bytes"]}
    if expected != by_path:
        raise ValueError("export source inventory differs from pinned acquisition provenance")
    records = [LINEAR.file_record(provenance)]
    for item in inventory:
        path = relative_file(source_root, item["path"])
        verify_record(path, item)
        records.append(LINEAR.file_record(path))
    implementation = manifest.get("implementation", [])
    required = {"scripts/model/export_kwt.py", "model/fixed16_acc48.py"}
    if {item.get("path") for item in implementation} != required or len(implementation) != 2:
        raise ValueError("export must bind the current exporter and numeric model")
    for item in implementation:
        path = relative_file(ROOT, item["path"])
        verify_record(path, item)
        records.append(LINEAR.file_record(path))
    restoration = manifest["restoration"]
    parameters = restoration.get("parameters", [])
    if (not parameters or restoration.get("model_variables") != len(parameters)
            or canonical_hash(parameters) != restoration.get("parameter_set_sha256")):
        raise ValueError("invalid checkpoint restoration parameter-set proof")
    return records


def validate_export(vector_root, model, source_root=None):
    vector_root = Path(vector_root).resolve()
    manifest_path = relative_file(vector_root, "manifest.json")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    layers = validate_manifest_structure(manifest)
    source_records = validate_source(manifest, source_root=source_root)
    sample_records = provenance_records(vector_root, manifest["input"])
    if not source_records or not sample_records:
        raise ValueError("source/checkpoint and input waveform provenance require verified file hashes")
    files = [LINEAR.file_record(manifest_path), *source_records, *sample_records]
    if manifest["input"]["kind"] == "user_supplied_waveform_smoke":
        original = Path(manifest["input"]["origin"])
        if not original.is_absolute():
            raise ValueError("original waveform provenance path must be absolute")
        verify_record(original, {"sha256": manifest["input"]["original_file_sha256"]})
        files.append(LINEAR.file_record(original))
    for name in ("checkpoint_inventory", "mfcc", "logits"):
        metadata = manifest[name]
        path = relative_file(vector_root, metadata["path"])
        verify_record(path, metadata)
        files.append(LINEAR.file_record(path))
    images = []
    for layer in layers:
        arrays, image = {}, {}
        for role in MEMORY_SPECS:
            arrays[role], record, payload = read_memory(vector_root, layer["files"][role], role)
            files.append(record)
            image[role] = payload
        float_path = relative_file(vector_root, layer["float_tensors"]["path"])
        verify_record(float_path, layer["float_tensors"])
        files.append(LINEAR.file_record(float_path))
        verify_layer_golden(arrays, model, layer["layer_id"])
        images.append(image)
    if manifest_path.read_bytes() != manifest_bytes:
        raise ValueError("export manifest changed while validating")
    return manifest, files, images


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vectors-dir", required=True, type=lambda p: Path(p).resolve())
    parser.add_argument("--source-root", type=lambda p: Path(p).resolve(),
                        help="explicit relocated KWT source directory; all pinned inventory hashes remain required")
    parser.add_argument("--tasks", type=int, choices=range(2, 13), default=12,
                        help="replay first N layers; the complete 12-layer export is always validated")
    parser.add_argument("--simulator", choices=("verilator", "iverilog"), default="verilator")
    parser.add_argument("--seed", type=int, default=20261015)
    parser.add_argument("--compile-timeout", type=int, default=180)
    parser.add_argument("--sim-timeout", type=int, default=180)
    args = parser.parse_args(argv)
    if min(args.compile_timeout, args.sim_timeout) <= 0 or not 0 <= args.seed <= 0x7fffffff:
        parser.error("timeouts must be positive; seed must fit nonnegative signed32")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "-exported-linear-" + uuid.uuid4().hex[:8]
    out = ROOT / "artifacts/runs" / run_id
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    model_path = ROOT / "model/fixed16_acc48.py"
    sources = [ROOT / "src/rtl/kwt_linear_engine.sv", ROOT / "sim/tb_kwt_linear_engine.sv"]
    inputs = [Path(__file__), ROOT / "scripts/verify/run_linear.py", ROOT / "scripts/verify/run_checks.py", model_path, *sources]
    result = {"schema": "kwt-exported-linear-checks-v1", "status": "FAIL", "run_id": run_id,
              "started_utc": COMMON.utc_now(), "output": str(out),
              "scope": "real checkpoint weights and one exported waveform/silence smoke sample only",
              "official_precision": "NOT_RUN", "validation_dataset_precision": "NOT_RUN", "soc": "NOT_RUN",
              "synthesis": "NOT_RUN", "timing": "NOT_RUN", "area": "NOT_RUN", "power": "NOT_RUN",
              "configuration": {"format": FORMAT, "shape": SHAPE, "lanes": 8, "tasks": args.tasks,
                                "layer_ids": list(range(args.tasks)), "seed": args.seed, "compile_jobs": 2},
              "simulator": args.simulator, "logic_semantics": "four-state" if args.simulator == "iverilog" else "two-state",
              "python_version": sys.version, "inputs": [], "export": {"status": "NOT_RUN"},
              "rtl": {"status": "NOT_RUN"}, "tools": {}, "commands": []}
    try:
        missing = [str(p) for p in [*inputs, args.vectors_dir / "manifest.json"] if not p.is_file()]
        if missing:
            result.update(status="BLOCKED", error="missing required file: " + ", ".join(missing))
        else:
            result["inputs"] = [LINEAR.file_record(p) for p in inputs]
            model = LINEAR.load_module("kwt_exported_numeric_model", model_path)
            manifest, export_records, images = validate_export(args.vectors_dir, model, source_root=args.source_root)
            result["export"] = {"status": "PASS", "manifest": export_records[0], "files": export_records,
                                "source": manifest["source"], "input": manifest["input"], "scope": manifest["scope"],
                                "source_resolution": {"declared_root": manifest["source"]["source_directory"],
                                                      "actual_root": str((args.source_root or Path(manifest["source"]["source_directory"])).resolve()),
                                                      "override": args.source_root is not None},
                                "verified_layers": 12, "golden_words_recomputed": 12 * LINEAR.OUTPUTS,
                                "per_layer_scales": [layer["scales"] for layer in manifest["layers"]]}
            result["scope"] = ("real checkpoint weights + synthetic zero-silence sample; synthetic frontend smoke only"
                               if manifest["input"]["kind"] == "synthetic_zero_silence_smoke" else
                               "real checkpoint weights + one user-supplied waveform; sample smoke only")
            vectors = out / "vectors"
            vectors.mkdir()
            copied = []
            for task, image in enumerate(images[:args.tasks]):
                for role, payload in image.items():
                    suffix = "b" if role == "bias" else role
                    target = vectors / f"task_{task:02d}_{suffix}.mem"
                    target.write_bytes(payload)
                    copied.append(LINEAR.file_record(target))
            result["replayed_vectors"] = copied
            config_path = out / "config.json"
            config_path.write_text(json.dumps(result["configuration"], sort_keys=True, indent=2) + "\n")
            result["config_file"] = LINEAR.file_record(config_path)
            needed = ["iverilog", "vvp"] if args.simulator == "iverilog" else ["verilator", "make", "g++"]
            for name in needed:
                result["tools"][name] = COMMON.tool_info(name, out, 2)
            if not all(shutil.which(name) for name in needed):
                result.update(status="BLOCKED", error="simulator/build dependencies missing")
                result["rtl"] = {"status": "BLOCKED"}
            else:
                if args.simulator == "verilator":
                    binary = out / "obj/simulation"
                    compile_argv = [shutil.which("verilator"), "--binary", "--timing", "--assert", "-Wno-fatal",
                                    "--top-module", "tb_kwt_linear_engine", "--Mdir", str(out / "obj"),
                                    "-o", "simulation", "-j", "2", "--threads", "1", *map(str, sources)]
                    run_argv = [str(binary)]
                else:
                    binary = out / "simulation.vvp"
                    compile_argv = [shutil.which("iverilog"), "-g2012", "-s", "tb_kwt_linear_engine", "-o", str(binary), *map(str, sources)]
                    run_argv = [shutil.which("vvp"), str(binary)]
                command = COMMON.run_command(compile_argv, out, out / "compile.log", args.compile_timeout, 2)
                result["commands"].append(command)
                result["rtl"] = {"status": "FAIL"}
                if command.get("exit_code") != 0 or command["timed_out"] or not binary.is_file():
                    result["error"] = "compilation failed/timed out; inspect compile.log"
                else:
                    result["binary"] = LINEAR.file_record(binary)
                    command = COMMON.run_command(run_argv + [f"+VECTORS={vectors}", f"+TASKS={args.tasks}", f"+SEED={args.seed}"],
                                                 out, out / "run.log", args.sim_timeout, 2)
                    result["commands"].append(command)
                    error, coverage = LINEAR.check_completion(command, COMMON.log_text(command), args.tasks)
                    if error:
                        result["error"] = error
                    else:
                        result.update(status="PASS", rtl={"status": "PASS", "coverage": coverage})
            changed = [item["path"] for item in [*result["inputs"], *export_records, *copied]
                       if LINEAR.file_record(item["path"])["sha256"] != item["sha256"]]
            if changed:
                result.update(status="FAIL", error="source/export/replay inputs changed during run", changed_inputs=changed)
    except Exception as exc:
        result.update(status="FAIL", error=f"{type(exc).__name__}: {exc}")
    finally:
        result.update(finished_utc=COMMON.utc_now(), elapsed_seconds=round(time.monotonic()-started, 3))
        (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("status", "scope", "output", "elapsed_seconds")}, ensure_ascii=False))
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
