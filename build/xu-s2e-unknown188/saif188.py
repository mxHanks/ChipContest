"""Bounded-memory selection of explicit macro pin SAIF marginals, not events."""
from decimal import Decimal
from pathlib import Path
import re


def need(ok, message):
    if not ok: raise ValueError(message)


def selected_signals(path, wanted, duration):
    # The normalized input is ~13MB; token matches are iterated rather than
    # building a complete syntax tree or retaining unrelated signal statistics.
    text = Path(path).read_text()
    tokens = re.finditer(r'//[^\n]*|/\*.*?\*/|\(|\)|"(?:\\.|[^"\\])*"|(?:\\.|[^\s()])+', text, re.S)
    stack = []; headers = {}; found = {}; instances = set(); roots = 0; records = 0
    unescape = lambda s: re.sub(r'\\(.)', r'\1', s)
    for match in tokens:
        token = match.group()
        if token.startswith('//') or token.startswith('/*'): continue
        if token == '(':
            stack.append([])
        elif token == ')':
            need(stack, 'unbalanced SAIF close')
            node = stack.pop(); need(node, 'empty SAIF expression')
            parent = stack[-1] if stack else None
            if parent and parent[0] in ['NET', 'PORT']:
                records += 1
                scopes = [unescape(frame[1]) for frame in stack if frame and frame[0] == 'INSTANCE']
                key = '/'.join(scopes + [unescape(node[0])])
                if key in wanted:
                    kind_key = (parent[0], key)
                    need(kind_key not in found, 'duplicate selected SAIF record')
                    stats = {}
                    for pair in node[1:]:
                        need(isinstance(pair, list) and len(pair) == 2 and pair[0] not in stats, 'invalid selected SAIF stats')
                        value = Decimal(pair[1]); need(value.is_finite() and value >= 0 and value == int(value), 'invalid statistic')
                        stats[pair[0]] = int(value)
                    need({'T0', 'T1', 'TX', 'TC'} <= set(stats) and
                         sum(stats.get(k, 0) for k in ['T0', 'T1', 'TX', 'TZ', 'TB']) == duration, 'selected SAIF dwell sum')
                    found[kind_key] = stats
            elif node[0] == 'INSTANCE':
                scopes = [unescape(frame[1]) for frame in stack if frame and frame[0] == 'INSTANCE'] + [unescape(node[1])]
                name = '/'.join(scopes); need(name not in instances, 'duplicate SAIF instance'); instances.add(name)
            elif node[0] in ['NET', 'PORT']:
                pass
            elif parent is not None:
                if parent[0] == 'SAIFILE':
                    need(node[0] not in headers, 'duplicate SAIF header'); headers[node[0]] = node[1:]
                else: parent.append(node)
            else:
                need(node[0] == 'SAIFILE', 'SAIFILE root required'); roots += 1
        else:
            need(stack, 'SAIF atom outside expression')
            stack[-1].append(token[1:-1] if token.startswith('"') else token)
    need(not stack and roots == 1 and headers.get('TIMESCALE') == ['1', 'fs'] and
         len(headers.get('DURATION', [])) == 1 and Decimal(headers['DURATION'][0]) == duration,
         'normalized SAIF root/timebase/window differs')
    need({key for kind, key in found} == wanted, 'missing selected canonical macro pins')
    return found, dict(signal_records=records, selected_records=len(found), duration_fs=duration)
