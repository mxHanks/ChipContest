#!/usr/bin/env python3
"""Passive profile SRAM/X probes and lossless, inventory-bound SAIF aliases.

No DUT assignment, force, preload, model change, or native tool invocation.
The caller owns source/tool freezes, window qualification and mapped relocation.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re

SCHEMA = 'xu-profile-macro-inventory145-v1'
PIN_WIDTHS = {
    ref: dict(CLK=1, CEN=1, WEN=16, A=address, D=16, EMA=3, EMAW=2,
              GWEN=1, RET1N=1, Q=16)
    for ref, address in [('RAMSP1024X16', 10), ('RAMSP128X16', 7)]
}
HIERARCHY = r'[A-Za-z_][A-Za-z0-9_$]*(?:\[\d+\])?(?:\.[A-Za-z_][A-Za-z0-9_$]*(?:\[\d+\])?)*'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def identity(path):
    path = Path(path).absolute()
    require(path.is_file(), 'regular input file required: ' + str(path))
    return dict(path=str(path), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def _hierarchy(value):
    require(isinstance(value, str) and re.fullmatch(HIERARCHY, value),
            'unsupported actual RTL hierarchy: ' + str(value))
    return value


def render_probes(refs, stage_expr='tb_xu_soc_ppa.xu_clear_stage', include_x=True):
    """Return global type binds; stage is 0=clear, 1=payload, 2=end.

    The caller must declare stage_expr in its TB. Every macro announces its
    actual %m. Physical writes are logged only below u_accel_icb_slave, while
    pin aliases and inventory include all instances of the requested refs.
    """
    refs = list(refs)
    require(refs and len(set(refs)) == len(refs) and set(refs) <= set(PIN_WIDTHS),
            'unique supported SRAM references required')
    _hierarchy(stage_expr)
    lines = ['`timescale 1ns/1fs', '// xu passive simulation probes only.']
    for ref in sorted(refs):
        widths = PIN_WIDTHS[ref]
        module = 'xu_macro145_' + ref.lower()
        ports = ['  input %sxu_in_%s' %
                 (('[%d:0] ' % (width - 1)) if width > 1 else '', pin)
                 for pin, width in widths.items()]
        lines += ['module ' + module + '(', ',\n'.join(ports), ');']
        for pin, width in widths.items():
            declaration = '[%d:0] ' % (width - 1) if width > 1 else ''
            lines += ['  reg ' + declaration + pin + ';',
                      '  initial ' + pin + ' = xu_in_' + pin + ';',
                      '  always @(xu_in_' + pin + ') ' + pin + ' = xu_in_' + pin + ';']
        lines += [
            '  string xu_actual_scope;',
            '  bit xu_accelerator = 0;',
            '  integer xu_i;',
            '  initial begin',
            '    xu_actual_scope = $sformatf("%m");',
            '    for (xu_i=0; xu_i+18<=xu_actual_scope.len(); xu_i=xu_i+1)',
            '      if (xu_actual_scope.substr(xu_i,xu_i+17)=="u_accel_icb_slave.") xu_accelerator=1;',
            '    $display("XU_MACRO145 ref=' + ref + ' scope=%m a_bits=' + str(widths['A']) +
            ' pin_bits=' + str(sum(widths.values())) + '");',
            '  end',
            '  always @(posedge xu_in_CLK) begin',
            "    if (xu_accelerator && xu_in_CEN===1'b0 && xu_in_GWEN===1'b0 && xu_in_WEN!==16'hffff)",
            '      $display("XU_MACRO_WRITE145 ref=' + ref + ' scope=%m tick_fs=%0.0f stage=%0d addr=%h data=%h mask=%h",',
            '               $realtime*1000000.0, ' + stage_expr + ', xu_in_A, xu_in_D, ~xu_in_WEN);',
            '  end', 'endmodule',
            'bind ' + ref + ' ' + module + ' xu_pin_probe (' +
            ', '.join('.xu_in_%s(%s)' % (pin, pin) for pin in widths) + ');', '']
    if include_x:
        ports = ['  input clock, io_wen', '  input [5:0] io_waddr',
                 '  input [15:0] io_wdata'] + ['  input [15:0] data_%d' % i for i in range(64)]
        lines += ['module xu_xrow145(', ',\n'.join(ports), ');',
                  '  wire [15:0] xu_data [0:63];']
        lines += ['  assign xu_data[%d] = data_%d;' % (i, i) for i in range(64)]
        lines += ['  reg [5:0] xu_addr;', '  reg [15:0] xu_word;', '  integer xu_stage;',
                  '  initial $display("XU_X145 scope=%m words=64");',
                  '  always @(posedge clock) begin',
                  "    if (io_wen===1'b1) begin",
                  "      if ((^{io_waddr,io_wdata})===1'bx) $fatal(1,\"XU_X145 unknown actual X commit\");",
                  '      xu_addr=io_waddr; xu_word=io_wdata; xu_stage=' + stage_expr + ';',
                  '      $display("XU_X_WRITE145 scope=%m tick_fs=%0.0f stage=%0d addr=%0d data=%h",',
                  '               $realtime*1000000.0,xu_stage,xu_addr,xu_word);',
                  '      #0.000001; // 1fs: observe the real storage after its NBA update.',
                  '      if (xu_data[xu_addr]!==xu_word) $fatal(1,"XU_X145 actual storage echo mismatch");',
                  '      $display("XU_X_ECHO145 scope=%m tick_fs=%0.0f stage=%0d addr=%0d data=%h",',
                  '               $realtime*1000000.0,xu_stage,xu_addr,xu_data[xu_addr]);',
                  '    end', '  end', 'endmodule',
                  'bind XRowBuffer xu_xrow145 xu_x_probe (' +
                  ', '.join('.%s(%s)' % (pin, pin) for pin in
                            ['clock', 'io_wen', 'io_waddr', 'io_wdata'] + ['data_%d' % i for i in range(64)]) + ');', '']
    return '\n'.join(lines)


def _glob(pattern, value):
    # Literal hierarchy brackets are never interpreted as fnmatch character sets.
    return re.fullmatch(re.escape(pattern).replace(r'\*', '.*').replace(r'\?', '.'), value) is not None


def parse_inventory(log, groups, expected_count=None, dut_scope='tb_xu_soc_ppa.dut', expected_x_count=None):
    """Validate every actual macro against exactly one memory_group ref/scope.

    log is simulator text (or a Path). Group patterns use the implementation's
    hierarchy relative to dut_scope. This is an RTL elaboration inventory;
    mapped names must be bound separately by the caller's native inventory.
    """
    text = Path(log).read_text() if isinstance(log, Path) else log
    require(isinstance(text, str), 'inventory log must be text or Path')
    _hierarchy(dut_scope)
    require(isinstance(groups, list) and groups, 'nonempty memory groups required')
    names = set()
    for group in groups:
        require(group['name'] not in names, 'duplicate memory group')
        names.add(group['name'])
        require(group.get('macro_ref') in PIN_WIDTHS and type(group.get('count')) is int and group['count'] > 0,
                'invalid group ref/count')
        widths = PIN_WIDTHS[group['macro_ref']]
        require(group.get('depth') == 2 ** widths['A'] and group.get('width') == 16,
                'group geometry differs from physical macro')
        require(isinstance(group.get('instance_pattern'), str) and group['instance_pattern'] and
                not group['instance_pattern'].startswith('/') and '.' not in group['instance_pattern'],
                'expected relative slash hierarchy group pattern')
    counts = {name: 0 for name in names}
    macros, x_buffers, seen = [], [], set()
    for line in text.splitlines():
        if line.startswith('XU_MACRO145'):
            match = re.fullmatch(r'XU_MACRO145 ref=(\w+) scope=(\S+) a_bits=(\d+) pin_bits=(\d+)', line)
            require(match, 'malformed actual macro announcement')
            ref, probe, address, bits = match.groups()
            require(ref in PIN_WIDTHS, 'unexpected actual macro ref')
            widths = PIN_WIDTHS[ref]
            require((int(address), int(bits)) == (widths['A'], sum(widths.values())), 'actual macro pin schema differs')
            _hierarchy(probe)
            require(probe.endswith('.xu_pin_probe'), 'macro announcement must come from exact bound probe')
            instance = probe[:-len('.xu_pin_probe')]
            require(instance.startswith(dut_scope + '.'), 'actual macro outside exact DUT scope')
            require(instance not in seen, 'duplicate actual macro announcement')
            relative = instance[len(dut_scope) + 1:].replace('.', '/')
            matches = [g for g in groups if g['macro_ref'] == ref and _glob(g['instance_pattern'], relative)]
            require(len(matches) == 1, 'actual macro must match exactly one group: ' + instance)
            group = matches[0]['name']; counts[group] += 1; seen.add(instance)
            macros.append(dict(instance=instance, relative_instance=relative, ref_name=ref,
                               probe_scope=probe, group=group, pin_widths=dict(widths)))
        elif line.startswith('XU_X145 '):
            match = re.fullmatch(r'XU_X145 scope=(\S+) words=64', line)
            require(match, 'malformed actual X buffer announcement')
            probe = _hierarchy(match.group(1))
            require(probe.endswith('.xu_x_probe'), 'X announcement must come from exact bound probe')
            instance = probe[:-len('.xu_x_probe')]
            require(instance.startswith(dut_scope + '.'), 'actual X buffer outside exact DUT scope')
            require(instance not in {x['instance'] for x in x_buffers}, 'duplicate actual X buffer')
            x_buffers.append(dict(instance=instance, probe_scope=probe, words=64))
    require(all(counts[g['name']] == g['count'] for g in groups), 'actual per-group macro counts differ: ' + str(counts))
    expected = sum(g['count'] for g in groups)
    require(len(macros) == expected and (expected_count is None or expected_count == expected),
            'actual/declared total macro count differs')
    require(expected_x_count is None or len(x_buffers) == expected_x_count, 'actual X buffer count differs')
    return dict(schema=SCHEMA, status='ELABORATED_REVIEW_PENDING_NOT_QUALIFIED', dut_scope=dut_scope,
                macro_count=len(macros), pin_bit_count=sum(sum(m['pin_widths'].values()) for m in macros),
                macros=sorted(macros, key=lambda m: m['instance']), group_counts=counts,
                memory_groups=copy.deepcopy(groups), x_buffers=sorted(x_buffers, key=lambda x: x['instance']),
                log_sha256=hashlib.sha256(text.encode()).hexdigest())


def _module(value, name):
    if isinstance(value, (str, Path)):
        spec = importlib.util.spec_from_file_location(name, str(value))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return value


def normalize(raw, out, inventory, reader, alias_helpers):
    """Move complete measured pin aliases to their inventoried macro pins.

    reader and alias_helpers are frozen module objects or file paths. Only the
    stateless raw_tree/write_sexpr/atom/decode_atom helpers are used. Preserve
    all real DUT NET/PORT entries; matching native pins must agree with aliases.
    Unknown/both dwell and any extra statistics are copied without alteration.
    """
    reader = _module(reader, 'xu_macro145_saif_reader')
    helper = _module(alias_helpers, 'xu_macro145_alias_helpers')
    raw, out = Path(raw).absolute(), Path(out).absolute()
    require(raw.resolve() != out.resolve() and not out.exists() and not out.is_symlink(),
            'normalized output must be a new file distinct from raw')
    if isinstance(inventory, (str, Path)):
        require(Path(inventory).resolve() != out.resolve(), 'output must differ from inventory')
        inventory = json.loads(Path(inventory).read_text())
    require(inventory.get('schema') == SCHEMA and inventory.get('status') == 'ELABORATED_REVIEW_PENDING_NOT_QUALIFIED' and
            inventory.get('macro_count') == len(inventory.get('macros', [])) > 0,
            'validated elaborated inventory required')
    original = identity(raw)
    measured = reader.read_saif(raw)
    source = {(s['kind'], s['path']): s for s in measured['signals']}
    pairs, spellings, roots = {}, {}, set()
    for macro in inventory['macros']:
        ref, instance, probe = macro['ref_name'], _hierarchy(macro['instance']), _hierarchy(macro['probe_scope'])
        require(ref in PIN_WIDTHS and macro['pin_widths'] == PIN_WIDTHS[ref], 'inventory pin schema differs')
        require(probe == instance + '.xu_pin_probe' and instance.startswith(inventory['dut_scope'] + '.'),
                'inventory probe/DUT binding differs')
        native, scope = instance.replace('.', '/'), probe.replace('.', '/')
        require(scope not in roots, 'duplicate inventoried macro probe'); roots.add(scope)
        for pin, width in PIN_WIDTHS[ref].items():
            for bit in range(width):
                name = pin if width == 1 else '%s[%d]' % (pin, bit)
                alias, target = scope + '/' + name, native + '/' + name
                require(alias not in pairs, 'duplicate pin alias'); pairs[alias] = target
                for spelling in [alias, native + '/xu_pin_probe.' + name]:
                    require(spelling not in spellings, 'ambiguous alias encoding'); spellings[spelling] = alias
    require(len(pairs) == inventory.get('pin_bit_count'), 'inventory pin-bit total differs')

    def probe_signal(path):
        return any(path.startswith(root + '/') or path.startswith(root + '.') for root in roots)

    aliases, actual_names = {}, {}
    for signal in measured['signals']:
        path = signal['path']
        if path in spellings:
            canonical = spellings[path]
            require(signal['kind'] == 'NET' and canonical not in aliases, 'duplicate/non-NET alias bit')
            aliases[canonical] = signal; actual_names[canonical] = path
        elif probe_signal(path):
            # Ports and bookkeeping inside an exact inventoried probe are
            # disposable. A malformed pin bit is not disposable bookkeeping.
            name = re.split(r'[/\.]', path)[-1]
            require(not re.fullmatch(r'(?:CLK|CEN|WEN|A|D|EMA|EMAW|GWEN|RET1N|Q)(?:\[\d+\])?', name),
                    'unexpected alias pin bit: ' + path)
        else:
            require('/xu_pin_probe/' not in path and '/xu_pin_probe.' not in path,
                    'uninventoried macro probe in raw SAIF: ' + path)
    require(set(aliases) == set(pairs), 'missing actual macro alias bits: ' + str(len(set(pairs) - set(aliases))))
    preserved = {key: value for key, value in source.items() if not probe_signal(value['path'])}
    inject, reused = {}, 0
    stats = lambda s: {k: v for k, v in s.items() if k not in ('kind', 'path')}
    equivalent = lambda a, b: all(stats(a).get(k, 0) == stats(b).get(k, 0) for k in set(stats(a)) | set(stats(b)))
    for alias, target in pairs.items():
        native = [preserved[(kind, target)] for kind in ('NET', 'PORT') if (kind, target) in preserved]
        require(all(equivalent(aliases[alias], s) for s in native), 'native macro pin differs from alias: ' + target)
        if native:
            reused += 1
        else:
            inject[target] = aliases[alias]
    tree = helper.raw_tree(raw.read_text())
    instances = {}

    def visit(node, parent):
        if not isinstance(node, list) or not node:
            return
        if node[0] == 'INSTANCE':
            current = parent + [helper.decode_atom(node[1])]
            key = '/'.join(current)
            require(key not in instances, 'duplicate SAIF instance: ' + key)
            instances[key] = node
            kept = []
            for child in node[2:]:
                if isinstance(child, list) and child and child[0] == 'INSTANCE' and '/'.join(current + [helper.decode_atom(child[1])]) in roots:
                    continue
                visit(child, current); kept.append(child)
            node[2:] = kept
        elif node[0] in ('NET', 'PORT'):
            node[1:] = [s for s in node[1:] if not probe_signal('/'.join(parent + [helper.decode_atom(s[0])]))]
        else:
            for child in node[1:]:
                visit(child, parent)
    visit(tree, [])
    for target, signal in sorted(inject.items()):
        scope, name = target.rsplit('/', 1)
        parts = scope.split('/')
        for depth in range(1, len(parts) + 1):
            key = '/'.join(parts[:depth])
            if key not in instances:
                node = ['INSTANCE', helper.atom(parts[depth - 1])]
                (tree if depth == 1 else instances['/'.join(parts[:depth - 1])]).append(node)
                instances[key] = node
        destination = instances[scope]
        ports = next((n for n in destination[2:] if isinstance(n, list) and n and n[0] == 'PORT'), None)
        if ports is None:
            ports = ['PORT']; destination.append(ports)
        ports.append([helper.atom(name)] + [[key, str(value)] for key, value in stats(signal).items()])
    out.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with out.open('x') as stream:
            created = True
            helper.write_sexpr(stream, tree)
        transformed = reader.read_saif(out)
        observed = {(s['kind'], s['path']): s for s in transformed['signals']}
        require(all(observed.get(key) == value for key, value in preserved.items()), 'nonalias DUT activity changed')
        require(set(observed) == set(preserved) | {('PORT', target) for target in inject}, 'unrelated SAIF signal introduced/dropped')
        require(all(equivalent(observed[('PORT', target)], value) for target, value in inject.items()), 'alias statistics changed')
        require(all(transformed[key] == measured[key] for key in ('duration_ticks', 'timescale_seconds')), 'SAIF time base changed')
        require(identity(raw) == original, 'raw SAIF changed during normalization')
        return dict(schema='xu-profile-macro-normalization145-v1', status='NORMALIZED_REVIEW_PENDING_NOT_QUALIFIED',
                    raw_saif=original, normalized_saif=identity(out), generator=identity(__file__),
                    inventory_sha256=hashlib.sha256(json.dumps(inventory, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                    alias_name_sha256=hashlib.sha256(json.dumps(sorted(actual_names.items())).encode()).hexdigest(),
                    macro_count=inventory['macro_count'],
                    pin_bit_count=len(pairs), injected_pin_bits=len(inject), native_pin_bits_verified_reused=reused,
                    nonalias_signal_count_preserved=len(preserved),
                    alias_unknown_bit_ticks=sum(s.get(k, 0) for s in aliases.values() for k in ('TX', 'TZ', 'TB')),
                    duration_ticks=measured['duration_ticks'], timescale_seconds=measured['timescale_seconds'],
                    policy='Complete actual-macro pin bijection; all raw nonprobe activity preserved; no inferred activity.')
    except Exception:
        if created and out.exists():
            out.unlink()
        raise
