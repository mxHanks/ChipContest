#!/usr/bin/env python3
"""Prepare/run full original-TB mapped private observation; final gate stays fatal.

One foreground CLI for controller150. No background session and no diagnostic
timing suppression. Native capture is disabled with the original host-check
capture guards; this cannot provide activity, power, energy or qualification.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

import support111 as base

HERE = Path(__file__).resolve().parent
B = Path.home() / 'Desktop/xu-score-optimization-20261102'
FROZEN = {'support111.py': '2a740fb35d8f6db7da3295031f4e7e66f1505d30c9ccf030a5cb1862cb8caa6d',
          'frozen111-vpi.c': '2403e25ee5ab453d017b6686da89df7553b79bcd89d70ca35be96281d5d8e7c7',
          'actual133-inventory.json': '14a0aec91b4ceca013861ce7f4703142e90a8c762fe8c6da632f28a13ccdabb9',
          'frozen-s2c-accel.v': '1a088c873c5e5de84ca92fdc74d693a326e430cc6191128979f573fe4e64ad45'}
ACCEL = 'u_soc.u_e203_subsys_top.u_e203_subsys_main.u_e203_subsys_perips.u_accel_icb_slave'
PUBLIC = {'cmd_valid': 1, 'cmd_ready': 1, 'cmd_addr': 32, 'cmd_read': 1,
          'cmd_wdata': 32, 'cmd_wmask': 4, 'rsp_valid': 1, 'rsp_ready': 1,
          'rsp_rdata': 32, 'rsp_err': 1, 'clk': 1, 'rst_n': 1}
GATE = 'XU_PRIVATE147_QUALIFICATION_GATE_PENDING physical_storage_readback native_warning_timing conditional_SRAM_joint_energy all_unresolved_gates_retained'
TERMINAL = 'ORIGINAL_TB_EXU_HALT_REACHED_FINAL_QUALIFICATION_GATE_PENDING_NOT_QUALIFIED'
PREPARED = 'PREPARED_FULL_ORIGINAL_TB_PRIVATE147_NOT_QUALIFIED'
CAPTURE_RESULT = '6eea4bb5ebddb4e186564ba3610e69fb7a48a72b12f4f0ea777d9f33c6f96e4d'
base.FAIL_STATUS = 'FAIL_PRIVATE147_NOT_QUALIFIED'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    base.dump(path, value)


def create_plan(original):
    need(hashlib.sha256(original.encode()).hexdigest() == base.TB_SHA, 'original d39016 TB differs')
    for name, expected in FROZEN.items():
        need(sha(HERE / name) == expected, 'frozen source differs: ' + name)
    actual = json.loads((HERE / 'actual133-inventory.json').read_text())
    need(actual['mapped_before'] == actual['mapped_after'] and
         actual['mapped_before']['sha256'] == base.NET and actual['mapped_before']['bytes'] == 14199670,
         'actual133 exact target input missing')
    private = {(r['original_macro'], r['original_path']): r for r in actual['references']}
    need(len(private) == 60 and Counter(r['classification'][0] for r in private.values()) == {'1': 58, '2': 1, '3': 1},
         'actual133 target reference classes differ')
    busy = private[('ACCEL', 'busy')]['physical_expression_operand_lookups']
    need(set(busy) == {'manual_busy', 'row_active', 'row_start'} and
         all(len(v) == 1 and v[0] and v[0]['exact_width'] for v in busy.values()), 'busy physical operands missing')
    row = private[('ACCEL', 'row_start_accept')]['physical_expression_operand_lookups']
    need([k for k, v in row.items() if not (len(v) == 1 and v[0] and v[0]['exact_width'])] == ['busy'],
         'row accept has additional unbound physical operands')
    wrapper = (HERE / 'frozen-s2c-accel.v').read_text()
    expressions = {s: re.search(r'wire\s+' + s + r'\s*=\s*(.*?);', wrapper, re.S).group(1)
                   for s in ['busy', 'row_start_accept']}
    need(re.sub(r'\s+', '', expressions['busy']) == 'manual_busy||row_active||row_start', 'busy source equation differs')
    need(re.search(r'REG_ROW_CTRL\s*=\s*12\'h0C0', wrapper), 'row-control constant differs')
    dependencies = {m: sorted(set(re.findall('`' + m + r'\.([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)', original)))
                    for m in ['ACCEL', 'EXU', 'XU_HCLK']}
    records = []
    for macro, names in dependencies.items():
        for name in names:
            public = macro == 'ACCEL' and name in PUBLIC
            r = dict(private[(macro, name)]) if not public else dict(original_macro=macro, original_path=name,
                width_each=PUBLIC[name], lanes=1, endpoint_lookups=[dict(scope=ACCEL, module='accel_icb_slave',
                net=name, path=ACCEL + '.' + name, width=PUBLIC[name], exact_width=True, kind='port')])
            r['observation'] = 'xu147_o_%03d' % len(records)
            r['private'] = not public
            records.append(r)
    need(len(records) == 72 and sum(r['private'] for r in records) == 60, 'original72/private60 changed')
    index = {(r['original_macro'], r['original_path']): r for r in records}
    for signal in ['busy', 'row_start_accept']:
        expr = expressions[signal].replace('REG_ROW_CTRL', "12'h0c0")
        names = sorted(set(re.findall(r'\b[A-Za-z_]\w*\b', expr)), key=len, reverse=True)
        for name in names:
            if ('ACCEL', name) in index:
                dependency = index[('ACCEL', name)]
                replacement = ('(' + dependency['inline_expression'] + ')' if 'inline_expression' in dependency
                               else dependency['observation'])
                expr = re.sub(r'\b' + name + r'\b', replacement, expr)
        index[('ACCEL', signal)]['inline_expression'] = '(' + expr + ')'
    need('xu147_o_' in index[('ACCEL', 'busy')]['inline_expression'] and
         index[('ACCEL', 'busy')]['observation'] not in index[('ACCEL', 'row_start_accept')]['inline_expression'],
         'row accept must recursively use physical busy operands')
    return records


def generated_tb(original, records):
    text = original
    declarations = []
    for r in records:
        if 'inline_expression' not in r:
            declarations.append('  reg [%d:0] %s%s;' % (r['width_each'] - 1, r['observation'],
                                ' [0:7]' if r['lanes'] == 8 else ''))
    text = text.replace('module tb_xu_soc_ppa;', 'module tb_xu_soc_ppa;\n' + '\n'.join(declarations), 1)
    replacements = {}
    for r in sorted(records, key=lambda r: len(r['original_path']), reverse=True):
        pattern = '`' + r['original_macro'] + '.' + r['original_path']
        if r['original_macro'] == 'EXU' and r['original_path'].endswith('.rf_r'):
            pattern += '[3]'
        regex = re.escape(pattern) + r'(?![\w$.])'
        replace = r.get('inline_expression', r['observation'])
        text, count = re.subn(regex, lambda _: replace, text)
        replacements[pattern] = count
        need(count > 0, 'original reference was not replaced: ' + pattern)
    # Restore the actual public clock in the original event expression only.
    clock = next(r['observation'] for r in records if (r['original_macro'], r['original_path']) == ('ACCEL', 'clk'))
    event = 'always @(posedge ' + clock + ') begin'
    need(text.count(event) == 1, 'original actual accelerator event differs')
    text = text.replace(event, 'always @(posedge dut.' + ACCEL + '.clk) begin\n    $xu_private147_sample(1);', 1)
    text = text.replace('always @(posedge clk) begin\n', 'always @(posedge clk) begin\n    $xu_private147_sample(0);\n', 1)
    anchor = '    reg [63:0] expected;\n    cycles <= cycles+1;'
    need(text.count(anchor) == 1, 'original main sampling entry differs')
    text = text.replace(anchor, '    reg [63:0] expected;\n    $xu_private147_sample(2);\n    cycles <= cycles+1;')
    initialize = '  initial begin : initialize\n    integer i;'
    need(text.count(initialize) == 1, 'original initialize entry differs')
    text = text.replace(initialize, initialize + '\n    $xu_private147_prepare();')
    for task, role in [('xu_preload_itcm', 'itcm'), ('xu_preload_shared', 'shared')]:
        pattern = r'task ' + task + r';.*?endtask'
        text, count = re.subn(pattern, 'task ' + task + ';\n  begin\n    $xu_private147_' + role + '();\n  end\nendtask', text, flags=re.S)
        need(count == 1, 'original role-specific preload task differs')
    # All now-unused private macro definitions and their include are removed.
    text = re.sub(r'^\s*`define (?:CPU|EXU|ACCEL|ITCM|XU_HCLK)\b[^\n]*\n', '', text, flags=re.M)
    text = text.replace('`include "e203_defines.v"\n', '')
    halt = '        $display("SOC_PASS tasks=%0d outputs=%0d writes=%0d",completed,completed*25344,completed*50688);'
    need(text.count(halt) == 1, 'original final EXU halt endpoint differs')
    text = text.replace(halt, '        $xu_private147_gate();\n        $fatal(1,"' + GATE + '");\n' + halt)
    original_fatals = re.findall(r'\$fatal\(1,"([^"\n]*)"', original)
    generated_fatals = re.findall(r'\$fatal\(1,"([^"\n]*)"', text)
    need(generated_fatals.count(GATE) == 1 and
         [s for s in generated_fatals if s != GATE] == original_fatals, 'original fatal messages/order changed')
    need(sum(replacements.values()) == 241 and sum(v for k, v in replacements.items()
         if next(r['private'] for r in records if k.startswith('`' + r['original_macro'] + '.' + r['original_path'])
                 and (k == '`' + r['original_macro'] + '.' + r['original_path'] or k.endswith('[3]')))) == 149,
         'original241/private149 read occurrence count differs')
    need(len(re.findall(r'\balways\s*@', text)) == len(re.findall(r'\balways\s*@', original)) == 3 and
         text.count('$xu_private147_sample(') == 3, 'original three consumer edges must be retained')
    need(not re.search(r'`(?:ACCEL|EXU|CPU|ITCM|XU_HCLK)\b', text) and 'rf_r[3]' not in text,
         'unadapted original private read remains')
    need('vpiForceFlag' not in text and '$force' not in text, 'DUT state force is forbidden')
    return text, dict(logical_references=72, private_references=60, original_read_occurrences=241,
        private_read_occurrences=149, original_fatal_count=len(original_fatals), original_fatals_preserved=True,
        original_sampling_edges_preserved=True, replacements=replacements,
        role_specific_preload_macros=288, final_qualification_gate=GATE)


def bindings_header(records):
    bindings = []
    for r in records:
        if 'inline_expression' in r:
            continue
        for lane, e in enumerate(r['endpoint_lookups']):
            need(e and e['exact_width'] and e['width'] == r['width_each'], 'native endpoint width missing')
            names = ([b[len(e['scope']) + 1:] for b in e['bits']]
                     if e['kind'] == 'escaped_scalar_bundle' else [e['net']])
            mask = 1 if r['original_macro'] == 'XU_HCLK' else 4
            if r['original_macro'] == 'ACCEL' and r['original_path'] == 'rst_n':
                mask |= 2
            bindings.append(dict(scope='tb_xu_soc_ppa.dut.' + e['scope'], definition=e['module'],
                names=names, parts=len(names), width=r['width_each'], logical=r['original_macro'] + '.' + r['original_path'],
                target=r['observation'], lane=lane if r['lanes'] == 8 else -1, phases=mask))
    need(len(bindings) == 84 and sum(b['logical'].startswith('ACCEL.') and
         b['logical'][6:] in PUBLIC for b in bindings) == 12, 'all native endpoint lanes must be represented')
    need(len(set((b['target'], b['lane']) for b in bindings)) == 84, 'TB observation destinations alias')
    need(all(0 < b['parts'] <= 48 and 0 < b['width'] <= 48 and
         b['parts'] in (1, b['width']) for b in bindings), 'native observation geometry unsupported')
    header = '#define XU147_BINDINGS %d\n' % len(bindings)
    header += 'struct xu_binding147_t {const char *scope,*definition,*logical,*target;int lane;unsigned width,phases,parts;const char *names[48];};\n'
    header += 'static const struct xu_binding147_t xu_binding147[XU147_BINDINGS]={\n'
    header += ',\n'.join('{%s,%s,%s,%s,%d,%d,%d,%d,{%s}}' % (
        json.dumps(b['scope']), json.dumps(b['definition']), json.dumps(b['logical']), json.dumps(b['target']),
        b['lane'], b['width'], b['phases'], b['parts'], ','.join(json.dumps(n) for n in b['names'])) for b in bindings)
    return header + '\n};\n', bindings


def generate_c():
    original = (HERE / 'frozen111-vpi.c').read_text()
    helpers = original[original.index('static void reject('):original.index('static unsigned scalar(')]
    helpers = helpers.replace('XU_MAPPED111_ADAPTER_REJECT', 'XU_PRIVATE147_ADAPTER_REJECT')
    geometry = original[original.index('static int geometry('):original.index('static void walk(')]
    preload = original[original.index('static PLI_INT32 preload('):original.index('void xu_mapped_task00_register111')]
    preload = preload.replace('static PLI_INT32 preload(PLI_BYTE8 *unused)', 'static PLI_INT32 preload_role(unsigned role)')
    preload = preload.replace('(void)unused;', '').replace('preload_calls++', 'preload_calls[role]++')
    preload = preload.replace('if(xu_expected111[i].role)', 'if((unsigned)xu_expected111[i].role==role)')
    preload = preload.replace('if(count!=288)', 'if(count!=(role==1?32u:256u))')
    old = 'vpi_printf("XU_MAPPED111_PRELOAD_DONE itcm=32 shared=256 words_per_macro=256 bits_per_row=64 arbitrary_XZ_preserved=1 Q_WRITES=0\\n");'
    need(preload.count(old) == 1, 'unchanged111 preload boundary missing')
    preload = preload.replace(old, 'vpi_printf("XU_PRIVATE147_PRELOAD_ROLE_DONE role=%u macros=%u rows=256 bits=64 arbitrary_XZ_preserved=1 Q_WRITES=0\\n",role,count);')
    text = (HERE / 'private147-runtime.c.in').read_text()
    for key, content in [('HELPERS', helpers), ('GEOMETRY', geometry), ('PRELOAD', preload)]:
        need(text.count('@@' + key + '@@') == 1, 'C generation boundary differs')
        text = text.replace('@@' + key + '@@', content)
    return text


def macro_header(inventory):
    records = []
    for row in inventory['macros']:
        name = row['instance']; role = 0; bank = lane = 0
        if name.startswith('u_shared/') or '/u_e203_itcm_ram/' in name:
            pair = re.search(r'depth_bank\[(\d+)\]\.width_lane\[(\d+)\]\.macro$', name)
            need(pair, 'native macro preload geometry differs')
            bank, lane = map(int, pair.groups()); role = 2 if name.startswith('u_shared/') else 1
            need((role == 1 and 0 <= bank < 8 and 0 <= lane < 4) or
                 (role == 2 and 0 <= bank < 128 and 0 <= lane < 2), 'native preload range differs')
        records.append(dict(name='tb_xu_soc_ppa.dut.' + name.replace('/', '.'), role=role, bank=bank, lane=lane))
    need(len(records) == 336 and len({r['name'] for r in records}) == 336 and
         Counter(r['role'] for r in records) == {0: 48, 1: 32, 2: 256} and
         len(set((r['role'], r['bank'], r['lane']) for r in records if r['role'])) == 288,
         'original336 macro roles differ or preload bank/lane aliases')
    return ('struct xu_expected111_t {const char *name;int role;int bank;int lane;};\n'
            'static const struct xu_expected111_t xu_expected111[336]={\n' +
            ',\n'.join('{%s,%d,%d,%d}' % (json.dumps(r['name']), r['role'], r['bank'], r['lane']) for r in records) + '\n};\n')


def classify(raw, code, tb_path, bindings, inventory):
    text = raw.decode('utf-8', errors='replace')
    need(code != 0 and text.count(GATE) == 1, 'mandatory terminal qualification gate not reached exactly once')
    need('SOC_PASS' not in text and 'XU_PRIVATE147_ADAPTER_REJECT' not in text,
         'unexpected complete qualification or native rejection')
    source = Path(tb_path).read_text()
    fatal_lines = [n for n, line in enumerate(source.splitlines(), 1)
                   if '$fatal(1,"' + GATE + '");' in line]
    need(len(fatal_lines) == 1, 'unique generated source qualification fatal missing')
    native = re.findall(r'^Fatal: "([^"\n]+)", (\d+): ([^\n]+): at time (\d+) fs\n([^\n]+)\n'
                        r'\$finish called from file "([^"\n]+)", line (\d+)\.\n'
                        r'\$finish at simulation time\s+(\d+)\n', text, re.M)
    need(len(native) == 1 and len(re.findall(r'^(?:Fatal|FATAL):', text, re.M)) == 1,
         'unique native VCS fatal block missing')
    f = native[0]
    need(f[0] == f[5] == str(Path(tb_path).resolve()) and int(f[1]) == int(f[6]) == fatal_lines[0] and
         f[4] == GATE and f[3] == f[7], 'native fatal source/message/time differs')
    need(not re.search(r'^\s*(?:Error:|Error-|FATAL:)', text, re.M), 'unexpected native error')
    required = ['XU_PRIVATE147_ADAPTER_READY logical_references=72 private_references=60 native_bindings=84 original_preload_macros=288 Q_WRITES=0 OTHER_DUT_FF_WRITES=0',
                'XU_PRIVATE147_PRELOAD_ROLE_DONE role=1 macros=32 rows=256 bits=64 arbitrary_XZ_preserved=1 Q_WRITES=0',
                'XU_PRIVATE147_PRELOAD_ROLE_DONE role=2 macros=256 rows=256 bits=64 arbitrary_XZ_preserved=1 Q_WRITES=0',
                'XU_CANDIDATE_UPLOAD_PASS task=0 w_commits=16384 bias=256 x_commits=6336 rows=99 starts=3168 dones=3168 pops_retired=3168',
                'TASK_PASS layer=0 outputs=25344 writes=50688',
                'XU_LF_CLOCK_STATIC_PASS nominal_hz=32768', 'XU_CLOCK_STATIC_PASS checked_hf_edges=',
                'XU_PRIVATE147_ORIGINAL_EXU_HALT_REACHED logical=72 private=60 bindings=84']
    positions = []
    for marker in required:
        need(text.count(marker) == 1, 'required unique original/native marker missing: ' + marker)
        positions.append(text.index(marker))
    need(positions == sorted(positions) and positions[-1] < text.index(GATE), 'original native/run endpoint ordering differs')
    halt = re.findall(r'^XU_PRIVATE147_ORIGINAL_EXU_HALT_REACHED logical=72 private=60 bindings=84 '
                      r'pll_samples=(\d+) reset_samples=(\d+) main_samples=(\d+) '
                      r'Q_WRITES=0 OTHER_DUT_FF_WRITES=0 QUALIFICATION_PENDING=1$', text, re.M)
    need(len(halt) == 1 and all(int(x) > 0 for x in halt[0]), 'all original sampling contexts required')
    bind_lines = re.findall(r'^XU_PRIVATE147_BIND (.*)$', text, re.M)
    need(len(bindings) == len(bind_lines) == 84, 'native handle binding count differs')
    tags = [re.match(r'^tag=(\d+) ', line) for line in bind_lines]
    need(all(tags) and sorted(int(t.group(1)) for t in tags) == list(range(84)), 'native handle tags not bijective')
    by_tag = {int(t.group(1)): line for t, line in zip(tags, bind_lines)}
    for tag, b in enumerate(bindings):
        line = by_tag[tag]
        target = 'tb_xu_soc_ppa.' + b['target'] + ('[%d]' % b['lane'] if b['lane'] >= 0 else '')
        expected = 'tag=%d logical=%s lane=%d width=%d sources=%d phase_mask=%d source=%s.%s target=%s source_type=' % (
            tag, b['logical'], b['lane'], b['width'], b['parts'], b['phases'], b['scope'], b['names'][0], target)
        need(line.startswith(expected) and re.match(r'^\d+$', line[len(expected):]) and
             int(line[len(expected):]) in (36, 44, 48), 'native handle identity/type differs at tag=' + str(tag))
    geometry = re.findall(r'^XU_MAPPED111_GEOMETRY tag=(\d+) role=([012]) status=PASS '
                          r'rows=256 row_bits=64 unique=256 memory_type=\d+ reg_words=(\d+) memoryword_words=(\d+) '
                          r'parent_present=(\d+) scope_present=(\d+) index_present=(\d+) name=(\S+)$', text, re.M)
    need(len(geometry) == 336 and sorted(int(r[0]) for r in geometry) == list(range(336)), 'all336 unique native geometries required')
    for row in geometry:
        tag, role, regs, words, parents, scopes, indices = map(int, row[:7])
        instance = inventory['macros'][tag]['instance']
        expected_role = 2 if instance.startswith('u_shared/') else 1 if '/u_e203_itcm_ram/' in instance else 0
        need(role == expected_role and regs + words == 256 and max(parents, scopes, indices) <= 256 and
             row[7] == 'tb_xu_soc_ppa.dut.' + instance.replace('/', '.'), 'native macro geometry/ownership differs')
    return dict(status=TERMINAL, qualification='NOT_QUALIFIED', original_private_reference_count=60,
                original_checks_reached_exu_halt=True, native_mandatory_fatal=list(f),
                private_qualification_gates_discharged=0, final_qualification_gate_retained=True,
                activity_energy_timing_qualification='NOT_PROVEN')


def work(args, run):
    for p in [Path(__file__), HERE / 'private147-runtime.c.in'] + [HERE / n for n in FROZEN]:
        run.freeze(p)
    capture = args.capture.resolve(); original_path = capture / 'simulator/tb_xu_s2c_task_activity.sv'
    need(run.freeze(original_path)['sha256'] == base.TB_SHA, 'original d39016 TB differs')
    need(run.freeze(capture / 'result.json')['sha256'] == CAPTURE_RESULT, 'original capture result differs')
    activity = json.loads((capture / 'result.json').read_text())
    wrapper_sources = [r for r in activity['configuration']['rtl_sources']
                       if r['path'].endswith('/accel_icb_slave.v')]
    need(len(wrapper_sources) == 1 and wrapper_sources[0]['sha256'] == FROZEN['frozen-s2c-accel.v'],
         'busy/row-accept source must be original capture wrapper')
    need(activity['configuration_sha256'] == base.CONFIG and hashlib.sha256(json.dumps(activity['configuration'],
         sort_keys=True, separators=(',', ':')).encode()).hexdigest() == base.CONFIG, 'frozen task configuration differs')
    need(run.freeze(args.macro_inventory)['sha256'] == base.INV, 'frozen native macro inventory differs')
    inventory = json.loads(args.macro_inventory.read_text()); need(inventory['netlist']['sha256'] == base.NET, 'wrong mapped macro target')
    original = original_path.read_text(); records = create_plan(original)
    tb, review = generated_tb(original, records); header, bindings = bindings_header(records)
    files = {'tb_private147.sv': tb, 'xu_private147.c': generate_c(),
             'xu_private147_bindings.h': header, 'xu_mapped_expected111.h': macro_header(inventory)}
    for name, content in files.items():
        (run.out / name).write_text(content); run.freeze(run.out / name)
    dump(run.out / 'adapter-plan147.json', dict(records=records, bindings=bindings, source_transform_review=review,
         qualification='NOT_QUALIFIED', all60_private_qualification_gates_pending=True))
    run.freeze(run.out / 'adapter-plan147.json')
    run.state.update(status=PREPARED, scope='FULL_ORIGINAL_TB_READ_ONLY_NATIVE_ADAPTER_147',
        original_tb=base.identity(original_path), source_transform_review=review,
        capture_policy='ORIGINAL_HOST_CHECK_CAPTURE_GUARDS_ONLY_NO_ACTIVITY_OR_ENERGY_EVIDENCE',
        final_qualification_gate=GATE, private_qualification_gates_discharged=0)
    run.save()
    if not args.run:
        return
    base.verify_preload_proof(args.preload_proof, run)
    need([run.freeze(p)['sha256'] for p in [args.mapped, args.vendor, args.standard]] ==
         [base.NET, base.RAM, base.LIB], 'exact target and original timing models differ')
    fw = activity['firmware_build']['image']; need(fw['sha256'] == base.FW and run.freeze(fw['path'])['sha256'] == base.FW, 'firmware differs')
    manifest_ref = activity['tasks'][0]['input_manifest']
    need(manifest_ref['sha256'] == base.TASK00_MANIFEST and run.freeze(manifest_ref['path'])['sha256'] == base.TASK00_MANIFEST, 'task00 vector manifest differs')
    manifest = json.loads(Path(manifest_ref['path']).read_text())
    for tensor in manifest['files']:
        for kind in ['original', 'materialized']:
            need(run.freeze(tensor[kind]['path'])['sha256'] == tensor[kind]['sha256'], 'actual tensor bytes differ')
    cc = shutil.which('gcc'); need(cc, 'native GCC missing'); run.freeze(cc); run.freeze(args.vcs)
    for p in sorted(args.vpi_include.resolve().rglob('*.h')):
        run.freeze(p)
    need((args.vpi_include / 'vpi_user.h').is_file(), 'native VPI SDK absent')
    so = run.out / 'adapter147.so'
    run.step('vpi-build', [cc, '-std=gnu99', '-fPIC', '-shared', '-Wall', '-Wextra', '-Werror',
        '-isystem', str(args.vpi_include.resolve()), '-I' + str(run.out), str(run.out / 'xu_private147.c'), '-o', str(so)], 1800)
    run.freeze(so)
    filelist = run.out / 'mapped.f'
    filelist.write_text('\n'.join(str(p.resolve()) for p in [args.mapped, args.vendor, args.standard, run.out / 'tb_private147.sv']) + '\n')
    run.freeze(filelist)
    vcs = [str(args.vcs.resolve()), '-full64', '-sverilog', '-timescale=1ns/1fs', '-top', 'tb_xu_soc_ppa',
           '-debug_access+all', '-debug_region+cell', '+vpi', '+define+ARM_UD_MODEL', '+define+DISABLE_SV_ASSERTION=1',
           '+define+XU_TASK_ACTIVITY_HOST_CHECK', '+lint=TFIPC-L', '-load', str(so) + ':xu_private147_register',
           '-f', str(filelist), '-Mdir=' + str(run.out / 'csrc'), '-o', str(run.out / 'task00')]
    need(not any('notimingcheck' in s or 'nospecify' in s for s in vcs), 'timing suppression is forbidden')
    run.step('vcs-build', vcs, 1800); run.freeze(run.out / 'task00')
    if (run.out / 'task00.daidir').is_dir():
        run.freeze_tree(run.out / 'task00.daidir')
    command = [str(run.out / 'task00')] + activity['tasks'][0]['run_command'][1:]
    need('+TASKS=1' in command and '+XU_GLOBAL_TASK=0' in command and
         not any('notimingcheck' in s or 'nospecify' in s for s in command), 'frozen native task00 args differ')
    code, raw = run.step('simulation', command, args.timeout, require_zero=False)
    run.state.update(classify(raw, code, run.out / 'tb_private147.sv', bindings, inventory)); run.save()


def contract():
    return dict(schema='xu.private147.controller150.v1', cli='xu_private147.py',
        python_minimum='3.6', foreground=True, prepare_status=PREPARED,
        expected_terminal_status=TERMINAL, failure_status=base.FAIL_STATUS,
        expected_cli_exit=0, expected_simulator_exit='NONZERO_FINAL_QUALIFICATION_FATAL',
        qualification='NOT_QUALIFIED', native_bindings=84, logical_references=72, private_references=60,
        final_gate=GATE, capture_policy='DISABLED_ORIGINAL_HOST_CHECK_GUARDS',
        qualification_gates=['physical_storage_readback', 'native_warning_timing',
                             'conditional_SRAM_joint_energy', 'all_other_unresolved_gates'],
        mapped_sha256=base.NET, original_tb_sha256=base.TB_SHA,
        original_capture_result_sha256=CAPTURE_RESULT, original_macro_inventory_sha256=base.INV)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture', type=Path, default=B / 's2c-formal-activity12-20261103-23')
    p.add_argument('--macro-inventory', type=Path, default=B / 's2c-pt-macro-pin-inventory-20261103-20/inventory.json')
    p.add_argument('--out', type=Path)
    p.add_argument('--run', action='store_true')
    p.add_argument('--mapped', type=Path, default=B / 's2c-ppa-campaign-20261103-01/s2c/ppa/mapped.v')
    p.add_argument('--vendor', type=Path, default=Path('/storage1/admin_public_dir/SRAM_Lib_2025/RAMSP1024X16/verilog/RAMSP1024X16.v'))
    p.add_argument('--standard', type=Path, default=B / 'standard-cell-model-private-20261104-90/scc40nll_vhsc40_rvt.v')
    p.add_argument('--vcs', type=Path, default=Path('/eda/synopsys/vcs/vcs_2020.03-SP2-6/bin/vcs'))
    p.add_argument('--vpi-include', type=Path, default=Path('/eda/synopsys/vcs/vcs_2020.03-SP2-6/include'))
    p.add_argument('--preload-proof', type=Path, default=B / 'vpi-vendor-preload-primitive-20261104-105')
    p.add_argument('--timeout', type=int, default=21600)
    p.add_argument('--describe', action='store_true', help='print the stable controller150 contract without running')
    args = p.parse_args()
    if args.describe:
        print(json.dumps(contract(), sort_keys=True, indent=2)); return 0
    need(args.out is not None, '--out is required unless --describe is used')
    need(args.timeout > 0, '--timeout must be positive')
    try:
        with base.EvidenceRun(args.out) as run:
            work(args, run)
    except Exception as exc:
        print('XU_PRIVATE147_TERMINAL ' + base.FAIL_STATUS + ' ' + type(exc).__name__ + ': ' + str(exc),
              file=sys.stderr, flush=True)
        return 1
    print('XU_PRIVATE147_TERMINAL ' + run.state['status'], flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
