#!/usr/bin/env python3
"""Find likely bypass/mask/protocol surfaces without modifying the project."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


SKIP = {".git", ".xil", "build", "artifacts", "node_modules", "__pycache__"}
SUFFIXES = {".v", ".sv", ".svh", ".vhd", ".vhdl", ".tcl", ".ps1", ".py", ".md"}
CATEGORIES = {
    "bypass": re.compile(r"\b(?:bypass|skip|fast[_ -]?path|early[_ -]?exit|discard|drop)\w*\b", re.I),
    "mask": re.compile(r"\b(?:causal|all[_ -]?masked|mask(?:ed)?)\w*\b", re.I),
    "handshake": re.compile(r"\b(?:valid|ready|stall|backpressure|enqueue|dequeue|fifo)\w*\b", re.I),
    "recovery": re.compile(r"\b(?:reset|rst_n|clear|flush|abort|drain|epoch)\w*\b", re.I),
    "accounting": re.compile(r"\b(?:counter|count|processed|accepted|emitted|outstanding|occupancy)\w*\b", re.I),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--max-matches", type=int, default=1000)
    parser.add_argument("--output", help="optional JSON output path")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")

    matches = []
    counts: Counter[str] = Counter()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().lower()):
        if len(matches) >= args.max_matches:
            break
        if not path.is_file() or path.suffix.lower() not in SUFFIXES:
            continue
        if any(part.lower() in SKIP for part in path.relative_to(root).parts[:-1]):
            continue
        try:
            if path.stat().st_size > 2_000_000:
                continue
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for number, line in enumerate(lines, 1):
            categories = [name for name, pattern in CATEGORIES.items() if pattern.search(line)]
            if not categories:
                continue
            for category in categories:
                counts[category] += 1
            matches.append({
                "file": path.relative_to(root).as_posix(),
                "line": number,
                "categories": categories,
                "text": line.strip()[:300],
            })
            if len(matches) >= args.max_matches:
                break

    result = {
        "schema": "bypass-surface-scan/v1",
        "root": str(root),
        "category_counts": dict(sorted(counts.items())),
        "truncated": len(matches) >= args.max_matches,
        "matches": matches,
        "note": "Heuristic discovery only; confirm semantics in RTL, testbenches, and contracts.",
    }
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8", newline="\n")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

