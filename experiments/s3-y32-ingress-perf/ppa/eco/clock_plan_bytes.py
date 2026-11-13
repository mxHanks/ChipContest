"""Reproduce reviewed Tcl bytes from the SHA-bound original1064 clock JSON."""
import hashlib

EXPECTED_TCL_SHA={'probe':'9063abe956c03cdcec4471ba13b48817355ecb090de35727fa0c4620c61ae54f',
                  'full':'2c40a71a5e1ebf08cbf080b5c6d4f0c8df99ded98d648c303735d0b4dfb3c9e2'}
KEYS=['id','owner','expected_local_net','allowed_local_net_aliases','loads','load_kinds','max_loads','new_cell_name','phase']

def literal(value):
    if isinstance(value,list):return '{'+' '.join(literal(x)for x in value)+'}'
    value=str(value)
    if any(x in value for x in '{}\\\r\n'):raise ValueError('unsafe reviewed clock-plan Tcl literal')
    return '{'+value+'}'

def emit(plan,kind):
    if kind not in EXPECTED_TCL_SHA:raise ValueError('unsupported clock plan selection')
    groups=plan['native_probe_groups']if kind=='probe'else plan['groups']
    lines=['set ::eco_clock_plan_schema '+literal(plan['schema']),
        'set ::eco_clock_plan_mapped_sha '+literal(plan['mapped_sha256']),
        'set ::eco_clock_root '+literal(plan['root_driver']),'set ::eco_clock_groups {}']
    for group in groups:
        lines.append('lappend ::eco_clock_groups [dict create '+' '.join(x for key in KEYS for x in [literal(key),literal(group[key])])+']')
    lines.append('set ::eco_clock_expected_final_root_fanout '+str(21589 if kind=='probe'else plan['predicted_root_flattened_sink_count']))
    raw=('\n'.join(lines)+'\n').encode()
    if hashlib.sha256(raw).hexdigest()!=EXPECTED_TCL_SHA[kind]:raise ValueError('generated clock Tcl differs from reviewed original bytes')
    return raw
