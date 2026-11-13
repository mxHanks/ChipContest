"""Required payload-only power continuation. Native raw evidence is preserved."""
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
import fcntl
import hashlib
import json
import os
import re
import resource
import subprocess
import sys
import time

R = Path('/tmp/xu-b41-close-20261111-r1')
P = R / 'xu-vcd2saif-preflight-20261113-r1'
CONVERTER = Path('/eda/synopsys/prime/prime_2022.03-SP5-1/bin/vcd2saif')
QUEUE = R / 'xu-power-payload-r3-queue.json'
GATE_SHA = 'c44f7a62da04ce9dbb4b52fec6023c1e4d9d265cd59fe479bffb0b0f4e28ee0a'
REVIEW_SHA = 'acb23e938adab68ebb194abe5fba9884456bd6ab6248e0cd3e2e327d65914a13'
PHYSICAL_SHA = '2d5adc613980dc21dc1f0aaa398045252911a5c67594349630ff35d78688a220'
SDC_SHA = '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'
PT_SHA = 'afdcfa7071f86d229ed3b4481f67adefd1c51bb0288b7e7d370213a43b70c9ef'
VARIANTS = ['tight-O2', 'phased_64_fast4-O2', 'backoff_8_256_fast4-O2']
IMPORT_METHOD = None
OUTPUTS = ['power.rpt', 'hierarchy-power.rpt', 'switching.rpt', 'check-power.rpt',
           'units.rpt', 'power-attributes.tsv', 'macro-power.tsv', 'macro-switching.rpt',
           'activity-not-annotated.rpt', 'activity-default.rpt', 'activity-inventory.tsv']


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024**2), b''):
            h.update(chunk)
    return h.hexdigest()


def write_new(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, indent=2)


def launch(script, root):
    assert root == R and not QUEUE.exists()
    assert sha(R/'xu-run-gate-reset-r16.py') == GATE_SHA
    proc = Path('/proc/156004')
    assert b'xu-run-gate-reset-r16.py' in (proc/'cmdline').read_bytes()
    data = {'gate_pid':156004, 'gate_start':(proc/'stat').read_text().split()[21],
            'controller':str(script), 'controller_sha256':sha(script),
            'helper_sha256':sha(Path(__file__)), 'converter_sha256':sha(CONVERTER),
            'policy':'Wait for full R16 campaign. Measure only 12 scoring payload intervals. Single EDA lock.'}
    write_new(QUEUE, data)
    with (R/'xu-b41-power-payload-r3.log').open('x') as log:
        p = subprocess.Popen([sys.executable,'-B',str(script)],cwd=str(R),
                             stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    write_new(R/'xu-power-payload-r3-controller.json', {'pid':p.pid,'queue_sha256':sha(QUEUE)})
    print('PAYLOAD_POWER_QUEUED',p.pid,'AFTER_GATE',156004,flush=True)


def heavy_jobs():
    rows = subprocess.check_output(['ps','-u',str(os.getuid()),'-o','pid,comm','--no-headers'],
                                   universal_newlines=True).splitlines()
    return [r for r in rows if len(r.split())>1 and r.split()[1].startswith(
        ('simv','fm_shell','pt_shell','dc_shell','common_shell','vcsi','vcselab','vcd2saif'))]


def wait_campaign():
    q = json.loads(QUEUE.read_text())
    assert sha(Path(q['controller'])) == q['controller_sha256']
    assert sha(Path(__file__)) == q['helper_sha256']
    assert sha(CONVERTER) == q['converter_sha256']
    proc = Path('/proc/'+str(q['gate_pid']))
    while True:
        try:
            active = (proc/'stat').read_text().split()[21] == q['gate_start']
        except FileNotFoundError:
            active = False
        if not active:
            break
        print('WAIT_GATE_R16_NATURAL_COMPLETION',time.strftime('%F %T'),flush=True)
        time.sleep(15)
    assert 'GATE_REMAINING_TWO_FULL12_PASS' in (R/'xu-run-gate-reset-r16.log').read_text()
    assert all((R/'xu-gate-20261112-r1'/(v+'-full12-r15')/'verified-binding.json').is_file() for v in VARIANTS)
    assert sha(R/'pt-clock-root-r1/constraints-pt-add.sdc') == SDC_SHA
    assert sha(Path('/eda/synopsys/prime/prime_2022.03-SP5-1/bin/pt_shell')) == PT_SHA
    print('GATE_CAMPAIGN_COMPLETE_POWER_READY',flush=True)


def checked_native(out, name, tool, body, f, seconds):
    assert not heavy_jobs(), heavy_jobs()
    run = f.execute(out,name,tool,body,heavy_jobs,seconds)
    receipt = json.loads((run/'receipt.json').read_text())
    assert receipt['native_exit']==0 and receipt['complete']
    assert receipt['script']==sha(run/'run.tcl') and receipt['log']==sha(run/'native.log')
    return run


def import_method(out, libs, f):
    """One necessary check of native SAIF versus native VCD boundary semantics."""
    global IMPORT_METHOD
    if IMPORT_METHOD is not None:
        return IMPORT_METHOD
    assert re.search(r'\(DURATION\s+2400\)',(P/'boundary.saif').read_text())
    prefix = ('set_app_var power_enable_analysis true\n'
              'set_app_var power_analysis_mode averaged\n'
              'set link_path [list * '+' '.join('{'+str(p)+'}' for p in libs)+']\n'
              'read_verilog {'+str(P/'tiny-r2.v')+'}\ncurrent_design tiny\nlink_design tiny\n')
    tail = r'''
set z [open activity-attributes.tsv w]
foreach a {toggle_rate static_probability x_probability} {
 puts $z "$a\t[get_attribute [get_nets probe] $a]"
}
close $z
'''
    commands = {'direct':'read_vcd -strip_path tb_dma64_soc/dut -time {0.0004 0.0016 0.0024 0.0036} {'+str(P/'probe.vcd')+'}\n',
                'saif':'read_saif -strip_path tb_dma64_soc/dut {'+str(P/'boundary.saif')+'}\n'}
    result = {}
    for name, command in commands.items():
        run = checked_native(out,'import-boundary-'+name,f.PT,prefix+command+tail,f,180)
        attrs = dict(line.split('\t') for line in (run/'activity-attributes.tsv').read_text().splitlines())
        result[name] = {'attributes':attrs,'receipt_sha256':sha(run/'receipt.json'),
                        'attributes_sha256':sha(run/'activity-attributes.tsv')}
    compatible = all(abs(Decimal(result['direct']['attributes'][a])-Decimal(result['saif']['attributes'][a]))
                     <= max(Decimal('1e-9'),abs(Decimal(result['direct']['attributes'][a]))*Decimal('1e-6'))
                     for a in ['toggle_rate','static_probability','x_probability'])
    IMPORT_METHOD = 'vendor_saif' if compatible else 'direct_vcd'
    result.update(selected_method=IMPORT_METHOD,converter_sha256=sha(CONVERTER),
                  fixture_sha256={p.name:sha(p) for p in [P/'probe.vcd',P/'boundary.saif',P/'tiny-r2.v']},
                  policy='Native mismatch selects direct VCD. No manual correction of switching counts.')
    write_new(out/'native-import-comparison.json',result)
    print('NATIVE_ACTIVITY_METHOD',IMPORT_METHOD,flush=True)
    return IMPORT_METHOD


def stat_identity(path):
    s = Path(path).stat()
    return {'device':s.st_dev,'inode':s.st_ino,'bytes':s.st_size,'mtime_ns':s.st_mtime_ns}


def prepare(entry, out, libs, f):
    variant = entry['variant']
    gate = R/'xu-gate-20261112-r1'
    d = gate/(variant+'-full12-r15')
    binding_path = d/'verified-binding.json'
    binding = json.loads(binding_path.read_text())
    assert (binding['tasks'],binding['warmup'],binding['physical_clears'])==(12,1,13)
    assert binding['pins']['physical']==entry['netlist_sha256']==PHYSICAL_SHA
    assert sha(d/'native.log')==entry['gate_log_sha256']==binding['native_log_sha256']
    assert Path(entry['gate_log'])==d/'native.log'
    paths = {'physical':R/'xu-closure-20261112-r4/dc/mapped.v',
             'functional':R/'xu-gate-reset-20261112-r2/mapped-functional-reset-r2.v',
             'binary':R/'xu-gate-reset-20261112-r1/simv-row-r1',
             'testbench':R/'xu-gate-reset-20261112-r1/tb_dma64_soc_mapped_r2.sv',
             'cpu_checkers':gate/'cpu-checkers.svh'}
    assert {k:sha(p) for k,p in paths.items()}==binding['pins']
    image = R/'xu-gate-inputs-20261112-r1/firmware'/variant/'dma64_soc.verilog'
    assert sha(image)==binding['firmware_image_sha256']
    review_path = R/'xu-gate-independent-20261113-r2'/(variant+'.json')
    if not review_path.exists():
        reviewer = R/'xu-review-gate-full12-r2.py'
        assert sha(reviewer)==REVIEW_SHA
        subprocess.check_call([sys.executable,'-B',str(reviewer),variant])
    review = json.loads(review_path.read_text())
    assert review['status']=='PASS_INDEPENDENT_GATE_FULL12_REVIEW'
    assert review['binding_sha256']==sha(binding_path) and review['pins']==binding['pins']
    assert review['native_log_sha256']==entry['gate_log_sha256']
    vcd = Path(entry['vcd'])
    assert vcd==gate/(variant+'-r15-fullsoc.vcd')
    identity = stat_identity(vcd)
    assert identity['bytes']==binding['vcd_bytes']==review['vcd_bytes']
    assert review['vcd_sha256_from_controller']==binding['vcd_sha256']
    assert sum(t['payload_cycles'] for t in entry['tasks'])==review['payload_cycles']
    entry.update(gate_binding_sha256=sha(binding_path),gate_review_sha256=sha(review_path),
                 pins=binding['pins'],firmware_image_sha256=binding['firmware_image_sha256'],
                 vcd_sha256_from_sealed_gate=binding['vcd_sha256'],vcd_identity=identity,
                 scope='12_payload_intervals_without_clear_gap_or_warmup')
    method = import_method(out,libs,f)
    if method == 'vendor_saif':
        converted = out/(variant+'-conversion')
        converted.mkdir(mode=0o700)
        pairs = []
        for task in entry['tasks']:
            ns = task['windows_ns'][2:4]
            fs = [int((Decimal(t)*1000000).to_integral_value(rounding=ROUND_HALF_UP)) for t in ns]
            assert fs[0]<fs[1]
            assert all(abs(Decimal(t)*1000000-z)<=Decimal('0.5') for t,z in zip(ns,fs))
            pairs.append({'source_ns':ns,'canonical_fs':fs})
        saif = converted/'payload.saif'
        command = [str(CONVERTER),'-64','-input',str(vcd),'-output',str(saif),
                   '-instance','tb_dma64_soc/dut']
        for pair in pairs:
            command += ['-time']+list(map(str,pair['canonical_fs']))
        write_new(converted/'command.json',command)
        started = time.time()
        def limits():
            os.nice(10)
            resource.setrlimit(resource.RLIMIT_CORE,(0,0))
            resource.setrlimit(resource.RLIMIT_AS,(16*1024**3,16*1024**3))
            allowed=sorted(os.sched_getaffinity(0))
            os.sched_setaffinity(0,set(allowed[:2]))
        assert not heavy_jobs(),heavy_jobs()
        with (converted/'native.log').open('x') as log:
            process = subprocess.run(['timeout','-k','30','7200']+command,cwd=str(converted),
                                     stdout=log,stderr=subprocess.STDOUT,preexec_fn=limits)
        expected = sum(x['canonical_fs'][1]-x['canonical_fs'][0] for x in pairs)
        text = saif.read_text() if saif.exists() else ''
        duration = re.search(r'\(DURATION\s+(\d+)\)',text)
        valid = process.returncode==0 and bool(re.search(r'\(TIMESCALE\s+1\s+fs\)',text)) and duration is not None and int(duration.group(1))==expected
        receipt = {'native_exit':process.returncode,'seconds':time.time()-started,'complete':valid,
                   'converter_sha256':sha(CONVERTER),'command_sha256':sha(converted/'command.json'),
                   'native_log_sha256':sha(converted/'native.log'),'windows':pairs,
                   'expected_duration_fs':expected,'saif_duration_fs':int(duration.group(1)) if duration else None,
                   'saif_sha256':sha(saif) if saif.exists() else None}
        write_new(converted/'receipt.json',receipt)
        assert stat_identity(vcd)==identity
        entry['conversion_receipt_sha256']=sha(converted/'receipt.json')
        if valid:
            entry.update(activity_method='vendor_saif',activity_saif=str(saif),
                         activity_saif_sha256=receipt['saif_sha256'],measurement_duration_fs=expected)
            return 'read_saif -strip_path tb_dma64_soc/dut {'+str(saif)+'}\n'
        print('CONVERSION_NOT_ACCEPTED_FALLING_BACK_DIRECT_VCD',variant,flush=True)
    entry['activity_method']='direct_vcd'
    return 'read_vcd -strip_path tb_dma64_soc/dut -time {'+' '.join(entry['time_intervals_ns'])+'} {'+str(vcd)+'}\n'


def reports():
    return r'''
set macros [get_cells -hierarchical -filter {ref_name == RAMSP1024X16}]
if {[sizeof_collection $macros] != 337} {error {SRAM inventory changed}}
set z [open macro-power.tsv w]
puts $z "instance\tinternal_power\tswitching_power\tleakage_power\ttotal_power"
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


def finalize(entry, run):
    assert stat_identity(entry['vcd'])==entry['vcd_identity']
    receipt = json.loads((run/'receipt.json').read_text())
    assert receipt['native_exit']==0 and receipt['complete']
    assert receipt['script']==sha(run/'run.tcl') and receipt['log']==sha(run/'native.log')
    entry.update(native_receipt_sha256=sha(run/'receipt.json'),
                 output_sha256={name:sha(run/name) for name in OUTPUTS},
                 status='NATIVE_PAYLOAD_POWER_COMPLETE_REVIEW_COVERAGE_AND_UNITS')
