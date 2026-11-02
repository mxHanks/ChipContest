#!/usr/bin/env python3
"""Package exact existing xu result JSON and selected raw logs after full acceptance."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile

campaign = Path(sys.argv[1]).resolve()
destination = Path(sys.argv[2])
state = json.loads((campaign / 'experiments.json').read_text())
acceptance = json.loads((campaign / 'acceptance/acceptance.json').read_text())
if state.get('status') != 'PASS' or state.get('acceptance', {}).get('status') != 'PASS' or acceptance.get('status') != 'PASS':
    raise ValueError('complete campaign acceptance must pass before packaging')
files = {campaign / 'experiments.json', campaign / 'acceptance/acceptance.json', campaign / 'acceptance/xu-performance.json'}
files.update(campaign.glob('*/result.json'))
files.update((campaign / 'acceptance').glob('*/result.json'))
files.update(campaign / 'acceptance' / name for name in ['host.log', 'numeric.log'])
manifest = {}
for path in sorted(files):
    data = path.read_bytes()
    manifest[str(path.relative_to(campaign))] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
with tarfile.open(str(destination), 'x:xz', preset=9) as archive:
    for path in sorted(files):
        data = path.read_bytes()
        info = tarfile.TarInfo(str(path.relative_to(campaign)))
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    data = (json.dumps(dict(schema='xu-exact-result-file-bundle-v1',
        evidence_kind='original result JSON and raw log byte copies; manifest is derived',
        campaign=str(campaign), files=manifest), indent=2, sort_keys=True) + '\n').encode('ascii')
    info = tarfile.TarInfo('xu-transfer-manifest.json')
    info.size = len(data)
    archive.addfile(info, io.BytesIO(data))
    simulation_lines = {}
    for path in sorted(list(campaign.glob('*/simulation.log')) + list((campaign / 'acceptance').glob('*/simulation.log'))):
        raw = path.read_bytes()
        simulation_lines[str(path.relative_to(campaign))] = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
            selected_exact_lines=[line for line in raw.decode('utf-8', errors='replace').splitlines()
                                  if line.startswith(('TASK_PASS ', 'PERF_TASK ', 'SOC_PASS '))])
    data = (json.dumps(dict(schema='xu-simulation-pass-lines-derived-v1',
        evidence_kind='selected exact TASK_PASS/PERF_TASK/SOC_PASS lines; NOT original complete simulation logs',
        logs=simulation_lines), indent=2, sort_keys=True) + '\n').encode('ascii')
    info = tarfile.TarInfo('xu-simulation-pass-lines-derived.json')
    info.size = len(data)
    archive.addfile(info, io.BytesIO(data))
    # Keep exact informative lines and original full-log identities when enormous
    # simulator build logs are impractical to transfer by visible screen frames.
    selected_logs = {}
    for path in sorted((campaign / 'acceptance').glob('*.log')):
        raw = path.read_bytes()
        lines = raw.decode('utf-8', errors='replace').splitlines()
        selected_logs[str(path.relative_to(campaign))] = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
            selected_exact_lines=[line for line in lines if ('PASS' in line or 'Ran ' in line or line == 'OK' or 'FAILED' in line)])
    data = (json.dumps(dict(schema='xu-selected-log-lines-derived-v1',
        evidence_kind='selected exact lines from full logs; NOT original complete logs',
        logs=selected_logs), indent=2, sort_keys=True) + '\n').encode('ascii')
    info = tarfile.TarInfo('xu-selected-validation-log-lines.json')
    info.size = len(data)
    archive.addfile(info, io.BytesIO(data))
print('PACKAGE {} files={} bytes={} sha256={}'.format(destination, len(files), destination.stat().st_size,
    hashlib.sha256(destination.read_bytes()).hexdigest()))
