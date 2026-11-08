#!/usr/bin/env python3
"""Byte-exact old BiasBankCache semantics and deterministic prototype stimulus."""
import argparse
from pathlib import Path
import random

MASK40 = (1 << 40)-1


def merge_bias(old, data, mask):
    if not (0 <= old <= MASK40 and 0 <= data <= MASK40 and 0 <= mask < 32):
        raise ValueError('raw signed40 codes and five-bit byte mask required')
    byte_mask = sum(255 << (8*byte) for byte in range(5) if mask & (1 << byte))
    return (old & ~byte_mask) | (data & byte_mask)


def sram_words(value):
    if not 0 <= value <= MASK40:
        raise ValueError('raw signed40 code required')
    return [value & 65535, (value >> 16) & 65535, value >> 32]


def signed_bias(value):
    return value-(1 << 40) if value & (1 << 39) else value


def generate(directory, seed=20261105, random_operations=1024):
    rng = random.Random(seed)
    memory = [0]*256
    records = []

    def command(read, active, addr, mask, data):
        error = int(not read and active)
        if not read and not error:
            memory[addr] = merge_bias(memory[addr], data, mask)
        records.append((int(read), int(active), addr, mask, data, memory[addr], error))

    for addr in range(256):
        value = [0, MASK40, 1 << 39, (1 << 39)-1][addr % 4] ^ (addr*0x102030405)
        command(False, False, addr, 31, value & MASK40)
        command(True, False, addr, 0, 0)
    # Every mask gets signed-boundary and lane/group-boundary targets.
    for mask in range(32):
        for addr in [0, 7, 8, 127, 128, 247, 248, 255]:
            command(False, False, addr, mask, rng.getrandbits(40))
            command(True, False, addr, 0, 0)
    for _ in range(random_operations):
        addr, mask, value = rng.randrange(256), rng.randrange(32), rng.getrandbits(40)
        command(False, rng.randrange(5)==0, addr, mask, value)
        command(True, rng.randrange(2)==0, addr, 0, 0)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory/'transactions.txt').write_text(''.join(
        '%d %d %02x %02x %010x %010x %d\n' % row for row in records))
    (directory/'final_bias.mem').write_text(''.join('%010x\n' % v for v in memory))
    return records, memory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    records, _ = generate(args.out)
    print('BIAS_REFERENCE_PASS transactions=%d masks=32 entries=256' % len(records))


if __name__ == '__main__':
    main()
