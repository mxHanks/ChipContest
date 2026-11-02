#!/usr/bin/env python3
"""Temporary xu screenshot receipt transfer; Python 3.6 server, Pillow decoder.

Only decode screenshots obtained through the authorized visible-screen channel.
This transports file bytes; it does not turn a derived receipt into original logs.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

MAGIC = b'XUSCRN1\0'
SCHEMA = 'xu-screen-page-v1'
COLS, ROWS = 128, 32
CAPACITY = COLS * (ROWS - 1) // 2
HEADER = struct.Struct('<8sHHII32sHHI4s')
CHUNK = CAPACITY - HEADER.size
# Eight outer and eight inner corners of the standard xterm 6x6x6 cube.
PALETTE = (16, 21, 46, 51, 196, 201, 226, 231,
           59, 62, 77, 80, 167, 170, 185, 188)
LEVELS = (0, 95, 135, 175, 215, 255)
RGB = tuple((LEVELS[(index - 16) // 36], LEVELS[((index - 16) // 6) % 6],
             LEVELS[(index - 16) % 6]) for index in PALETTE)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def content(path):
    raw = path.read_bytes()
    compressed = zlib.compress(raw, 9)
    total = max(1, (len(compressed) + CHUNK - 1) // CHUNK)
    if total > 65535 or len(raw) > 0xffffffff:
        raise ValueError('receipt is too large for this temporary transfer format')
    return raw, compressed, total


def header(page, total, compressed_len, raw_len, raw_sha256, chunk_len, crc=0):
    return HEADER.pack(MAGIC, page, total, compressed_len, raw_len,
                       bytes.fromhex(raw_sha256), chunk_len, 0, crc, b'\0' * 4)


def frame(path, page):
    raw, compressed, total = content(path)
    if not 1 <= page <= total:
        raise ValueError('page must be 1..{}'.format(total))
    chunk = compressed[(page - 1) * CHUNK:page * CHUNK]
    metadata = dict(page=page, total=total, compressed_len=len(compressed), raw_len=len(raw),
                    raw_sha256=sha(raw), chunk_len=len(chunk))
    zero = header(**metadata)
    crc = zlib.crc32(zero + chunk) & 0xffffffff
    payload = header(crc=crc, **metadata) + chunk
    return payload.ljust(CAPACITY, b'\0'), metadata, crc


def nibbles(payload):
    values = [index % 16 for index in range(COLS)]
    for value in payload:
        values.extend([value >> 4, value & 15])
    return values


def emit(path, page):
    payload, metadata, crc = frame(path, page)
    values = nibbles(payload)
    output = ['\x1b[2J\x1b[H',
              'XU_SCREEN {}/{} raw={} compressed={} chunk={} crc32={:08x}\r\n'.format(
                  page, metadata['total'], metadata['raw_len'], metadata['compressed_len'], metadata['chunk_len'], crc),
              'SHA256 {}\r\n'.format(metadata['raw_sha256'])]
    for row in range(ROWS):
        previous = None
        for value in values[row * COLS:(row + 1) * COLS]:
            if value != previous:
                output.append('\x1b[48;5;{}m'.format(PALETTE[value]))
                previous = value
            output.append(' ')
        output.append('\x1b[0m\r\n')
    output.append('XU_SCREEN END {}/{}; 128 columns, 32 rows, 16 cube colors\r\n\x1b[0m'.format(page, metadata['total']))
    sys.stdout.write(''.join(output))
    sys.stdout.flush()


def parse_payload(payload):
    magic, page, total, compressed_len, raw_len, raw_sha, chunk_len, reserved, crc, padding = HEADER.unpack(payload[:HEADER.size])
    if (magic != MAGIC or reserved or padding != b'\0' * 4 or not 1 <= page <= total or
            not 1 <= chunk_len <= CHUNK or compressed_len < chunk_len or
            total != (compressed_len + CHUNK - 1) // CHUNK):
        raise ValueError('invalid frame magic/header')
    expected_chunk = CHUNK if page < total else compressed_len - CHUNK * (total - 1)
    if chunk_len != expected_chunk:
        raise ValueError('invalid frame chunk length')
    chunk = payload[HEADER.size:HEADER.size + chunk_len]
    metadata = dict(page=page, total=total, compressed_len=compressed_len, raw_len=raw_len,
                    raw_sha256=raw_sha.hex(), chunk_len=chunk_len)
    if zlib.crc32(header(**metadata) + chunk) & 0xffffffff != crc:
        raise ValueError('frame CRC32 mismatch')
    return dict(metadata, schema=SCHEMA, crc32='{:08x}'.format(crc),
                chunk_base64=base64.b64encode(chunk).decode('ascii'))


class Pixels:
    def __init__(self, image):
        self.image = image.convert('RGB')
        self.pixels = self.image.load()
        self.cache = {}

    def value(self, x, y):
        rgb = self.pixels[x, y]
        if rgb not in self.cache:
            distances = [sum((a - b) ** 2 for a, b in zip(rgb, expected)) for expected in RGB]
            nearest = min(range(16), key=lambda index: distances[index])
            self.cache[rgb] = nearest if distances[nearest] <= 24 ** 2 else None
        return self.cache[rgb]

    def calibration(self, origin, width, y, count=COLS):
        return all(self.value(origin + index * width + width // 2, y) == index % 16
                   for index in range(count))


def decode_image(screenshot):
    # The only optional dependency is local Pillow; server emit/info stay stdlib.
    from PIL import Image
    pixels = Pixels(Image.open(str(screenshot)))
    image_width, image_height = pixels.image.size
    tried, errors = set(), []
    for y in range(75, min(300, image_height - 1) + 1):
        for width in range(6, 13):
            for guessed_origin in range(17):
                if guessed_origin + COLS * width > image_width:
                    continue
                if not pixels.calibration(guessed_origin, width, y, 16):
                    continue
                # Cell one is blue, so its boundaries locate the grid even when
                # cell zero black blends into the terminal's surrounding margin.
                center = guessed_origin + width + width // 2
                left, right = center, center
                while left > 0 and pixels.value(left - 1, y) == 1:
                    left -= 1
                while right + 1 < image_width and pixels.value(right + 1, y) == 1:
                    right += 1
                actual_width = right - left + 1
                origin = left - actual_width
                if not 6 <= actual_width <= 12 or not 0 <= origin <= 16 or origin + COLS * actual_width > image_width:
                    continue
                if not pixels.calibration(origin, actual_width, y):
                    continue
                top, bottom = y, y
                while top > 0 and pixels.calibration(origin, actual_width, top - 1, 16):
                    top -= 1
                while bottom + 1 < image_height and pixels.calibration(origin, actual_width, bottom + 1, 16):
                    bottom += 1
                height = bottom - top + 1
                geometry = (origin, actual_width, top, height)
                if geometry in tried or not 8 <= height <= 32 or top + ROWS * height > image_height:
                    continue
                tried.add(geometry)
                try:
                    values = []
                    for row in range(1, ROWS):
                        center_y = top + row * height + height // 2
                        for column in range(COLS):
                            value = pixels.value(origin + column * actual_width + actual_width // 2, center_y)
                            if value is None:
                                raise ValueError('unknown color at data row {}, column {}'.format(row, column))
                            values.append(value)
                    payload = bytes((values[index] << 4) | values[index + 1] for index in range(0, len(values), 2))
                    result = parse_payload(payload)
                    result.update(source_screenshot=str(screenshot.resolve()), screenshot_sha256=sha(screenshot.read_bytes()),
                                  geometry=dict(x=origin, y=top, cell_width=actual_width, cell_height=height))
                    return result
                except ValueError as error:
                    errors.append(str(error))
    raise ValueError('no valid calibrated frame: ' + (errors[0] if errors else 'calibration row not found'))


def write_new(path, data):
    with path.open('xb') as stream:
        stream.write(data)


def combine(paths, destination):
    pages, metadata = {}, None
    for path in paths:
        record = json.loads(path.read_text())
        if record.get('schema') != SCHEMA:
            raise ValueError('incorrect page JSON schema: ' + str(path))
        identity = tuple(record[name] for name in ['total', 'compressed_len', 'raw_len', 'raw_sha256'])
        if metadata is None:
            metadata = identity
        if metadata != identity or record['page'] in pages:
            raise ValueError('mixed transfers or duplicate page')
        chunk = base64.b64decode(record['chunk_base64'], validate=True)
        payload = header(page=record['page'], total=record['total'], compressed_len=record['compressed_len'],
                         raw_len=record['raw_len'], raw_sha256=record['raw_sha256'], chunk_len=record['chunk_len'],
                         crc=int(record['crc32'], 16)) + chunk
        validated = parse_payload(payload)
        pages[validated['page']] = chunk
    if metadata is None or set(pages) != set(range(1, metadata[0] + 1)):
        raise ValueError('missing transfer pages')
    compressed = b''.join(pages[index] for index in range(1, metadata[0] + 1))
    if len(compressed) != metadata[1]:
        raise ValueError('combined compressed length mismatch')
    raw = zlib.decompress(compressed)
    if len(raw) != metadata[2] or sha(raw) != metadata[3]:
        raise ValueError('restored file length/SHA256 mismatch')
    write_new(destination, raw)
    print('RESTORED {} bytes={} sha256={}'.format(destination, len(raw), sha(raw)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command')
    info_parser = commands.add_parser('info')
    info_parser.add_argument('file', type=Path)
    emit_parser = commands.add_parser('emit')
    emit_parser.add_argument('file', type=Path)
    emit_parser.add_argument('--page', type=int, required=True)
    decode_parser = commands.add_parser('decode')
    decode_parser.add_argument('screenshot', type=Path)
    decode_parser.add_argument('--out', type=Path, required=True)
    combine_parser = commands.add_parser('combine')
    combine_parser.add_argument('pages', type=Path, nargs='+')
    combine_parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'info':
        raw, compressed, total = content(args.file)
        print('XU_SCREEN raw={} compressed={} pages={} chunk={} sha256={}'.format(len(raw), len(compressed), total, CHUNK, sha(raw)))
    elif args.command == 'emit':
        emit(args.file, args.page)
    elif args.command == 'decode':
        result = decode_image(args.screenshot)
        write_new(args.out, (json.dumps(result, indent=2, sort_keys=True) + '\n').encode('ascii'))
        print('PAGE {}/{} crc32={} geometry={} -> {}'.format(result['page'], result['total'], result['crc32'], result['geometry'], args.out))
    elif args.command == 'combine':
        combine(args.pages, args.out)
    else:
        parser.error('choose info, emit, decode or combine')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, struct.error, zlib.error) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        sys.exit(1)
