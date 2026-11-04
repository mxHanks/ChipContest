#!/usr/bin/env python3
"""Verify actual107 bytes and limited native conclusions; never grants timing/energy."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

ROOT = Path(__file__).resolve().parent
SHA = 'b21734f9957a35feeb847b8a5d2a03c1934c2f3ff7e5270001822e9630faeb58'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--extract', type=Path)
    args = ap.parse_args()
    raw = (ROOT / 'payload.tar.xz').read_bytes()
    assert len(raw) == 49904 and hashlib.sha256(raw).hexdigest() == SHA
    data = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:xz') as tar:
        manifest_raw = tar.extractfile('manifest.json').read()
        assert manifest_raw == (ROOT / 'payload-manifest.json').read_bytes()
        rows = json.loads(manifest_raw)
        assert len(rows) == 13 and sum(x['bytes'] for x in rows) == 1066360
        assert set(tar.getnames()) == {x['path'] for x in rows} | {'manifest.json'}
        for x in rows:
            rel = Path(x['path'])
            assert not rel.is_absolute() and '..' not in rel.parts
            member = tar.getmember(x['path'])
            assert member.isfile()
            body = tar.extractfile(member).read()
            assert len(body) == x['bytes']
            assert hashlib.sha256(body).hexdigest() == x['sha256']
            data[x['path']] = body
    pre = 's2e-ppa-campaign-20261104-89/'
    fm = json.loads(data[pre + 'formality/state.json'])
    campaign = json.loads(data[pre + 'state.json'])
    log = data[pre + 'formality/fm.log'].decode()
    assert fm['status'] == 'FAIL' and fm['returncode'] == 0
    assert fm['frozen_before'] == fm['frozen_after'] and len(fm['frozen_before']) == 159
    assert campaign['status'] == 'EXECUTED_FORMALITY_FAILED_NOT_QUALIFIED'
    assert campaign['inputs_before'] == campaign['inputs_after']
    assert campaign['source_before'] == campaign['source_after']
    assert len(campaign['inputs_before']) == 15
    marker = 'XU_S2E_FULL_SOC_FORMALITY_PASS'
    assert log.splitlines().count(marker) == 1
    assert re.findall(r'^XU_S2E_FULL_SOC_FORMALITY_PASS\s*$', log, re.M) == [marker + '\n']
    assert re.findall(r'^Verification SUCCEEDED[ \t]*$', log, re.M) == ['Verification SUCCEEDED']
    assert re.findall(r'^\s*(\d+) Passing compare points[ \t]*$', log, re.M) == ['42338']
    assert not re.search(r'^\s*(?:Error:|Fatal:|XU_S2E_FULL_SOC_FORMALITY_(?:FAIL|SCRIPT_ERROR))', log, re.M)
    assert hashlib.sha256(data[pre + 'formality/fm.log']).hexdigest() == fm['log']['sha256']
    area = data[pre + 'ppa/area.rpt'].decode()
    assert re.search(r'u_accel_icb_slave\n\s+295000\.3804\s+8\.8\s+', area)
    assert 'Total cell area:               3365957.200429' in area
    pins = json.loads(data['s2c-native-pin-stream-20261104-93/state.json'])
    assert pins['status'] == 'EXTRACTED_24_ORIGINAL_REPORTS_NOT_QUALIFIED'
    assert len(pins['tasks']) == 12 and pins['native_pin_blocks'] == 540288
    assert pins['original_reports_streamed'] == 24
    if args.extract:
        args.extract.mkdir(parents=True, exist_ok=False)
        for name, body in data.items():
            dest = args.extract / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(body)
        (args.extract / 'manifest.json').write_bytes(manifest_raw)
    print('PASS: actual107 13 raw files; native FM succeeded, original driver false negative preserved; no timing/energy qualification')


if __name__ == '__main__':
    main()
