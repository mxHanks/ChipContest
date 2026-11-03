#!/usr/bin/env python3
"""Host-only real-candidate source mutation checks in disposable shared clones.

The original candidate is read only. No DC/PT, vendor model or credential use.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import types

ROOT = Path(__file__).resolve().parents[3]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--candidate', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
out = a.out.resolve()
out.mkdir(parents=True, exist_ok=False)
spec = importlib.util.spec_from_file_location('xu_real_guard_implementation', ROOT/'tools/ppa/xu_soc_implementation.py')
impl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(impl)
ppa = impl.ppa_module()
candidate = a.candidate.resolve()
before = ppa.source_profile_identity(candidate, 's3-pe32')

def git(path, *args):
    return subprocess.check_output(['git', '--no-replace-objects']+list(args), cwd=str(path), stderr=subprocess.STDOUT).decode().strip()

result = dict(schema='xu-pe32-main-source-guard-host-v1', status='HOST_ONLY_PENDING_NOT_EDA',
              candidate=str(candidate), producer_sha256=ppa.sha(ppa.__file__),
              main=ppa.PE32_MAIN_COMMIT, child=ppa.SOURCE_PROFILES['s3-pe32']['commit'],
              original_before=before, cases=[])
standard = out/'standard.db'
sram = out/'sram.db'
standard.write_text('HOST FIXTURE ONLY; NOT AN EDA LIBRARY\n')
sram.write_text('HOST SRAM FIXTURE ONLY; NOT AN EDA LIBRARY\n')
with tempfile.TemporaryDirectory(prefix='xu-pe32-main-guard-') as temporary:
    scratch = Path(temporary)/'source'
    git(candidate, 'clone', '--quiet', '--shared', '--no-checkout', str(candidate), str(scratch))
    git(scratch, 'checkout', '--quiet', '--detach', ppa.PE32_MAIN_COMMIT)
    git(scratch, 'config', 'user.name', 'xu host source guard probe')
    git(scratch, 'config', 'user.email', 'xu-source-guard@example.invalid')
    git(scratch, 'config', 'commit.gpgsign', 'false')
    git(candidate/ppa.SUB, 'clone', '--quiet', '--shared', '--no-checkout', str(candidate/ppa.SUB), str(scratch/ppa.SUB))
    git(scratch/ppa.SUB, 'checkout', '--quiet', '--detach', ppa.SOURCE_PROFILES['s3-pe32']['commit'])
    assert ppa.source_profile_identity(scratch, 's3-pe32') == before
    tb = scratch/'tests/e203/tb_accel_soc.sv'
    original = tb.read_bytes()
    assert original.count(b'always #2 clk = ~clk;') == 1

    def reject(name):
        destination = out/name
        status = git(scratch, 'status', '--porcelain')
        try:
            impl.generate(scratch, destination, standard, ppa.sha(standard), sram, ppa.sha(sram), profile='s3-pe32')
        except ValueError as error:
            assert not destination.exists(), name+' created output before guard rejection'
            ordinary = subprocess.check_output(['git', 'status', '--porcelain'], cwd=str(scratch)).decode().strip()
            result['cases'].append(dict(name=name, status='REJECTED_BEFORE_OUTPUT', error=str(error),
                                        git_status=status, ordinary_git_status=ordinary, output_exists=False))
        else:
            raise AssertionError('real candidate mutation accepted: '+name)

    for flag in ['assume-unchanged', 'skip-worktree']:
        git(scratch, 'update-index', '--'+flag, 'tests/e203/tb_accel_soc.sv')
        tb.write_bytes(original.replace(b'always #2 clk = ~clk;', b'always #3 clk = ~clk;'))
        assert git(scratch, 'status', '--porcelain') == ''
        reject('hidden-tb-'+flag)
        tb.write_bytes(original)
        git(scratch, 'update-index', '--no-'+flag, 'tests/e203/tb_accel_soc.sv')
    mode = tb.stat().st_mode
    tb.chmod(0o755)
    reject('executable-mode-change')
    tb.chmod(mode)
    tb.unlink()
    external = Path(temporary)/'external-tb.sv'
    external.write_bytes(original)
    tb.symlink_to(external)
    reject('same-bytes-symlink-substitution')
    tb.unlink()
    tb.write_bytes(original)
    tb.chmod(mode)
    injected = scratch/'tools/scripts/xu_injected_guard_probe.py'
    injected.write_text('raise RuntimeError("untracked source")\n')
    reject('untracked-active-tool')
    injected.unlink()
    injected = scratch/'tests/e203/xu_ignored_guard_probe.sv'
    with (scratch/'.git/info/exclude').open('a') as stream:
        stream.write('\n/tests/e203/xu_ignored_guard_probe.sv\n')
    injected.write_text('module injected; endmodule\n')
    assert git(scratch, 'status', '--porcelain') == ''
    reject('ignored-active-testbench')
    injected.unlink()
    tb.write_bytes(original.replace(b'always #2 clk = ~clk;', b'always #3 clk = ~clk;'))
    git(scratch, 'add', 'tests/e203/tb_accel_soc.sv')
    git(scratch, 'commit', '-qm', 'xu actual-candidate replacement-object negative probe')
    replacement = git(scratch, 'rev-parse', 'HEAD')
    git(scratch, 'replace', ppa.PE32_MAIN_COMMIT, replacement)
    # Use Git's ordinary replaced checkout intentionally for the negative.
    subprocess.run(['git', 'checkout', '--quiet', '--detach', ppa.PE32_MAIN_COMMIT], cwd=str(scratch), check=True)
    assert subprocess.check_output(['git', 'status', '--porcelain'], cwd=str(scratch)) == b''
    reject('main-replace-object-hidden-tb')

old = types.ModuleType('xu_old_ppa')
old.__file__ = str(ROOT/'tools/scripts/xu_soc_ppa.py')
exec(compile(subprocess.check_output(['git', 'show', 'ffa34db:tools/scripts/xu_soc_ppa.py'], cwd=str(ROOT)),
             old.__file__, 'exec'), old.__dict__)
compatibility = {}
for profile in old.SOURCE_PROFILES:
    inventory = dict(platform_source_manifest_sha256='HOST_FIXED')
    before_template = old.template(inventory, profile)
    after_template = ppa.template(inventory, profile)
    assert old.encoded(before_template) == ppa.encoded(after_template), profile
    assert old.memory_checks(before_template) == ppa.memory_checks(after_template), profile
    compatibility[profile] = dict(template_bytes_equal=True, macro_check_tcl_bytes_equal=True,
        template_sha256=ppa.digest(after_template),
        macro_check_tcl_sha256=hashlib.sha256(ppa.memory_checks(after_template).encode()).hexdigest())
assert old.clock_contract_checks() == ppa.clock_contract_checks()
receipt = impl.generate(candidate, out/'positive-implementation', standard, ppa.sha(standard),
                        sram, ppa.sha(sram), profile='s3-pe32')
configuration = json.loads((out/'positive-implementation/implementation.json').read_text())
assert receipt['macro_total'] == 352
old_configuration = copy.deepcopy(configuration)
old_configuration['source_freeze']['profile'].pop('main_source_freeze')
old_proof = out/'old-mapping-proof.json'
ppa.write(old_proof, old.mapping_review_template(old_configuration))
old_configuration['mapping_proof'] = dict(path=str(old_proof), sha256=ppa.sha(old_proof))
# Use the identical output path on each call so no path normalization can hide
# a changed Tcl/source-list byte. Both calls only prepare, with dummy DB files.
prepared = out/'same-prepared-output-path'
old.prepare(candidate, prepared, old_configuration, True)
names = ['synth.tcl', 'sta.tcl', 'constraints.sdc', 'clock-review.tcl', 'rtl.f']
old_files = {name: (prepared/name).read_bytes() for name in names}
shutil.rmtree(str(prepared))
manifest = ppa.prepare(candidate, prepared, configuration, True)
ppa.verify_prepared(candidate, prepared, manifest)
new_files = {name: (prepared/name).read_bytes() for name in names}
assert old_files == new_files
result['actual_preparation'] = dict(status='HOST_PREPARATION_AND_TCL_BYTE_IDENTICAL_NOT_EDA',
    macro_total=receipt['macro_total'], prior_tool_commit='ffa34db',
    files={name: dict(bytes=len(new_files[name]), sha256=hashlib.sha256(new_files[name]).hexdigest())
           for name in names})
result['original_after'] = ppa.source_profile_identity(candidate, 's3-pe32')
assert result['original_after'] == result['original_before']
result.update(status='HOST_MUTATIONS_REJECTED_NOT_EDA', compatibility=compatibility,
              clock_contract_tcl_bytes_equal=True, cases_count=len(result['cases']))
(out/'result.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
print(json.dumps(dict(status=result['status'], cases=result['cases_count'],
                     untouched_original=result['original_before']==result['original_after'])))
