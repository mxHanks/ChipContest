#!/usr/bin/env python3
"""Exercise large native TSV and immutable five-phase adoption; no EDA tool."""
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import resume155 as m

api = m.load_original()
checks = []
with tempfile.TemporaryDirectory(prefix='xu155-') as tmp:
    root = Path(tmp)
    huge = root/'large.tsv'
    value = 'fanout/'*50000
    huge.write_text('name\tloads\nclk\t'+value+'\n')
    previous = csv.field_size_limit(131072)
    try:
        try:
            api.rows(huge)
        except csv.Error:
            checks.append('reproduced actual134 CSV field failure')
        else:
            raise AssertionError('old limit did not fail')
        csv.field_size_limit(64*1024*1024)
        assert api.rows(huge) == [dict(name='clk', loads=value)]
        checks.append('large field preserved without truncation')
    finally:
        csv.field_size_limit(previous)
    old, new = root/m.OLD_NAME, root/m.NEW_NAME
    old.mkdir();new.mkdir()
    state = dict(status='FAILED_NOT_QUALIFIED', error='Error: field larger than field limit (131072)',
                 frozen_before={}, frozen_after={}, frozen_input_errors=[], hold_outputs={}, generated={}, diagnostics={}, runs=[])
    for phase, kind in m.PHASES:
        directory = old/phase;directory.mkdir(exist_ok=True)
        script = directory/('sta.tcl' if kind == 'pt' else 'repair.tcl' if phase == 'hold-gating' else 'inventory.tcl')
        script.write_text('read '+str(old/'hold-gating/mapped.v')+'\nputs DONE\n')
        log = directory/(kind+'.log');log.write_text('original native rc0\nDONE\n')
        state['generated'][str(script)] = api.ident(script)
        run = dict(directory=str(directory), tool=kind, command=['original-native', '-f', script.name],
                   returncode=0, marker_count=1, errors=[], script=api.ident(script), log=api.ident(log))
        state['runs'].append(run)
    for phase in ('original-inventory', 'posthold-inventory'):
        directory = old/phase
        report = directory/'native-cells.tsv';report.write_text('native\toutputs\ncell\tnone\n')
        state['diagnostics'][phase] = dict(mapped=api.ident(report), reports={str(report): api.ident(report)})
    for name in ('mapped.v', 'hold.svf'):
        path = old/'hold-gating'/name;path.write_text('original own134 '+name)
        state['hold_outputs'][str(path)] = api.ident(path)
    (old/'state.json').write_text(json.dumps(state))
    m.OLD_STATE_SHA = m.sha(old/'state.json')
    adapter = m.Adoption(api, old, new)
    fresh = dict(runs=[])
    for phase, kind in m.PHASES:
        directory = new/phase;directory.mkdir(exist_ok=True)
        original = next(r for r in state['runs'] if Path(r['directory']).name == phase and r['tool'] == kind)
        script = directory/Path(original['script']['path']).name
        script.write_bytes(Path(original['script']['path']).read_bytes().replace(str(old).encode(), str(new).encode()))
        adapter.native(directory, fresh, kind, script.name, 'DONE', {})
    assert adapter.done == m.PHASES and len(fresh['runs']) == 5
    assert all(r['execution_provenance'] == 'ADOPTED_ORIGINAL134_NATIVE_PHASE_NOT_RERUN' for r in fresh['runs'])
    assert (new/'hold-gating/mapped.v').read_bytes() == (old/'hold-gating/mapped.v').read_bytes()
    adapter.recheck()
    checks.append('five ordered original phases adopted with explicit provenance')
    second = root/'second';second.mkdir();(second/'original-inventory').mkdir()
    adapter2 = m.Adoption(api, old, second)
    (second/'original-inventory/inventory.tcl').write_text('different constraints\n')
    try:
        adapter2.native(second/'original-inventory', dict(runs=[]), 'dc', 'inventory.tcl', 'DONE', {})
    except ValueError:
        checks.append('nonrelocation script change rejected')
    else:
        raise AssertionError('changed script adopted')
    (old/'posthold-inventory/native-cells.tsv').write_text('mutated')
    try:
        adapter.recheck()
    except ValueError:
        checks.append('original report mutation rejected')
    else:
        raise AssertionError('mutated report accepted')
print(json.dumps(dict(status='HOST155_ADOPTION_CHECKS_PASS_NO_EDA', checks=checks), indent=2))
