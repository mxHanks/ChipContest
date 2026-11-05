#!/usr/bin/env python3
"""Local mechanism checks. Does not simulate the mapped SoC or prove VCS timing."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xu_private147 as m

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent


def need(ok, message):
    if not ok:
        raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--capture', type=Path, default=REPO / 'build/xu-score-resume-20261103/next-results-export-53/s2c-formal-activity12-20261103-23')
    parser.add_argument('--macro-inventory', type=Path, default=REPO / 'build/xu-score-resume-20261103/terminal-results-export-22/s2c-pt-macro-pin-inventory-20261103-20/inventory.json')
    parser.add_argument('--vpi-include', type=Path, default=Path('/usr/include/iverilog'))
    args = parser.parse_args()
    out = args.out.resolve(); out.mkdir(parents=True, exist_ok=False)
    checks = []

    def command(name, argv, expected=0):
        log = out / (name + '.log')
        with log.open('xb') as stream:
            process = subprocess.run([str(x) for x in argv], stdout=stream, stderr=subprocess.STDOUT, timeout=45)
        need(process.returncode == expected, name + ': ' + log.read_text())
        checks.append(dict(name=name, command=[str(x) for x in argv], returncode=process.returncode,
                           log_sha256=m.sha(log)))
        return log.read_text()

    command('prepare', [sys.executable, '-B', HERE / 'xu_private147.py', '--capture', args.capture.resolve(),
                        '--macro-inventory', args.macro_inventory.resolve(), '--out', out / 'prepared'])
    prepared = out / 'prepared'
    state = json.loads((prepared / 'state.json').read_text())
    need(state['status'] == m.PREPARED and state['inputs_equal_before_after'], 'preparation identity/status differs')
    original = (args.capture / 'simulator/tb_xu_s2c_task_activity.sv').read_text()
    records = m.create_plan(original); header, bindings = m.bindings_header(records)
    inventory = json.loads(args.macro_inventory.read_text())
    need(header == (prepared / 'xu_private147_bindings.h').read_text(), 'bindings differ')
    generated = (prepared / 'tb_private147.sv').read_text()
    need(generated.count('$fatal(1,') == original.count('$fatal(1,') + 1 == 87, 'original fatal checks differ')
    need(generated.count('always @') == original.count('always @') == 3, 'sampling edges differ')
    need('else if (offset==HOST+4) begin' in generated and 'if (layer<tasks) load_layer(layer);' in generated and
         "==32'h80000086" in generated, 'HOST ACK must continue to original EXU halt check')
    if sys.version_info >= (3, 8):
        for name in ['xu_private147.py', 'support111.py', 'host_checks147.py']:
            ast.parse((HERE / name).read_text(), filename=name, feature_version=6)
    command('vpi-syntax', ['gcc', '-std=gnu99', '-fsyntax-only', '-Wall', '-Wextra', '-Werror',
                          '-isystem', args.vpi_include, '-I' + str(prepared), prepared / 'xu_private147.c'])
    (prepared / 'mock147.c').write_bytes((HERE / 'mock147.c.in').read_bytes())
    command('mock-build', ['gcc', '-std=gnu99', '-Wall', '-Wextra', '-Werror', '-ffunction-sections', '-fdata-sections',
                          '-isystem', args.vpi_include, '-I' + str(prepared), prepared / 'mock147.c',
                          '-Wl,--gc-sections', '-o', out / 'mock147'])
    for mode in range(11):
        result = command('mock-%02d' % mode, [out / 'mock147', str(mode)])
        if mode == 0:
            need('MOCK147_PASS bindings=84 phases=3 four_state=1 preload_macros=288 forbidden_writes=0 native_VCS_proof=0' in result,
                 'all84 native-object mechanism checks missing')
        else:
            need('XU_PRIVATE147_ADAPTER_REJECT' in result and 'MOCK147_PASS' not in result, 'mutated handle must reject')

    # Compile the entire generated TB with a clearly separate structural stub.
    # The stub is never a runtime input to xu_private147.py.
    instance = re.search(r'  xu_soc_ppa_top dut \(.*?\n  \);', generated, re.S).group(0)
    ports = re.findall(r'\.([A-Za-z_]\w*)\(', instance)
    definitions = []
    for port in ports:
        direction = 'input' if port in ['hfextclk', 'lfextclk'] or '_i_ival' in port else 'output'
        definitions.append(direction + (' [31:0] ' if 'gpio' in port else ' ') + port)
    stub = 'module xu_soc_ppa_top(' + ',\n'.join(definitions) + ');\n'
    for signal, width in m.PUBLIC.items():
        if signal in ['clk', 'rst_n']:
            continue
        stub += 'wire [%d:0] ext_sysmem_%s;\n' % (width - 1, signal)
    levels = [('u_soc', 'u_e203_subsys_top'), ('u_e203_subsys_top', 'u_e203_subsys_main'),
              ('u_e203_subsys_main', 'u_e203_subsys_perips'), ('u_e203_subsys_perips', 'u_accel_icb_slave')]
    stub += 'xu147_level0 u_soc();\nendmodule\n'
    for index, (_, child) in enumerate(levels):
        stub += 'module xu147_level%d; xu147_level%d %s(); endmodule\n' % (index, index + 1, child)
    stub += 'module xu147_level4; wire clk=0; endmodule\n'
    (out / 'structural-stub.sv').write_text(stub)
    command('full-tb-syntax', ['iverilog', '-g2012', '-DXU_TASK_ACTIVITY_HOST_CHECK', '-s', 'tb_xu_soc_ppa',
                             '-tnull', prepared / 'tb_private147.sv', out / 'structural-stub.sv'])

    by_name = {r['original_path']: r for r in records if r['original_macro'] == 'ACCEL'}
    busy = by_name['busy']['inline_expression']; accept = by_name['row_start_accept']['inline_expression']
    scalar_names = ['manual_busy', 'row_active', 'row_start', 'cmd_valid', 'cmd_ready', 'cmd_read',
                    'cache_enable', 'core_start', 'x_load_wen', 'w_load_wen']
    names = scalar_names + ['cmd_addr', 'cmd_wmask', 'cmd_wdata', 'row_count']
    sv = '`timescale 1ns/1ps\nmodule tb;\n'
    for name in names:
        record = by_name[name]; sv += 'reg [%d:0] %s;\n' % (record['width_each'] - 1, record['observation'])
    sv += 'reg [1:0] values[0:3]; integer i,j,k,n,cases=0; reg expected_busy,expected_accept;\n'
    aliases = {name: by_name[name]['observation'] for name in names}
    wrapper = (HERE / 'frozen-s2c-accel.v').read_text()
    reference_accept = re.search(r'wire row_start_accept = (.*?);', wrapper, re.S).group(1)
    reference_accept = reference_accept.replace('REG_ROW_CTRL', "12'h0c0").replace('!busy', '!expected_busy')
    for name in sorted(names, key=len, reverse=True):
        reference_accept = re.sub(r'\b' + name + r'\b', aliases[name], reference_accept)
    sv += 'task check; begin\nexpected_busy=%s||%s||%s;\nexpected_accept=%s;\n' % (
        aliases['manual_busy'], aliases['row_active'], aliases['row_start'], reference_accept)
    sv += 'if ((%s)!==expected_busy || (%s)!==expected_accept) $fatal(1,"FOUR_STATE_MISMATCH"); cases=cases+1; end endtask\n' % (busy, accept)
    sv += 'task baseline; begin\n'
    for name in scalar_names:
        sv += '%s=%d;\n' % (aliases[name], 1 if name in ['cmd_valid', 'cmd_ready', 'cache_enable'] else 0)
    sv += "%s=32'hc0;%s=4'hf;%s=32'd1;%s=0;end endtask\n" % tuple(aliases[n] for n in ['cmd_addr', 'cmd_wmask', 'cmd_wdata', 'row_count'])
    sv += "initial begin values[0]=0;values[1]=1;values[2]=2'bxx;values[3]=2'bzz;baseline();check();\n"
    sv += 'for(i=0;i<4;i=i+1)for(j=0;j<4;j=j+1)for(k=0;k<4;k=k+1)begin baseline();%s=values[i];%s=values[j];%s=values[k];check();end\n' % tuple(aliases[n] for n in ['manual_busy', 'row_active', 'row_start'])
    for name in names:
        sv += 'for(i=0;i<4;i=i+1)begin baseline();%s=values[i];check();end\n' % aliases[name]
    sv += '$display("MOCK147_FOUR_STATE_PASS cases=%0d native_scheduling_proof=0",cases);$finish;end\nendmodule\n'
    (out / 'four-state.sv').write_text(sv)
    command('four-state-build', ['iverilog', '-g2012', '-s', 'tb', '-o', out / 'four-state', out / 'four-state.sv'])
    command('four-state-run', ['vvp', out / 'four-state'])

    lines = []
    for tag, b in reversed(list(enumerate(bindings))):
        target = 'tb_xu_soc_ppa.' + b['target'] + ('[%d]' % b['lane'] if b['lane'] >= 0 else '')
        lines.append('XU_PRIVATE147_BIND tag=%d logical=%s lane=%d width=%d sources=%d phase_mask=%d source=%s.%s target=%s source_type=36' %
                     (tag, b['logical'], b['lane'], b['width'], b['parts'], b['phases'], b['scope'], b['names'][0], target))
    for tag, macro in enumerate(inventory['macros']):
        instance = macro['instance']; role = 2 if instance.startswith('u_shared/') else 1 if '/u_e203_itcm_ram/' in instance else 0
        lines.append('XU_MAPPED111_GEOMETRY tag=%d role=%d status=PASS rows=256 row_bits=64 unique=256 memory_type=116 reg_words=256 memoryword_words=0 parent_present=256 scope_present=256 index_present=256 name=tb_xu_soc_ppa.dut.%s' % (tag, role, instance.replace('/', '.')))
    lines += ['XU_PRIVATE147_ADAPTER_READY logical_references=72 private_references=60 native_bindings=84 original_preload_macros=288 Q_WRITES=0 OTHER_DUT_FF_WRITES=0',
              'XU_PRIVATE147_PRELOAD_ROLE_DONE role=1 macros=32 rows=256 bits=64 arbitrary_XZ_preserved=1 Q_WRITES=0',
              'XU_PRIVATE147_PRELOAD_ROLE_DONE role=2 macros=256 rows=256 bits=64 arbitrary_XZ_preserved=1 Q_WRITES=0',
              'XU_CANDIDATE_UPLOAD_PASS task=0 w_commits=16384 bias=256 x_commits=6336 rows=99 starts=3168 dones=3168 pops_retired=3168',
              'TASK_PASS layer=0 outputs=25344 writes=50688 cycles=990657 firmware_cycles=990677',
              'XU_LF_CLOCK_STATIC_PASS nominal_hz=32768 checked_edges=1 max_phase_error_fs=1',
              'XU_CLOCK_STATIC_PASS checked_hf_edges=1',
              'XU_PRIVATE147_ORIGINAL_EXU_HALT_REACHED logical=72 private=60 bindings=84 pll_samples=1 reset_samples=1 main_samples=1 Q_WRITES=0 OTHER_DUT_FF_WRITES=0 QUALIFICATION_PENDING=1']
    fatal_line = next(n for n, line in enumerate(generated.splitlines(), 1) if '$fatal(1,"' + m.GATE + '");' in line)
    path = str(prepared / 'tb_private147.sv')
    fatal = 'Fatal: "%s", %d: tb_xu_soc_ppa: at time 2 fs\n%s\n$finish called from file "%s", line %d.\n$finish at simulation time 2\n' % (path, fatal_line, m.GATE, path, fatal_line)
    raw = ('\n'.join(lines) + '\n' + fatal).encode()
    result = m.classify(raw, 1, prepared / 'tb_private147.sv', bindings, inventory)
    need(result['status'] == m.TERMINAL and result['qualification'] == 'NOT_QUALIFIED', 'classification escapes qualification gate')
    negatives = [('zero-exit', raw, 0), ('no-fatal-block', ('\n'.join(lines) + '\n' + m.GATE + '\n').encode(), 1),
                 ('wrong-fatal-file', raw.replace(path.encode(), b'/wrong/tb.sv'), 1),
                 ('wrong-fatal-time', raw.replace(b'at time 2 fs', b'at time 3 fs'), 1),
                 ('duplicate-binding', raw.replace(lines[1].encode(), lines[0].encode()), 1),
                 ('wrong-width', raw.replace(b'width=48 ', b'width=47 ', 1), 1),
                 ('wrong-source-type', raw.replace(b'source_type=36', b'source_type=29', 1), 1),
                 ('wrong-geometry-rowcount', raw.replace(b'rows=256 row_bits=64', b'rows=255 row_bits=64', 1), 1),
                 ('wrong-geometry-bijection', raw.replace(b'GEOMETRY tag=335 ', b'GEOMETRY tag=334 '), 1),
                 ('wrong-geometry-owner', raw.replace(b'role=2 status=PASS', b'role=0 status=PASS', 1), 1),
                 ('missing-preload', raw.replace(lines[-7].encode(), b''), 1),
                 ('earlier-rejection', b'XU_PRIVATE147_ADAPTER_REJECT\n' + raw, 1),
                 ('unexpected-SOC_PASS', raw + b'SOC_PASS tasks=1\n', 1),
                 ('missing-sampling-context', raw.replace(b'pll_samples=1', b'pll_samples=0'), 1)]
    for name, data, code in negatives:
        try:
            m.classify(data, code, prepared / 'tb_private147.sv', bindings, inventory)
        except ValueError:
            pass
        else:
            raise AssertionError('malformed classifier fixture accepted: ' + name)
    manifest = dict(schema='xu.private147.local-review.v1', status='LOCAL_MECHANISM_CHECKS_PASS_NOT_MAPPED_VCS_OR_QUALIFICATION',
                    qualification='NOT_QUALIFIED', checks=checks, binding_mock_modes=11, classifier_negative_cases=len(negatives),
                    original_tb_sha256=m.base.TB_SHA, original_fatals_preserved=86, native_bindings=84,
                    logical_references=72, private_references=60, source_transform_review=state['source_transform_review'],
                    limitations=['C VPI mocks and Icarus structural/four-state fixtures only.',
                                 'No actual mapped VCS execution, native scheduling, timing, storage-readback, activity, power or energy proof.'])
    m.dump(out / 'review147.json', manifest)
    print(manifest['status'])


if __name__ == '__main__':
    main()
