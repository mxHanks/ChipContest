#!/usr/bin/env python3
"""Read-only independent check of the unique retrieved S2a payload."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tarfile
import tempfile
import types

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / 'tests/e203/vectors/kwt-silence-v1.tar.gz').is_file())
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path)
args = parser.parse_args()


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(path.read_bytes())


def read(path):
    return json.loads(path.read_text())


original = read(HERE / 'original-export-manifest.json')
selected = read(HERE / 'selected-manifest.json')
require(len(selected) == len({row['path'] for row in selected}) == 24, 'unique payload count differs')
for row in selected:
    require([entry for entry in original if entry['path'] == row['path']] == [row],
            'selected path not unique in original manifest')
    path = HERE / 'raw' / row['path']
    require(path.stat().st_size == row['bytes'] and sha(path) == row['sha256'], 'original payload hash differs')
require({q.relative_to(HERE / 'raw').as_posix() for q in (HERE / 'raw').rglob('*') if q.is_file()}
        == {row['path'] for row in selected}, 'raw file set differs')
source_audit = read(HERE / 'git-source-audit.json')
with tarfile.open(HERE / 'frozen-git-sources.tar.xz', 'r:xz') as archive:
    snapshot = {m.name:archive.extractfile(m).read() for m in archive.getmembers() if m.isfile()}
require({name:digest(data) for name,data in snapshot.items()} == source_audit['source_sha256'],
        'frozen source archive differs')
contract = types.ModuleType('xu_firmware_contract')
exec(compile(snapshot['tools/scripts/xu_firmware_contract.py'], '<frozen-contract>', 'exec'), contract.__dict__)
sys.modules['xu_firmware_contract'] = contract
soc = types.ModuleType('xu_frozen_s2a_soc')
soc.__file__ = str(ROOT / 'tools/scripts/e203_soc.py')
exec(compile(snapshot['tools/scripts/e203_soc.py'], '<frozen-runner>', 'exec'), soc.__dict__)
fixture = read(ROOT / 'tests/e203/vectors/kwt-silence-v1.json')
require(sha(ROOT / 'tests/e203/vectors/kwt-silence-v1.tar.gz') == fixture['archive_sha256'], 'fixture differs')
with tempfile.TemporaryDirectory(prefix='xu-s2a-fixed-vectors-') as temporary:
    soc.load_fixture(Path(temporary), 12)
    vectors = soc.check_vectors(Path(temporary), 12)

raw = HERE / 'raw/s2-s2a-accept-01'
state = read(raw / 'state.json')
require(state['status'] == 'VCS_ACCEPTED_NOT_RETAINED', 'server state incomplete')
expected_steps = ['host', 'numeric', 'vectors', 'doctor', 'baseline', 'synthetic1', 'synthetic2', 'real12']
variants, negatives = {}, []
for name, schedule in [('oldabi','bias-hw-window'), ('stream','bias-hw-stream16-window')]:
    directory = raw / 'acceptance' / name
    acceptance = read(directory / 'acceptance.json')
    acceptance_state = next(row for row in state['acceptances'] if row['recipe'] == name)
    require(acceptance['status'] == acceptance_state['status'] == 'PASS'
            and sha(directory / 'acceptance.json') == acceptance_state['acceptance_sha256'], 'acceptance hash/status differs')
    require([step['name'] for step in acceptance['steps']] == expected_steps
            and all(step['status'] == 'PASS' for step in acceptance['steps']), 'eight steps incomplete')
    require(acceptance['firmware_configuration'] == contract.configuration(schedule,'-O2','both-unroll-no-masks'),
            'acceptance configuration differs')
    for step in acceptance['steps'][2:]:
        command = step['command']
        require(command[command.index('--sim') + 1] == 'vcs'
                and command[command.index('--firmware-schedule') + 1] == schedule
                and '--firmware-opt=-O2' in command
                and command[command.index('--firmware-experiment') + 1] == 'both-unroll-no-masks',
                'recorded command backend/configuration differs')
    missing_logs, real = {}, None
    for mode, tasks in [('synthetic1',1),('synthetic2',2),('real12',12)]:
        run_dir = directory / mode
        result = read(run_dir / 'result.json')
        require(result['status'] == 'PASS' and result['tasks'] == tasks and result['simulator'] == 'vcs',
                'run did not pass')
        require(result['main_commit'] == state['candidate']['main'] == source_audit['main_commit']
                and result['e203_commit'] == state['candidate']['child'] == source_audit['e203_commit'],
                'source commits differ')
        require(result['firmware_schedule'] == schedule and result['firmware_opt'] == '-O2'
                and result['firmware_experiment'] == 'both-unroll-no-masks', 'run configuration differs')
        require(digest(snapshot['tools/scripts/e203_soc.py']) == result['runner_sha256']
                and digest(snapshot['tools/scripts/xu_firmware_contract.py']) == result['contract_sha256'], 'checker identity differs')
        require(all(digest(snapshot[path]) == value for path,value in result['source_sha256'].items()),
                'RTL/TB source identity differs')
        require(result['firmware_sha256'] == result['firmware_build']['source_sha256']
                and all(digest(snapshot['tests/e203/firmware/' + path]) == value
                        for path,value in result['firmware_sha256'].items()), 'firmware source identity differs')
        require(result['firmware_elf_sha256'] == result['firmware_build']['elf_sha256']
                and result['firmware_image_sha256'] == result['firmware_build']['image_sha256'],
                'reported firmware identities disagree')
        missing = []
        for filename,value in result['log_sha256'].items():
            if (run_dir / filename).is_file():
                require(sha(run_dir / filename) == value, 'retrieved log SHA differs')
            else:
                missing.append(filename)
        missing_logs[mode] = missing
        log = (run_dir / 'simulation.log').read_text().split('\n',1)[1]
        layers = soc.check_log(log,tasks)
        counters = soc.check_performance(log,layers,schedule)
        for layer,counter in zip(layers,counters):
            layer['performance'] = counter
            require(counter['busy'] == 215424, 'fixed busy latency differs')
        require(layers == result['layers'] and result['outputs'] == tasks*25344
                and result['write_words'] == tasks*50688, 'actual output/count records differ')
        if mode == 'real12':
            require(result['fixture'] == fixture and result['vectors'] == fixture['files'], 'fixed vectors differ')
            real = result
        for case,bad in [
            ('missing_TASK', re.sub(r'^TASK_PASS[^\n]*\n','',log,count=1,flags=re.M)),
            ('duplicate_TASK',log + next(line for line in log.splitlines() if line.startswith('TASK_PASS ')) + '\n'),
            ('missing_PERF',re.sub(r'^PERF_TASK[^\n]*\n','',log,count=1,flags=re.M)),
            ('wrong_MMIO',log.replace('mmio_writes='+str(counters[0]['mmio_writes']),
                                      'mmio_writes='+str(counters[0]['mmio_writes']-1),1)),
            ('wrong_MAC',log.replace('mac_fire=202752','mac_fire=202751',1)),
            ('wrong_shared_reads',log.replace('shared_reads=23232','shared_reads=23231',1)),
            ('missing_SOC',re.sub(r'^SOC_PASS[^\n]*\n','',log,flags=re.M)),
            ('appended_FATAL',log+'\nFATAL: negative\n')]:
            try:
                checked = soc.check_log(bad,tasks)
                soc.check_performance(bad,checked,schedule)
            except ValueError:
                negatives.append(name+'/'+mode+'/'+case)
            else:
                raise ValueError('accepted corrupt actual log: '+case)
    for mode in ['baseline','doctor','vectors']:
        result = read(directory / mode / 'result.json')
        require(result['status'] == 'PASS' and result['main_commit'] == source_audit['main_commit'],
                mode+' result incomplete')
    require(read(directory/'vectors/result.json')['layers'] == vectors, 'vector-check result differs')
    require(read(directory/'baseline/result.json')['tests'] ==
            ['rv32ui-p-add','accel_mmio','accel_compute','accel_multigroup','accel_repeat_x'], 'legacy cases incomplete')
    wrapper = (directory/'host-wrapper-vcs/simulation.log').read_text()
    require(len(re.findall(r'XU_CACHED_WRAPPER_PASS accepted=4909 retired=4909',wrapper)) == 1
            and 'Compiler version Q-2020.03-SP2-6_Full64' in wrapper, 'cached VCS wrapper incomplete')
    missing_files = [str((directory/(step['name']+'.log')).relative_to(raw))
                     for step in acceptance['steps'] if not (directory/(step['name']+'.log')).is_file()]
    variants[name] = dict(real_result=real, eight_step_receipt='PASS', missing_acceptance_logs=missing_files,
                          missing_declared_logs=missing_logs, host_count_and_skips='not retrieved; cannot independently establish',
                          new_stream_direct_server_tb='not retrieved; frozen unittest requires Icarus and may skip')

old, stream = variants['oldabi']['real_result'],variants['stream']['real_result']
same = ['main_commit','e203_commit','source_sha256','runner_sha256','contract_sha256','firmware_sha256',
        'versions','tools','fixture','vectors','simulator_sha256','firmware_opt','firmware_experiment']
for field in same:
    require(old[field] == stream[field], 'same-run comparison identity differs: '+field)
rows = []
for base,candidate in zip(old['layers'],stream['layers']):
    rows.append(dict(layer=base['layer'],oldabi=base,stream=candidate,
                     stream_minus_oldabi=dict(cycles=candidate['cycles']-base['cycles'],
                        performance={key:value-base['performance'][key] for key,value in candidate['performance'].items()})))
totals = {name:sum(layer['cycles'] for layer in data['real_result']['layers']) for name,data in variants.items()}
require(totals == dict(oldabi=16510344,stream=15361356), 'twelve-layer totals differ')
report = dict(status='VERIFIED_VCS_DEVELOPMENT_SOC_RESULTS_WITH_RETRIEVAL_GAPS', payload_paths=24,
              main_commit=source_audit['main_commit'],e203_commit=source_audit['e203_commit'],
              source_paths_verified=151,same_identity_fields=same,total_cycles=totals,
              cycle_reduction=totals['oldabi']-totals['stream'],
              cycle_reduction_percent=100*(totals['oldabi']-totals['stream'])/totals['oldabi'],
              variants=variants,per_layer=rows,rejected_corruptions=negatives,
              fixed_outputs_independently_recomputed=304128,
              limitations=['raw host/numeric/step logs omitted; receipts report PASS but counts/skips unverified',
                 'no new direct stream TB server trace retrieved; cached VCS trace is a different TB',
                 'firmware/simulator binaries, actual server vectors and build/version logs omitted',
                 'legacy loading window; no S2a formal clear/request/PPA/energy/qualification/retention claim'])
if args.out:
    args.out.write_text(json.dumps(report,indent=2)+'\n')
print('PASS: 24 unique payloads; 151 frozen source identities; six VCS SoC runs; '
      '304128 fixed outputs; '+str(len(negatives))+' rejected corruptions; retrieval gaps retained')
