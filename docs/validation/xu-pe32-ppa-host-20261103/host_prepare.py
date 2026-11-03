#!/usr/bin/env python3
"""Reproduce host-only PE32 manifest preparation using visibly invalid dummy DBs.

Never runs DC/PT or represents these preparation checks as physical results.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import types

ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--candidate',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
spec=importlib.util.spec_from_file_location('xu_host_implementation',ROOT/'tools/ppa/xu_soc_implementation.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);ppa=m.ppa_module()
standard=out/'standard.db';standard.write_text('HOST PREPARATION FIXTURE ONLY; NOT AN EDA LIBRARY\n')
sram=out/'sram.db';sram.write_text('HOST SRAM PREPARATION FIXTURE ONLY; NOT AN EDA LIBRARY\n')
command=[sys.executable,str(ROOT/'tools/ppa/xu_soc_implementation.py'),
    '--root',str(a.candidate),'--out',str(out/'implementation'),'--profile','s3-pe32',
    '--standard-cell-db',str(standard),'--standard-cell-sha256',ppa.sha(standard),
    '--sram-db',str(sram),'--sram-sha256',ppa.sha(sram)]
with (out/'implementation-cli.log').open('x') as stream:
    stream.write(json.dumps(dict(argv=command,cwd=str(ROOT)))+'\n');stream.flush()
    subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,check=True)
receipt=json.loads((out/'implementation/generation.json').read_text())
impl=json.loads((out/'implementation/implementation.json').read_text())
prepared=ppa.prepare(a.candidate,out/'prepared',impl,allow_unqualified=True)
ppa.verify_prepared(a.candidate,out/'prepared',prepared)
assert receipt['macro_total']==352 and impl['defines']==ppa.PE32_DEFINES
assert 'XU_ACCEL_PE32=1' in (out/'prepared/synth.tcl').read_text()
assert 'full-SoC SRAM total must be exactly 352' in (out/'prepared/synth.tcl').read_text()
assert 'xu_pe32_icb_slave*' in (out/'prepared/synth.tcl').read_text()
result=dict(status='HOST_PREPARATION_PASS_NOT_EDA',candidate_main=prepared['inventory']['main_commit'],
    candidate_child=prepared['inventory']['e203_commit'],source_profile=receipt['source_profile'],macro_total=receipt['macro_total'],
    defines=impl['defines'],configuration=impl['accelerator_configuration'],source_freeze=impl['source_freeze'],
    gaps=receipt['qualification_gaps'],producer_sha256=ppa.sha(ROOT/'tools/scripts/xu_soc_ppa.py'),
    implementation_sha256=ppa.sha(ROOT/'tools/ppa/xu_soc_implementation.py'))
ppa.write(out/'host-preparation.json',result)
old=types.ModuleType('xu_old_ppa');old.__file__=str(ROOT/'tools/scripts/xu_soc_ppa.py')
old_source=subprocess.check_output(['git','show','28e394a:tools/scripts/xu_soc_ppa.py'],cwd=str(ROOT))
exec(compile(old_source,old.__file__,'exec'),old.__dict__)
compatibility=dict(status='HOST_DEFAULT_COMPATIBILITY_PASS_NOT_EDA',baseline_tool_commit='28e394a0c2e748841fb17ef5736f2f530b572de0',profiles={})
for profile in old.SOURCE_PROFILES:
    before=old.template(dict(platform_source_manifest_sha256='HOST_FIXED'),profile)
    after=ppa.template(dict(platform_source_manifest_sha256='HOST_FIXED'),profile)
    assert old.encoded(before)==ppa.encoded(after),profile
    assert old.memory_checks(before)==ppa.memory_checks(after),profile
    assert old.clock_contract_checks()==ppa.clock_contract_checks()
    compatibility['profiles'][profile]=dict(template_bytes_equal=True,macro_check_bytes_equal=True,
        template_sha256=ppa.digest(after),macro_checks_sha256=hashlib.sha256(ppa.memory_checks(after).encode()).hexdigest())
ppa.write(out/'default-compatibility.json',compatibility)
print(json.dumps(dict(status=result['status'],macro_total=result['macro_total'],configuration=result['configuration']),indent=2))
