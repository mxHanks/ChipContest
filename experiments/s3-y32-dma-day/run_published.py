#!/usr/bin/env python3
"""Check current production RTL with the sealed fabric-clock CPU testbench.

The sealed run supplies the measured testbench, physical-clear observer and
endpoint model. Production RTL comes from the current E203 checkout and the
current PPA wrapper. The existing CPU runner owns all numerical, protocol,
physical-clear, timing-window and source-identity checks.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument('--sealed-run', type=Path, required=True)
    known, rest = parser.parse_known_args()
    forbidden = ['--replay-from', '--generated-dir', '--extra-source', '--observer']
    if any(option in rest for option in forbidden):
        parser.error('this runner owns the exact production and test sources')
    sealed = known.sealed_run.resolve()
    record = json.loads((sealed / 'result.json').read_text())
    replay = load('published_sealed_verifier', HERE / 'replay_frozen.py')
    replay.check_sealed(sealed, record)
    model = sealed / 'source/rtl/perips/boundary_tb_shared_endpoint.sv'
    if not model.is_file():
        raise ValueError('sealed run lacks the fabric-clock endpoint model')
    tb = (sealed / 'source/tests/tb_dma_day_soc.sv').read_text()
    if '.shared_mem_clk(shared_mem_clk)' not in tb or \
            'always @(posedge shared_mem_clk) begin : monitor_and_memory' not in tb:
        raise ValueError('sealed CPU testbench is not the verified boundary repair')
    runner = load('published_original_cpu_runner', HERE / 'run_soc.py')

    def snapshot(out, generated, extras, observer):
        if generated or extras or observer:
            raise ValueError('unexpected source override')
        source = out / 'source'
        shutil.copytree(sealed / 'source', source)
        production = ROOT / 'third-party/e203_hbirdv2/rtl/e203'
        inputs = {}
        for path in sorted(production.rglob('*')):
            if path.is_file() and path.suffix in {'.v', '.sv', '.vh', '.svh'}:
                rel = path.relative_to(production)
                target = source / 'rtl' / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                inputs['rtl/e203/' + rel.as_posix()] = sha(path)
        wrapper = ROOT / 'tools/ppa/xu_soc_ppa_top.sv'
        shutil.copy2(wrapper, source / 'ppa/xu_soc_ppa_top.sv')
        inputs['tools/ppa/xu_soc_ppa_top.sv'] = sha(wrapper)
        shutil.copy2(Path(__file__), source / 'run_published.py')
        manifest = {str(p.relative_to(source)): sha(p)
                    for p in sorted(source.rglob('*')) if p.is_file()}
        runner.write_json(out / 'publication-inputs.json', dict(
            production_inputs=inputs, sealed_run=str(sealed),
            sealed_result_sha256=sha(sealed / 'result.json'),
            runner_sha256=sha(Path(__file__)),
            transaction_clock='exported fabric clock',
            cycle_counter='external HF wall clock',
            inherited_testbench_and_physical_observer=True,
            scope='functional CPU validation; no STA or new area result'))
        runner.write_json(out / 'source-manifest.json', dict(
            files=manifest, adapter='run_published.py',
            sealed_test_source=str(sealed)))
        return source, manifest

    runner.snapshot_sources = snapshot
    return runner.main(rest)


if __name__ == '__main__':
    raise SystemExit(main())
