#!/usr/bin/env python3
"""Qualified OpenSTA known-load cap parsing and public Tcl recipe.

Imported helper only; run.py supplies an actual completed partial-STA source.
This checks standard-cell outputs against known reference-model capacitance.
Absent SRAM input capacitance is UNKNOWN, never a zero-valued qualification.
"""
import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import fcntl
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import uuid

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'scripts/verify'))
import sram_evidence as E

COLUMNS = ('driver_pin', 'cell_type', 'output_pin', 'net', 'driver_count', 'load_count',
           'pin_r_ff', 'pin_f_ff', 'wire_r_ff', 'wire_f_ff', 'total_r_ff', 'total_f_ff',
           'limit_ff', 'cut_output_count', 'cut_output_ports', 'ordinary_output_count')
NUMERIC = ('pin_r_ff', 'pin_f_ff', 'wire_r_ff', 'wire_f_ff', 'total_r_ff', 'total_f_ff', 'limit_ff')
D = Decimal


def checked_records(records):
    for record in records:
        actual = E.record(record['path'])
        length = record.get('size_bytes', record.get('bytes'))
        if actual['sha256'] != record['sha256'] or (length is not None and actual['size_bytes'] != length):
            raise ValueError('bound file changed: ' + record['path'])


def group_bodies(text, kind):
    # Pinned Liberty uses unquoted scalar cell/pin group names. Brace matching
    # ignores quotes and comments so this is not a cross-cell regex shortcut.
    result = {}
    pattern = re.compile(r'(?m)^\s*' + re.escape(kind) + r'\s*\(\s*([^\)\n]+)\s*\)\s*\{')
    for match in pattern.finditer(text):
        name = match[1].strip().strip('"')
        i = start = match.end()
        level = 1
        quoted = False
        while level and i < len(text):
            c = text[i]
            if quoted:
                if c == '\\':
                    i += 2
                    continue
                if c == '"':
                    quoted = False
            elif text.startswith('/*', i):
                end = text.find('*/', i + 2)
                if end < 0:
                    raise ValueError('unterminated Liberty comment')
                i = end + 2
                continue
            elif text.startswith('//', i):
                end = text.find('\n', i + 2)
                i = len(text) if end < 0 else end + 1
                continue
            elif c == '"':
                quoted = True
            elif c == '{':
                level += 1
            elif c == '}':
                level -= 1
            i += 1
        if level or name in result:
            raise ValueError('incomplete or duplicate Liberty group: ' + name)
        result[name] = text[start:i - 1]
    return result


def inventory(boundary, liberty):
    top = boundary['modules']['kwt_icb_slave_sram']
    if not re.search(r'\bcapacitive_load_unit\s*\(\s*1\s*,\s*ff\s*\)', liberty):
        raise ValueError('expected pinned fF library units')
    groups = group_bodies(liberty, 'cell')
    used_types = {cell['type'] for cell in top['cells'].values()}
    limits = {}
    for cell_type in sorted(used_types):
        if cell_type not in groups:
            raise ValueError('unknown/macro cell inside boundary view: ' + cell_type)
        for pin, body in group_bodies(groups[cell_type], 'pin').items():
            direction = re.search(r'\bdirection\s*:\s*(\w+)\s*;', body)
            if direction and direction[1] == 'output':
                cap = re.findall(r'\bmax_capacitance\s*:\s*([0-9.eE+-]+)\s*;', body)
                if len(cap) != 1 or not D(cap[0]).is_finite() or D(cap[0]) <= 0:
                    raise ValueError('missing/ambiguous positive max_capacitance: ' + cell_type + '/' + pin)
                limits[cell_type + '/' + pin] = D(cap[0])
    drivers = {}
    used_limits = set()
    for cell in top['cells'].values():
        for pin, direction in cell['port_directions'].items():
            if direction == 'output':
                key = cell['type'] + '/' + pin
                if key not in limits:
                    raise ValueError('output pin has no bound limit: ' + key)
                used_limits.add(key)
                for bit in cell['connections'][pin]:
                    if not isinstance(bit, int):
                        raise ValueError('non-wire standard output connection')
                    drivers.setdefault(bit, []).append(key)
    if any(len(items) != 1 for items in drivers.values()):
        raise ValueError('multiple standard drivers in fixed boundary')
    cut_outputs = {b for n, p in top['ports'].items() if n.startswith('sram_cut_') and p['direction'] == 'output'
                   for b in p['bits'] if isinstance(b, int)}
    cut_inputs = {b for n, p in top['ports'].items() if n.startswith('sram_cut_') and p['direction'] == 'input'
                  for b in p['bits'] if isinstance(b, int)}
    ordinary_outputs = {b for n, p in top['ports'].items() if not n.startswith('sram_cut_') and p['direction'] == 'output'
                        for b in p['bits'] if isinstance(b, int)}
    return limits, {'standard_cell_types': len(used_types), 'output_limit_classes': len(used_limits),
                    'standard_output_driver_bits': len(drivers), 'multiple_standard_drivers': 0,
                    'driver_bits_with_unknown_SRAM_input_load': len(set(drivers) & cut_outputs),
                    'driver_bits_with_ordinary_output_SDC_load': len(set(drivers) & ordinary_outputs),
                    'unknown_SRAM_output_driver_bits': len(cut_inputs)}


def parse_table(text, limits, expected):
    reader = csv.DictReader(io.StringIO(text), delimiter='\t')
    if reader.fieldnames != list(COLUMNS):
        raise ValueError('missing/different compact capacitance header')
    seen_pins, seen_nets, classes = set(), set(), set()
    failures, borderline = [], []
    unknown = ordinary = rows = 0
    minimum_margin = None
    # Borderline values are unresolved, not tolerated into a PASS.
    resolution_guard = D('0.000001')
    for row in reader:
        if set(row) != set(COLUMNS) or any(v is None for v in row.values()):
            raise ValueError('malformed compact row')
        rows += 1
        if not row['driver_pin'] or row['driver_pin'] in seen_pins or not row['net'] or row['net'] in seen_nets:
            raise ValueError('empty/duplicate driver or multiply reported net')
        seen_pins.add(row['driver_pin']); seen_nets.add(row['net'])
        key = row['cell_type'] + '/' + row['output_pin']
        if key not in limits:
            raise ValueError('unexpected output class: ' + key)
        classes.add(key)
        try:
            values = {name: D(row[name]) for name in NUMERIC}
            if any(not x.is_finite() or x < 0 for x in values.values()):
                raise ValueError('nonfinite/negative capacitance')
            if values['limit_ff'] != limits[key]:
                raise ValueError('reported max-cap limit differs from pinned Liberty')
            integers = {name: int(row[name]) for name in ('driver_count', 'load_count', 'cut_output_count', 'ordinary_output_count')}
            if (integers['driver_count'] != 1 or any(x < 0 for x in integers.values()) or
                    any(not re.fullmatch(r'\d+', row[name]) for name in integers)):
                raise ValueError('invalid driver/load count')
        except (ValueError, InvalidOperation) as exc:
            raise ValueError('invalid numeric capacitance row: ' + row['driver_pin']) from exc
        ports = row['cut_output_ports'].split(';') if row['cut_output_ports'] else []
        if (len(ports) != integers['cut_output_count'] or len(ports) != len(set(ports)) or
                any(not name.startswith('sram_cut_') for name in ports) or
                integers['load_count'] < integers['cut_output_count'] + integers['ordinary_output_count']):
            raise ValueError('inconsistent unknown macro load classification')
        unknown += bool(ports)
        ordinary += integers['ordinary_output_count'] > 0
        for polarity in ('r', 'f'):
            total = values['total_' + polarity + '_ff']
            components = values['pin_' + polarity + '_ff'] + values['wire_' + polarity + '_ff']
            # OpenSTA 2.0.17 computes in float; independent printed components
            # can differ from the printed sum by several float ULPs.
            if abs(total - components) > D('0.000001') * (D(1) + total + components):
                raise ValueError('pin/wire/total capacitance arithmetic mismatch')
            margin = values['limit_ff'] - total
            if minimum_margin is None or margin < minimum_margin:
                minimum_margin = margin
            detail = {'driver_pin': row['driver_pin'], 'cell_type': row['cell_type'], 'polarity': polarity,
                      'known_total_ff': str(total), 'limit_ff': str(values['limit_ff']), 'margin_ff': str(margin),
                      'real_macro_input_load': 'UNKNOWN' if ports else 'NOT_ON_THIS_NET'}
            if margin < -resolution_guard:
                failures.append(detail)
            elif margin <= resolution_guard:
                borderline.append(detail)
    got = {'standard_output_driver_bits': rows, 'output_limit_classes': len(classes),
           'driver_bits_with_unknown_SRAM_input_load': unknown,
           'driver_bits_with_ordinary_output_SDC_load': ordinary}
    for name, count in got.items():
        if expected[name] != count:
            raise ValueError('bound inventory/collected coverage mismatch: ' + name + ' ' + str(count) + ' != ' + str(expected[name]))
    if rows == 0:
        raise ValueError('empty capacitance sample')
    return {'coverage': got, 'known_load_status': 'FAIL' if failures else 'UNRESOLVED_ROUNDING' if borderline else 'PASS',
            'known_load_violating_polarities': len(failures), 'known_load_violating_drivers': len({x['driver_pin'] for x in failures}),
            'known_load_borderline_polarities': len(borderline), 'minimum_known_margin_ff': str(minimum_margin),
            'comparison_resolution_guard_ff': str(resolution_guard), 'failures': failures, 'borderline': borderline,
            'full_macro_input_capacitance': 'BLOCKED; ' + str(unknown) + ' standard drivers touch cut SRAM input loads',
            'unknown_SRAM_output_driver_bits': expected.get('unknown_SRAM_output_driver_bits'),
            'full_design_or_official_capacitance': 'BLOCKED'}


TCL = r'''

# OpenSTA 2.0.17 capacitances_str emits scalar, r/f, or r min:max f min:max.
# Keep the maximum modeled load of each polarity; never skip a reported net.
proc cap_value_max {value} {
    if {![regexp {^([0-9.eE+-]+)(?::([0-9.eE+-]+))?$} $value _ lo hi]} {
        error "unsupported capacitance value: $value"
    }
    if {$hi eq ""} {set hi $lo}
    if {![string is double -strict $lo] || ![string is double -strict $hi] || $lo < 0 || $hi < $lo} {
        error "invalid/reversed capacitance range: $value"
    }
    return $hi
}
proc cap_pair {text label} {
    set lines [regexp -all -inline -line "^ $label capacitance: .*\$" $text]
    if {[llength $lines] != 1} {error "missing/duplicate $label capacitance line; see net.tmp"}
    set line [lindex $lines 0]
    set value [string range $line [string length " $label capacitance: "] end]
    if {[regexp {^r ([^ ]+) f ([^ ]+)$} $value _ r f]} {
        return [list [cap_value_max $r] [cap_value_max $f]]
    }
    set cap [cap_value_max $value]
    return [list $cap $cap]
}

if {[catch {
read_liberty {@LIB@}
read_verilog boundary.v
link_design kwt_icb_slave_sram
read_sdc reference.sdc
set fh [open limits.tsv r]
set limits [dict create]
while {[gets $fh line] >= 0} {
    lassign [split $line "\t"] key value
    if {[dict exists $limits $key]} {error "duplicate max-cap class"}
    dict set limits $key $value
}
close $fh
set out [open capacitance.tsv w]
puts $out {@HEADER@}
set pairs {}
foreach pin [get_pins -hierarchical -filter {direction == output} *] {
    lappend pairs [list [get_full_name $pin] $pin]
}
set pairs [lsort -index 0 $pairs]
if {[llength $pairs] != @COUNT@} {error "standard output inventory differs from bound JSON"}
set count 0
foreach pair $pairs {
    lassign $pair pin_name pin
    set cell [get_cells -of_objects $pin]
    if {[llength $cell] != 1} {error "output has no unique leaf cell"}
    set cell_type [get_property $cell ref_name]
    set output_pin [file tail $pin_name]
    set key $cell_type/$output_pin
    if {![dict exists $limits $key]} {error "output has no pinned max-cap limit: $key"}
    set nets [get_nets -of_objects $pin]
    if {[llength $nets] != 1} {error "driver has no unique connected net"}
    set net_name [get_full_name [lindex $nets 0]]
    set cut_ports {}
    set ordinary_outputs 0
    foreach port [get_ports -quiet -of_objects $nets] {
        if {[get_property $port direction] eq "output"} {
            set port_name [get_full_name $port]
            if {[string match sram_cut_* $port_name]} {lappend cut_ports $port_name} else {incr ordinary_outputs}
        }
    }
    set cut_ports [lsort -unique $cut_ports]
    # Public report command: no get_property capacitance/private SWIG access.
    # Keep one scratch report; only the compact TSV is retained.
    report_net -connections -verbose -digits 9 $pin_name > net.tmp
    set scratch [open net.tmp r]
    set text [read $scratch]
    close $scratch
    lassign [cap_pair $text Pin] pr pf
    lassign [cap_pair $text Wire] wr wf
    lassign [cap_pair $text Total] tr tf
    if {![regexp -line {^ Number of drivers: ([0-9]+)$} $text _ dc] ||
        ![regexp -line {^ Number of loads: ([0-9]+)$} $text _ lc]} {
        error "driver/load count absent/malformed for $pin_name; see net.tmp"
    }
    if {$dc != 1 || [string first " $pin_name output ($cell_type)" $text] < 0} {
        error "unexpected driver identity/count for $pin_name; see net.tmp"
    }
    set fields [list $pin_name $cell_type $output_pin $net_name $dc $lc $pr $pf $wr $wf $tr $tf \
        [dict get $limits $key] [llength $cut_ports] [join $cut_ports ";"] $ordinary_outputs]
    foreach value $fields {
        if {[regexp {[\t\r\n]} $value]} {error "unsupported control character in compact field"}
    }
    puts $out [join $fields "\t"]
    incr count
}
close $out
file delete net.tmp
} failure options]} {
    catch {close $out}
    puts stderr "ERROR: $failure; last raw report remains in net.tmp"
    if {[dict exists $options -errorinfo]} {puts stderr [dict get $options -errorinfo]}
    exit 1
}
puts "KWT_REFERENCE_CAP_ROWS $count"
puts KWT_REFERENCE_CAP_COMPLETE
exit 0
'''


def self_test():
    limits = {'BUF_X1/Z': D('60.653700')}
    expected = {'standard_output_driver_bits': 1, 'output_limit_classes': 1,
                'driver_bits_with_unknown_SRAM_input_load': 1,
                'driver_bits_with_ordinary_output_SDC_load': 0, 'unknown_SRAM_output_driver_bits': 16}
    row = dict(zip(COLUMNS, ('u/Z', 'BUF_X1', 'Z', 'n', '1', '1', '10', '11', '2', '3', '12', '14',
                             '60.653700', '1', 'sram_cut_000_rd_addr[0]', '0')))
    def data(rows):
        stream = io.StringIO(); writer = csv.DictWriter(stream, fieldnames=COLUMNS, delimiter='\t', lineterminator='\n')
        writer.writeheader(); writer.writerows(rows); return stream.getvalue()
    count = 0
    assert parse_table(data([row]), limits, expected)['known_load_status'] == 'PASS'; count += 1
    fail = dict(row, pin_r_ff='68', total_r_ff='70')
    result = parse_table(data([fail]), limits, expected)
    assert result['known_load_status'] == 'FAIL' and result['known_load_violating_polarities'] == 1; count += 1
    edge = dict(row, pin_r_ff='58.653700', total_r_ff='60.653700')
    assert parse_table(data([edge]), limits, expected)['known_load_status'] == 'UNRESOLVED_ROUNDING'; count += 1
    rejected = [data([]), data([row, row]), data([dict(row, limit_ff='61')]),
                data([dict(row, total_r_ff='NaN')]), data([dict(row, total_r_ff='-1')]),
                data([dict(row, total_r_ff='30')]), data([dict(row, cut_output_count='0')]),
                data([dict(row, cut_output_ports='fake_port')]), data([dict(row, driver_count='2')]),
                data([dict(row, cell_type='FAKE')]), 'bad\theader\n']
    for text in rejected:
        try:
            parse_table(text, limits, expected)
        except ValueError:
            count += 1
        else:
            raise AssertionError('malformed/incomplete evidence was accepted')
    print('KWT_CAP_PARSER_SELFTEST_PASS cases=' + str(count))

