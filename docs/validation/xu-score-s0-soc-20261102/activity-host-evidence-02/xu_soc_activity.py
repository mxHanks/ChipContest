#!/usr/bin/env python3
"""Probe VCS SAIF support and audit task-scoped full-SoC energy evidence.

Python standard library only; no implicit remote execution. A probe is an actual
EDA experiment, not a claim that a remembered VCS system task is supported.
"""
import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
UNITS = {'s': Decimal(1), 'ms': Decimal('1e-3'), 'us': Decimal('1e-6'),
         'ns': Decimal('1e-9'), 'ps': Decimal('1e-12'), 'fs': Decimal('1e-15')}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def parse_sexpr(source):
    """Read SAIF syntax without evaluating it; escaped bus names stay names."""
    tokens = re.findall(r'//[^\n]*|/\*.*?\*/|\(|\)|"(?:\\.|[^"\\])*"|(?:\\.|[^\s()])+', source, flags=re.S)
    tokens = [t for t in tokens if not t.startswith('//') and not t.startswith('/*')]
    stack, result = [], []
    for token in tokens:
        if token == '(':
            node = []
            (stack[-1] if stack else result).append(node)
            stack.append(node)
        elif token == ')':
            require(stack, 'unbalanced SAIF close parenthesis')
            stack.pop()
        else:
            require(stack, 'SAIF token outside expression')
            stack[-1].append(token[1:-1] if token.startswith('"') else token)
    require(not stack and len(result) == 1, 'unbalanced or multiple SAIF roots')
    require(result[0] and result[0][0] == 'SAIFILE', 'not a SAIFILE')
    return result[0]


def read_saif(path, allow_zero=False):
    tree = parse_sexpr(Path(path).read_text(errors='strict'))
    headers = {node[0]: node[1:] for node in tree[1:] if isinstance(node, list) and node and
               node[0] not in ['INSTANCE']}
    require('TIMESCALE' in headers and len(headers['TIMESCALE']) == 2, 'SAIF TIMESCALE missing')
    scale, unit = headers['TIMESCALE']
    require(unit in UNITS and Decimal(scale) > 0, 'invalid SAIF timescale')
    tick_seconds = Decimal(scale)*UNITS[unit]
    require(len(headers.get('DURATION', [])) == 1, 'SAIF DURATION missing')
    duration = Decimal(headers['DURATION'][0])
    require((duration >= 0 if allow_zero else duration > 0) and duration == int(duration),
            'SAIF duration must be positive integral ticks (zero allowed only for destructive-report probe)')
    signals = []

    def visit(node, parent):
        if not isinstance(node, list) or not node:
            return
        if node[0] == 'INSTANCE':
            require(len(node) >= 2 and isinstance(node[1], str), 'invalid INSTANCE')
            current = parent + [re.sub(r'\\(.)', r'\1', node[1])]
            for item in node[2:]:
                visit(item, current)
        elif node[0] in ['NET', 'PORT']:
            for item in node[1:]:
                require(isinstance(item, list) and item and isinstance(item[0], str), 'invalid SAIF signal')
                stats = {}
                for stat in item[1:]:
                    require(isinstance(stat, list) and len(stat) == 2, 'unsupported SAIF signal statistics')
                    require(stat[0] not in stats, 'duplicate SAIF statistic')
                    number = Decimal(stat[1])
                    require(number >= 0 and number == int(number), 'negative/nonintegral SAIF statistic')
                    stats[stat[0]] = int(number)
                require(all(key in stats for key in ['T0', 'T1', 'TX', 'TC']), 'SAIF signal statistics incomplete')
                require(sum(stats.get(key, 0) for key in ['T0', 'T1', 'TX', 'TZ', 'TB']) == duration,
                        'SAIF state dwell times differ from DURATION')
                signals.append(dict(path='/'.join(parent+[re.sub(r'\\(.)', r'\1', item[0])]), kind=node[0], **stats))
        else:
            for item in node[1:]:
                visit(item, parent)

    for node in tree[1:]:
        visit(node, [])
    require(signals, 'SAIF has no per-signal activity')
    require(len({(s['kind'],s['path']) for s in signals}) == len(signals), 'duplicate SAIF signal path')
    return dict(path=str(Path(path).resolve()), sha256=sha(path), timescale_seconds=str(tick_seconds),
                duration_ticks=int(duration), duration_seconds=str(duration*tick_seconds), signals=signals)


PROBE_EXPECTED = {
    'first': {'clk': (20, 20, 8), 'q': (20, 20, 4),
              'count[0]': (20, 20, 4), 'count[1]': (20, 20, 2),
              'count[2]': (13, 27, 1), 'count[3]': (40, 0, 0)},
    'second': {'clk': (20, 20, 8), 'q': (20, 20, 4),
               'count[0]': (20, 20, 4), 'count[1]': (20, 20, 2),
               'count[2]': (33, 7, 1), 'count[3]': (0, 40, 0)},
}
PROBE_EXPECTED['cumulative'] = {name: tuple(a+b for a, b in zip(values, PROBE_EXPECTED['second'][name]))
                                for name, values in PROBE_EXPECTED['first'].items()}


def match_probe(activity, expected):
    expected_duration_ns = Decimal(80 if expected == 'cumulative' else 40)
    if Decimal(activity['duration_seconds']) != expected_duration_ns*UNITS['ns']:
        return False
    for name, values in PROBE_EXPECTED[expected].items():
        found = [s for s in activity['signals'] if s['path'].split('/')[-1] == name]
        if not found:
            return False
        for signal in found:
            if signal['TX'] or signal.get('TZ', 0) or signal.get('TB', 0):
                return False
            actual = (Decimal(signal['T0'])*Decimal(activity['timescale_seconds'])/UNITS['ns'],
                      Decimal(signal['T1'])*Decimal(activity['timescale_seconds'])/UNITS['ns'], signal['TC'])
            if actual != values:
                return False
    return True


def probe_signature(activity):
    return {key: activity[key] for key in ['timescale_seconds', 'duration_ticks', 'signals']}


def classify_probe(directory):
    directory = Path(directory)
    first = read_saif(directory/'all/first.saif')
    second = read_saif(directory/'second/final.saif')
    require(match_probe(first, 'first'), 'first isolated window differs from known circuit')
    require(match_probe(second, 'second'), 'second isolated window differs from known circuit')
    observations, files = {}, [first, second]

    def observe(path):
        try:
            result = read_saif(path, allow_zero=True)
            files.append(result)
            return result
        except (ValueError, InvalidOperation, OSError) as error:
            observations[str(path.relative_to(directory))] = dict(error=str(error))
            return None

    def report_effect(before, after):
        if after is None:
            return 'unrecognized_or_empty_output'
        if probe_signature(before) == probe_signature(after):
            return 'preserved'
        if after['duration_ticks'] == 0 and all(not any(s.get(k, 0) for k in ['T0','T1','TX','TZ','TC']) for s in after['signals']):
            return 'cleared_by_report'
        return 'changed_or_unrecognized'

    repeat = observe(directory/'all/first_repeat.saif')
    first_effect = report_effect(first, repeat)
    semantics, effects = {}, {}
    for mode in ['all', 'combined', 'second']:
        final = observe(directory/mode/'final.saif')
        idle = observe(directory/mode/'after_idle.saif')
        if final is None:
            semantics[mode] = 'unrecognized_or_empty_output'
            effects[mode] = 'unrecognized_or_empty_output'
            continue
        matches = [name for name in ['first', 'second', 'cumulative'] if match_probe(final, name)]
        semantics[mode] = matches[0] if len(matches) == 1 else 'unrecognized'
        effects[mode] = report_effect(final, idle)
    require(semantics['second'] == 'second', 'isolated second window differs')
    return dict(status='VERIFIED_SINGLE_WINDOW', first_report_effect=first_effect,
                report_preserves_counters=(first_effect == 'preserved'),
                final_report_semantics=semantics, stopped_report_effect=effects, observations=observations,
                multi_window_accumulates_without_idle=(semantics['combined'] == 'cumulative'),
                recommendation='one fresh simulation process and one SAIF window per formal task; never subtract SAIF files',
                files=[{k:v for k,v in value.items() if k != 'signals'} for value in files])


def execute(command, cwd, log, timeout):
    with Path(log).open('w') as output:
        output.write(json.dumps([str(x) for x in command])+'\n')
        output.flush()
        result = subprocess.run([str(x) for x in command], cwd=str(cwd), stdout=output,
                                stderr=subprocess.STDOUT, timeout=timeout)
    require(result.returncode == 0, 'command failed; see '+str(log))
    content = Path(log).read_text(errors='replace')
    require(not re.search(r'undefined system task|unknown system task|Error-\[|Fatal:', content, re.I),
            'EDA diagnostic failure; see '+str(log))
    return content


def run_probe(args):
    out = Path(args.out).resolve()
    require(not out.exists(), 'probe output must be new to prevent stale SAIF reuse')
    out.mkdir(parents=True)
    vcs = shutil.which(args.vcs)
    require(vcs, 'VCS executable unavailable: '+args.vcs)
    source = Path(args.source).resolve()
    require(source.is_file(), 'probe source missing')
    report = dict(schema='xu-saif-capability-probe-v2', created_utc=datetime.now(timezone.utc).isoformat(),
                  source=dict(path=str(source), sha256=sha(source)), vcs=str(Path(vcs).resolve()), recipes={})
    recipes = ['debug', 'coverage'] if args.recipe == 'both' else [args.recipe]
    policies = (['default', 'rtl_on', 'rtl_sv', 'on_sv', 'union'] if args.monitor_policy == 'all' else [args.monitor_policy])
    for recipe in recipes:
        directory = out/recipe
        directory.mkdir()
        command = [vcs, '-full64', '-sverilog', '-debug_access+all', '-top', 'xu_activity_probe',
                   '-Mdir='+str(directory/'csrc'), '-o', str(directory/'simv')]
        if recipe == 'coverage':
            command += ['-cm', 'tgl']
        command += [str(source)]
        result = dict(compile_command=command, status='FAILED', policies={})
        try:
            execute(command, directory, directory/'compile.log', args.timeout)
            result['binary_sha256'] = sha(directory/'simv')
            for policy in policies:
                policy_dir = directory/policy
                policy_dir.mkdir()
                observed = dict(status='FAILED')
                try:
                    for mode in ['all', 'combined', 'second']:
                        run_dir = policy_dir/mode
                        run_dir.mkdir()
                        log = execute([directory/'simv', '+PROBE_MODE='+mode, '+PROBE_POLICY='+policy],
                                      run_dir, run_dir/'simulation.log', args.timeout)
                        require(log.count('XU_ACTIVITY_PROBE_FINISHED mode='+mode) == 1, 'probe completion marker missing')
                    # Keep diagnostics even when incomplete monitoring correctly fails the known-state test.
                    observed['activity_inventory'] = []
                    for mode, name in [('all','first'), ('combined','final'), ('second','final')]:
                        value = read_saif(policy_dir/mode/(name+'.saif'))
                        observed['activity_inventory'].append(dict(mode=mode, duration_seconds=value['duration_seconds'],
                                                                   signals=value['signals']))
                    observed.update(classify_probe(policy_dir))
                except (ValueError, InvalidOperation, OSError, subprocess.TimeoutExpired) as error:
                    observed['error'] = str(error)
                result['policies'][policy] = observed
                write_json(out/'probe.json', dict(report, recipes=dict(report['recipes'], **{recipe:result})))
            result['status'] = ('VERIFIED_SINGLE_WINDOW' if any(p['status'] == 'VERIFIED_SINGLE_WINDOW'
                                for p in result['policies'].values()) else 'FAILED')
        except (ValueError, InvalidOperation, OSError, subprocess.TimeoutExpired) as error:
            result['error'] = str(error)
        report['recipes'][recipe] = result
        write_json(out/'probe.json', report)
    report['status'] = ('VERIFIED_SINGLE_WINDOW' if any(r['status'] == 'VERIFIED_SINGLE_WINDOW'
                         for r in report['recipes'].values()) else 'FAILED')
    write_json(out/'probe.json', report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report['status'] == 'VERIFIED_SINGLE_WINDOW' else 1



def vcd_to_saif(source, destination, begin, end, scope):
    """Stream digital VCD into one task SAIF; keep hierarchy and every bus bit.

    Snapshot directives initialize values, never fabricate toggle events. Known
    0<->1 changes count as TC; time in X/Z remains explicit TX/TZ. The selected
    physical interval is [begin,end); no timestamp or frequency scaling occurs.
    """
    require(type(begin) is int and type(end) is int and 0 <= begin < end, 'invalid VCD window')
    require(scope and not any(c in scope for c in '*?'), 'an exact full-SoC hierarchy scope is required')
    source_hash = hashlib.sha256()
    source_bytes = [0]

    def tokens():
        for line in source:
            raw = line.encode('ascii')
            source_hash.update(raw)
            source_bytes[0] += len(raw)
            for token in line.split():
                yield token

    stream = iter(tokens())
    scopes, records, definitions, unsupported = [], {}, [], []
    timescale = None

    def directive():
        values = []
        for token in stream:
            if token == '$end':
                return values
            values.append(token)
        raise ValueError('unterminated VCD directive')

    for token in stream:
        require(token.startswith('$'), 'unexpected VCD header token')
        values = directive()
        if token == '$scope':
            require(len(values) == 2, 'invalid VCD scope')
            scopes.append(values[1].lstrip('\\'))
        elif token == '$upscope':
            require(scopes, 'unbalanced VCD scope')
            scopes.pop()
        elif token == '$timescale':
            match = re.fullmatch(r'(1|10|100)\s*(s|ms|us|ns|ps|fs)', ''.join(values))
            require(match is not None, 'unsupported VCD timescale')
            timescale = (int(match[1]), match[2])
        elif token == '$var':
            require(len(values) in [4, 5], 'invalid VCD variable declaration')
            kind, width_text, code, name = values[:4]
            width = int(width_text)
            path = '/'.join(scopes+[name.lstrip('\\')])
            if not ('/'.join(scopes) == scope or '/'.join(scopes).startswith(scope+'/')):
                continue
            require(width > 0, 'invalid VCD width')
            if kind in ['real', 'realtime', 'string', 'event']:
                unsupported.append(dict(path=path, kind=kind))
                continue
            require(kind in ['wire', 'reg', 'integer', 'time', 'parameter', 'logic', 'bit',
                             'tri', 'tri0', 'tri1', 'supply0', 'supply1', 'wand', 'wor', 'trireg', 'uwire'],
                    'unsupported digital VCD type: '+kind)
            if code in records:
                require(records[code]['width'] == width, 'VCD aliases have different widths')
            else:
                records[code] = dict(width=width, state='x'*width, last=0,
                                     stats=[[0, 0, 0, 0, 0] for _ in range(width)])
            if len(values) == 5:
                bounds = re.fullmatch(r'\[(-?\d+):(-?\d+)\]', values[4])
                require(bounds is not None and abs(int(bounds[1])-int(bounds[2]))+1 == width,
                        'VCD vector range disagrees with width')
                start, stop = int(bounds[1]), int(bounds[2])
                indices = list(range(start, stop+(1 if stop >= start else -1), 1 if stop >= start else -1))
            else:
                indices = list(range(width-1, -1, -1))
            names = [name.lstrip('\\')] if width == 1 and len(values) == 4 else [name.lstrip('\\')+'['+str(i)+']' for i in indices]
            definitions.append(dict(scopes=list(scopes), names=names, code=code))
        elif token == '$enddefinitions':
            break
    require(timescale is not None and definitions and records, 'VCD lacks timescale/full-scope digital signals')
    time, largest_time, dump_enabled, snapshot = 0, 0, True, False

    def integrate(record, until):
        ticks = max(0, min(until, end)-max(record['last'], begin))
        if ticks:
            for bit, state in enumerate(record['state']):
                record['stats'][bit]['01xz'.index(state)] += ticks
        record['last'] = until

    for token in stream:
        if token.startswith('#'):
            new_time = int(token[1:])
            require(new_time >= time, 'VCD time moved backwards')
            require(dump_enabled or max(time, begin) >= min(new_time, end), 'VCD recording disabled inside task window')
            time, largest_time = new_time, max(largest_time, new_time)
            continue
        if token in ['$dumpvars', '$dumpon', '$dumpall', '$dumpoff']:
            require(not snapshot, 'nested VCD snapshot')
            if token == '$dumpoff':
                require(not begin <= time < end, 'VCD dumpoff inside task window')
                dump_enabled = False
            elif token == '$dumpon':
                dump_enabled = True
            snapshot = True
            continue
        if token == '$end':
            require(snapshot, 'unexpected VCD $end')
            snapshot = False
            continue
        if token.startswith('$'):
            directive()
            continue
        if token[0] in 'bBrRsS':
            value, code = token[1:].lower(), next(stream, None)
            require(code is not None, 'VCD vector identifier missing')
        else:
            value, code = token[0].lower(), token[1:]
        if code not in records or time >= end:
            continue
        record = records[code]
        require(value and set(value) <= set('01xz'), 'non-digital value on digital VCD signal')
        require(len(value) <= record['width'], 'VCD value wider than declaration')
        fill = value[0] if value[0] in 'xz' else '0'
        value = value.rjust(record['width'], fill)
        if value == record['state']:
            continue
        integrate(record, time)
        if not snapshot and begin <= time < end:
            for bit, (old, new) in enumerate(zip(record['state'], value)):
                if old in '01' and new in '01' and old != new:
                    record['stats'][bit][4] += 1
        record['state'] = value
    require(not snapshot and largest_time >= end, 'VCD ends before task end / in snapshot')
    for record in records.values():
        integrate(record, end)
        require(all(sum(bit[:4]) == end-begin for bit in record['stats']), 'VCD dwell accounting differs from task duration')
    tree = {}
    paths = set()
    for definition in definitions:
        branch = tree
        for name in definition['scopes']:
            branch = branch.setdefault(name, {})
        for bit, name in enumerate(definition['names']):
            path = '/'.join(definition['scopes']+[name])
            require(path not in paths, 'duplicate VCD signal path')
            paths.add(path)
            branch.setdefault(None, []).append((name, records[definition['code']]['stats'][bit]))

    def atom(name):
        # SAIF escapes delimiters in net names, while hierarchy remains INSTANCE nodes.
        return re.sub(r'([\\()\s\[\]])', r'\\\1', name)

    def emit_tree(output, branch, depth):
        indent = '  '*depth
        nets = branch.get(None, [])
        if nets:
            output.write(indent+'(NET\n')
            for name, stats in nets:
                output.write(indent+'  ('+atom(name)+' '+' '.join('({} {})'.format(key, number)
                             for key, number in zip(['T0', 'T1', 'TX', 'TZ', 'TC'], stats))+')\n')
            output.write(indent+')\n')
        for name in sorted(key for key in branch if key is not None):
            output.write(indent+'(INSTANCE '+atom(name)+'\n')
            emit_tree(output, branch[name], depth+1)
            output.write(indent+')\n')

    with Path(destination).open('w') as output:
        output.write('(SAIFILE\n  (SAIFVERSION "2.0")\n  (DIRECTION "backward")\n'
                     '  (DESIGN)\n  (DATE "'+datetime.now(timezone.utc).isoformat()+'")\n'
                     '  (VENDOR "xu")\n  (PROGRAM_NAME "xu_soc_activity.py streaming VCD")\n'
                     '  (VERSION "1")\n  (DIVIDER /)\n  (TIMESCALE {} {})\n  (DURATION {})\n'.format(
                         timescale[0], timescale[1], end-begin))
        emit_tree(output, tree, 1)
        output.write(')\n')
    return dict(schema='xu-vcd-to-saif-v1', status='CONVERTED_NOT_POWER_QUALIFIED',
                source_sha256=source_hash.hexdigest(), source_bytes=source_bytes[0],
                source_scope=scope, begin_tick=begin, end_tick=end,
                timescale_seconds=str(Decimal(timescale[0])*UNITS[timescale[1]]),
                duration_seconds=str((end-begin)*Decimal(timescale[0])*UNITS[timescale[1]]),
                digital_signal_bits=len(paths), independent_vcd_codes=len(records),
                omitted_nondigital_model_objects=unsupported,
                saif=dict(path=str(Path(destination).resolve()), sha256=sha(destination)),
                transition_policy='TC counts known 0<->1 transitions in [begin,end); snapshots do not count; TX/TZ remain explicit',
                limitation='Digital activity only. Full-SoC pin annotation, mapped-net coverage and SRAM Liberty internal power still require PT review.')

REQUIRED_SCOPES = {'cpu', 'accelerator', 'interconnect', 'shared', 'itcm', 'dtcm', 'accelerator_weights'}
REQUIRED_MEMORY_BITS = {'shared': 524288*8, 'itcm': 65536*8,
                        'dtcm': 65536*8, 'accelerator_weights': 32768*8}


def identity(record, label):
    require(isinstance(record, dict), label+' file identity missing')
    path = Path(record.get('path', ''))
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), label+' needs an absolute regular file')
    require(re.fullmatch(r'[0-9a-f]{64}', record.get('sha256', '')) is not None,
            label+' SHA256 missing')
    require(sha(path) == record['sha256'], label+' SHA256 differs')
    return path


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def audit_macro_power(record, task, configuration, total_power):
    path = identity(record, 'SRAM power/port review')
    review = json.loads(path.read_text())
    require(review.get('schema') == 'xu-sram-power-coverage-v1' and review.get('status') == 'REVIEWED',
            'SRAM power/port review incomplete')
    require(review.get('saif_sha256') == task['saif']['sha256'] and
            review.get('netlist_sha256') == configuration['netlist']['sha256'],
            'SRAM review belongs to different SAIF/netlist')
    require(sorted(review.get('library_sha256', [])) == sorted(x['sha256'] for x in configuration['libraries']),
            'SRAM review uses different libraries/PVT')
    groups = review.get('groups', [])
    require(len(groups) == 4 and {g.get('name') for g in groups} == set(REQUIRED_MEMORY_BITS),
            'SRAM power review requires all four memory groups')
    memory = {g['name']:g for g in configuration['memories']}
    memory_power = Decimal(0)
    for group in groups:
        count = memory[group['name']]['macro_count']
        require(group.get('expected_count') == count and group.get('observed_count') == count and
                group.get('library_power_modeled_count') == count, 'unmodeled/missing SRAM macro: '+group['name'])
        require(group.get('missing_input_pin_count') == 0 and group.get('unknown_input_pin_count') == 0,
                'SRAM input pin activity is missing/unknown: '+group['name'])
        power = Decimal(str(group.get('total_power_w', 'NaN')))
        require(power.is_finite() and power > 0, 'SRAM internal+switching+leakage power is absent/zero')
        memory_power += power
    require(memory_power <= total_power, 'disjoint SRAM groups exceed whole-SoC power')
    return dict(path=str(path), sha256=record['sha256'], total_sram_power_w=str(memory_power))


def audit_cache_policy(record, task, freeze):
    path = identity(record, 'task cache policy review')
    review = json.loads(path.read_text())
    require(review.get('schema') == 'xu-task-cache-policy-review-v1' and review.get('status') == 'REVIEWED',
            'task cache invalidation/reload review incomplete')
    require(review.get('task_id') == task['task_id'] and review.get('configuration_sha256') == freeze and
            review.get('saif_sha256') == task['saif']['sha256'], 'cache review belongs to different task/configuration/SAIF')
    for field in ['task_cache_invalidated_before_begin', 'complete_parameter_upload_inside_window', 'no_cross_task_reuse']:
        require(review.get(field) is True, 'cache policy not proven: '+field)
    evidence = review.get('evidence', [])
    require(evidence, 'cache invalidation/reload needs original evidence, not shared preload marker alone')
    for item in evidence:
        identity(item, 'cache review original evidence')
    return dict(path=str(path), sha256=record['sha256'])


def audit_energy(manifest):
    require(manifest.get('schema') == 'xu-soc-activity-energy-v1', 'energy manifest schema differs')
    configuration = manifest.get('configuration', {})
    require(configuration.get('nominal_hz') == 150000000, 'formal collection must use nominal 150 MHz')
    require(configuration.get('power_method') == 'averaged', 'this flow requires per-task averaged power')
    require(configuration.get('pvt') and configuration.get('interconnect_model'), 'PVT and interconnect model must be disclosed')
    for key in ['netlist', 'constraints', 'firmware', 'testbench']:
        identity(configuration.get(key), 'configuration '+key)
    libraries = configuration.get('libraries', [])
    require({x.get('role') for x in libraries} >= {'standard_cell', 'sram'}, 'same-PVT cell/SRAM libraries required')
    for library in libraries:
        identity(library, 'library')
    memories = configuration.get('memories', [])
    require(len(memories) == 4 and {g.get('name') for g in memories} == set(REQUIRED_MEMORY_BITS), 'memory inventory incomplete')
    for memory in memories:
        require(memory.get('logical_bits') == REQUIRED_MEMORY_BITS[memory['name']] and
                type(memory.get('macro_count')) is int and memory['macro_count'] > 0,
                'memory logical capacity or macro count missing')
    groups = configuration.get('activity_scopes', [])
    require(len(groups) == len(REQUIRED_SCOPES) and {g.get('name') for g in groups} == REQUIRED_SCOPES,
            'full CPU/accelerator/interconnect/all-SRAM activity scopes are required')
    prefixes = [g.get('prefix', '') for g in groups]
    require(len(set(prefixes)) == len(prefixes) and all('/' in x and not any(c in x for c in '*?') for x in prefixes),
            'activity scopes need distinct exact hierarchy prefixes')
    freeze = canonical_hash(configuration)
    tasks = manifest.get('tasks', [])
    require(len(tasks) == 12 and [t.get('task_id') for t in tasks] == list(range(12)),
            'all twelve tasks, once and in order, are required')
    rows, total_energy, total_duration = [], Decimal(0), Decimal(0)
    for task in tasks:
        require(task.get('configuration_sha256') == freeze, 'task configuration differs from frozen configuration')
        saif_path = identity(task.get('saif'), 'task SAIF')
        activity = read_saif(saif_path)
        identity(task.get('input_manifest'), 'task input/parameter manifest')
        reload_log = identity(task.get('cache_reload_log'), 'cache reload evidence').read_text()
        marker = 'XU_CACHE_RELOAD task={} done_before_begin=1 scope=shared_fixture'.format(task['task_id'])
        require(reload_log.splitlines().count(marker) == 1, 'task shared-fixture preload marker missing/duplicate')
        cache_review = audit_cache_policy(task.get('cache_review'), task, freeze)
        window = task.get('window', {})
        require(window.get('start_event') == 'first_input_or_parameter_read_accepted' and
                window.get('end_event') == 'final_y_write_response_retired' and
                window.get('convention') == 'edge_to_edge', 'task physical start/end event contract differs')
        begin, end = window.get('begin_tick'), window.get('end_tick')
        require(type(begin) is int and type(end) is int and 0 <= begin < end, 'invalid physical task timestamps')
        tick = Decimal(str(window.get('timescale_seconds', 'NaN')))
        require(tick.is_finite() and tick > 0, 'window timestamp timescale missing')
        duration = (end-begin)*tick
        require(duration == Decimal(activity['duration_seconds']), 'SAIF duration differs from physical task window')
        period = Decimal(str(window.get('hf_period_seconds', 'NaN')))
        nominal_period = Decimal(1)/Decimal(150000000)
        require(period.is_finite() and abs(period/nominal_period-1) <= Decimal('0.000001'),
                'source activity clock is not 150 MHz within 1 ppm; implicit 4 ns rescaling is forbidden')
        clocks = [s for s in activity['signals'] if s['path'] == configuration.get('hf_clock_path')]
        require(clocks, 'actual source HF clock signal absent from SAIF')
        expected_edges = 2*duration/period
        require(all(abs(Decimal(s['TC'])-expected_edges) <= 2 and not s['TX'] and not s.get('TZ', 0) for s in clocks),
                'source SAIF HF clock toggle rate differs from 150 MHz')
        boundary_log = identity(task.get('boundary_log'), 'task boundary log').read_text()
        expected = ['XU_ACTIVITY_BEGIN task={} tick={}'.format(task['task_id'], begin),
                    'XU_ACTIVITY_END task={} tick={}'.format(task['task_id'], end)]
        lines = boundary_log.splitlines()
        require(all(lines.count(line) == 1 for line in expected) and lines.index(expected[0]) < lines.index(expected[1]),
                'physical boundary log does not match timestamps')
        scope_rows = []
        for group in groups:
            signals = [s for s in activity['signals'] if s['path'].startswith(group['prefix']+'/')]
            require(len(signals) >= 2, 'SAIF scope absent/ports-only: '+group['name'])
            toggles = sum(s['TC'] for s in signals)
            require(toggles > 0, 'SAIF scope has no observed activity: '+group['name'])
            unknown = sum(s['TX']+s.get('TZ', 0)+s.get('TB', 0) for s in signals)
            scope_rows.append(dict(name=group['name'], signals=len(signals), toggles=toggles,
                                   unknown_bit_time_fraction=str(Decimal(unknown)/(len(signals)*activity['duration_ticks']))))
        power = task.get('power', {})
        watts = Decimal(str(power.get('total_w', 'NaN')))
        require(watts.is_finite() and watts > 0, 'whole-SoC power must be positive watts')
        for key in ['report', 'activity_before', 'activity_after', 'annotation_review']:
            identity(power.get(key), 'task power '+key)
        require(power.get('unannotated_policy') == 'propagate_and_review',
                'unannotated logic must be propagated and reviewed; zero is forbidden')
        macro_review = audit_macro_power(power.get('sram_review'), task, configuration, watts)
        energy = watts*duration
        rows.append(dict(task_id=task['task_id'], duration_seconds=str(duration), average_power_w=str(watts),
                         energy_joules=str(energy), saif_sha256=activity['sha256'], scopes=scope_rows,
                         sram_review=macro_review, cache_review=cache_review))
        total_energy += energy
        total_duration += duration
    return dict(schema='xu-soc-activity-energy-result-v1', status='AUDITED_ESTIMATE_NOT_CONTEST_QUALIFIED',
                configuration_sha256=freeze, nominal_hz=150000000, pvt=configuration['pvt'],
                interconnect_model=configuration['interconnect_model'], task_count=12, tasks=rows,
                total_duration_seconds=str(total_duration), total_energy_joules=str(total_energy),
                duration_weighted_power_w=str(total_energy/total_duration),
                energy_per_task_joules=str(total_energy/12),
                tasks_per_second=str(Decimal(12)/total_duration),
                limitation='Identity/scope/duration/energy audit only. Actual PT annotation coverage, SRAM Liberty power completeness, '
                           'STA, numerical correctness and mapped functional equivalence require independent review. '
                           'Power values are explicitly supplied in watts and bound to raw reports; this tool does not infer report units.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command')
    probe = sub.add_parser('probe', help='run small local/server VCS capability experiment')
    probe.add_argument('--vcs', default='vcs')
    probe.add_argument('--source', default=str(ROOT/'tools/ppa/xu_activity_probe.sv'))
    probe.add_argument('--out', required=True)
    probe.add_argument('--recipe', choices=['debug', 'coverage', 'both'], default='both')
    probe.add_argument('--monitor-policy', choices=['default', 'rtl_on', 'rtl_sv', 'on_sv', 'union', 'all'], default='all')
    probe.add_argument('--timeout', type=int, default=300)
    inspect = sub.add_parser('inspect-saif', help='validate SAIF dwell times and inventory annotated scopes')
    inspect.add_argument('saif')
    inspect.add_argument('--out')
    energy = sub.add_parser('energy', help='audit frozen twelve-task SAIF/power evidence and compute energy')
    energy.add_argument('manifest')
    energy.add_argument('--out', required=True)
    convert = sub.add_parser('vcd-to-saif', help='stream a full-scope digital VCD into one exact-window SAIF')
    convert.add_argument('--vcd', required=True, help='VCD file or - for stdin/FIFO pipeline')
    convert.add_argument('--saif', required=True)
    convert.add_argument('--out', required=True, help='conversion identity JSON')
    convert.add_argument('--begin', required=True, type=int, help='physical start timestamp in original VCD ticks')
    convert.add_argument('--end', required=True, type=int, help='physical end timestamp in original VCD ticks')
    convert.add_argument('--scope', required=True, help='exact full-SoC VCD hierarchy prefix, / separated')
    args = parser.parse_args(argv)
    try:
        if args.command == 'probe':
            return run_probe(args)
        if args.command == 'vcd-to-saif':
            if args.vcd == '-':
                result = vcd_to_saif(sys.stdin, args.saif, args.begin, args.end, args.scope)
            else:
                with Path(args.vcd).open(encoding='ascii', newline='') as source:
                    result = vcd_to_saif(source, args.saif, args.begin, args.end, args.scope)
            write_json(args.out, result)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == 'energy':
            result = audit_energy(json.loads(Path(args.manifest).read_text()))
            write_json(args.out, result)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == 'inspect-saif':
            result = read_saif(args.saif)
            result['signal_count'] = len(result.pop('signals'))
            if args.out:
                write_json(args.out, result)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        parser.error('choose a subcommand')
    except (ValueError, InvalidOperation, OSError, subprocess.TimeoutExpired) as error:
        print('xu_soc_activity: '+str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
