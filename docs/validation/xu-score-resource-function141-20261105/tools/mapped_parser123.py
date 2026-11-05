#!/usr/bin/env python3
"""Read-only frozen111 structural connectivity, without simulation or vendor text export.

Directed bit connections are exact for parsed wires, selects, concatenations and
module ports. A combinational cell arc means an input/output *potential* relation
from its declaration only; it is not a sensitized functional or timing proof.
Stateful cells are explicit barriers in the primary search. No value is forced,
no timing check is changed, and no source/model body is copied to the output.
"""
import argparse
import collections
import hashlib
import json
import os
import re
import time
import traceback
from pathlib import Path

STATE_SHA = '3f0ec494e0fa06efcd5617242c358b1e6242a9eea69b3acffdfcacbbe99ed414'
NET_SHA = '9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892'
STD_SHA = '9ceaac7085f267c9a2da19d86aa9d88ddb25894df4b2485e32d13e04d0e46581'
VENDOR_SHA = '81b55d87d5e6821d44037d6f0290ec89c9edb9582eb1932957f181aefc300d51'
TARGET = ('u_soc', 'u_e203_subsys_top', 'u_e203_subsys_main',
          'u_e203_subsys_mems', 'u_sirv_mem_fab', 'u_sirv_gnrl_icb_buffer',
          'u_sirv_gnrl_rsp_fifo', 'dp_gt0.vec_31_dfflr', 'qout_r_reg[0]')
FIFO = TARGET[:-2]
SHARED = ('u_shared',)
TOKEN = re.compile(r'//[^\n]*|/\*.*?\*/|\(\*.*?\*\)|"(?:\\.|[^"\\])*"|'
                   r'\\[^\s]+|[A-Za-z_$][A-Za-z0-9_$]*|'
                   r"(?:\d+)?'[sS]?[bBoOdDhH][0-9a-fA-FxXzZ?_]+|"
                   r'\d+|\s+|.', re.S)


def need(ok, message):
    if not ok:
        raise ValueError(message)


def save(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
    os.replace(str(temporary), str(path))


def identity(path):
    path = Path(path).absolute()
    actual = path.resolve(strict=True)
    before = actual.stat()
    digest = hashlib.sha256()
    with actual.open('rb') as source:
        for block in iter(lambda: source.read(1048576), b''):
            digest.update(block)
    after = actual.stat()
    key = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    need(key(before) == key(after), 'input changed while hashing: ' + str(path))
    return dict(input_path=str(path), path=str(actual), bytes=before.st_size,
                sha256=digest.hexdigest(), device=before.st_dev, inode=before.st_ino,
                mtime_ns=before.st_mtime_ns, ctime_ns=before.st_ctime_ns)


def tokens(text):
    return [(m.group(), m.start(), m.end()) for m in TOKEN.finditer(text)
            if not m.group().isspace() and not m.group().startswith(('//', '/*', '(*'))]


def name(token):
    return token[1:] if token.startswith('\\') else token


def ident(token):
    return token.startswith('\\') or re.match(r'^[A-Za-z_$][A-Za-z0-9_$]*$', token) is not None


def split_top(values, delimiter=','):
    result, last, nesting = [], 0, []
    pairs = {')': '(', ']': '[', '}': '{'}
    for i, value in enumerate(values):
        if value in ('(', '[', '{'):
            nesting.append(value)
        elif value in pairs:
            need(nesting and nesting.pop() == pairs[value], 'unbalanced expression')
        elif value == delimiter and not nesting:
            result.append(values[last:i]); last = i + 1
    need(not nesting, 'unclosed expression')
    result.append(values[last:])
    return result


def enclosed(values, start, left='(', right=')'):
    need(start < len(values) and values[start] == left, 'missing ' + left)
    depth = 0
    for i in range(start, len(values)):
        if values[i] == left:
            depth += 1
        elif values[i] == right:
            depth -= 1
            if depth == 0:
                return values[start + 1:i], i + 1
    raise ValueError('unterminated ' + left)


def integer(values):
    value = ''.join(values)
    need(re.match(r'^-?\d+$', value) is not None, 'nonconstant integer: ' + value)
    return int(value)


def width_range(values):
    if values and values[0] == '[':
        body, finish = enclosed(values, 0, '[', ']')
        sides = split_top(body, ':')
        need(len(sides) == 2, 'declaration range must be constant pair')
        return (integer(sides[0]), integer(sides[1])), finish
    return None, 0


def declaration(values, ports, widths):
    direction = values[0] if values and values[0] in ('input', 'output', 'inout') else None
    body = values[1:]
    while body and body[0] in ('wire', 'reg', 'logic', 'signed', 'unsigned', 'tri'):
        body = body[1:]
    bounds, finish = width_range(body)
    for part in split_top(body[finish:]):
        need(len(part) == 1 and ident(part[0]), 'unsupported declaration: ' + ' '.join(values))
        key = name(part[0])
        if key in widths:
            need(widths[key] == bounds, 'inconsistent width: ' + key)
        widths[key] = bounds
        if direction:
            need(key not in ports or ports[key] == direction, 'inconsistent direction: ' + key)
            ports[key] = direction


def modules(text, structural=True):
    stream, result, i = tokens(text), {}, 0
    while i < len(stream):
        if stream[i][0] != 'module':
            i += 1; continue
        start = i
        need(i + 1 < len(stream) and ident(stream[i + 1][0]), 'missing module name')
        module_name = name(stream[i + 1][0]); i += 2
        while i < len(stream) and stream[i][0] != ';':
            i += 1
        need(i < len(stream), 'unterminated module header')
        header = [t[0] for t in stream[start + 2:i]]
        i += 1; body_start = i
        while i < len(stream) and stream[i][0] != 'endmodule':
            i += 1
        need(i < len(stream), 'unterminated module ' + module_name)
        end = i; i += 1
        ports, widths = {}, {}
        # ANSI support is intentionally constant-width, matching the structural subset.
        if header and header[0] == '(':
            header_ports, header_end = enclosed(header, 0)
            need(header_end == len(header), 'parameterized module header unsupported')
            current = None
            for part in split_top(header_ports):
                if part and part[0] in ('input', 'output', 'inout'):
                    # Keep direction, net kind and range for the next name in
                    # `input wire [3:0] a, b`, rather than silently scalarizing b.
                    current = part[:-1]
                    declaration(part, ports, widths)
                elif part and current is not None:
                    declaration(current + part, ports, widths)
        records = []
        body = stream[body_start:end]
        # Module library internals are never exported or structurally traversed.
        if not structural:
            for j, item in enumerate(body):
                if item[0] not in ('input', 'output', 'inout'):
                    continue
                k = j + 1
                while k < len(body) and body[k][0] != ';':
                    k += 1
                declaration([v[0] for v in body[j:k]], ports, widths)
            words = {v[0].lower() for v in body}
            stateful = bool(words.intersection({'reg', 'always', 'always_ff', 'initial', 'notifier', 'posedge', 'negedge'}))
        else:
            stateful = False
            # Split only at module-scope semicolons; mapped structural statements
            # have no procedural blocks. Unexpected syntax is a hard failure.
            for part in split_top([v[0] for v in body], ';'):
                if not part:
                    continue
                first = part[0]
                if first in ('input', 'output', 'inout', 'wire', 'reg', 'logic', 'tri'):
                    declaration(part, ports, widths)
                elif first in ('parameter', 'localparam', 'supply0', 'supply1'):
                    if first in ('supply0', 'supply1'):
                        declaration(['wire'] + part[1:], ports, widths)
                elif first == 'assign':
                    sides = split_top(part[1:], '=')
                    need(len(sides) == 2, 'non-simple assign')
                    records.append(dict(kind='assign', lhs=sides[0], rhs=sides[1]))
                else:
                    need(ident(first), 'unsupported structural statement: ' + ' '.join(part[:12]))
                    position = 1
                    if position < len(part) and part[position] == '#':
                        _, position = enclosed(part, position + 1)
                    need(position < len(part) and ident(part[position]), 'missing instance name')
                    instance = name(part[position]); position += 1
                    bindings, finish = enclosed(part, position)
                    need(finish == len(part), 'multiple instances or unsupported statement: ' + module_name)
                    pins = {}
                    for pin in split_top(bindings):
                        need(len(pin) >= 4 and pin[0] == '.' and ident(pin[1]), 'only named port bindings supported')
                        expression, finish_pin = enclosed(pin, 2)
                        need(finish_pin == len(pin) and name(pin[1]) not in pins, 'duplicate/trailing pin')
                        pins[name(pin[1])] = expression
                    records.append(dict(kind='instance', type=name(first), name=instance, pins=pins))
        row = dict(name=module_name, ports=ports, widths=widths, records=records,
                   stateful=stateful, byte_start=stream[start][1], byte_end=stream[end][2])
        if module_name in result:
            old = result[module_name]
            need(old['ports'] == ports and old['widths'] == widths, 'conditional module schema disagreement: ' + module_name)
            need(not structural, 'duplicate structural module: ' + module_name)
            old['stateful'] = old['stateful'] or stateful
        else:
            result[module_name] = row
    need(result, 'no modules parsed')
    return result


def bit_names(signal, bounds):
    if bounds is None:
        return [signal]
    a, b = bounds
    step = 1 if b >= a else -1
    return [signal + '[' + str(index) + ']' for index in range(a, b + step, step)]


def expression(values, widths):
    """Exact MSB-first bits, constants as None; reject operators/unknown nets."""
    if not values:
        return []
    if values[0] == '{':
        inner, finish = enclosed(values, 0, '{', '}')
        need(finish == len(values), 'trailing concat expression')
        if len(inner) > 1 and inner[0].isdigit() and inner[1] == '{':
            repeated, repeated_end = enclosed(inner, 1, '{', '}')
            need(repeated_end == len(inner), 'bad replication')
            return expression(repeated, widths) * int(inner[0])
        return [bit for part in split_top(inner) for bit in expression(part, widths)]
    constant = re.match(r"^(\d+)'[sS]?[bBoOdDhH][0-9a-fA-FxXzZ?_]+$", ''.join(values))
    if constant:
        return [None] * int(constant.group(1))
    need(ident(values[0]), 'unsupported bit expression: ' + ' '.join(values))
    signal = name(values[0]); need(signal in widths, 'undeclared signal: ' + signal)
    if len(values) == 1:
        return bit_names(signal, widths[signal])
    body, finish = enclosed(values, 1, '[', ']')
    need(finish == len(values), 'trailing select expression')
    sides = split_top(body, ':')
    bounds = widths[signal]
    need(bounds is not None, 'scalar select: ' + signal)
    valid = set(range(min(bounds), max(bounds) + 1))
    if len(sides) == 1:
        index = integer(sides[0]); need(index in valid, 'select out of bounds: ' + signal)
        return [signal + '[' + str(index) + ']']
    need(len(sides) == 2, 'nonconstant select')
    a, b = integer(sides[0]), integer(sides[1])
    need(a in valid and b in valid, 'part select out of bounds: ' + signal)
    need((bounds[0] <= bounds[1]) == (a <= b), 'part select direction differs')
    return bit_names(signal, (a, b))


class Graph:
    def __init__(self, designs, libraries):
        self.designs, self.libraries = designs, libraries
        self.ids, self.nodes, self.edges = {}, [], []
        self.adj = collections.defaultdict(list)
        self.reverse = collections.defaultdict(list)
        self.instances, self.scopes, self.cells = {}, {}, []

    def node(self, scope, bit):
        if bit is None:
            return None
        key = (scope, bit)
        if key not in self.ids:
            self.ids[key] = len(self.nodes); self.nodes.append(key)
        return self.ids[key]

    def edge(self, source, destination, kind, detail):
        if source is None or destination is None:
            return
        index = len(self.edges)
        self.edges.append((source, destination, kind, detail))
        self.adj[source].append(index); self.reverse[destination].append(index)

    def wire(self, source_scope, sources, destination_scope, destinations, kind, detail):
        need(len(sources) == len(destinations), 'binding width mismatch: ' + repr(detail))
        for source, destination in zip(sources, destinations):
            self.edge(self.node(source_scope, source), self.node(destination_scope, destination), kind, detail)

    def elaborate(self, module_name, scope=(), stack=()):
        need(module_name not in stack, 'recursive hierarchy: ' + module_name)
        module = self.designs[module_name]
        self.scopes[scope] = module_name
        for record in module['records']:
            if record['kind'] == 'assign':
                source = expression(record['rhs'], module['widths'])
                destination = expression(record['lhs'], module['widths'])
                self.wire(scope, source, scope, destination, 'continuous_assign',
                          dict(scope=list(scope), module=module_name, lhs=record['lhs'], rhs=record['rhs']))
                continue
            path = scope + (record['name'],)
            need(path not in self.instances, 'duplicate instance hierarchy')
            self.instances[path] = record
            schema = self.designs.get(record['type']) or self.libraries.get(record['type'])
            need(schema is not None, 'unknown module/cell type: ' + record['type'])
            bound = {}
            for pin, values in record['pins'].items():
                need(pin in schema['ports'], 'unknown pin: ' + record['type'] + '/' + pin)
                actual = expression(values, module['widths'])
                formal = bit_names(pin, schema['widths'][pin])
                need(not actual or len(actual) == len(formal), 'pin width mismatch: ' + repr(path) + '/' + pin)
                bound[pin] = actual
                if record['type'] in self.designs and actual:
                    direction = schema['ports'][pin]
                    detail = dict(instance=list(path), type=record['type'], pin=pin, direction=direction)
                    if direction in ('input', 'inout'):
                        self.wire(scope, actual, path, formal, 'hierarchy_input', detail)
                    if direction in ('output', 'inout'):
                        self.wire(path, formal, scope, actual, 'hierarchy_output', detail)
            if record['type'] in self.designs:
                self.elaborate(record['type'], path, stack + (module_name,))
            else:
                cell = dict(instance=list(path), type=record['type'], stateful_or_behavioral_boundary=schema['stateful'],
                            pin_directions=schema['ports'], pin_bit_connections=bound,
                            declaration_source='vendor/model schema only; no body exported')
                self.cells.append(cell)
                hub = self.node(path, '@cell_potential_relation')
                kind = 'stateful_boundary' if schema['stateful'] else 'combinational_potential_relation'
                for pin, bits in bound.items():
                    for bit in bits:
                        endpoint = self.node(scope, bit)
                        detail = dict(instance=list(path), type=record['type'], pin=pin,
                                      direction=schema['ports'][pin], stateful=schema['stateful'])
                        if schema['ports'][pin] in ('input', 'inout'):
                            self.edge(endpoint, hub, kind, detail)
                        if schema['ports'][pin] in ('output', 'inout'):
                            self.edge(hub, endpoint, kind, detail)

    def node_record(self, index):
        scope, bit = self.nodes[index]
        return dict(scope=list(scope), bit=bit, display='tb_xu_soc_ppa.dut.' + '.'.join(scope + (bit,)))

    def path(self, source, destination, allow_state=False):
        queue, parent = collections.deque([source]), {source: None}
        state_frontier = {}
        while queue:
            current = queue.popleft()
            if current == destination:
                break
            for index in self.adj.get(current, []):
                edge = self.edges[index]
                if edge[2] == 'stateful_boundary' and not allow_state:
                    state_frontier[tuple(edge[3]['instance'])] = edge[3]['type']
                    continue
                if edge[1] not in parent:
                    parent[edge[1]] = index; queue.append(edge[1])
        found = destination in parent
        sequence = []
        if found:
            current = destination
            while parent[current] is not None:
                edge = self.edges[parent[current]]
                sequence.append(dict(source=self.node_record(edge[0]), destination=self.node_record(edge[1]),
                                     kind=edge[2], detail=edge[3]))
                current = edge[0]
            sequence.reverse()
        return dict(found=found, semantics='static potential connectivity; no sensitization, simulation, or timing proof',
                    sequential_arcs_allowed=allow_state, visited_nodes=len(parent), edges=sequence,
                    stateful_frontier_count=len(state_frontier),
                    stateful_frontier=[dict(instance=list(k), type=v) for k, v in sorted(state_frontier.items())[:64]],
                    stateful_frontier_truncated=len(state_frontier) > 64)


def analyze(mapped_text, model_texts, top='xu_soc_ppa_top'):
    designs, library = modules(mapped_text), {}
    for text in model_texts:
        for key, row in modules(text, structural=False).items():
            if key in library:
                need(library[key]['ports'] == row['ports'] and library[key]['widths'] == row['widths'], 'duplicate library schema differs')
                library[key]['stateful'] |= row['stateful']
            else:
                library[key] = row
    need(top in designs, 'missing mapped top: ' + top)
    graph = Graph(designs, library); graph.elaborate(top)
    return graph


def run(root, output):
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=False)
    state = dict(status='RUNNING_READ_ONLY_CONNECTIVITY123_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
                 pid=os.getpid(), started_epoch=time.time(), inputs_before=[], writes_to_inputs=0,
                 eda_commands=0, vendor_bodies_exported=0)
    save(output / 'state.json', state)
    error = None
    try:
        original_path = Path(root) / 'state.json'
        original_identity = identity(original_path)
        need(original_identity['sha256'] == STATE_SHA, 'original111 state changed')
        original = json.loads(original_path.read_text())
        state['inputs_before'] = [original_identity, identity(__file__)]
        need(original['inputs_equal_before_after'] and original['inputs_before'] == original['inputs_after'], 'original111 frozen inputs incomplete')
        selected = []
        for wanted in (NET_SHA, STD_SHA, VENDOR_SHA):
            found = [row for row in original['inputs_before'] if row['sha256'] == wanted]
            need(len(found) == 1, 'missing/duplicate frozen source SHA: ' + wanted)
            row = identity(found[0]['input_path'])
            need(row == found[0], 'frozen111 source identity changed: ' + row['input_path'])
            selected.append(row); state['inputs_before'].append(row)
        save(output / 'state.json', state)
        mapped = Path(selected[0]['path']).read_text()
        models = [Path(row['path']).read_text() for row in selected[1:]]
        graph = analyze(mapped, models)
        need(TARGET in graph.instances, 'actual target FF hierarchy not found')
        target = graph.instances[TARGET]
        need(target['type'] == 'DRNQV0_12TR40', 'target cell type differs from actual117')
        need(FIFO in graph.scopes and SHARED in graph.scopes, 'FIFO/shared hierarchy not found')
        target_cell = next(row for row in graph.cells if tuple(row['instance']) == TARGET)
        need('Q' in target_cell['pin_bit_connections'] and len(target_cell['pin_bit_connections']['Q']) == 1, 'scalar target Q missing')
        start = graph.node(TARGET[:-1], target_cell['pin_bit_connections']['Q'][0])
        fifo_output = graph.node(FIFO, 'o_vld')
        need(fifo_output in graph.adj or fifo_output in graph.reverse, 'FIFO.o_vld has no parsed connections')
        evidence = dict(qualification='NOT_QUALIFIED', target_cell=target_cell,
                        parsed_counts=dict(design_modules=len(graph.designs), library_schemas=len(graph.libraries),
                                           hierarchy_scopes=len(graph.scopes), instances=len(graph.instances),
                                           cells=len(graph.cells), bit_nodes=len(graph.nodes), directed_edges=len(graph.edges)),
                        target_q_to_fifo_o_vld=graph.path(start, fifo_output), queries=[],
                        important_limits=['Cell input/output relations are conservative declaration-based relations, not Boolean sensitization.',
                                          'Any stateful/model behavioral declaration is a barrier in the primary search.',
                                          'Secondary searches explicitly cross stateful boundaries and cannot be called combinational paths.',
                                          'Earlier shared-handshake transient X in actual117 predates the target notifier; this read-only graph does not attribute that X.',
                                          'No vendor behavior, UDP truth table, or notifier semantics is exported or proved by this tool.',
                                          'No functional, 150MHz, numerical, or energy qualification is awarded.'])
        for source_name, source in [('target_FF_Q', start), ('FIFO_o_vld', fifo_output)]:
            for pin in ('cmd_valid', 'cmd_ready', 'rsp_valid', 'rsp_ready'):
                endpoint = graph.node(SHARED, pin)
                need(endpoint in graph.adj or endpoint in graph.reverse, 'shared port absent from mapped connections: ' + pin)
                primary = graph.path(source, endpoint)
                secondary = graph.path(source, endpoint, allow_state=True) if not primary['found'] else None
                evidence['queries'].append(dict(source=source_name, destination='shared.' + pin,
                                                combinational_only=primary, stateful_potential_path=secondary))
        # Incidence supplies direct primitive/port bindings around the source,
        # even if a long downstream path reaches stateful barriers.
        local_nodes = {start, fifo_output}
        incidence = sorted({edge for node in local_nodes for edge in graph.adj.get(node, []) + graph.reverse.get(node, [])})
        evidence['direct_source_incidence'] = [dict(source=graph.node_record(graph.edges[i][0]),
                                                   destination=graph.node_record(graph.edges[i][1]),
                                                   kind=graph.edges[i][2], detail=graph.edges[i][3]) for i in incidence]
        save(output / 'connectivity.json', evidence)
        state.update(status='EXTRACTED_FROZEN_MAPPED_CONNECTIVITY123_NOT_QUALIFIED', result=identity(output / 'connectivity.json'))
    except BaseException as exc:
        error = type(exc).__name__ + ': ' + str(exc)
        state.update(status='FAIL_READ_ONLY_CONNECTIVITY123_NOT_QUALIFIED', error=error, traceback=traceback.format_exc())
        raise
    finally:
        after, issues = [], []
        for row in state['inputs_before']:
            try:
                actual = identity(row['input_path']); after.append(actual)
                if actual != row:
                    issues.append(dict(path=row['input_path'], error='INPUT_CHANGED'))
            except BaseException as exc:
                issues.append(dict(path=row['input_path'], error=type(exc).__name__ + ': ' + str(exc)))
        state.update(inputs_after=after, inputs_equal_before_after=not issues, identity_errors=issues,
                     finished_epoch=time.time())
        if issues:
            state['status'] = 'FAIL_READ_ONLY_CONNECTIVITY123_NOT_QUALIFIED'
        save(output / 'state.json', state)
        need(not issues and error is None, 'connectivity extraction failed; state retained')
    print(state['status'], flush=True)


def main():
    base = Path.home() / 'Desktop/xu-score-optimization-20261102'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=base / 'mapped-task00-public-diagnostic-20261104-111')
    parser.add_argument('--out', type=Path, default=base / 'mapped-connectivity-20261105-123')
    args = parser.parse_args()
    run(args.root, args.out)


if __name__ == '__main__':
    main()
