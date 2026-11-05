#!/usr/bin/env python3
"""Replay126 failure call patterns with actual116/131 fixtures, without EDA."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ACTUAL = ROOT / 'build/xu-score-resume-20261103/terminal122/full-soc-timing-combined-20261105-116'
FAILED = ROOT / 'build/xu-score-resume-20261103/coverage131/full-soc-coverage-rdc-20261105-126'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--worker', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args(); out = args.out.resolve(); out.mkdir(exist_ok=False)
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location('xu_repro_worker', args.worker.resolve())
    worker = importlib.util.module_from_spec(spec); spec.loader.exec_module(worker)
    mapped = (ACTUAL / 'mapped.v').read_text()
    assert hashlib.sha256(mapped.encode()).hexdigest() == worker.MAPPED_SHA
    match = re.findall(r'DSNQNV0_12TR40\s+erst_reset_r_r_reg\s*\((.*?)\);', mapped, re.S)
    assert len(match) == 1
    pins = re.findall(r'\.(\w+)\s*\(', match[0]); assert set(pins) == {'D', 'CK', 'SDN', 'QN'}
    options = json.loads((FAILED / 'installed-options.json').read_text())
    generated = worker.diagnostic_tcl('', options)
    cell = worker.SINKS[1][0]
    at = generated.index('set c [get_cells -quiet {' + cell + '}]')
    loop = re.search(r'foreach pn \{([^}]+)\}', generated[at:]).group(1)
    helper = worker.TCL_HELPERS.split('proc xu_pin {', 1)[1].split('proc xu_arcs {', 1)[0]
    prefix = '''proc sizeof_collection {value} {return [llength $value]}
proc get_object_name {value} {return $value}
proc get_pins {args} {set name [lindex $args end]; set pin [lindex [split $name /] end]; if {$pin in {D CK SDN QN}} {return $name};return {}}
'''
    pin_script = prefix + 'proc xu_pin {' + helper
    pin_script += '\nforeach pn {' + loop + '} {xu_pin [format {%s/%s} {' + cell + '} $pn]}\nputs PIN_REPLAY_PASS\n'
    (out / 'pin-replay.tcl').write_text(pin_script)
    pin = subprocess.run(['tclsh', str(out / 'pin-replay.tcl')], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out / 'pin-replay.stdout').write_bytes(pin.stdout); (out / 'pin-replay.stderr').write_bytes(pin.stderr)
    # Actual131 has2016 netless literal macro mode pins plus the one netless
    # PMU D constant. This stub models documented query emptiness, not timing.
    line = next(line for line in generated.splitlines() if 'xu_row $mf [list $name $pinname' in line)
    assert 'nets' in generated
    harness = r'''
proc sizeof_collection {value} {return [llength $value]}
proc get_object_name {value} {if {$value eq {}} {puts stderr {Warning: Nothing implicitly matched '' (SEL-003)}}; return $value}
proc get_attribute {args} {set attribute [lindex $args end]; if {$attribute eq "constant_value"} {return 1};return {}}
proc get_nets {args} {if {[lsearch -exact $args -quiet]<0} {puts stderr {Error: Nothing matched for -of_objects collection (SEL-005)}};return {}}
'''
    # Reuse original generated helper definitions and the exact macro callsite.
    definitions = worker.TCL_HELPERS.split('proc xu_capture {', 1)[0]
    #132 may define collection/net helpers after xu_capture; retain complete
    # helper definitions because uncalled graph procs need no native commands.
    if 'proc xu_nets {' in worker.TCL_HELPERS:
        definitions = worker.TCL_HELPERS
    net_script = harness + definitions
    net_script += '\nset mf [open macro-replay.tsv w]\nset name TEST_ONLY_ACTUAL131_DIRECT_CONSTANT\nset pinname RET1N\nset p TEST_ONLY/RET1N\n' + line + '\nclose $mf\nclose $xu_unknown\n'
    (out / 'net-replay.tcl').write_text(net_script)
    net = subprocess.run(['tclsh', str(out / 'net-replay.tcl')], cwd=str(out), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out / 'net-replay.stdout').write_bytes(net.stdout); (out / 'net-replay.stderr').write_bytes(net.stderr)
    result = {'status': 'HOST_REPLAY_ONLY_NOT_NATIVE132', 'qualification': 'NOT_QUALIFIED',
              'worker_sha256': hashlib.sha256(args.worker.read_bytes()).hexdigest(),
              'actual116_second_pmu_ports': pins, 'generated_second_pmu_port_loop': loop.split(),
              'pin_returncode': pin.returncode,
              'pin_native_symptom_reproduced': b'exact pin identity missing:' in pin.stderr,
              'net_returncode': net.returncode,
              'net_native_symptom_reproduced': b'Error: Nothing matched for -of_objects collection (SEL-005)' in net.stderr,
              'pass': pin.returncode == 0 and net.returncode == 0 and b'Error:' not in net.stderr}
    (out / 'results.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result['pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
