import hashlib
import json
from pathlib import Path
import re
import sys
import tarfile

repo = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(repo/'tools/scripts'))
import e203_soc as soc
import xu_firmware_contract as contract
import xu_perf_report as perf

archive, destination = map(Path, sys.argv[1:3])
destination.mkdir(exist_ok=False)
with tarfile.open(archive) as tar:
    for member in tar.getmembers():
        name = Path(member.name)
        assert member.isfile() and not name.is_absolute() and '..' not in name.parts
        path = destination/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(tar.extractfile(member).read())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
manifest = json.loads((destination/'xu-transfer-manifest.json').read_text())
for name, identity in manifest['files'].items():
    path = destination/name
    assert sha(path) == identity['sha256'] and path.stat().st_size == identity['bytes'], name
campaign = json.loads((destination/'experiments.json').read_text())
accepted = json.loads((destination/'acceptance/acceptance.json').read_text())
receipt = json.loads((repo/'docs/validation/xu-fw-optimization-20261102/observed-receipt.json').read_text())
assert receipt['integrity_errors'] == [] and receipt['final']['status'] == 'PASS'
assert receipt['campaign_sha256'] == sha(destination/'experiments.json')
assert receipt['final']['acceptance_sha256'] == sha(destination/'acceptance/acceptance.json')
assert receipt['final']['accepted_result_sha256'] == sha(destination/'acceptance/real12/result.json')
assert receipt['final']['performance_summary_sha256'] == sha(destination/'acceptance/xu-performance.json')
assert campaign['status'] == accepted['status'] == 'PASS'
assert campaign['retention_status'] == 'retained' and campaign['retained_optimization']
assert [(x['name'], x['status']) for x in accepted['steps']] == [(x, 'PASS') for x in
    ['host', 'numeric', 'vectors', 'doctor', 'baseline', 'synthetic1', 'synthetic2', 'real12']]
assert accepted['profile'] == 'vcs-platform' and accepted['not_run'] == ['icarus1', 'chisel']
assert accepted['firmware_configuration'] == campaign['selected']['configuration']
matrix = json.loads((repo/'docs/validation/xu-fw-optimization-20261102/compile-matrix.json').read_text())
assert soc.verify_submodule(repo, soc.E203) == 'e36d34a52e6eef93fd0bdfed1b13009e1056bea3'
gcc_tools = [value for name, value in campaign['environment']['tool_sha256'].items()
             if name.endswith('riscv64-unknown-elf-gcc')]
assert len(gcc_tools) == 1 and gcc_tools[0]['sha256'] == matrix['compiler_sha256']
compiled = {tuple(sorted(c['configuration'].items())): c for c in matrix['configurations']}
results = {}
checks = []
extracted_logs = json.loads((destination/'xu-simulation-pass-lines-derived.json').read_text())['logs']
for path in sorted(destination.rglob('result.json')):
    result = json.loads(path.read_text())
    assert result['status'] == 'PASS', path
    name = str(path.relative_to(destination).parent)
    results[name] = result
    if result['mode'] not in ['real', 'synthetic']:
        continue
    config = contract.configuration_from_result(result)
    log_name = name+'/simulation.log'
    log_evidence = extracted_logs[log_name]
    assert result['log_sha256']['simulation.log'] == log_evidence['sha256']
    log = '\n'.join(log_evidence['selected_exact_lines'])+'\n'
    layers = soc.check_log(log, result['tasks'])
    for layer, counters in zip(layers, soc.check_performance(log, layers, config['schedule'])):
        layer['performance'] = counters
    assert layers == result['layers'], name
    assert result['outputs'] == result['tasks']*25344
    assert result['write_words'] == result['tasks']*50688
    for source, digest in result['source_sha256'].items():
        source_path = repo/source
        if not source_path.exists():
            source_path = repo/source.replace('/vsim/install/rtl/', '/rtl/e203/')
        assert sha(source_path) == digest, source
    for source, digest in result['firmware_sha256'].items():
        assert sha(repo/'tests/e203/firmware'/source) == digest, source
    local = compiled[tuple(sorted(config.items()))]
    assert result['firmware_elf_sha256'] == local['elf_sha256'], name
    assert result['firmware_image_sha256'] == local['image_sha256'], name
    checks.append(dict(case=name, tasks=result['tasks'], cycles=sum(x['cycles'] for x in layers),
                       result_sha256=sha(path), simulation_log_sha256=log_evidence['sha256'],
                       simulation_log_bytes=log_evidence['bytes']))
baseline = results['E0-baseline-real12']
final = results['acceptance/real12']
candidate = results['E4-no-masks-real12']
assert baseline['firmware_image_sha256'] == '4932e8d8f62cdd2732d894abc4c7008809283fe3de29445de90ec764cd12f32e'
assert [x['cycles'] for x in baseline['layers']] == [2368078]+[2368074]*11
assert final['layers'] == candidate['layers']
assert sum(x['cycles'] for x in final['layers']) == 25251416
for filename, count in [('host.log',38), ('numeric.log',34)]:
    log = (destination/'acceptance'/filename).read_text()
    assert re.search(r'Ran '+str(count)+r' tests? in ', log) and re.search(r'^OK$',log,re.M), filename
assert len(results['acceptance/baseline']['tests']) == 5
summary = perf.summarize(final,150)
server_summary = json.loads((destination/'acceptance/xu-performance.json').read_text())
assert all(summary[key] == server_summary[key] for key in summary)
derived = dict(summary, source_result_sha256=sha(destination/'acceptance/real12/result.json'),
               source_result=str(destination/'acceptance/real12/result.json'),
               evidence_kind='locally recomputed from exact server result JSON copied via visible-screen transfer')
with (destination.parent/'derived-performance.json').open('x') as stream:
    stream.write(json.dumps(derived,indent=2,sort_keys=True)+'\n')
report = dict(status='PASS', archive_sha256=sha(archive), verified_files=len(manifest['files']),
              passing_simulations=checks, host_tests=38, numeric_tests=34, baseline_soc_tests=5,
              final_matches_selected_experiment=True, extracted_exact_pass_lines_reparsed=True,
              raw_simulation_log_scope='complete originals remain on server; original SHA256 matched to raw result JSON; receipt verifies complete originals at source',
              current_rtl_tb_and_firmware_hashes_match=True, firmware_elf_images_match_local_sifive_compiles=True,
              server_summary_recomputed=True, final_configuration=campaign['selected']['configuration'],
              final_observed_receipt_crosschecked=True,
              final_cycles=summary['aggregate']['cycles'], baseline_cycles=28416892,
              speedup=28416892/summary['aggregate']['cycles'],
              source_campaign_sha256=sha(destination/'experiments.json'),
              acceptance_sha256=sha(destination/'acceptance/acceptance.json'))
with (destination.parent/'verification.json').open('x') as stream:
    stream.write(json.dumps(report,indent=2,sort_keys=True)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='passing_simulations'},indent=2))
