#!/usr/bin/env python3
"""Produce a deterministic, read-only inventory of an AMD FPGA project."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


SKIP_DIRS = {
    ".git", ".xil", "__pycache__", "node_modules", "build", "dist",
    "runs", "cache", "ip_user_files", ".cache", "artifacts",
}
ENTRY_SUFFIXES = {".bat", ".cmd", ".ps1", ".tcl", ".py"}
ENTRY_WORDS = re.compile(r"(?:run|build|check|synth|impl|sim|vivado|vitis|xsct|program)", re.I)
MODULE_RE = re.compile(r"^\s*module\s+([A-Za-z_][A-Za-z0-9_$]*)", re.M)


def iter_files(root: Path):
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().lower()):
        if not path.is_file():
            continue
        if any(part.lower() in SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        yield path


def relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def read_small(path: Path, limit: int = 2_000_000) -> str:
    try:
        if path.stat().st_size > limit:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="project root")
    parser.add_argument("--output", help="optional JSON output path")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")

    files = list(iter_files(root))
    counts = Counter(path.suffix.lower() or "<none>" for path in files)
    entries = [
        relative(path, root) for path in files
        if path.suffix.lower() in ENTRY_SUFFIXES and ENTRY_WORDS.search(path.name)
    ]
    manifests = [
        relative(path, root) for path in files
        if re.search(r"(?:manifest|filelist|sources?)", path.name, re.I)
        and path.suffix.lower() in {".tcl", ".f", ".txt", ".json"}
    ]
    constraints = [relative(path, root) for path in files if path.suffix.lower() == ".xdc"]
    block_designs = [relative(path, root) for path in files if path.suffix.lower() in {".bd", ".bda"}]

    mode_signals = {"project": [], "non_project": []}
    modules: list[dict[str, str]] = []
    for path in files:
        suffix = path.suffix.lower()
        if suffix == ".tcl":
            text = read_small(path)
            if re.search(r"\b(?:create_project|open_project|launch_runs)\b", text):
                mode_signals["project"].append(relative(path, root))
            if re.search(r"\b(?:read_verilog|read_vhdl|synth_design|place_design|route_design)\b", text):
                mode_signals["non_project"].append(relative(path, root))
        if suffix in {".v", ".sv"}:
            text = read_small(path)
            for name in MODULE_RE.findall(text)[:8]:
                modules.append({"name": name, "file": relative(path, root)})

    config = None
    config_path = root / "project_config.json"
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            config = {"parse_error": str(error)}

    if mode_signals["project"] and mode_signals["non_project"]:
        detected_mode = "mixed-or-multiple-flows"
    elif mode_signals["project"]:
        detected_mode = "project"
    elif mode_signals["non_project"]:
        detected_mode = "non-project"
    else:
        detected_mode = "unknown"

    result = {
        "schema": "amd-fpga-project-inventory/v1",
        "root": str(root),
        "project_config": config,
        "detected_mode": detected_mode,
        "mode_signals": {key: sorted(set(value)) for key, value in mode_signals.items()},
        "entry_points": entries,
        "candidate_manifests": manifests,
        "constraints": constraints,
        "block_designs": block_designs,
        "modules": modules,
        "file_counts_by_suffix": dict(sorted(counts.items())),
        "notes": [
            "Candidates are discovered heuristically; confirm authoritative paths from repository documentation.",
            "No build, simulation, synthesis, implementation, or hardware action was executed.",
        ],
    }
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8", newline="\n")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

