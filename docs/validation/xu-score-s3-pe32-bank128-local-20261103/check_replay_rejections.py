#!/usr/bin/env python3
"""Run xu's resigned semantic corruption cases only in temporary copies."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('output must be new')
    root = args.root.resolve()
    here = Path(__file__).resolve().parent
    audit = here/'audit_local.py'
    records = []
    for case in ('result-cycles', 'row-retirement', 'integer-vector', 'legacy-variant',
                 'host-skips', 'child-identity', 'source-mode', 'deleted-source-record'):
        with tempfile.TemporaryDirectory(prefix='xu-bank128-replay-negative-') as temporary:
            directory = Path(temporary)
            raw = directory/'raw'
            shutil.copytree(here/'raw', raw)

            def change_json(name, change):
                path = raw/name
                value = json.loads(path.read_text())
                change(value)
                path.write_text(json.dumps(value, indent=2)+'\n')

            if case == 'result-cycles':
                change_json('real1-bank128/result.json', lambda value:value['layers'][0].update(cycles=value['layers'][0]['cycles']+1))
            elif case == 'row-retirement':
                path = raw/'real1-bank128/simulation.log'
                path.write_text(path.read_text().replace('pops_retired=792', 'pops_retired=791'))
                change_json('real1-bank128/result.json', lambda value:value['log_sha256'].update({'simulation.log':sha(path)}))
            elif case == 'integer-vector':
                path = raw/'real1-bank128/vectors/layer_00/x.mem'
                words = path.read_text().splitlines()
                words[0] = format((int(words[0],16)+1)&65535, '04x')
                path.write_text('\n'.join(words)+'\n')

                def replace_vector_hash(value):
                    value['vectors']['layer_00/x.mem'] = sha(path)
                    value['fixture']['files']['layer_00/x.mem'] = sha(path)

                change_json('real1-bank128/result.json', replace_vector_hash)
            elif case == 'legacy-variant':
                change_json('legacy5-bank128/result.json', lambda value:value.update(accel_variant='pe32'))
            elif case == 'host-skips':
                path = raw/'host-final.log'
                path.write_text(path.read_text().replace('OK (skipped=2)', 'OK (skipped=1)'))
            elif case == 'child-identity':
                change_json('identity.json', lambda value:value.update(child='fc3977d0a6d5f85fbfd871fd9439c01c9acab5f5'))
            elif case == 'source-mode':
                change_json('source-files.json', lambda value:value['src/main/scala/GenerateRTL.scala'].update(git_mode='100755'))
            else:
                change_json('source-files.json', lambda value:value.pop('src/main/scala/linear/XuParallelCore.scala'))
            manifest = {path.relative_to(raw).as_posix():dict(bytes=path.stat().st_size, sha256=sha(path))
                        for path in raw.rglob('*') if path.is_file() and path.name != 'manifest.json'}
            (raw/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
            command = [sys.executable, str(audit), '--root', str(root), '--raw', str(raw), '--out', str(directory/'result.json')]
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if result.returncode == 0 or (directory/'result.json').exists():
                raise AssertionError('corruption was accepted: '+case)
            records.append(dict(case=case, exit_code=result.returncode, diagnostic=result.stdout.splitlines()[-1],
                                mutated_manifest_sha256=sha(raw/'manifest.json')))

    with tempfile.TemporaryDirectory(prefix='xu-bank128-gitlink-negative-') as temporary:
        directory = Path(temporary)
        copied = directory/'source'
        subprocess.run(['git','clone','--quiet','--no-hardlinks',str(root),str(copied)], check=True)
        child = copied/'third-party/e203_hbirdv2'
        child.rmdir()
        subprocess.run(['git','clone','--quiet','--no-hardlinks',str(root/'third-party/e203_hbirdv2'),str(child)], check=True)
        subprocess.run(['git','update-index','--cacheinfo','160000,fc3977d0a6d5f85fbfd871fd9439c01c9acab5f5,third-party/e203_hbirdv2'], cwd=copied, check=True)
        subprocess.run(['git','-c','user.name=xu','-c','user.email=xu@localhost','commit','--quiet','-m','xu temporary gitlink corruption'], cwd=copied, check=True)
        command = [sys.executable,str(audit),'--root',str(copied),'--raw',str(here/'raw'),'--out',str(directory/'result.json')]
        result = subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        if result.returncode == 0 or (directory/'result.json').exists() or 'gitlink differs' not in result.stdout:
            raise AssertionError('actual wrong gitlink was not specifically rejected')
        records.append(dict(case='actual-head-gitlink',exit_code=result.returncode,diagnostic=result.stdout.splitlines()[-1]))
    output = dict(status='PASS_ALL_9_REJECTED', scope='actual mutations in temporary copies; original evidence/repositories unchanged',
                  audit_sha256=sha(audit), checker_sha256=sha(Path(__file__)), raw_manifest_sha256=sha(here/'raw/manifest.json'), cases=records)
    args.out.write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(dict(status=output['status'],cases=len(records))))


if __name__ == '__main__':
    main()
