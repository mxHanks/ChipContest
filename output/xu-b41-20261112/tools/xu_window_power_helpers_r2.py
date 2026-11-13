"""Auditable continuation helpers; original gate/power evidence stays intact."""
from pathlib import Path
from decimal import Decimal
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time

R = Path(__file__).resolve().parent
FAILURE_SHA = 'bd765e8f210b9faf07e9e6e92ada22d31f81ce133b6b0d97eebf9d55940eb479'
PHYSICAL_SHA = '2d5adc613980dc21dc1f0aaa398045252911a5c67594349630ff35d78688a220'
REVIEW_CODE_SHA = 'acb23e938adab68ebb194abe5fba9884456bd6ab6248e0cd3e2e327d65914a13'
SDC_SHA = '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'
PT_PATH = Path('/eda/synopsys/prime/prime_2022.03-SP5-1/bin/pt_shell')
PT_SHA = 'afdcfa7071f86d229ed3b4481f67adefd1c51bb0288b7e7d370213a43b70c9ef'
OUTPUTS = ('power.rpt', 'hierarchy-power.rpt', 'switching.rpt',
           'check-power.rpt', 'units.rpt', 'power-attributes.tsv')
EXTRA_OUTPUTS = ('macro-power.tsv', 'macro-switching.rpt', 'activity-not-annotated.rpt',
                 'activity-default.rpt', 'pin-attribute-inventory.rpt', 'activity-inventory.tsv')


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(8 * 1024**2), b''):
            h.update(b)
    return h.hexdigest()


def guard_original_terminal():
    assert str(R) == '/tmp/xu-b41-close-20261111-r1'
    assert not Path('/proc/299096').exists() and not Path('/proc/316319').exists()
    p = R / 'xu-power-20261112-r1/tight-O2-ss/receipt.json'
    assert sha(p) == FAILURE_SHA
    receipt = json.loads(p.read_text())
    assert receipt['native_exit'] == 124 and receipt['complete'] is False
    assert sha(R / 'pt-clock-root-r1/constraints-pt-add.sdc') == SDC_SHA
    assert sha(PT_PATH) == PT_SHA
    assert sha(R / 'xu-closure-20261112-r4/dc/mapped.v') == PHYSICAL_SHA


def heavy_jobs():
    result = []
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if p.stat().st_uid != os.getuid():
                continue
            name = (p / 'comm').read_text().strip()
            if name.startswith(('simv', 'pt_shell', 'dc_shell', 'fm_shell', 'vcs')):
                result.append((p.name, name))
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    return result


def active_extract(variant):
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if p.stat().st_uid != os.getuid():
                continue
            args = (p / 'cmdline').read_bytes().split(b'\0')
            if (variant.encode() in args and b'--launch' in args and
                    any(Path(a.decode(errors='replace')).name == 'prepare_window_vcd_r2.py'
                        for a in args if a)):
                return True
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    return False


def prepare(variant, entry, out):
    guard_original_terminal()
    gate = R / 'xu-gate-20261112-r1'
    binding_path = gate / (variant + '-full12-r15') / 'verified-binding.json'
    binding_sha = sha(binding_path)
    binding = json.loads(binding_path.read_text())
    assert (binding['tasks'], binding['warmup'], binding['physical_clears']) == (12, 1, 13)
    assert binding['pins']['physical'] == PHYSICAL_SHA == entry['netlist_sha256']
    assert binding['native_log_sha256'] == entry['gate_log_sha256'] == sha(entry['gate_log'])
    pin_paths = {
        'physical': R / 'xu-closure-20261112-r4/dc/mapped.v',
        'functional': R / 'xu-gate-reset-20261112-r2/mapped-functional-reset-r2.v',
        'binary': R / 'xu-gate-reset-20261112-r1/simv-row-r1',
        'testbench': R / 'xu-gate-reset-20261112-r1/tb_dma64_soc_mapped_r2.sv',
        'cpu_checkers': gate / 'cpu-checkers.svh'}
    assert {k: sha(p) for k, p in pin_paths.items()} == binding['pins']
    review_path = R / 'xu-gate-independent-20261113-r2' / (variant + '.json')
    if not review_path.exists():
        reviewer = R / 'xu-review-gate-full12-r2.py'
        assert sha(reviewer) == REVIEW_CODE_SHA
        subprocess.check_call([sys.executable, '-B', str(reviewer), variant])
    review = json.loads(review_path.read_text())
    assert review['status'] == 'PASS_INDEPENDENT_GATE_FULL12_REVIEW'
    assert review['binding_sha256'] == binding_sha and review['pins'] == binding['pins']
    image = R / 'xu-gate-inputs-20261112-r1/firmware' / variant / 'dma64_soc.verilog'
    assert sha(image) == binding['firmware_image_sha256'] == review['firmware_image_sha256']
    receipt_path = R / 'xu-windowed-vcd-20261113-r1' / variant / 'receipt.json'
    while active_extract(variant):
        print('WAIT_ACTIVE_WINDOW_EXTRACT', variant, flush=True)
        time.sleep(15)
    if not receipt_path.exists():
        parent = receipt_path.parent
        assert not parent.exists(), 'Partial extraction exists; review its actual failure before continuing'
        subprocess.check_call([sys.executable, '-B', str(R / 'prepare_window_vcd_r2.py'),
                               variant, '--launch', '--windows-manifest', str(out / 'windows.json')])
    receipt = json.loads(receipt_path.read_text())
    assert receipt['status'] == 'WINDOW_VCD_EXTRACT_COMPLETE_NOT_POWER_ACCEPTED'
    assert receipt['binding_sha256'] == binding_sha
    assert receipt['source_sha256'] == binding['vcd_sha256']
    assert receipt['native_log_sha256'] == entry['gate_log_sha256']
    assert receipt['time_intervals_ns'] == entry['time_intervals_ns']
    assert receipt['source_bytes'] == binding['vcd_bytes'] == Path(entry['vcd']).stat().st_size
    activity = Path(receipt['output'])
    assert activity.parent == receipt_path.parent and activity.name == 'activity.vcd'
    assert activity.stat().st_size == receipt['output_bytes']
    assert sha(activity) == receipt['output_sha256']
    entry.update(vcd_sha256=binding['vcd_sha256'], activity_vcd=str(activity),
                 activity_vcd_sha256=receipt['output_sha256'],
                 window_slice_receipt_sha256=sha(receipt_path),
                 gate_binding_sha256=binding_sha, gate_independent_review_sha256=sha(review_path),
                 original_power_failure_receipt_sha256=FAILURE_SHA)
    return activity


def additional_reports():
    return r'''
redirect -file pin-attribute-inventory.rpt {list_attributes -application -class pin}
set z [open macro-power.tsv w]
puts $z "instance\tinternal_power\tswitching_power\tleakage_power\ttotal_power"
set macros [get_cells -hierarchical -filter {ref_name == RAMSP1024X16}]
if {[sizeof_collection $macros] != 337} {error {SRAM inventory changed}}
foreach_in_collection c $macros {
  puts $z "[get_object_name $c]\t[get_attribute $c internal_power]\t[get_attribute $c switching_power]\t[get_attribute $c leakage_power]\t[get_attribute $c total_power]"
}
close $z
redirect -file activity-not-annotated.rpt {report_switching_activity -list_not_annotated}
redirect -file activity-default.rpt {report_switching_activity -list_by_source default}
redirect -file macro-switching.rpt {report_switching_activity -cells $macros -show_pin}
set z [open activity-inventory.tsv w]
puts $z "leaf_cells\t[sizeof_collection [get_cells -hierarchical -filter {is_hierarchical == false}]]"
puts $z "nets\t[sizeof_collection [get_nets -hierarchical]]"
puts $z "sram_macros\t[sizeof_collection $macros]"
close $z
'''


def payload_case(variant, entry, body, out, f, heavy):
    # Called while the outer controller holds the original eda.lock.
    intervals = []
    total = Decimal(0)
    for task in entry['tasks']:
        a, b = task['windows_ns'][2:4]
        assert Decimal(a) < Decimal(b)
        intervals.extend([a, b])
        total += Decimal(b) - Decimal(a)
    assert len(intervals) == 24
    needle = '-time {' + ' '.join(entry['time_intervals_ns']) + '}'
    assert body.count(needle) == 1
    payload_body = body.replace(needle, '-time {' + ' '.join(intervals) + '}')
    run = f.execute(out, variant + '-payload-ss', f.PT, payload_body, heavy, 2400)
    receipt = json.loads((run / 'receipt.json').read_text())
    assert receipt['complete'] and receipt['native_exit'] == 0
    return {'scope': '12_payload_intervals_without_clear_or_gap',
            'native_run': str(run), 'time_intervals_ns': intervals,
            'total_payload_ns': str(total), 'native_receipt_sha256': sha(run / 'receipt.json'),
            'output_sha256': {name: sha(run / name) for name in OUTPUTS},
            'coverage_output_sha256': {name: sha(run / name) for name in EXTRA_OUTPUTS}}


def publish(entry, out):
    """Publish genuine native completion with its continuation provenance."""
    guard_original_terminal()
    run = Path(entry['native_run'])
    receipt = json.loads((run / 'receipt.json').read_text())
    assert receipt['complete'] and receipt['native_exit'] == 0
    assert receipt['script'] == sha(run / 'run.tcl') and receipt['log'] == sha(run / 'native.log')
    assert entry['output_sha256'] == {name: sha(run / name) for name in OUTPUTS}
    assert entry['payload']['native_receipt_sha256'] == sha(Path(entry['payload']['native_run']) / 'receipt.json')
    payload_run = Path(entry['payload']['native_run'])
    payload_receipt = json.loads((payload_run / 'receipt.json').read_text())
    assert payload_receipt['complete'] and payload_receipt['native_exit'] == 0
    assert payload_receipt['script'] == sha(payload_run / 'run.tcl')
    assert payload_receipt['log'] == sha(payload_run / 'native.log')
    assert entry['payload']['output_sha256'] == {name: sha(payload_run / name) for name in OUTPUTS}
    entry.update(native_receipt_sha256=sha(run / 'receipt.json'),
                 continuation_helper_sha256=sha(Path(__file__)),
                 coverage_output_sha256={name: sha(run / name) for name in EXTRA_OUTPUTS},
                 status='NATIVE_PRINCIPAL_AND_PAYLOAD_COMPLETE_REVIEW_COVERAGE_AND_UNITS')
    manifest = R / 'xu-power-20261112-r1/windows.json'
    before = manifest.read_text()
    rows = json.loads(before)
    found = [x for x in rows if x['variant'] == entry['variant']]
    assert len(found) <= 1
    if found:
        old = found[0]
        assert not old.get('output_sha256'), 'Existing completed result must not be overwritten'
        for k in ('gate_log_sha256', 'netlist_sha256', 'vcd', 'vcd_bytes', 'time_intervals_ns'):
            assert old[k] == entry[k], (k, old[k], entry[k])
        rows[rows.index(old)] = entry
    else:
        rows.append(entry)
    backup = out / ('original-windows-before-' + entry['variant'] + '.json')
    with backup.open('x') as f:
        f.write(before)
    fd, temporary = tempfile.mkstemp(prefix='.resume-windows-', dir=str(manifest.parent))
    with os.fdopen(fd, 'w') as f:
        json.dump(rows, f, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, str(manifest))
    print('PUBLISHED_NATIVE_CONTINUATION', entry['variant'], str(run), flush=True)
