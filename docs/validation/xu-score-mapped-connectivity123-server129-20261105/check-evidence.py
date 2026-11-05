#!/usr/bin/env python3
"""Recheck returned123 graph and original117 observations without EDA/vendor text.

This validates archive bytes, graph-path consistency, provenance and bounded
observations. It does not rebuild the missing private mapped/model sources or
prove Boolean sensitization, notifier semantics, physical causality or signoff.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parent
PRE = 'mapped-connectivity-20261105-123/'
NET = '9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892'
STD = '9ceaac7085f267c9a2da19d86aa9d88ddb25894df4b2485e32d13e04d0e46581'
SRAM = '81b55d87d5e6821d44037d6f0290ec89c9edb9582eb1932957f181aefc300d51'
SOURCE = '688aa9aa49b85c08d493e9cf50b150376f311acfa07bfa0245d80c14c100b4e9'
TARGET = ['u_soc', 'u_e203_subsys_top', 'u_e203_subsys_main', 'u_e203_subsys_mems',
          'u_sirv_mem_fab', 'u_sirv_gnrl_icb_buffer', 'u_sirv_gnrl_rsp_fifo',
          'dp_gt0.vec_31_dfflr', 'qout_r_reg[0]']
FIFO = TARGET[:-2]
Q1 = TARGET[:-1] + ['qout_r_reg[1]']
EVENT = re.compile(r'^XU_CAUSAL117_EVENT serial=(\d+) tick_fs=(\d+) reason=(\S+) role=(\S+) bits=(\d+) aval=([0-9a-f]+) bval=([0-9a-f]+) name=(\S+)$', re.M)


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def canonical(obj):
    return sha(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode())


def archive():
    payload = ROOT / 'payload.tar.xz'
    need(payload.stat().st_size == 57416 and sha(payload.read_bytes()) ==
         '0ab784c48fed419fbd70d5862a9f2be6bd8a2d82b550b6ed9ad05bffaea3b82b', 'complete129 original package differs')
    rows = json.loads((ROOT / 'payload-manifest.json').read_text())
    need(len(rows) == 14 and sum(r['bytes'] for r in rows) == 1063231, 'complete129 payload dimensions differ')
    expected, data, seen, internal = {r['path']: r for r in rows}, {}, set(), None
    with tarfile.open(payload, 'r|xz') as stream:
        for member in stream:
            path = PurePosixPath(member.name)
            need(member.isfile() and not path.is_absolute() and '..' not in path.parts and member.name not in seen and
                 0 <= member.size < 2000000, 'unsafe/duplicate129 member')
            seen.add(member.name)
            body = stream.extractfile(member).read()
            if member.name == 'manifest.json':
                internal = json.loads(body)
            else:
                need(expected.get(member.name) == dict(path=member.name, bytes=len(body), sha256=sha(body)),
                     'original129 member differs: ' + member.name)
                data[member.name] = body
    need(internal == rows and set(data) == set(expected) and seen == set(expected) | {'manifest.json'}, 'incomplete129 original package')
    return data


def support_manifest():
    rows = json.loads((ROOT / 'manifest.json').read_text())
    expected = {r['path'] for r in rows}
    actual = {str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p != ROOT / 'manifest.json'}
    need(actual == expected and len(expected) == len(rows), 'support member set differs')
    for row in rows:
        part = PurePosixPath(row['path'])
        need(not part.is_absolute() and '..' not in part.parts, 'unsafe support path')
        body = (ROOT / row['path']).read_bytes()
        need(len(body) == row['bytes'] and sha(body) == row['sha256'], 'support bytes differ: ' + row['path'])


def node_key(node):
    need(node['display'] == 'tb_xu_soc_ppa.dut.' + '.'.join(node['scope'] + [node['bit']]), 'node display differs from atomic scope')
    return tuple(node['scope']), node['bit']


def path_cells(path):
    need(path['found'] and path['edges'] and path['sequential_arcs_allowed'], 'missing explicit secondary potential path')
    previous, cells, index = None, [], 0
    edges = path['edges']
    while index < len(edges):
        edge = edges[index]
        source, destination = node_key(edge['source']), node_key(edge['destination'])
        need(previous is None or source == previous, 'discontinuous returned path')
        kind, detail = edge['kind'], edge['detail']
        if kind in ('stateful_boundary', 'combinational_potential_relation'):
            need(index + 1 < len(edges) and detail['direction'] == 'input', 'cell arc must start at declared input')
            following = edges[index + 1]
            need(node_key(following['source']) == destination and following['kind'] == kind and
                 following['detail']['direction'] == 'output' and
                 following['detail']['instance'] == detail['instance'] and following['detail']['type'] == detail['type'] and
                 destination == (tuple(detail['instance']), '@cell_potential_relation'), 'cell input/output hub pair differs')
            if kind == 'stateful_boundary':
                need(detail['stateful'] is True and following['detail']['stateful'] is True, 'stateful flag lost')
                cells.append(dict(instance=detail['instance'], type=detail['type'], input_pin=detail['pin'], output_pin=following['detail']['pin']))
            previous = node_key(following['destination']); index += 2
        else:
            need(kind in ('hierarchy_input', 'hierarchy_output', 'continuous_assign'), 'unknown returned path arc')
            if kind == 'hierarchy_input':
                need(detail['direction'] == 'input' and destination[0] == tuple(detail['instance']) and source[0] == destination[0][:-1], 'invalid hierarchy input direction')
            if kind == 'hierarchy_output':
                need(detail['direction'] == 'output' and source[0] == tuple(detail['instance']) and destination[0] == source[0][:-1], 'invalid hierarchy output direction')
            previous = destination; index += 1
    return cells


def derive(data):
    obj = lambda key: json.loads(data[key])
    state, graph = obj(PRE + 'state.json'), obj(PRE + 'connectivity.json')
    need(state['status'] == 'EXTRACTED_FROZEN_MAPPED_CONNECTIVITY123_NOT_QUALIFIED' and not state.get('error') and
         state['qualification'] == graph['qualification'] == 'NOT_QUALIFIED' and
         state['inputs_equal_before_after'] and state['inputs_before'] == state['inputs_after'] and
         not state['identity_errors'] and len(state['inputs_before']) == 5 and state['writes_to_inputs'] == state['eda_commands'] == state['vendor_bodies_exported'] == 0,
         'actual123 terminal identity/scope differs')
    need(state['result']['bytes'] == len(data[PRE + 'connectivity.json']) == 589099 and
         state['result']['sha256'] == sha(data[PRE + 'connectivity.json']) == '174a38d8719b2b49237cf200072ec04fe80fcc8dbb3b2512150fe780acc65f73', 'returned123 graph body identity differs')
    original = json.loads((ROOT / 'original111/state.json').read_text())
    original_sha = sha((ROOT / 'original111/state.json').read_bytes())
    need(original_sha == '3f0ec494e0fa06efcd5617242c358b1e6242a9eea69b3acffdfcacbbe99ed414' and
         original['status'] == 'FAIL_PUBLIC_DIAGNOSTIC_NOT_QUALIFIED' and len(original['inputs_before']) == 628, 'original111 failure context differs')
    earlier = json.loads((ROOT / 'original117/state.json').read_text())
    need(sha((ROOT / 'original117/state.json').read_bytes()) == 'b68f89e0fab872f3af3fb1967a5732d52b43d57ae37d3d5c9c486f358d28e79c' and
         earlier['status'] == 'NATIVE117_PASSIVE_EVENTS_COLLECTED_NOT_FUNCTIONAL_OR_TIMING_OR_ENERGY_QUALIFIED' and
         earlier['inputs_equal_before_after'] and earlier['inputs_before'] == earlier['inputs_after'] and len(earlier['inputs_before']) == 636,
         'original117 passive-event context differs')
    for digest in (NET, STD, SRAM):
        current = [r for r in state['inputs_before'] if r['sha256'] == digest]
        need(len(current) == 1 and current[0] in original['inputs_before'] and current[0] in earlier['inputs_before'], '123/111/117 selected mapped/model identities differ')
    need(sha((ROOT / 'tools/xu_mapped_connectivity123.py').read_bytes()) == SOURCE and
         any(r['sha256'] == SOURCE for r in state['inputs_before']) and any(r['sha256'] == original_sha for r in state['inputs_before']), 'actual123 original source/state binding differs')
    launch = obj('mapped-connectivity-launch-20261105-123/state.json')
    need(launch['pid'] == state['pid'] == 132032 and launch['source_sha256'] == SOURCE and launch['status'] == 'LAUNCHED_READ_ONLY123_NOT_QUALIFIED', 'actual launch/source binding differs')
    target = graph['target_cell']
    need(target['instance'] == TARGET and target['type'] == 'DRNQV0_12TR40' and target['stateful_or_behavioral_boundary'] and
         target['pin_bit_connections'] == dict(CK=['clk'], D=['n5'], Q=['qout[0]'], RDN=['rst_n']) and
         target['pin_directions'] == dict(CK='input', D='input', Q='output', RDN='input'), 'actual target FF schema/binding differs')
    direct = graph['target_q_to_fifo_o_vld']
    need(direct['found'] and not direct['sequential_arcs_allowed'] and len(direct['edges']) == 1, 'Q-to-FIFO direct alias differs')
    alias = direct['edges'][0]
    need(alias['kind'] == 'hierarchy_output' and node_key(alias['source']) == (tuple(TARGET[:-1]), 'qout[0]') and
         node_key(alias['destination']) == (tuple(FIFO), 'o_vld') and alias['detail']['pin'] == 'qout', 'exact Q-to-FIFO output connection differs')
    need(graph['parsed_counts'] == dict(bit_nodes=338232, cells=126622, design_modules=927, directed_edges=598724,
                                       hierarchy_scopes=927, instances=127548, library_schemas=1272), 'actual parsed graph dimensions differ')
    rows = []
    sizes = dict(cmd_valid=42, cmd_ready=30, rsp_valid=32, rsp_ready=26)
    for query in graph['queries']:
        primary, secondary = query['combinational_only'], query['stateful_potential_path']
        pin = query['destination'].split('.')[-1]
        need(not primary['found'] and not primary['edges'] and primary['stateful_frontier_count'] == 48 and
             len(primary['stateful_frontier']) == 48 and primary['stateful_frontier_truncated'] is False,
             'primary no-path/frontier abstraction changed')
        cells = path_cells(secondary)
        need(cells[0]['instance'] == Q1 and all(c['input_pin'] == 'D' and c['output_pin'] == 'Q' for c in cells), 'secondary paths no longer use the returned D/Q state barriers')
        need(any(e['kind'] == 'hierarchy_output' and
                 node_key(e['source']) == (tuple(TARGET[:-1]), 'qout[1]') and
                 node_key(e['destination']) == (tuple(FIFO), 'dp_gt0.vec_r[2]')
                 for e in secondary['edges']), 'returned Q1 output no longer binds the observed FIFO.vec_r[2] alias')
        need(len(cells) == (2 if pin in ('cmd_valid', 'rsp_valid') else 1) and
             len(secondary['edges']) == sizes[pin] + (query['source'] == 'target_FF_Q'), 'returned shortest potential path dimensions differ')
        rows.append(dict(source=query['source'], destination=query['destination'], primary_found=False,
                         primary_stateful_frontier_count=48, secondary_edge_count=len(secondary['edges']),
                         secondary_stateful_cells=cells))
    need(len(rows) == 8 and {(r['source'], r['destination']) for r in rows} ==
         {(s, 'shared.' + p) for s in ('target_FF_Q', 'FIFO_o_vld') for p in sizes}, 'all8 query endpoints missing/duplicated')
    raw = (ROOT / 'original117/causal-simulation.log').read_bytes()
    reviewbody = (ROOT / 'original117/passive-event-review.json').read_bytes()
    need(sha(raw) == 'ecca99bd7acf7700c125a1f449010a73a9321bed1710cf6cf324cd83b682c825' and
         sha(reviewbody) == 'd24c39ff5647a34f03a77398721f16515e0cf50cc3c76886602281ae69b5b9fb', 'original117 native evidence differs')
    events = [dict(serial=int(m[0]), tick_fs=int(m[1]), reason=m[2], role=m[3], bits=int(m[4]), aval=m[5], bval=m[6], name=m[7]) for m in EVENT.findall(raw.decode())]
    review = json.loads(reviewbody)
    need(events == review['events'] and len(events) == 453 and [r['serial'] for r in events] == list(range(1, 454)) and
         review['native_timing_violations'] == 25 and review['native_fatals'][0]['tick_fs'] == 9359423333333 and
         review['native_fatals'][0]['message'] == 'XU_MAPPED111_PROTOCOL_REJECT unknown_shared_handshake', 'original117 complete event/fatal record differs')
    chosen = [events[i - 1] for i in (175, 179, 181, 189, 216, 221, 224, 225, 250, 251, 277, 312, 315, 345, 352, 444, 451)]
    notifier = events[223]
    need(events[174]['tick_fs'] < notifier['tick_fs'] and events[180]['tick_fs'] < notifier['tick_fs'] and
         events[249]['tick_fs'] == events[250]['tick_fs'] == 9359390060000 and
         int(events[249]['bval'], 16) == int(events[250]['bval'], 16) == 1, 'earlier handshake X or Q/FIFO simultaneous-X observation differs')
    stable = []
    for suffix, value in (('.dp_gt0.vec_r[2]', 0), ('.i_rdy', 1)):
        observed = [e for e in events if e['name'].endswith(suffix)]
        need(len(observed) == 1 and observed[0]['reason'] == 'end_snapshot' and int(observed[0]['bval'], 16) == 0 and
             int(observed[0]['aval'], 16) == value and observed[0]['tick_fs'] == 9359423333333,
             'returned shortest-path known intermediate observation differs')
        stable.append(dict(name=observed[0]['name'], recorded_value_changes_in_slice=0, final_snapshot=observed[0]))
    snapshot = obj('mapped-public-function-20261105-128/state.json')
    need(snapshot['status'] == 'RUNNING_CAUSAL_NATIVE117_NOT_QUALIFIED', 'original129 contains only a RUNNING128 snapshot')
    return dict(status='PASS', qualification='STATIC_POTENTIAL_CONNECTIVITY_AND_BOUNDED_NATIVE_OBSERVATIONS_NOT_QUALIFIED',
                original129_payload_files=14, original129_payload_bytes=1063231, selected_inputs_rehashed_by123=5,
                graph_counts=graph['parsed_counts'], exact_Q_to_FIFO_edge=alias, path_queries=rows,
                original117_event_count=453, original117_selected_events=chosen,
                shortest_path_intermediates_with_no_recorded_change_and_known_final_value=stable,
                causal_conclusion='NOT_PROVEN: all returned secondary shortest paths cross Q1 whose FIFO.vec_r[2] alias is known at final snapshot; earlier shared X precedes notifier; other paths/earlier transients are not excluded',
                package128_scope='Original129 RUNNING snapshot only; no terminal/functionality/timing/energy conclusion')


def verify(extract=None, compare_saved=True):
    if compare_saved:
        support_manifest()
    data = archive()
    result = derive(data)
    if compare_saved:
        need(result == json.loads((ROOT / 'analysis.json').read_text()), 'saved strict path/event analysis differs')
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    tested = subprocess.run([sys.executable, str(ROOT / 'tools/test_connectivity123.py')], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    need(tested.returncode == 0 and b'Ran 19 tests' in tested.stdout and tested.stdout.rstrip().endswith(b'OK'), '19 original host mechanism/negative checks failed')
    if extract:
        extract.mkdir(parents=True, exist_ok=False)
        for name, body in data.items():
            target = extract / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(body)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', type=Path, help='retain all14 original129 payload bodies in a new directory')
    args = parser.parse_args()
    result = verify(args.extract)
    print(json.dumps({k: result[k] for k in ('status', 'qualification', 'original129_payload_files', 'original129_payload_bytes', 'original117_event_count', 'causal_conclusion')}, sort_keys=True, indent=2))
