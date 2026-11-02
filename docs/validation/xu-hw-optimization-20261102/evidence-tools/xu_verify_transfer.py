#!/usr/bin/env python3
"""Re-decode retained visible frames and verify their payload against delivered files."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import xu_screen_transfer as transfer


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    root = args.report.resolve()
    transfers = {'ppa-paired-exact-frames': 'ppa/paired-exact-summary.json',
                 'hw-results-01-frames': 'artifacts/hw-results-01.tar.xz',
                 'hw-receipt-01-frames': 'observed-receipt.json',
                 'hw-wrapper-originals-01-frames': 'artifacts/hw-wrapper-originals-01.tar.xz'}
    # Additional own-report transfers can be added without including installed
    # vendor manuals or library payloads in this delivery.
    mapping = root / 'transfer/additional-transfers.json'
    if mapping.is_file():
        transfers.update(json.loads(mapping.read_text()))
    results = []
    with tempfile.TemporaryDirectory(prefix='xu-visible-frame-audit-') as temporary:
        for folder, filename in transfers.items():
            pages = sorted((root / 'transfer' / folder).glob('page-*.json'))
            checked = []
            for path in pages:
                record = json.loads(path.read_text())
                screenshot = root / 'transfer/screens' / Path(record['source_screenshot']).name
                actual = transfer.decode_image(screenshot)
                # The original JSON retains the source machine's absolute path.
                actual['source_screenshot'] = record['source_screenshot']
                if actual != record or sha(screenshot) != record['screenshot_sha256']:
                    raise ValueError('frame/image integrity mismatch: ' + str(path))
                checked.append(dict(page=record['page'], crc32=record['crc32'],
                                    screenshot=str(screenshot.relative_to(root)), sha256=sha(screenshot)))
            restored = Path(temporary) / folder
            transfer.combine(pages, restored)
            if sha(restored) != sha(root / filename) or restored.read_bytes() != (root / filename).read_bytes():
                raise ValueError('restored visible payload differs from delivered file: ' + filename)
            results.append(dict(file=filename, sha256=sha(restored), pages=checked))
    result = dict(status='PASS', scope='independent image decode, per-page CRC and complete restored bytes/SHA256', transfers=results)
    with args.out.open('x') as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print('PASS: {} complete files from {} visible frames'.format(len(results), sum(len(row['pages']) for row in results)))


if __name__ == '__main__':
    main()
