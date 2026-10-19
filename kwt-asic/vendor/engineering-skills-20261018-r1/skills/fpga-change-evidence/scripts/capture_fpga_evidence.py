#!/usr/bin/env python3
"""Capture read-only FPGA change identity and selected file/log evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


METRIC_PATTERNS = {
    "wns_ns": re.compile(r"\bWNS(?:\s*\(ns\))?\s*[:=]\s*([+-]?\d+(?:\.\d+)?)", re.I),
    "tns_ns": re.compile(r"\bTNS(?:\s*\(ns\))?\s*[:=]\s*([+-]?\d+(?:\.\d+)?)", re.I),
    "whs_ns": re.compile(r"\bWHS(?:\s*\(ns\))?\s*[:=]\s*([+-]?\d+(?:\.\d+)?)", re.I),
    "ths_ns": re.compile(r"\bTHS(?:\s*\(ns\))?\s*[:=]\s*([+-]?\d+(?:\.\d+)?)", re.I),
    "pass_marker": re.compile(r"\bPASS(?:ED)?\b", re.I),
    "fail_marker": re.compile(r"\bFAIL(?:ED|URE)?\b|\bFATAL\b", re.I),
}


def run_git(root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args], cwd=root, check=True, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
        )
        return completed.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def file_record(path: Path, root: Path, parse_metrics: bool = False) -> dict:
    try:
        display_path = path.relative_to(root).as_posix()
    except ValueError:
        display_path = str(path)
    record = {
        "path": display_path,
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }
    if parse_metrics and path.stat().st_size <= 20_000_000:
        text = path.read_text(encoding="utf-8", errors="replace")
        metrics = {}
        for name, pattern in METRIC_PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                metrics[name] = matches[-1] if isinstance(matches[-1], str) else True
        record["observed_markers"] = metrics
    return record


def resolve_many(root: Path, values: list[str], kind: str) -> tuple[list[dict], list[str]]:
    records, missing = [], []
    for value in values:
        path = Path(value)
        if not path.is_absolute():
            path = root / path
        path = path.resolve()
        if not path.is_file():
            missing.append(value)
            continue
        records.append(file_record(path, root, parse_metrics=(kind == "log")))
    return records, missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--label", default="FPGA change evidence")
    parser.add_argument("--include", action="append", default=[], help="relevant source/config file")
    parser.add_argument("--log", action="append", default=[], help="selected log/report file")
    parser.add_argument("--artifact", action="append", default=[], help="selected output artifact")
    parser.add_argument("--command", action="append", default=[], help="record a reproduction command; does not execute it")
    parser.add_argument("--output", help="optional JSON output path")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")

    included, missing_include = resolve_many(root, args.include, "file")
    logs, missing_logs = resolve_many(root, args.log, "log")
    artifacts, missing_artifacts = resolve_many(root, args.artifact, "artifact")

    config = None
    config_path = root / "project_config.json"
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            config = {"parse_error": str(error)}

    status = run_git(root, "status", "--porcelain=v1")
    record = {
        "schema": "fpga-change-evidence/v1",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "claim": {"label": args.label, "status": "UNVERIFIED"},
        "root": str(root),
        "git": {
            "branch": run_git(root, "branch", "--show-current"),
            "head_sha": run_git(root, "rev-parse", "HEAD"),
            "dirty": bool(status) if status is not None else None,
            "status_porcelain": status.splitlines() if status else [],
        },
        "project_config": config,
        "reproduction_commands_not_executed": args.command,
        "files": included,
        "logs": logs,
        "artifacts": artifacts,
        "missing": {
            "files": missing_include,
            "logs": missing_logs,
            "artifacts": missing_artifacts,
        },
        "limitations": [
            "This collector did not execute any recorded command or FPGA tool.",
            "PASS/FAIL markers are text observations and require scope-aware validation.",
            "Set claim status only after checking the required evidence level.",
        ],
    }
    rendered = json.dumps(record, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        output = Path(args.output)
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8", newline="\n")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

