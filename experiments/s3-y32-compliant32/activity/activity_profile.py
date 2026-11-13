#!/usr/bin/env python3
"""Seal an explicit, source-reviewed activity macro inventory to production RTL.

The inventory must be derived from the frozen source/elaboration contract,
independently of the FST being audited. This tool never infers completeness
from the observed waveform or accepts only an expected numeric count.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

PIN_WIDTHS = dict(CLK=1, CEN=1, GWEN=1, WEN=16, A=10, D=16, Q=16, EMA=3, EMAW=2, RET1N=1)
DEFINITIONS = ['SYNTHESIS', 'DISABLE_SV_ASSERTION=1', 'XU_MATRIX_DMA',
               'XU_MATRIX_DMA_SYSBUS32', 'XU_MATRIX_X_SRAM']
PREFIX = 'TOP.tb_sysbus32_soc'
CPU = PREFIX + '.dut.u_e203_subsys_top.u_e203_subsys_main.u_e203_cpu_top.u_e203_srams'
CPU_INTERFACES = {
    CPU + '.u_e203_dtcm_ram.u_e203_dtcm_gnrl_ram.u_sirv_sim_ram':
        dict(clk=1, cs=1, we=1, wem=4, addr=14, din=32, dout=32),
    CPU + '.u_e203_itcm_ram.u_e203_itcm_gnrl_ram.u_sirv_sim_ram':
        dict(clk=1, cs=1, we=1, wem=8, addr=13, din=64, dout=64),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(profile, run):
    if profile.get('schema') != 'compliant32-explicit-activity-profile-v1' or profile.get('status') != 'SEALED_SOURCE_REVIEWED_INVENTORY':
        raise ValueError('explicit sealed source-reviewed activity profile required')
    selected = profile.get('definitions', [])
    if (selected != run.get('definitions') or len(set(selected)) != len(selected) or
            not set(DEFINITIONS).issubset(selected) or any('XU_SYSBUS_TEST_LOADER' in name for name in selected)):
        raise ValueError('profile must retain exact selected production N2 definitions')
    storage = run.get('storage_binding')
    required = [] if storage is None else storage.get('required_defines', [])
    if set(selected) != set(DEFINITIONS + required):
        raise ValueError('extra preprocessor definitions require explicit sealed storage binding')
    if profile.get('storage_binding') != storage:
        raise ValueError('activity profile / selected storage overlay identity differs')
    binding = profile.get('production_binding', {})
    current = run.get('ppa_binding', {})
    keys = ('package_files_sha256', 'manifest_sha256', 'production_rtl_files', 'definitions_exact')
    if any(not binding.get(key) or binding.get(key) != current.get(key) for key in keys):
        raise ValueError('profile/production PPA source binding differs')
    if binding['definitions_exact'] != selected:
        raise ValueError('profile effective production definitions differ')
    macros = profile.get('macros', {})
    counts = profile.get('group_counts', {})
    if not macros or not counts or len(macros) != profile.get('actual_macro_count') or sum(counts.values()) != len(macros):
        raise ValueError('profile needs all exact macro paths and group counts')
    for path, group in macros.items():
        if (not isinstance(path, str) or not path.endswith('.macro') or any(ch in path for ch in '*?/\\') or
                not (path.startswith(PREFIX + '.dut.') or path.startswith(PREFIX + '.endpoint.')) or group not in counts):
            raise ValueError('invalid/wildcard/unclassified macro instance in explicit profile')
    if {group: list(macros.values()).count(group) for group in counts} != counts:
        raise ValueError('profile macro group inventory differs from declared counts')
    if counts.get('itcm') != 32 or counts.get('dtcm') != 32 or counts.get('shared') != 256:
        raise ValueError('profile must include all fixed CPU/shared macros')
    if profile.get('macro_pin_widths') != PIN_WIDTHS or profile.get('cpu_interfaces') != CPU_INTERFACES:
        raise ValueError('profile macro pins / CPU logical interface contract differs')
    if not profile.get('source_review') or not profile.get('inventory_input_sha256'):
        raise ValueError('source-reviewed inventory provenance is missing')
    actual = run.get('macro_scope', {}).get('actual_ramsp_instances', run.get('actual_generic_macro_instances'))
    if actual != len(macros):
        raise ValueError('activity run macro configuration differs from explicit profile')
    return profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-result', type=Path, required=True)
    parser.add_argument('--inventory', type=Path, required=True,
                        help='source-reviewed JSON with name, macros, group_counts and source_review')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    run = json.loads(args.baseline_result.read_text())
    if (run.get('schema') != 's3-compliant32-production-gpio-cpu-v1' or run.get('status') != 'PASS' or
            run.get('production_topology', {}).get('ingress_sources') != 2 or
            run.get('production_topology', {}).get('pointer_bits') != 1):
        raise ValueError('profile baseline must be completed production N2 GPIO CPU PASS')
    inventory = json.loads(args.inventory.read_text())
    profile = dict(schema='compliant32-explicit-activity-profile-v1', status='SEALED_SOURCE_REVIEWED_INVENTORY',
        created_at=datetime.now(timezone.utc).isoformat(), name=inventory['name'],
        definitions=run['definitions'], production_binding=run['ppa_binding'],
        storage_binding=run.get('storage_binding'),
        actual_macro_count=len(inventory['macros']), macros=inventory['macros'], group_counts=inventory['group_counts'],
        macro_pin_widths=PIN_WIDTHS, cpu_interfaces=CPU_INTERFACES, source_review=inventory['source_review'],
        inventory_input_sha256=sha(args.inventory), baseline_result_sha256=sha(args.baseline_result),
        producer_sha256=sha(Path(__file__)),
        qualification='Exact source/configuration inventory only; not timing, power or mapped annotation qualification')
    validate(profile, run)
    with args.out.open('x') as stream:
        stream.write(json.dumps(profile, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(status=profile['status'], macros=profile['actual_macro_count'], profile=str(args.out.resolve()))))


if __name__ == '__main__':
    main()
