#!/usr/bin/env python3
"""xu exact archived host evidence review; no original tool execution implied."""
import argparse,copy,hashlib,json,re,shutil,tempfile
from pathlib import Path


def require(ok,message):
    if not ok:raise ValueError(message)


def unique(pairs):
    result={}
    for k,v in pairs:
        require(k not in result,'duplicate JSON key');result[k]=v
    return result


def read(path):return json.loads(path.read_text(),object_pairs_hook=unique)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def check(root):
    entries=read(root/'manifest.json')['files']
    require(set(entries)=={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p!=root/'manifest.json'},'manifest file membership differs')
    for name,row in entries.items():
        p=root/name
        require(not p.is_symlink() and not Path(name).is_absolute() and '..' not in Path(name).parts,'unsafe archive input')
        require(p.stat().st_size==row['bytes'] and digest(p)==row['sha256'],'archive bytes changed: '+name)
    summary=read(root/'summary.json')
    require(summary['producer_commit']=='61f74dc2741764be79194b73aff064589d9c3d6a' and summary['tests']==10 and summary['skipped']==0 and summary['actual_vcs_execution'] is False,'host scope changed')
    text=(root/'raw/unittest.log').read_text()
    require('Ran 10 tests in 12.582s\n\nOK\n' in text and len(re.findall(r'^test_.* \.\.\. ok$',text,re.M))==10 and 'skipped' not in text,'complete actual host test result differs')
    require(digest(root/'raw/unittest.log')==summary['unittest_sha256'],'unittest identity differs')
    receipt=read(root/'raw/header-class-actual-compile.json');compiled=receipt['compile'];cmd=compiled['command']
    require(cmd.count('-isystem')==1 and cmd[cmd.index('-isystem')+1]==str(Path(compiled['header']['path']).parent),'vendor include is not system classified')
    for flag in ('-Wall','-Wextra','-Wshadow','-Wstrict-prototypes','-Werror','-MD','-MF'):
        require(flag in cmd,'strict warning or system dependency option missing: '+flag)
    require('-MMD' not in cmd,'system header dependency exclusion')
    require(compiled['source']['sha256']==digest(root/'evidence-tools/xu_sram_joint_vpi.c') and compiled['source']['bytes']==(root/'evidence-tools/xu_sram_joint_vpi.c').stat().st_size,'compiled C is not archived production C')
    require(any(r==compiled['header'] for r in compiled['dependencies']),'requested synthetic system header absent from dependencies')
    require(any(r['path']=='/usr/include/iverilog/vpi_user.h' for r in compiled['dependencies']),'actual host VPI interface dependency missing')
    require(all(r in compiled['frozen_files'] for r in compiled['dependencies']),'dependencies not frozen')
    require(receipt['vendor_user_header_control_returncode']!=0 and receipt['own_source_old_prototype_rejected'] is True and receipt['system_header_mutation_rejected'] is True,'negative header controls missing')
    for name in ('header-class-user-vendor-rejected.log','header-class-joint-vpi-build.log'):
        require('-Werror=strict-prototypes' in (root/'raw'/name).read_text(),'actual negative compiler diagnostic missing')
    generated=(root/'raw/generated-joint-candidate-tb.sv').read_text()
    require(generated.count('$xu_sram_joint_register(')==336 and generated.count('$xu_sram_joint_begin(')==generated.count('$xu_sram_joint_end(')==1,'actual 336 registration/boundary count differs')
    return dict(status='EXACT_ARCHIVE_AND_HOST_HEADER_CONTROLS_PASS_NOT_ACTUAL_VCS_OR_ENERGY_QUALIFIED',files=len(entries),host_tests=10,seconds=12.582)


def resign(root):
    rows={str(p.relative_to(root)):dict(bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(root.rglob('*')) if p.is_file() and p!=root/'manifest.json'}
    (root/'manifest.json').write_text(json.dumps(dict(files=rows),indent=2,sort_keys=True)+'\n')


def negatives(root):
    cases=[]
    for name in ('isystem','own-werror','dependency','source','negative-control','unittest'):
        with tempfile.TemporaryDirectory(prefix='xu-header-evidence-negative-') as t:
            r=Path(t)/'evidence';shutil.copytree(str(root),str(r))
            p=r/'raw/header-class-actual-compile.json';x=read(p)
            if name=='isystem':x['compile']['command'][x['compile']['command'].index('-isystem')]='-I'
            elif name=='own-werror':x['compile']['command'].remove('-Werror')
            elif name=='dependency':x['compile']['dependencies']=[d for d in x['compile']['dependencies'] if d!=x['compile']['header']]
            elif name=='source':x['compile']['source']['sha256']='0'*64
            elif name=='negative-control':x['vendor_user_header_control_returncode']=0
            else:(r/'raw/unittest.log').write_text((r/'raw/unittest.log').read_text().replace('Ran 10 tests','Ran 9 tests'))
            p.write_text(json.dumps(x,sort_keys=True,indent=2)+'\n');resign(r)
            try:check(r)
            except ValueError as error:cases.append(dict(case=name,rejected=True,reason=str(error)))
            else:raise AssertionError('re-signed semantic mutation accepted: '+name)
    return cases


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent.parent);p.add_argument('--self-test',action='store_true');a=p.parse_args();result=check(a.root)
    if a.self_test:result['re_signed_negative_cases']=negatives(a.root)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))

if __name__=='__main__':main()
