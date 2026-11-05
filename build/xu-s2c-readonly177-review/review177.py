#!/usr/bin/env python3
"""xu independent local provenance and job-contract audit; never launches EDA."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = ROOT / 'build/xu-s2c-readonly177'


def need(condition, message):
    if not condition:
        raise ValueError(message)


def ident(path):
    data = path.read_bytes()
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def read(path):
    return json.loads(path.read_text())


def triple(row):
    return {key: row[key] for key in ['path', 'bytes', 'sha256']}


def main():
    ref = read(SRC / 'references177.json')
    for name in ['actual175', 'original57_prepared', 'original57_execution']:
        row = ref[name]
        need(ident(ROOT / row['path']) == {key: row[key] for key in ['bytes', 'sha256']}, 'historical reference ' + name)
    analysis = read(ROOT / ref['actual175']['path'])
    prepared = read(ROOT / ref['original57_prepared']['path'])
    execution = read(ROOT / ref['original57_execution']['path'])
    original167 = read(ROOT / 'build/xu-score-resume-20261103/progress174/s2c-passive-unknown-20261105-167/state.json')
    queryref = ref['next_minimal_readonly_query']
    need(queryref == analysis['next_minimal_readonly_query'], 'actual175 proposed scope differs')
    need(triple(queryref['target']) == prepared['netlist'], 'own9c16 map differs')
    need(queryref['own_s2c_sdc'] == prepared['analysis_sdc'], 'own S2c SDC differs')
    need(queryref['own_s2c_libraries'] == prepared['implementation_controls']['libraries'], 'own S2c two libraries differ')
    need(ref['own_clock_method_source'] == prepared['tasks'][0]['script'], 'own57 clock producer differs')
    need(ref['pt'] == execution['tool'] and ref['library_compiler_root'] == execution['library_compiler_root'], 'own57 tool identity differs')
    model = [row for row in original167['inputs_before'] if row['path'] == ref['model']['path']]
    need(model == [ref['model']], 'actual167 model receipt differs')
    template = SRC / 'frozen-ownS2c-power57.tcl'
    need(ident(template) == {key: ref['own_clock_method_source'][key] for key in ['bytes', 'sha256']}, 'whole frozen own57 Tcl differs')
    original = template.read_text()
    start, end = original.index('set XU_CLOCK_MODE envelope\n'), original.index('# Exact post-elaboration macro groups;')
    exact_method = original[start:end]
    need(exact_method.startswith('set XU_CLOCK_MODE envelope\nset XU_PLL_DIV 0\nsource {') and
         exact_method.endswith('set_propagated_clock [all_clocks]\nupdate_timing\n'), 'clock method is not original own57 interval')
    manifest = read(SRC / 'manifest177.json')
    need(manifest['qualification'] == 'NOT_QUALIFIED', 'manifest qualification')
    runtime = manifest['runtime']
    need(len({row['name'] for row in runtime}) == len(runtime), 'duplicate runtime')
    for row in runtime:
        need(Path(row['name']).name == row['name'] and not (SRC / row['name']).is_symlink(), 'unsafe runtime name')
        need(ident(SRC / row['name']) == {key: row[key] for key in ['bytes', 'sha256']}, 'final manifest SHA differs')
    # Import definitions only; the main guard prevents worker execution.
    spec = importlib.util.spec_from_file_location('xu_review177_runtime', str(SRC / 'readonly177.py'))
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    rendered, method = api.render_query(ref)
    need(method == exact_method and rendered.count(exact_method) == 1, 'rendered method differs')
    need('dp_gt0.vec_31_dfflr/qout_r_reg[0]' in rendered and 'dp_gt0/vec_31_dfflr' not in rendered, 'literal target changed')
    for token in ['if {[get_object_name $c] eq $xu_exact}', '[sizeof_collection $xu_cell] != 1',
                  '[dict size $xu_pins] != 4', 'wrong direction', 'get_attribute $xu_cell ref_name',
                  'report_timing -delay_type min -to $xu_D -path_type full_clock_expanded',
                  'all_fanout -flat -endpoints_only -from $xu_Q', 'STOP_OWNER']:
        need(token in rendered, 'missing exact/native/stop-state query: ' + token)
    need('get_timing_arcs' not in rendered and 'timing_arc' not in rendered, 'timing arc full_name hazard')
    need(not re.search(r'\b(?:set_false_path|set_case_analysis|set_disable_timing|set_min_delay|insert_buffer|set_logic_zero|set_logic_one)\b', rendered), 'new constraint/design mutation')
    need(not re.search(r'\b(?:force|remove_clock|remove_case_analysis|write_verilog|write_sdc)\b', rendered), 'query mutation/output source')
    jobproc = subprocess.run([sys.executable, '-B', str(SRC / 'job177.py')], cwd=str(ROOT),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    need(jobproc.returncode == 0, 'job generation failed: ' + jobproc.stderr)
    job = json.loads(jobproc.stdout)
    need(job == read(SRC / 's2c_readonly177.json'), 'saved reviewed job differs from generator')
    need(job['dependencies'] == [dict(id='two_candidate_autopack173', policy='terminal'), dict(id='s2c_unknown167', policy='success')], 'dependencies differ')
    need(job['native'] is True and job['process_contains'] == job['output_root'] and
         job['result_state'] == job['output_root'] + '/state.json', 'single-slot unique output contract')
    need(job['success_statuses'] == [api.SUCCESS] and job['failure_statuses'] == [api.FAILURE], 'result contract')
    frozen = {row['path']: row for row in job['frozen_inputs']}
    need(len(frozen) == len(job['frozen_inputs']), 'duplicate frozen input')
    expected_external = [queryref['target'], queryref['own_s2c_sdc']] + queryref['own_s2c_libraries'] + [ref['pt'], ref['model'], ref['own_clock_method_source']]
    for row in expected_external:
        need(frozen[row['path']] == triple(row), 'external job freeze differs')
    server_root = Path('/storage2/2026contest/server4/s4_23usr/Desktop/xu-s2c-readonly177')
    for row in runtime:
        need(frozen[str(server_root / row['name'])] == dict(path=str(server_root / row['name']), bytes=row['bytes'], sha256=row['sha256']), 'runtime job freeze differs')
    need(frozen[str(server_root / 'manifest177.json')] == dict(path=str(server_root / 'manifest177.json'), **ident(SRC / 'manifest177.json')), 'manifest itself not frozen')
    # Static-only examination: importing or executing the server registration
    # wrapper would target the wrong host and is deliberately not attempted.
    control = ROOT / 'build/xu-s2c-readonly177-control182'
    wrapper_path = control / 'register182.py'
    wrapper = wrapper_path.read_text()
    tree = ast.parse(wrapper)
    constants = {node.targets[0].id: node.value.value for node in tree.body
                 if isinstance(node, ast.Assign) and len(node.targets) == 1 and
                 isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Constant)}
    worker = ROOT / 'build/xu-campaign-batch154/control153/xu_experiments.py'
    need(constants['WORKER_SHA'] == ident(worker)['sha256'], '182 frozen153 hash differs')
    need(constants['JOB_SHA'] == ident(SRC / 's2c_readonly177.json')['sha256'], '182 final job SHA not locked')
    need((control / 's2c_readonly177.json').read_bytes() == (SRC / 's2c_readonly177.json').read_bytes(), '182 job copy differs')
    for token in ["m.same_process(state['controller_identity'],actual)",
                  "v['status']=='DEFERRED_ORIGINAL_WORKERS_PRESERVED_CONTROLLER_RESUMED_NOT_QUALIFIED'",
                  "v['preserved_profiles']==['s2e','s2c']", "v['workers_signalled']==v['workers_restarted']==0",
                  "v['status']=='REGISTERED_AUTOPACK173_NOT_QUALIFIED'", "m.identity(oldreg)==v['registration']",
                  "m.check_records(job['frozen_inputs'])", "assert after==before", 'm.register(C,JOB)',
                  'not Path(job[\'output_root\']).exists()', 'not Path(job[\'output_root\']).is_symlink()']:
        need(token in wrapper, '182 guard missing: ' + token)
    def call_name(node):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return call_name(node.value) + '.' + node.attr
        return ''
    calls = {call_name(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
    need(not any(name in calls for name in ['m.initialize', 'm.run', 'm.launch', 'os.kill', 'os.killpg',
                                            'subprocess.run', 'subprocess.Popen', 'm.signal']), '182 directly starts/stops work')
    need('subprocess' not in wrapper and 'os.kill' not in wrapper, '182 process control import')
    result = dict(schema='xu-s2c-readonly177-independent-review-v1', qualification='NOT_QUALIFIED',
                  status='REVIEW_PASS_PENDING_NATIVE_EXECUTION_NOT_QUALIFIED', blocking_findings=[],
                  reviewed_runtime=runtime, reviewed_manifest=ident(SRC / 'manifest177.json'),
                  reviewed_job=ident(SRC / 's2c_readonly177.json'), reviewed_registration_wrapper=ident(wrapper_path),
                  exact_own57_clock_interval_sha256=hashlib.sha256(exact_method.encode()).hexdigest(),
                  historical_identity_sources=['actual175', 'original57_prepared', 'original57_execution', 'actual167_model_receipt'],
                  job_id=job['id'], dependencies=job['dependencies'], native_slot=True,
                  process_contains=job['process_contains'], frozen_input_count=len(frozen),
                  exact_literal_target=queryref['target_pt_cell_candidate'],
                  no_timing_arc_full_name_access=True, production_changes=0, remote_actions=0, native_runs=0,
                  limitations=['Review verifies code/provenance/job contract, not native object resolution or report availability.',
                               'The native run must retain missing clock/zero path/constraint gaps and all diagnostics; completed query does not qualify function/timing/energy.',
                               'VCS model timing check observations and static PT paths are not a proved unknown-causality chain.'])
    (HERE / 'review177.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(result['status'])


if __name__ == '__main__':
    main()
