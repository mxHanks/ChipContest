#!/usr/bin/env python3
"""Read-only local source/command evidence for mapped functional qualification gaps."""
import argparse
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
WORK = HERE.parent.parent
BASE = WORK / 'build/xu-score-resume-20261103'
CASES = {
 '111': BASE / 'progress114/mapped-task00-public-diagnostic-20261104-111',
 '147': BASE / 'serverfailed159/s2c-private-native-20261105-147',
 '167': BASE / 'progress174/s2c-passive-unknown-20261105-167',
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def read(p):
    return json.loads(Path(p).read_text())


def rec(p):
    p = Path(p)
    return dict(path=str(p.relative_to(WORK)), bytes=p.stat().st_size,
                sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def dump(p, data):
    Path(p).write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def input_receipts(state):
    rows = state['inputs_before']
    after = state['inputs_after']
    left = {r['path']: (r['sha256'], r['bytes']) for r in rows}
    right = {r['path']: (r['sha256'], r['bytes']) for r in after}
    need(left == right, 'server recorded input identities changed')
    return rows, dict(count=len(rows), hash_size_projection_before_after_equal=True,
                      scope='Recorded server receipts; unreturned input bodies are not locally rehashed.')


def analyze(out):
    sources = []
    cases = {}
    commands = {}
    for key, root in CASES.items():
        state = read(root / 'state.json')
        sources.append(rec(root / 'state.json'))
        steps = {x['name']: x for x in state['steps']}
        need(set(steps) == {'vpi-build', 'vcs-build', 'simulation'}, 'unexpected native step set')
        rows, freeze = input_receipts(state)
        build = (root / 'vcs-build.log').read_text(errors='replace')
        simulation = (root / 'simulation.log').read_text(errors='replace')
        for name in ['vcs-build.log', 'simulation.log']:
            sources.append(rec(root / name))
            expected = steps['vcs-build' if name == 'vcs-build.log' else 'simulation']['log']
            need(rec(root / name)['sha256'] == expected['sha256'] and rec(root / name)['bytes'] == expected['bytes'], 'actual native log identity differs')
        buildcmd, simcmd = steps['vcs-build']['command'], steps['simulation']['command']
        need('-timescale=1ns/1fs' in buildcmd and '+define+ARM_UD_MODEL' in buildcmd,
             'original compiler timescale/model macro differ')
        suppression = [x for x in buildcmd + simcmd if re.search('notimingcheck|nospecify', x, re.I)]
        need(not suppression, 'strict111/147/167 unexpectedly suppress timing')
        explicit_sdf = [x for x in buildcmd + simcmd if re.search(r'(^-sdf|^\+sdf|\.sdf(?:$|[=:]))', x, re.I)]
        files = re.findall(r"^Parsing design file '([^']+)'", build, re.M)
        scan = []
        for name in ['tb_xu_mapped_task00111.sv', 'tb_private147.sv', 'xu_mapped_task00_vpi111.c', 'xu_private147.c']:
            path = root / name
            if path.is_file():
                sources.append(rec(path))
                scan.append(dict(source=rec(path), explicit_sdf_annotation_matches=[i for i, line in enumerate(path.read_text().splitlines(), 1) if re.search(r'\$sdf_annotate|vpi_sdf|\b-sdf\b', line, re.I)]))
        sdf_files = [r for r in rows if Path(r['path']).suffix.lower() == '.sdf']
        sdf_named = [r for r in rows if 'sdf' in r['path'].lower()]
        need(not explicit_sdf and not sdf_files and not any(x['explicit_sdf_annotation_matches'] for x in scan), 'explicit SDF evidence appeared; revise conclusion')
        mapped = [r for r in rows if r['path'].endswith('/s2c/ppa/mapped.v')]
        standard = [r for r in rows if r['path'].endswith('/standard-cell-model-private-20261104-90/scc40nll_vhsc40_rvt.v')]
        vendor = [r for r in rows if r['path'].endswith('/RAMSP1024X16/verilog/RAMSP1024X16.v')]
        need(len(mapped) == len(standard) == len(vendor) == 1, 'exact own map/model identities not unique')
        need(mapped[0]['sha256'] == '9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892', 'own S2c mapping changed')
        need(standard[0]['sha256'] == '9ceaac7085f267c9a2da19d86aa9d88ddb25894df4b2485e32d13e04d0e46581', 'standard model changed')
        cases[key] = dict(status=state['status'], native_returncodes={k: v['returncode'] for k, v in steps.items()},
            server_input_receipts=freeze, mapped={k: mapped[0][k] for k in ['path', 'bytes', 'sha256']},
            standard_model={k: standard[0][k] for k in ['path', 'bytes', 'sha256']},
            vendor_model={k: vendor[0][k] for k in ['path', 'bytes', 'sha256']},
            parsing_design_files=files, compiler_timescale_report=re.findall(r'^TimeScale is (.+)$', build, re.M),
            model_macro='ARM_UD_MODEL (macro spelling alone does not prove its implementation semantics)',
            explicit_sdf_command_options=explicit_sdf, explicit_sdf_files_in_recorded_inputs=sdf_files,
            sdf_named_receipts=[dict(path=x['path'], sha256=x['sha256']) for x in sdf_named],
            returned_tb_c_annotation_scan=scan, timing_suppression_options=suppression,
            native_timing_violation_count=len(re.findall('Timing violation in ', simulation)),
            udp_override_warning_count=build.count('Warning-[OPD] Override previous declaration'),
            sdf_conclusion='No explicit SDF annotation evidenced in returned argv, TB/C, input filenames or native logs; model/mapped source-body audit remains pending, so no universal absence claim.',
            qualify=False)
        commands[key] = {k: steps[k]['command'] for k in ['vpi-build', 'vcs-build', 'simulation']}
    p128 = BASE / 'resource141/mapped-public-function-20261105-128/state.json'
    s128 = read(p128)
    sources.append(rec(p128))
    sim128 = [x for x in s128['steps'] if x['name'] == 'functional-simulation']
    need(len(sim128) == 1 and '+notimingcheck' in sim128[0]['command'], 'actual128 suppression diagnostic identity differs')
    a175 = WORK / 'build/xu-s2c-observation175/analysis175.json'
    analysis = read(a175)
    sources.append(rec(a175))
    need(analysis['native_timing_violation_count'] == 25 and analysis['fatal_native_sampled_differences'] == [] and
         analysis['unknown_fatal_operands'] == ['bias_commit'], 'original175 exact fatal feedback signal differs')
    result = dict(schema='xu-mapped-function-diagnosis201-v1', qualification='NOT_QUALIFIED',
        status='READ_ONLY_LOCAL_DIAGNOSIS_NO_NATIVE_JOB', cases=cases,
        diagnostic128=dict(status=s128['status'], runtime=sim128[0]['command'],
                           qualification='NOT_QUALIFIED', limit='Timing-suppressed public path cannot qualify strict mapped timing/function or private gates.'),
        actual175=dict(analysis=rec(a175), native_target_hold=analysis['native_target_hold'],
                       event_counts=analysis['event_counts'], fatal=analysis['original_native_fatal'],
                       notifier_to_q_x_fs=analysis['notifier_to_q_x_fs'],
                       q_x_to_bias_x_fs=analysis['q_x_to_bias_x_fs'],
                       callback_semantics=analysis['callback_semantics']),
        source_files=sources,
        pending=['Explicit SDF scan of unchanged server-only mapped/model bodies and actual filelists.',
                 'Native177 exact own9c16 D/CK/RDN paths, minimum timing and model metadata; no assumptions before results.',
                 'Actual model macro expansion, timescale, specify/UDP relationship and timing-model-to-SS-DB correspondence.',
                 'Clock/pulse/recovery coverage and same-corner SDF annotation completeness before a timed diagnostic.',
                 'S2e155 own native endpoint inventory and original120 TB adapter; S2c133/147 cannot qualify new155.',
                 'Full unchanged private-TB task0 then twelve fresh independent tasks; public128 does not fill private storage/assertion gaps.'])
    out.mkdir(parents=True, exist_ok=False)
    dump(out / 'analysis201.json', result)
    dump(out / 'native-commands201.json', commands)
    dump(out / 'source-manifest201.json', dict(schema='xu201-local-source-manifest-v1', files=sources,
        limitations='Actual local source bytes hashed; remote input tuples are only recorded original receipts. No model/library body copied.'))
    print('XU201_READONLY_DIAGNOSIS_PASS_NOT_QUALIFIED strict_cases=111,147,167 explicit_sdf=NOT_EVIDENCED model_body_audit=PENDING')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    analyze(args.out)


if __name__ == '__main__':
    main()
