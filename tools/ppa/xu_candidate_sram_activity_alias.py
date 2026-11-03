#!/usr/bin/env python3
"""Generate explicit frozen S2c SRAM observers and normalize measured aliases.

No functional RTL/model is edited. Every normalized bit comes from a measured
observer bit; missing activity is an error and X/Z/B dwell is never made zero.
The raw SAIF is immutable. This tool makes no power or annotation claim.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import xu_candidate_activity_context as context
PIN_WIDTHS = {'CLK': 1, 'CEN': 1, 'WEN': 16, 'A': 10, 'D': 16,
              'EMA': 3, 'EMAW': 2, 'GWEN': 1, 'RET1N': 1, 'Q': 16}
SCHEMA = 'xu-s2c-sram-activity-alias-v1'
IDENTIFIER = r'[A-Za-z_][A-Za-z0-9_$]*(?:\[\d+\])?'
TOKEN = re.compile(r'//[^\n]*|/\*.*?\*/|\(|\)|"(?:\\.|[^"\\])*"|(?:\\.|[^\s()])+', re.S)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def activity_module():
    spec = importlib.util.spec_from_file_location('xu_alias_saif_reader', ROOT / 'tools/scripts/xu_soc_activity.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def identity(path):
    path = Path(path).absolute()
    require(path.is_file() and not path.is_symlink(), 'expected regular non-symlink file: ' + str(path))
    return {'path': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def canonical_hash(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def hierarchy(value):
    require(isinstance(value, str) and re.fullmatch(IDENTIFIER + r'(?:\.' + IDENTIFIER + ')*', value),
            'hierarchy must use exact ordinary identifiers and constant indices: ' + str(value))
    return value


def slash(value):
    return hierarchy(value).replace('.', '/')


def full_soc_macros(root, dut_scope):
    """Explicit frozen S2c + tool adapter topology, not elaboration proof."""
    context.tool_identity()
    context.source_identity(root)
    root = Path(root).resolve()
    rtl = 'third-party/e203_hbirdv2/rtl/e203/'
    guards = {
        'tools/ppa/xu_soc_ppa_top.sv': [r'e203_soc_top\s*#\s*\(\.EXTERNAL_SYSMEM\(1\)\)\s+u_soc\s*\(',
                                      r'xu_shared_icb_sram\s+u_shared\s*\('],
        'tools/ppa/xu_shared_icb_sram.sv': [r'sirv_sim_ram\s*#\s*\(\.DP\(131072\),\.DW\(32\),\.MW\(4\),\.AW\(17\),\.FORCE_X2ZERO\(0\)\)\s+storage'],
        'tools/ppa/xu_sirv_sram_adapter.sv': [r'begin:\s*macro_storage', r'begin:\s*depth_bank',
                                             r'begin:\s*width_lane', r'RAMSP1024X16\s+macro\s*\('],
        'tools/ppa/xu_weight_sram_adapter.sv': [r'module\s+mem_1024x16\b', r'RAMSP1024X16\s+macro\s*\('],
        rtl + 'soc/e203_soc_top.v': [r'e203_subsys_top\s+u_e203_subsys_top\s*\('],
        rtl + 'subsys/e203_subsys_top.v': [r'e203_subsys_main\s+u_e203_subsys_main\s*\('],
        rtl + 'subsys/e203_subsys_main.v': [r'e203_cpu_top\s+u_e203_cpu_top\s*\(', r'e203_subsys_perips\s+u_e203_subsys_perips\s*\('],
        rtl + 'subsys/e203_subsys_perips.v': [r'accel_icb_slave\s+u_accel_icb_slave\s*\('],
        rtl + 'core/e203_cpu_top.v': [r'e203_srams\s+u_e203_srams\s*\('],
        rtl + 'core/e203_srams.v': [r'e203_itcm_ram\s+u_e203_itcm_ram\s*\(', r'e203_dtcm_ram\s+u_e203_dtcm_ram\s*\('],
        rtl + 'core/e203_itcm_ram.v': [r'\)\s*u_e203_itcm_gnrl_ram\s*\('],
        rtl + 'core/e203_dtcm_ram.v': [r'\)\s*u_e203_dtcm_gnrl_ram\s*\('],
        rtl + 'general/sirv_gnrl_ram.v': [r'\)\s*u_sirv_sim_ram\s*\('],
        rtl + 'core/config.v': [r'^\s*`define\s+E203_CFG_ITCM_ADDR_WIDTH\s+16\s*$',
                                r'^\s*`define\s+E203_CFG_DTCM_ADDR_WIDTH\s+16\s*$',
                                r'^\s*`define\s+E203_CFG_HAS_ITCM\b', r'^\s*`define\s+E203_CFG_HAS_DTCM\b'],
        rtl + 'core/e203_defines.v': [r'`define\s+E203_ITCM_DATA_WIDTH\s+64\b', r'`define\s+E203_DTCM_DATA_WIDTH\s+32\b'],
        rtl + 'perips/accel_icb_slave.v': [r'LinearAutoGroupCore\s+u_linear_compute_core\s*\('],
        rtl + 'perips/LinearCachedCore.sv': [r'LinearComputeCore\s+core\s*\('],
        rtl + 'perips/LinearComputeCore.sv': [r'WeightBankArray\s+weightBanks\s*\('],
        rtl + 'perips/WeightBankArray.sv': [r'WeightBank\s+banks_' + str(i) + r'\s*\(' for i in range(8)],
        rtl + 'perips/WeightBank.sv': [r'Sram1024x16\s+sram0\s*\(', r'Sram1024x16\s+sram1\s*\('],
        rtl + 'perips/Sram1024x16.sv': [r'mem_1024x16\s+mem_ext\s*\('],
    }
    sources = []
    for relative, patterns in sorted(guards.items()):
        path = (ROOT if relative.startswith('tools/ppa/') else root) / relative
        text = re.sub(r'/\*.*?\*/|//[^\n]*', '', path.read_text(), flags=re.S)
        for pattern in patterns:
            require(re.search(pattern, text, re.M | re.S), 'current source topology differs: ' + relative + ': ' + pattern)
        sources.append(identity(path))
    main = dut_scope + '.u_soc.u_e203_subsys_top.u_e203_subsys_main'
    srams = main + '.u_e203_cpu_top.u_e203_srams'
    records = []
    for group, base, banks, lanes in [
        ('shared', dut_scope + '.u_shared.storage', 128, 2),
        ('itcm', srams + '.u_e203_itcm_ram.u_e203_itcm_gnrl_ram.u_sirv_sim_ram', 8, 4),
        ('dtcm', srams + '.u_e203_dtcm_ram.u_e203_dtcm_gnrl_ram.u_sirv_sim_ram', 16, 2),
    ]:
        for bank in range(banks):
            for lane in range(lanes):
                records.append({'group': group, 'instance': base + '.macro_storage.depth_bank[%d].width_lane[%d].macro' % (bank, lane)})
    weights = main + '.u_e203_subsys_perips.u_accel_icb_slave.u_linear_compute_core.core.weightBanks'
    for bank in range(8):
        for half in range(2):
            records.append({'group': 'accelerator_weights', 'instance': weights + '.banks_%d.sram%d.mem_ext.macro' % (bank, half)})
    require(len(records) == 336, 'full SoC must have 336 macros')
    return records, sources


def render_observer(macros, dut_scope, observer_scope, placement):
    """Use direct references and blocking event copies; never sanitize X/Z."""
    hierarchy(dut_scope)
    hierarchy(observer_scope)
    parent, separator, observer_name = observer_scope.rpartition('.')
    require(separator and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$]*', observer_name), 'observer scope needs an ordinary leaf name')
    if placement == 'bind':
        require(parent == dut_scope, 'bound observer must be immediately inside DUT')
        lines = ['// xu simulation-only pin observer. No force, model edit, or synthesis source.',
                 '`ifndef SYNTHESIS', 'module xu_sram_activity_alias_observer;', '  generate']
    else:
        lines = ['// Include INSIDE ' + parent + ' module. xu simulation-only pin observer.',
                 '`ifndef SYNTHESIS', 'generate', '  if (1) begin : ' + observer_name]
    for index, macro in enumerate(macros):
        instance = hierarchy(macro['instance'])
        lines.append('    if (1) begin : macro_%04d' % index)
        for pin, width in PIN_WIDTHS.items():
            declaration = ('[%d:0] ' % (width - 1)) if width > 1 else ''
            lines += ['      reg ' + declaration + pin + ';',
                      '      initial ' + pin + ' = ' + instance + '.' + pin + ';',
                      '      always @(' + instance + '.' + pin + ') ' + pin + ' = ' + instance + '.' + pin + ';']
        lines.append('    end')
    if placement == 'bind':
        lines += ['  endgenerate', 'endmodule',
                  'bind ' + dut_scope + ' xu_sram_activity_alias_observer ' + observer_name + '();']
    else:
        lines += ['  end', 'endgenerate']
    lines += ['`endif', '']
    return '\n'.join(lines)


def generate(root, out, dut_scope='tb_xu_soc_ppa.dut', observer_scope=None, placement='bind', macro_paths=None):
    root, out = Path(root).resolve(), Path(out).absolute()
    hierarchy(dut_scope)
    observer_scope = observer_scope or ((dut_scope if placement == 'bind' else dut_scope.rsplit('.', 1)[0]) + '.xu_sram_activity_alias')
    require(placement in ('bind', 'include'), 'unknown observer placement')
    require(not out.exists(), 'observer output directory must be new')
    require(macro_paths is None, 'candidate mapping forbids unguarded explicit probes')
    macros, sources = full_soc_macros(root, dut_scope)
    mode = 'frozen_s2c_source_guarded_full_soc_336'
    require(all(m['instance'].startswith(dut_scope + '.') for m in macros), 'macro is outside DUT scope')
    require(not any(observer_scope.startswith(m['instance'] + '.') for m in macros), 'observer must not be inside a macro')
    out.mkdir(parents=True)
    path = out / ('xu_candidate_sram_activity_alias.sv' if placement == 'bind' else 'xu_candidate_sram_activity_alias.svh')
    path.write_text(render_observer(macros, dut_scope, observer_scope, placement))
    mapping = {'schema': SCHEMA, 'status': 'GENERATED_NOT_CAPTURE_OR_POWER_QUALIFIED', 'mode': mode,
               'root': str(root), 'profile': context.PROFILE, 'source_context': context.source_identity(root),
               'tool_context': context.tool_identity(), 'dut_scope': dut_scope, 'observer_scope': observer_scope,
               'placement': placement, 'pin_widths': PIN_WIDTHS, 'macros': macros,
               'macro_count': len(macros), 'alias_bit_count': len(macros) * sum(PIN_WIDTHS.values()),
               'observer_source': identity(path), 'generator': identity(__file__),
               'source_files': sources, 'saif_reader': identity(ROOT / 'tools/scripts/xu_soc_activity.py'),
               'limitation': 'Source guards are not elaboration proof. Actual simulator alias equality and PT annotation/power review remain required.'}
    write_json(out / 'xu_candidate_sram_activity_alias.mapping.json', mapping)
    return mapping


def validate_mapping(path):
    path = Path(path)
    mapping = json.loads(path.read_text())
    require(mapping.get('schema') == SCHEMA and mapping.get('pin_widths') == PIN_WIDTHS, 'unsupported observer mapping/pin widths')
    require(mapping.get('placement') in ('bind', 'include'), 'invalid observer placement')
    hierarchy(mapping['dut_scope'])
    hierarchy(mapping['observer_scope'])
    macros = mapping['macros']
    require(isinstance(macros, list) and macros and len(macros) == mapping['macro_count'], 'invalid macro mapping count')
    require(len({m['instance'] for m in macros}) == len(macros), 'mapping target macros are not bijective')
    require(mapping['alias_bit_count'] == len(macros) * sum(PIN_WIDTHS.values()), 'mapping bit count differs')
    for item in [mapping['observer_source'], mapping['generator'], mapping['saif_reader']] + mapping['source_files']:
        require(identity(item['path']) == item, 'mapping source identity changed: ' + item['path'])
    require(Path(mapping['generator']['path']).resolve() == Path(__file__).resolve(), 'mapping uses a different normalizer source')
    require(mapping.get('profile') == context.PROFILE, 'candidate mapping profile differs')
    require(mapping.get('source_context') == context.source_identity(mapping['root']), 'candidate mapping source context differs')
    require(mapping.get('tool_context') == context.tool_identity(), 'candidate mapping tool context differs')
    require(mapping['mode'] == 'frozen_s2c_source_guarded_full_soc_336', 'candidate mapping forbids unguarded/probe mode')
    expected, sources = full_soc_macros(mapping['root'], mapping['dut_scope'])
    require(macros == expected and sources == mapping['source_files'], 'full-SoC macro mapping differs from guarded topology')
    expected_source = render_observer(macros, mapping['dut_scope'], mapping['observer_scope'], mapping['placement'])
    require(Path(mapping['observer_source']['path']).read_text() == expected_source, 'observer source does not implement mapping')
    pairs = {}
    for index, macro in enumerate(macros):
        require(hierarchy(macro['instance']).startswith(mapping['dut_scope'] + '.'), 'mapped macro is outside DUT')
        alias = slash(mapping['observer_scope']) + '/macro_%04d/' % index
        target = slash(macro['instance']) + '/'
        for pin, width in PIN_WIDTHS.items():
            for bit in range(width):
                name = pin if width == 1 else pin + '[%d]' % bit
                pairs[alias + name] = target + name
    require(len(pairs) == len(set(pairs.values())) == mapping['alias_bit_count'], 'pin mapping is not bijective')
    return mapping, pairs


def raw_tree(source):
    """Preserve literal header/string tokens; comments and whitespace are cosmetic."""
    roots, stack = [], []
    for match in TOKEN.finditer(source):
        token = match.group()
        if token.startswith('//') or token.startswith('/*'):
            continue
        if token == '(':
            node = []
            (stack[-1] if stack else roots).append(node)
            stack.append(node)
        elif token == ')':
            require(stack, 'unbalanced SAIF expression')
            stack.pop()
        else:
            require(stack, 'SAIF token outside expression')
            stack[-1].append(token)
    require(not stack and len(roots) == 1 and roots[0][0] == 'SAIFILE', 'invalid SAIF root')
    return roots[0]


def decode_atom(token):
    if token.startswith('"'):
        token = token[1:-1]
    return re.sub(r'\\(.)', r'\1', token)


def atom(name):
    return re.sub(r'([\\()\s\[\]"])', r'\\\1', name)


def write_sexpr(output, node, depth=0):
    """Stream a tree without constructing another full serialized SAIF string."""
    indent = '  ' * depth
    output.write(indent + '(')
    prefix = []
    for part in node:
        if isinstance(part, list):
            break
        prefix.append(part)
    output.write(' '.join(prefix))
    rest = node[len(prefix):]
    if not rest:
        output.write(')\n')
        return
    if all(isinstance(part, list) and all(isinstance(item, str) for item in part) for part in rest) and node[0] not in ('INSTANCE', 'SAIFILE', 'NET', 'PORT'):
        for part in rest:
            output.write(' (' + ' '.join(part) + ')')
        output.write(')\n')
        return
    output.write('\n')
    for part in rest:
        require(isinstance(part, list), 'unsupported interleaved SAIF expression')
        write_sexpr(output, part, depth + 1)
    output.write(indent + ')\n')


def stats(signal):
    return {key: value for key, value in signal.items() if key not in ('path', 'kind')}


def equivalent(left, right):
    a, b = stats(left), stats(right)
    # Missing optional dwell buckets mean zero; no nonzero bucket is dropped.
    return all(a.get(key, 0) == b.get(key, 0) for key in set(a) | set(b))


def alias_name_encodings(mapping, pairs):
    """Enumerate exact source spellings; dots elsewhere remain literal names.

    VCS 2020 writes the named generate block and its register as one NET atom
    (macro_0000.CLK), while the canonical encoding uses an INSTANCE node. Do
    not split arbitrary dotted atoms or infer any other flattened hierarchy.
    """
    prefix = slash(mapping['observer_scope']) + '/'
    names = {}
    for index in range(mapping['macro_count']):
        block = 'macro_%04d' % index
        for pin, width in PIN_WIDTHS.items():
            for bit in range(width):
                name = pin if width == 1 else pin + '[%d]' % bit
                canonical = prefix + block + '/' + name
                require(canonical in pairs, 'alias encoding differs from pin mapping')
                for path, encoding in [(canonical, 'hierarchical'),
                                       (prefix + block + '.' + name, 'vcs_generate_net_atom')]:
                    require(path not in names, 'ambiguous observer alias spelling: ' + path)
                    names[path] = (canonical, encoding)
    require(len(names) == 2 * len(pairs), 'alias name encodings are not bijective per encoding')
    return names


def normalize(raw, mapping_path, out, receipt_path=None):
    raw, out = Path(raw).absolute(), Path(out).absolute()
    mapping_path = Path(mapping_path).absolute()
    receipt_path = Path(receipt_path).absolute() if receipt_path else out.with_suffix(out.suffix + '.receipt.json')
    require(len({p.resolve() for p in (raw, out, mapping_path, receipt_path)}) == 4, 'raw, output, mapping, and receipt paths must differ')
    require(not out.exists() and not out.is_symlink() and not receipt_path.exists() and not receipt_path.is_symlink(),
            'normalized SAIF and receipt must be new files')
    raw_identity = identity(raw)
    mapping, pairs = validate_mapping(mapping_path)
    reader = activity_module()
    measured = reader.read_saif(raw)
    source = {(s['kind'], s['path']): s for s in measured['signals']}
    observer_prefix = slash(mapping['observer_scope']) + '/'
    encodings = alias_name_encodings(mapping, pairs)
    aliases, alias_names, unexpected = {}, {}, []
    encoding_counts = {'hierarchical': 0, 'vcs_generate_net_atom': 0}
    for signal in measured['signals']:
        if not signal['path'].startswith(observer_prefix):
            continue
        require(signal['kind'] == 'NET', 'observer aliases must be ordinary RTL NET activity')
        if signal['path'] not in encodings:
            unexpected.append(signal['path'])
            continue
        canonical, encoding = encodings[signal['path']]
        require(canonical not in aliases, 'duplicate alias representation: ' + canonical)
        aliases[canonical] = signal
        alias_names[canonical] = signal['path']
        encoding_counts[encoding] += 1
    require(set(aliases) == set(pairs) and not unexpected,
            'missing or unexpected alias bits: missing=%d unexpected=%d' %
            (len(set(pairs) - set(aliases)), len(unexpected)))
    inject, native_reused, native_both = {}, 0, 0
    comparison = []
    for alias, target in sorted(pairs.items()):
        existing = [source[(kind, target)] for kind in ('NET', 'PORT') if (kind, target) in source]
        for native in existing:
            require(equivalent(aliases[alias], native), 'native macro pin differs from measured alias: ' + target + ' (' + native['kind'] + ')')
        if existing:
            native_reused += 1
            native_both += len(existing) == 2
        else:
            inject[target] = aliases[alias]
        comparison.append([alias, target, stats(aliases[alias])])
    tree = raw_tree(raw.read_text())
    instances = {}

    def visit(node, parent):
        if not isinstance(node, list) or not node:
            return
        if node[0] == 'INSTANCE':
            current = parent + [decode_atom(node[1])]
            key = '/'.join(current)
            require(key not in instances, 'duplicate SAIF INSTANCE path: ' + key)
            instances[key] = node
            kept = []
            for child in node[2:]:
                if isinstance(child, list) and child and child[0] == 'INSTANCE' and '/'.join(current + [decode_atom(child[1])]) == observer_prefix[:-1]:
                    continue
                visit(child, current)
                kept.append(child)
            node[2:] = kept
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
                node = ['INSTANCE', atom(parts[depth - 1])]
                if depth == 1:
                    tree.append(node)
                else:
                    instances['/'.join(parts[:depth - 1])].append(node)
                instances[key] = node
        destination = instances[scope]
        ports = next((n for n in destination[2:] if isinstance(n, list) and n and n[0] == 'PORT'), None)
        if ports is None:
            ports = ['PORT']
            destination.append(ports)
        ports.append([atom(name)] + [[key, str(value)] for key, value in stats(signal).items()])
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with out.open('x') as stream:
            write_sexpr(stream, tree)
        transformed = reader.read_saif(out)
        observed = {(s['kind'], s['path']): s for s in transformed['signals']}
        preserved = {key: s for key, s in source.items() if not s['path'].startswith(observer_prefix)}
        require(all(observed.get(key) == signal for key, signal in preserved.items()), 'nonalias raw SAIF activity changed')
        expected_keys = set(preserved) | {('PORT', path) for path in inject}
        require(set(observed) == expected_keys, 'normalizer introduced or dropped unrelated activity')
        require(all(equivalent(observed[('PORT', target)], signal) for target, signal in inject.items()), 'transformed alias dwell/TC differs')
        require(transformed['duration_ticks'] == measured['duration_ticks'] and transformed['timescale_seconds'] == measured['timescale_seconds'], 'SAIF time base changed')
        require(identity(raw) == raw_identity, 'raw SAIF changed during normalization')
        receipt = {'schema': 'xu-s2c-sram-activity-normalization-v1', 'status': 'NORMALIZED_NOT_ANNOTATION_OR_POWER_QUALIFIED',
                   'raw_saif': raw_identity, 'normalized_saif': identity(out), 'mapping': identity(mapping_path),
                   'observer_source': mapping['observer_source'], 'generator': identity(__file__),
                   'macro_count': mapping['macro_count'], 'alias_bit_count': len(pairs),
                   'alias_name_encoding_counts': encoding_counts,
                   'alias_name_comparison_sha256': canonical_hash(sorted(alias_names.items())),
                   'mapped_pin_bits_added_as_port': len(inject), 'native_pin_bits_verified_reused': native_reused,
                   'preexisting_native_net_and_port_bits_preserved': native_both,
                   'nonalias_raw_signal_count_preserved': len(preserved), 'per_bit_comparison_sha256': canonical_hash(comparison),
                   'duration_ticks': measured['duration_ticks'], 'timescale_seconds': measured['timescale_seconds'],
                   'alias_unknown_bit_ticks': sum(s.get(k, 0) for s in aliases.values() for k in ('TX', 'TZ', 'TB')),
                   'policy': 'Complete bijection; exact per-bit dwell/TC/all statistics; native duplicates must agree; no inferred activity; raw immutable.',
                   'limitation': 'Observer capture qualification, mapped PT annotation, native cross-kind duplicates, Liberty power and contest qualification require separate review.'}
        write_json(receipt_path, receipt)
        return receipt
    except Exception:
        if out.exists():
            out.unlink()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command')
    gen = sub.add_parser('generate')
    gen.add_argument('--root', type=Path, required=True, help='exact frozen S2c source checkout')
    gen.add_argument('--out', type=Path, required=True)
    gen.add_argument('--dut-scope', default='tb_xu_soc_ppa.dut')
    gen.add_argument('--observer-scope')
    gen.add_argument('--placement', choices=['bind', 'include'], default='bind')
    norm = sub.add_parser('normalize')
    norm.add_argument('--raw', type=Path, required=True)
    norm.add_argument('--mapping', type=Path, required=True)
    norm.add_argument('--out', type=Path, required=True)
    norm.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    require(args.command is not None, 'choose generate or normalize')
    if args.command == 'generate':
        result = generate(args.root, args.out, args.dut_scope, args.observer_scope, args.placement)
        print(json.dumps({key: result[key] for key in ('status', 'macro_count', 'alias_bit_count', 'observer_source')}, sort_keys=True))
    else:
        print(json.dumps(normalize(args.raw, args.mapping, args.out, args.receipt), sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as exc:
        print('FAIL: ' + str(exc), file=sys.stderr)
        sys.exit(1)
