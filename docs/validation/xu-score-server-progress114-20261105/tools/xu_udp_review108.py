#!/usr/bin/env python3
"""xu actual108: read-only original UDP callers and native behavior probe.

Vendor bodies are written only to a separate private directory. Export only the
output metadata/logs/testbench, never that private directory. No model is selected
as a fix and no qualification is inferred from compilation or finite simulation.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

NET = '9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892'
STD = '9ceaac7085f267c9a2da19d86aa9d88ddb25894df4b2485e32d13e04d0e46581'
NEG = 'ad8e713747f3c95c5e2ecd4ddc6d50d5e2914d895d73e0b37a7b6900561227b2'
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|\\[^\s]+|[A-Za-z_$][\w$]*|\d+(?:\s*\x27\s*[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ?]+)?|\x27\s*[01xXzZ]|===|!==|==|!=|<=|>=|&&|\|\||<<|>>|[^\s]')
COMMENT = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"', re.S)
NAME = re.compile(r'^(?:[A-Za-z_$][\w$]*|\\[^\s]+)$')
BASE_DEFINES = ['ARM_UD_MODEL', 'DISABLE_SV_ASSERTION']
MODES = [('actual_default', []), ('FUNCTIONAL', ['FUNCTIONAL']),
         ('functional', ['functional']), ('both_functional_symbols', ['FUNCTIONAL', 'functional'])]


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def ident(path):
    path = Path(path).resolve()
    body = path.read_bytes()
    return dict(path=str(path), bytes=len(body), sha256=sha(body))


def dump(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def clean(text):
    return COMMENT.sub(lambda match: match.group() if match.group().startswith('"') else
                       ''.join('\n' if c == '\n' else ' ' for c in match.group()), text)


def tokens(text):
    return [match.group() for match in TOKEN.finditer(text)]


def balanced(values, start, opening='(', closing=')'):
    need(start < len(values) and values[start] == opening, 'balanced opener missing')
    level = 1
    for index in range(start + 1, len(values)):
        level += (values[index] == opening) - (values[index] == closing)
        if level == 0:
            return index
    raise ValueError('unterminated balanced expression')


def preprocess(text, extra=()):
    defined = set(BASE_DEFINES + list(extra))
    stack = []
    active = True
    result = []
    for line in text.splitlines(keepends=True):
        match = re.match(r'^[ \t]*`(ifdef|ifndef|elsif|else|endif|define|undef)\b[ \t]*([A-Za-z_$][\w$]*)?', line)
        if match:
            directive, symbol = match.groups()
            if directive in ['ifdef', 'ifndef']:
                condition = (symbol in defined) if directive == 'ifdef' else (symbol not in defined)
                stack.append([active, condition])
                active = active and condition
            elif directive == 'elsif':
                need(stack, 'unmatched elsif')
                parent, taken = stack[-1]
                condition = not taken and symbol in defined
                stack[-1][1] = taken or condition
                active = parent and condition
            elif directive == 'else':
                need(stack, 'unmatched else')
                parent, taken = stack[-1]
                active = parent and not taken
                stack[-1][1] = True
            elif directive == 'endif':
                need(stack, 'unmatched endif')
                active = stack.pop()[0]
            elif directive == 'define' and active:
                defined.add(symbol)
            elif directive == 'undef' and active:
                defined.discard(symbol)
            result.append(''.join('\n' if c == '\n' else ' ' for c in line))
        else:
            result.append(line if active else ''.join('\n' if c == '\n' else ' ' for c in line))
    need(not stack, 'unclosed conditional compilation')
    return ''.join(result)


def modules(text):
    result = {}
    for match in re.finditer(r'\bmodule\s+(\\[^\s]+|[A-Za-z_$][\w$]*)\b(.*?)\bendmodule\b', text, re.S):
        name = match.group(1)
        need(name not in result, 'duplicate active module ' + name)
        result[name] = dict(tokens=tokens(match.group()), line=text.count('\n', 0, match.start()) + 1)
    return result


def instances(values, names):
    """Same strict named-port instance traversal used for actual101 direction audit."""
    result = []
    index = 0
    while index + 2 < len(values):
        reference = values[index]
        if reference not in names or (index > 0 and values[index - 1] == 'module'):
            index += 1
            continue
        cursor = index + 1
        if values[cursor] == '#':
            cursor = balanced(values, cursor + 1) + 1
        if not NAME.match(values[cursor]):
            index += 1
            continue
        instance = values[cursor]
        cursor += 1
        if values[cursor] == '[':
            cursor = balanced(values, cursor, '[', ']') + 1
        if values[cursor] != '(':
            index += 1
            continue
        end = balanced(values, cursor)
        result.append(dict(reference=reference, instance=instance))
        index = end + 1
    return result


def primitive_calls(values, names):
    """UDP instance names are optional; preserve anonymous declarations too."""
    result = []
    for index, reference in enumerate(values):
        if reference not in names:
            continue
        cursor = index + 1
        if cursor >= len(values):
            continue
        if values[cursor] == '#':
            cursor += 1
            if values[cursor] == '(':
                cursor = balanced(values, cursor) + 1
            else:
                cursor += 1
        if values[cursor] == '(':
            instance = '<anonymous-token-%d>' % index
        elif NAME.match(values[cursor]) and values[cursor + 1] == '(':
            instance = values[cursor]
            cursor += 1
        else:
            raise ValueError('unsupported UDP instantiation form needs review: ' + reference)
        balanced(values, cursor)
        result.append(dict(reference=reference, instance=instance))
    return result


def primitive_records(text):
    result = defaultdict(list)
    for match in re.finditer(r'\bprimitive\s+([A-Za-z_$][\w$]*)\b.*?\bendprimitive\b', text, re.S):
        name = match.group(1)
        values = tokens(match.group())
        end = balanced(values, 2)
        ports = [v for v in values[3:end] if v != ',']
        need(ports and all(NAME.match(v) for v in ports), 'ambiguous UDP header')
        table = values[values.index('table') + 1:values.index('endtable')]
        rows = []
        current = []
        for value in table:
            if value == ';':
                rows.append(current)
                current = []
            else:
                current.append(value)
        need(not current, 'unterminated UDP table row')
        result[name].append(dict(name=name, line=text.count('\n', 0, match.start()) + 1,
                                 ports=ports, body=match.group(), tokens=values, rows=rows))
    return result


def fingerprint(record):
    return dict(line=record['line'], port_count=len(record['ports']), table_row_count=len(record['rows']),
                complete_token_count=len(record['tokens']), complete_token_sha256=sha(
                    json.dumps(record['tokens'], separators=(',', ':')).encode()),
                table_row_set_sha256=sha(json.dumps(sorted(set(tuple(r) for r in record['rows'])),
                                                  separators=(',', ':')).encode()))


def row_summary(rows):
    return dict(count=len(rows), sequential_rows=sum(r.count(':') == 2 for r in rows),
                edge_sensitive_rows=sum('(' in r or '*' in r or any(v in r for v in ['r', 'f', 'p', 'n']) for r in rows),
                output_symbol_counts=dict(Counter(r[-1] for r in rows)),
                row_token_hashes=sorted(sha(json.dumps(r, separators=(',', ':')).encode()) for r in rows))


def source_review(standard_body, mapped_body, extra):
    source = preprocess(clean(standard_body), extra)
    stdmods = modules(source)
    netmods = modules(preprocess(clean(mapped_body)))
    primitives = primitive_records(source)
    duplicates = {name: records for name, records in primitives.items() if len(records) > 1}
    names = set(stdmods) | set(netmods) | {'RAMSP1024X16'}
    graph = {name: instances(row['tokens'], names) for name, row in netmods.items()}
    declarations = Counter(row['reference'] for values in graph.values() for row in values)
    callers = defaultdict(list)
    for name, row in stdmods.items():
        for call in primitive_calls(row['tokens'], set(duplicates)):
            callers[call['reference']].append(dict(cell=name, primitive_instance=call['instance'],
                                                   cell_definition_line=row['line']))
    relevant = {row['cell'] for values in callers.values() for row in values}
    paths = defaultdict(list)
    top = 'xu_soc_ppa_top'
    need(top in netmods, 'fixed mapped top absent')

    def visit(name, parent, ancestors):
        need(name not in ancestors, 'recursive mapped hierarchy')
        for row in graph[name]:
            path = parent + '/' + row['instance']
            if row['reference'] in relevant:
                paths[row['reference']].append(path)
            if row['reference'] in netmods:
                visit(row['reference'], path, ancestors | {name})

    visit(top, top, set())
    review = []
    for name, records in sorted(duplicates.items()):
        need(len(records) == 2, 'expected exactly two duplicate definitions')
        a = set(tuple(row) for row in records[0]['rows'])
        b = set(tuple(row) for row in records[1]['rows'])
        cells = []
        for row in callers[name]:
            cell = row['cell']
            cells.append(dict(row, mapped_definition_instance_count=declarations[cell],
                              mapped_reachable_instance_count=len(paths[cell]),
                              mapped_reachable_paths=paths[cell]))
        review.append(dict(name=name, definitions=[fingerprint(r) for r in records],
                           complete_tokens_identical=records[0]['tokens'] == records[1]['tokens'],
                           same_port_order=records[0]['ports'] == records[1]['ports'],
                           first_only_rows=row_summary(sorted(a - b)), last_only_rows=row_summary(sorted(b - a)),
                           table_row_set_equal=a == b, direct_callers=cells,
                           unique_caller_cells=len({r['cell'] for r in cells}),
                           mapped_reachable_instance_count=sum(len(paths[c]) for c in {r['cell'] for r in cells})))
    return dict(status='ACTIVE_SOURCE_DEPENDENCY_REVIEW_NOT_FUNCTIONAL_QUALIFIED',
                active_module_count=len(stdmods), mapped_module_count=len(netmods),
                mapped_instance_declarations=sum(declarations.values()),
                active_primitive_definitions=sum(len(v) for v in primitives.values()),
                duplicates=review,
                limitations=['Source parser paths are not a VPI runtime proof.',
                             'Table row set differences are lexical structure, not standalone stateful equivalence.']), duplicates


def bench(name, ports, alias_a, alias_b):
    count = len(ports) - 1
    need(1 <= count <= 6, 'probe bounded to 1..6 scalar UDP inputs')
    arguments = ', '.join('p[%d]' % i for i in range(count))
    template = r'''`timescale 1ns/1ps
module tb_xu_udp108;
 localparam N=@@N@@;
 reg [N-1:0] p, v, base;
 wire original_q, first_q, last_q;
 integer i,j,k,a,b,steps=0,pair_diffs=0,original_last_diffs=0,original_first_diffs=0;
 integer q0=0,q1=0,qx=0;
 @@NAME@@ original_definition(original_q, @@ARGS@@);
 @@ALIASA@@ first_definition(first_q, @@ARGS@@);
 @@ALIASB@@ last_definition(last_q, @@ARGS@@);
 function [N-1:0] quad;
   input integer code;
   integer n;
   begin
     for(n=0;n<N;n=n+1) begin
       case(code % 4)
         0:quad[n]=1'b0; 1:quad[n]=1'b1; 2:quad[n]=1'bx; 3:quad[n]=1'bz;
       endcase
       code=code/4;
     end
   end
 endfunction
 task observe;
 begin
   #1; steps=steps+1;
   if(last_q===1'b0)q0=q0+1;else if(last_q===1'b1)q1=q1+1;else qx=qx+1;
   if(first_q !== last_q) begin
     pair_diffs=pair_diffs+1;
     if(pair_diffs <= 32)$display("XU_UDP108_DIFFERENCE step=%0d p=%b first=%b last=%b original=%b", steps,p,first_q,last_q,original_q);
   end
   if(original_q !== last_q)original_last_diffs=original_last_diffs+1;
   if(original_q !== first_q)original_first_diffs=original_first_diffs+1;
 end
 endtask
 initial begin
   p={N{1'bx}};observe;
   // Exhaustive binary predecessor -> 4-state target pairs, natural Q history.
   for(a=0;a<(1<<N);a=a+1)begin
     for(b=0;b<(1<<(2*N));b=b+1)begin
       p=a;observe;
       p=quad(b);observe;
     end
   end
   // All 4-state input vectors and single-input target symbols; restore base.
   for(a=0;a<(1<<(2*N));a=a+1)begin
     base=quad(a);p=base;observe;
     for(i=0;i<N;i=i+1)begin
       for(j=0;j<4;j=j+1)begin
         v=base;
         case(j)
           0:v[i]=1'b0;1:v[i]=1'b1;2:v[i]=1'bx;3:v[i]=1'bz;
         endcase
         p=v;observe;p=base;observe;
       end
     end
   end
   $display("XU_UDP108_RESULT steps=%0d pair_diffs=%0d original_last_diffs=%0d original_first_diffs=%0d last_q0=%0d last_q1=%0d last_qx=%0d",steps,pair_diffs,original_last_diffs,original_first_diffs,q0,q1,qx);
   $finish;
 end
endmodule
'''
    for key, value in {'@@N@@': str(count), '@@NAME@@': name, '@@ARGS@@': arguments,
                       '@@ALIASA@@': alias_a, '@@ALIASB@@': alias_b}.items():
        template = template.replace(key, value)
    return template


def run_probe(name, records, standard, vcs, out, private, extra=()):
    need(records[0]['ports'] == records[1]['ports'], 'cannot compare different port order')
    alias_a = 'xu108_first_' + name
    alias_b = 'xu108_last_' + name
    generated = []
    for record, alias in zip(records, [alias_a, alias_b]):
        body, count = re.subn(r'\bprimitive\s+' + re.escape(name) + r'\b',
                              'primitive ' + alias, record['body'], count=1)
        need(count == 1, 'private alias rename differs')
        generated.append(body)
    source = private / (name + '.v')
    source.write_text('\n'.join(generated) + '\n')
    test = out / 'tb.sv'
    test.write_text(bench(name, records[0]['ports'], alias_a, alias_b))
    command = [str(vcs), '-full64', '-sverilog', '-timescale=1ns/1ps', '-top', 'tb_xu_udp108']
    command += ['+define+' + define for define in BASE_DEFINES + list(extra)]
    command += [str(standard), str(source), str(test), '-Mdir=' + str(out / 'csrc'), '-o', str(out / 'simv')]
    with (out / 'vcs.log').open('xb') as log:
        compiled = subprocess.run(command, cwd=str(out), stdin=subprocess.DEVNULL, stdout=log,
                                  stderr=subprocess.STDOUT, timeout=600)
    result = dict(command=command, compile_returncode=compiled.returncode,
                  private_vendor_fragment_identity=ident(source), testbench=ident(test),
                  compile_log=ident(out / 'vcs.log'), qualification='NOT_QUALIFIED')
    need(compiled.returncode == 0, 'native UDP compile failed: ' + name)
    with (out / 'sim.log').open('xb') as log:
        simulated = subprocess.run([str(out / 'simv')], cwd=str(out), stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT, timeout=600)
    raw = (out / 'sim.log').read_text()
    matches = re.findall(r'^XU_UDP108_RESULT steps=(\d+) pair_diffs=(\d+) original_last_diffs=(\d+) original_first_diffs=(\d+) last_q0=(\d+) last_q1=(\d+) last_qx=(\d+)$', raw, re.M)
    need(simulated.returncode == 0 and len(matches) == 1, 'native UDP result missing/duplicate: ' + name)
    values = dict(zip(['steps', 'pair_diffs', 'original_last_diffs', 'original_first_diffs',
                       'last_q0', 'last_q1', 'last_qx'], map(int, matches[0])))
    need(values['steps'] > 1 and values['last_q0'] + values['last_q1'] + values['last_qx'] == values['steps'],
         'native UDP observation conservation differs')
    result.update(simulation_returncode=simulated.returncode, simulation_log=ident(out / 'sim.log'),
                  counters=values, last_definition_behavior_observed_for_every_step=values['original_last_diffs'] == 0,
                  status='FINITE_ORIGINAL_UDP_BEHAVIOR_OBSERVED_NOT_GENERAL_EQUIVALENCE',
                  limitations=['Natural initial Q=X; no forced Q, notifier suppression, model repair or gate-level functional acceptance.',
                               'Inputs sampled after 1ns settling; no analog delay, timing-check, SDF or simultaneous-event portability proof.',
                               'Finite sequence inequality is a counterexample; equality does not prove full stateful equivalence.'])
    dump(out / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=Path.home() / 'Desktop/xu-score-optimization-20261102')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--private-dir', type=Path)
    parser.add_argument('--vcs', type=Path, default=Path('/eda/synopsys/vcs/vcs_2020.03-SP2-6/bin/vcs'))
    args = parser.parse_args()
    base = args.base.resolve()
    out = args.out.resolve() if args.out else base / 'mapped-udp-review-20261104-108'
    private = args.private_dir.resolve() if args.private_dir else base / 'udp-definition-private-20261104-108'
    need(not out.exists() and not private.exists(), 'new output and private directory required')
    need(out != private and out not in private.parents and private not in out.parents, 'private vendor fragments must be outside exported output')
    out.mkdir(parents=True)
    private.mkdir(parents=True, mode=0o700)
    standard = base / 'standard-cell-model-private-20261104-90/scc40nll_vhsc40_rvt.v'
    negative = base / 'standard-cell-model-private-20261104-90/scc40nll_vhsc40_rvt_neg.v'
    mapped = base / 's2c-ppa-campaign-20261103-01/s2c/ppa/mapped.v'
    identities = [ident(path) for path in [standard, negative, mapped]]
    need([row['sha256'] for row in identities] == [STD, NEG, NET], 'frozen original model/net identities differ')
    state = dict(status='RUNNING_READ_ONLY_UDP_REVIEW', qualification='NOT_QUALIFIED', pid=os.getpid(),
                 started_epoch=time.time(), tool=ident(__file__), inputs_before=identities,
                 private_vendor_directory=str(private), source_body_exported=False, reviews=[], probes=[])
    dump(out / 'state.json', state)
    try:
        body = standard.read_text()
        negbody = negative.read_text()
        netbody = mapped.read_text()
        directives = sorted(set(re.findall(r'^\s*`(?:ifdef|ifndef|elsif)\s+([A-Za-z_$][\w$]*)', body, re.M)))
        dump(out / 'conditional-symbol-inventory.json', dict(symbols=directives, actual_compile_defines=BASE_DEFINES,
             modes_reviewed=[dict(mode=name, additional_defines=extra) for name, extra in MODES],
             scope='Only explicitly listed conditional configurations, not arbitrary macro settings'))
        default_primitives = None
        for mode, extra in MODES:
            review, records = source_review(body, netbody, extra)
            review.update(mode=mode, additional_defines=extra, source_identity=identities[0])
            dump(out / ('source-' + mode + '.json'), review)
            state['reviews'].append(dict(mode=mode, report=ident(out / ('source-' + mode + '.json'))))
            if mode == 'actual_default':
                need(review['active_module_count'] == 1270 and review['mapped_module_count'] == 927,
                     'actual101 module-count control differs')
                need(set(records) == {'udp_tlatrf', 'udp_tlatrf2'}, 'actual101 duplicate primitive controls differ')
                default_primitives = records
            negrecords = primitive_records(preprocess(clean(negbody), extra))
            summary = []
            for name, current in records.items():
                other = negrecords.get(name, [])
                summary.append(dict(name=name, negative_definition_count=len(other),
                                    negative_fingerprints=[fingerprint(record) for record in other],
                                    default_vs_negative_definition_tokens_equal=[a['tokens'] == b['tokens'] for a, b in zip(current, other)]
                                    if len(current) == len(other) else None))
            dump(out / ('negative-comparison-' + mode + '.json'), dict(mode=mode, source_identity=identities[1],
                 duplicates=summary, qualification='NOT_QUALIFIED', scope='Comparison only; not a proposed replacement model'))
            dump(out / 'state.json', state)
        for name, records in sorted(default_primitives.items()):
            probe_out = out / ('probe-' + name)
            probe_out.mkdir()
            result = run_probe(name, records, standard, args.vcs, probe_out, private)
            state['probes'].append(dict(name=name, counters=result['counters'], result=ident(probe_out / 'result.json')))
            dump(out / 'state.json', state)
        state['inputs_after'] = [ident(path) for path in [standard, negative, mapped]]
        need(state['inputs_before'] == state['inputs_after'], 'original inputs changed during read-only review')
        state['status'] = 'EXECUTED_ORIGINAL_UDP_DEPENDENCY_AND_FINITE_BEHAVIOR_NOT_QUALIFIED'
    except BaseException as error:
        state.update(status='FAIL_REVIEW_NOT_QUALIFIED', error=type(error).__name__ + ': ' + str(error))
        dump(out / 'state.json', state)
        raise
    finally:
        state['finished_epoch'] = time.time()
        dump(out / 'state.json', state)
    print(state['status'], flush=True)


if __name__ == '__main__':
    main()
