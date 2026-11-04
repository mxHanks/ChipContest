#!/usr/bin/env python3
"""Check archived actual115 and local117 records without a remote or EDA run."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import re
import sys

sys.dont_write_bytecode = True
B = Path(__file__).resolve().parent


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name):
    return json.loads((B / name).read_text())


manifest = load('manifest.json')
rows = manifest['files']
names = {row['path'] for row in rows}
need(len(names) == len(rows), 'duplicate archive identity')
actual = {str(p.relative_to(B)) for p in B.rglob('*')
          if p.is_file() and p.name != 'manifest.json'}
need(actual == names, 'archive membership changed')
for row in rows:
    p = B / row['path']
    need(p.stat().st_size == row['bytes'] and sha(p) == row['sha256'],
         'archived raw bytes changed: ' + row['path'])
need(manifest['qualification'] == 'NOT_QUALIFIED'
     and manifest['actual115_included'] is True
     and manifest['actual117_included'] is False, 'archive scope changed')

spec = importlib.util.spec_from_file_location('xu_archived115', B / 'tools/xu_audit_mapped111_failure115.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
original = load('original111/state.json')
log = (B / 'original111/simulation.log').read_text()
tb = (B / 'original111/tb_xu_mapped_task00111.sv').read_text()
for name, digest in audit.EXPECTED.items():
    need(sha(B / 'original111' / name) == digest, 'original111 frozen body changed')
report = audit.parse_failure(log, tb, original)
actual_report = load('actual115/mapped-task00-readonly-audit-20261105-115/failure-review.json')
need(report == actual_report, 'actual115 report differs from independently replayed original111')
need(actual_report == load('local-audit115-v1/actual114-failure-review.json'),
     'local preflight and actual115 classify different failures')

state = load('actual115/mapped-task00-readonly-audit-20261105-115/state.json')
need(state['status'] == audit.STATUS and state['qualification'] == 'NOT_QUALIFIED'
     and not state['public_task_complete'] and state['private_gate_pending_count'] == 60,
     'actual115 scope was promoted')
need(state['inputs_equal_before_after'] and not state['identity_errors'],
     'actual115 did not record stable input identities')
need(len(state['source_inputs_before']) == 8
     and len(state['current_frozen_inputs_before']) == 628
     and state['current_frozen_inputs_before'] == original['inputs_before'],
     'actual115 omitted or changed original628 input records')
need(state['source_inputs_before'] + state['current_frozen_inputs_before']
     == state['current_and_source_inputs_after'], 'actual115 before/after records differ')
need(state['runtime_trees_before'] == original['runtime_trees']
     and len(state['runtime_trees_before']) == 1
     and len(state['runtime_trees_before'][0]['files']) == 56,
     'original56 runtime tree membership evidence differs')
for row in state['source_inputs_before']:
    p = B / 'original111' / Path(row['path']).name
    need(p.stat().st_size == row['bytes'] and sha(p) == row['sha256'],
         'actual115 source receipt differs from local original body')
p = B / 'actual115/mapped-task00-readonly-audit-20261105-115/failure-review.json'
need(state['report']['sha256'] == sha(p) and state['report']['bytes'] == p.stat().st_size,
     'actual115 raw report identity differs')
export = {r['path']: r for r in load('source-export119-manifest.json')}
for p in (B / 'actual115').rglob('*'):
    if p.is_file():
        name = str(p.relative_to(B / 'actual115'))
        need(export[name]['sha256'] == sha(p) and export[name]['bytes'] == p.stat().st_size,
             'selected actual115 body differs from original119 export')
launch = load('actual115/mapped-task00-audit-launch-20261105-115/state.json')
need(launch['status'] == audit.STATUS and launch['audit_status'] == audit.STATUS
     and launch['child_returncode'] == 0 and launch['helpers_equal']
     and launch['helpers_before'] == launch['helpers_after'],
     'actual115 launcher did not finish with stable helper identities')
for path, digest in launch['helpers_before'].items():
    need(sha(B / 'tools' / Path(path).name) == digest, 'actual115 deployed helper differs')
need((B / 'actual115/mapped-task00-audit-launch-20261105-115/driver.log').read_text()
     == audit.STATUS + '\nXU_AUDIT115_TERMINAL ' + audit.STATUS + '\n',
     'actual115 terminal native stdout differs')

# Replay the already recorded21 semantic/identity negatives; no EDA process runs.
mutations = [
    ('wrong-fatal-file', lambda t: t.replace('/tb_xu_mapped_task00111.sv", 216:', '/other.sv", 216:')),
    ('wrong-fatal-line', lambda t: t.replace('.sv", 216:', '.sv", 215:')),
    ('wrong-finish-line', lambda t: t.replace('.sv", line 216.', '.sv", line 217.')),
    ('wrong-fatal-scope', lambda t: t.replace(': tb_xu_soc_ppa.public_scoreboard: at time', ': tb_xu_soc_ppa.other: at time')),
    ('wrong-native-fatal-tick', lambda t: t.replace('at time 9359423333333 fs', 'at time 9359423333334 fs')),
    ('wrong-native-finish-tick', lambda t: t.replace('$finish at simulation time        9359423333333', '$finish at simulation time        9359423333334')),
    ('wrong-native-message', lambda t: t.replace(audit.FAILURE, 'XU_MAPPED111_PROTOCOL_REJECT different')),
    ('invented-source-request', lambda t: t + '\nXU_MAPPED111_SOURCE_REQUEST forged\n'),
    ('invented-final-retire', lambda t: t + '\nXU_MAPPED111_FINAL_Y_RETIRE forged\n'),
    ('invented-public-complete', lambda t: t + '\nXU_MAPPED111_PUBLIC_DIAGNOSTIC_COMPLETE forged\n'),
    ('invented-private-pending', lambda t: t + '\nXU_MAPPED111_REQUIRED_GATE_PENDING forged\n'),
    ('invented-full-pass', lambda t: t + '\nSOC_PASS tasks=1\n'),
    ('missing-native-fatal', lambda t: re.sub(r'^Fatal:[^\n]*\n', '', t, flags=re.M)),
    ('extra-native-fatal', lambda t: t + '\nFatal: invented\n'),
    ('missing-recent-hold', lambda t: re.sub(r'^"[^\n]*u_sirv_mem_fab[^\n]*\n[^\n]*\n', '', t, flags=re.M)),
    ('geometry-row-count', lambda t: t.replace('rows=256 row_bits=64 unique=256', 'rows=255 row_bits=64 unique=256', 1)),
    ('earlier-native-error', lambda t: 'Error-[TEST] invented\n' + t),
]
rejections = []


def reject(name, altered_log, own):
    try:
        audit.parse_failure(altered_log, tb, own)
    except ValueError as exc:
        rejections.append(dict(name=name, rejection=str(exc)))
    else:
        raise ValueError('mutant accepted: ' + name)


for name, change in mutations:
    altered = change(log)
    need(altered != log, 'mutant did not alter input: ' + name)
    own = copy.deepcopy(original)
    own['steps'][-1]['log']['sha256'] = hashlib.sha256(altered.encode()).hexdigest()
    reject(name, altered, own)
for name, change in [
    ('wrong-raw-step-hash', lambda s: s['steps'][-1]['log'].__setitem__('sha256', '0' * 64)),
    ('original-failure-promoted', lambda s: s.__setitem__('status', 'PASS')),
    ('missing-input-record', lambda s: s['inputs_before'].pop()),
    ('input-change-hidden', lambda s: s.__setitem__('inputs_equal_before_after', False)),
]:
    own = copy.deepcopy(original)
    change(own)
    reject(name, log, own)
local = load('local-audit115-v1/check-results.json')
need(rejections == local['negative'] and len(rejections) == 21,
     'existing21 negative results differ from replay')
need(local['positive']['status'] == audit.STATUS
     and local['positive']['raw_log_sha256'] == sha(B / 'original111/simulation.log')
     and local['positive']['native_returncode'] == 0
     and local['positive']['public_complete'] is False, 'local positive scope differs')

callbacks = load('local-callback117-v1/results.json')
need(callbacks['scope'] == 'ICARUS_PASSIVE_CALLBACK_MECHANISM_ONLY_NOT_VENDOR_OR_MAPPED_VCS'
     and callbacks['source_sha256'] == sha(B / 'tools/xu_mapped_causal117.c'),
     'local117 source or scope changed')
need([r['name'] for r in callbacks['commands']]
     == ['cc', 'reference-compile', 'reference-run', 'missing-target-compile', 'missing-target-run'],
     'local117 mechanism command records missing')
for row in callbacks['commands']:
    need(row['returncode'] == 0 and row['log_sha256']
         == sha(B / 'local-callback117-v1' / (row['name'] + '.log')),
         'local117 original command/log record differs')
trace = (B / 'local-callback117-v1/reference-run.log').read_text()
negative = (B / 'local-callback117-v1/missing-target-run.log').read_text()
need(re.search(r'XU_CAUSAL117_READY target_cells=1 fifo_modules=1 shared_modules=1 accel_modules=1 observed_nodes=\d+ failed=0 ', trace),
     'local117 synthetic positive binding missing')
for pattern in [r'XU_CAUSAL117_EVENT .*bval=0000000000000001 name=.*\.Q$',
                r'XU_CAUSAL117_EVENT .*aval=0000000000000001 bval=0000000000000000 name=.*\.notifier$',
                r'XU_CAUSAL117_EVENT .*bval=0000000000000001 name=.*\.cmd_ready$']:
    need(re.search(pattern, trace, re.M), 'local117 native callback four-state record missing')
need(re.search(r'XU_CAUSAL117_READY target_cells=0 fifo_modules=1 shared_modules=1 accel_modules=1 observed_nodes=\d+ failed=1 ', negative),
     'local117 missing-target rejection absent')
source = (B / 'tools/xu_mapped_causal117.c').read_text()
need(not re.search(r'\b(?:vpi_put_value|vpiForceFlag|vpi_control)\b', source),
     'archived117 VPI source writes or controls simulation')
inventory = load('tools/reference-candidates115.json')
need(len(inventory['references']) == 72 and sum(inventory['counts'].values()) == 72
     and inventory['counts']['already111_public_port'] == 12
     and inventory['counts']['mapped_private_state_or_equivalent_endpoint_needed'] == 17,
     'original72 reference/private60 source-only inventory differs')
need(all(r['mapped_runtime_status'] == 'NOT_INSPECTED_IN_THIS_SOURCE_ONLY_REVIEW'
         for r in inventory['references']), 'source candidate was promoted to runtime evidence')
print('PASS actual115 raw failure and636 identity records; original111 native failure;21 replayed negatives; local117 callback records only;60 gates pending; NOT QUALIFIED')
