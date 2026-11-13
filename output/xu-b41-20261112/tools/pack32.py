#!/usr/bin/env python3
"""Pack frozen INT16/signed40 B41 layer inputs into native 32-bit beats.

This script performs only representation changes. It does not train, quantize,
reorder the model, or alter the numerical values.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def read_hex(path: Path, width: int) -> list[int]:
    mask = (1 << width) - 1
    values: list[int] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            value = int(line, 16)
            if value & ~mask:
                raise ValueError(f"{path}: value wider than {width} bits: {line}")
            values.append(value)
    return values


def write_hex(path: Path, values: list[int], width: int) -> None:
    digits = (width + 3) // 4
    path.write_text("".join(f"{v & ((1 << width) - 1):0{digits}x}\n" for v in values))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("layer", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    layer = args.layer
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    x = read_hex(layer / "x.mem", 16)
    w = read_hex(layer / "w.mem", 16)
    bias = read_hex(layer / "bias.mem", 40)
    if len(x) != 6336 or len(w) != 16384 or len(bias) != 256:
        raise ValueError(f"unexpected dimensions x={len(x)} w={len(w)} bias={len(bias)}")

    x32 = [(x[2 * i + 1] << 16) | x[2 * i] for i in range(len(x) // 2)]
    w32 = [(w[2 * i + 1] << 16) | w[2 * i] for i in range(len(w) // 2)]
    bias_low = [v & 0xFFFFFFFF for v in bias]
    bias_high = [(v >> 32) & 0xFF for v in bias]
    write_hex(out / "x_packed32.mem", x32, 32)
    write_hex(out / "w_packed16.mem", w32, 32)
    write_hex(out / "bias_low32.mem", bias_low, 32)
    write_hex(out / "bias_high8.mem", bias_high, 8)

    supplied = layer / "w_packed16.mem"
    if supplied.exists() and read_hex(supplied, 32) != w32:
        raise ValueError(f"{supplied}: does not match w.mem pair packing")
    manifest = out / "pack32.sha256"
    entries = []
    for path in sorted(out.glob("*.mem")):
        entries.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    manifest.write_text("\n".join(entries) + "\n")
    print(f"PACK32_PASS x={len(x32)} w={len(w32)} bias={len(bias)} out={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
