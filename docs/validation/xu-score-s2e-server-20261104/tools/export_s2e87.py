#!/usr/bin/env python3
"""Snapshot completed S2e74 server evidence; no source mutation or credential use.

Python 3.6 compatible. Tar member/manifest paths are relative to campaign base.
Excluded bodies retain byte-count/SHA256/reason records; no silent omissions.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile
import time

B = Path.home()/'Desktop/xu-score-optimization-20261102'
ACCEPT = 's2e-full-vcs-accept-20261104-74'
DEPLOY = 's2e-deploy-20261104-74'
OUTPUT = B/'xu-s2e-server-full-export-20261104-87.tar.xz'
STATE = B/'xu-export87-state.json'
DRIVER = B/'xu-export87-driver.log'
META = 'xu-s2e-server-full-export87'
MAIN = '5bf123bfead8f2a37f97f3234d4e40ce8201aae9'
CHILD = 'a0767db69628ef30e53de2d1e93dd0360c0ccf76'
DONE = 'EXECUTED_VCS_ACCEPTANCE_NOT_PPA_OR_ENERGY_QUALIFIED'
MAX_BODY = 64*1024*1024
EXCLUDED_DIRS = {'.git','csrc','obj','obj_dir','__pycache__','DVEfiles'}
BINARY_SUFFIXES = {'.o','.a','.so','.vvp','.elf','.pyc','.db','.svf','.xz','.gz','.zip','.tar'}
snapshot = {}
omitted = []
state = dict(schema='xu-s2e-server-export-v1', status='SNAPSHOTTING_NOT_QUALIFIED',
             pid=os.getpid(), started_epoch=time.time(), main=MAIN, e203=CHILD,
             roots=[ACCEPT,DEPLOY], output=OUTPUT.name)


def need(ok, message):
    if not ok: raise ValueError(message)


def save():
    temporary = STATE.with_name(STATE.name+'.tmp')
    temporary.write_text(json.dumps(state,sort_keys=True,indent=2)+'\n')
    os.replace(str(temporary),str(STATE))


def digest(path):
    h = hashlib.sha256()
    count = 0
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            h.update(block)
            count += len(block)
    return count,h.hexdigest()


def member_name(path):
    name = path.relative_to(B).as_posix()
    need(not name.startswith('/') and '..' not in Path(name).parts,'unsafe member path')
    return name


def add_bytes(name,data):
    need(not name.startswith('/') and '..' not in Path(name).parts,'unsafe synthetic member')
    need(name not in snapshot,'duplicate member: '+name)
    snapshot[name] = data


def body_reason(path,name):
    parts = Path(name).parts
    if any(p in EXCLUDED_DIRS or p.endswith('.daidir') or p.endswith('.vdb') for p in parts):
        return 'excluded_obj_csrc_cache_directory'
    lower = name.lower()
    if any(p.lower() in ('vendor','vendor-models','vendor-models-private-01') for p in parts):
        return 'excluded_vendor_body'
    if path.suffix.lower() in ('.v','.sv','.vh','.svh') and (
            path.name.lower().startswith('tb') or 'testbench' in lower or
            any(p.lower() in ('tb','testbench') for p in parts) or
            'ramsp' in path.name.lower()):
        return 'excluded_tb_or_vendor_hdl_body'
    if path.suffix.lower() in BINARY_SUFFIXES:
        return 'excluded_binary_or_nested_archive_body'
    if path.stat().st_size > MAX_BODY:
        return 'excluded_large_body_over_64MiB'
    with path.open('rb') as stream:
        sample = stream.read(8192)
    if b'\x00' in sample or sample.startswith(b'\x7fELF'):
        return 'excluded_binary_body'
    return None


def snapshot_file(path,expected_raw):
    name = member_name(path)
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        link = os.readlink(str(path))
        data = os.fsencode(link)
        omitted.append(dict(path=name,kind='symlink',bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
                            link_text=link,reason='symlink_body_not_followed'))
        return
    need(stat.S_ISREG(info.st_mode),'non-regular output: '+name)
    reason = body_reason(path,name)
    if reason:
        count,sha256 = digest(path)
        record = dict(path=name,bytes=count,sha256=sha256,reason=reason)
        omitted.append(record)
    else:
        data = path.read_bytes()  # One immutable byte snapshot; never hash a second read.
        count,sha256 = len(data),hashlib.sha256(data).hexdigest()
        add_bytes(name,data)
    if name.startswith(ACCEPT+'/'):
        relative = name[len(ACCEPT)+1:]
        if relative != 'state.json':
            expected = expected_raw.get(relative)
            need(expected is not None,'output absent from original terminal raw manifest: '+name)
            need(expected.get('bytes')==count and expected.get('sha256')==sha256,
                 'output changed since original terminal raw manifest: '+name)


def files_under(root):
    # Do not follow directory symlinks. Their literal identity is retained.
    for directory,dirs,files in os.walk(str(root),followlinks=False):
        here = Path(directory)
        for name in list(dirs):
            path = here/name
            if path.is_symlink():
                dirs.remove(name)
                yield path
        for name in files:
            yield here/name


def run():
    need(not OUTPUT.exists() and not STATE.exists(),'new export output/state required')
    save()
    try:
        acceptance = B/ACCEPT
        original_state_data = (acceptance/'state.json').read_bytes()
        original = json.loads(original_state_data.decode())
        need(original.get('status')==DONE,'complete final74 VCS terminal state required')
        need(original.get('expected_main')==MAIN and original.get('expected_e203')==CHILD,
             'final74 frozen main/child differ')
        need(original.get('frozen_before')==original.get('frozen_after') and original.get('frozen_before'),
             'original runtime before/after freeze differs')
        expected_raw = original.get('raw_files')
        need(isinstance(expected_raw,dict) and expected_raw,'original complete raw manifest missing')
        actual = json.loads((acceptance/'acceptance.json').read_text())
        need(actual.get('status')=='PASS','complete VCS steps did not pass')
        baseline = json.loads((acceptance/'baseline/result.json').read_text())
        need(baseline.get('tests')==['rv32ui-p-add','accel_mmio','accel_compute','accel_multigroup','accel_repeat_x'],
             'all five original VCS tests required')
        legacy = json.loads((acceptance/'legacy-images/image-equality.json').read_text())
        need(legacy.get('status')=='PASS' and legacy.get('configurations')==192 and len(legacy.get('records',[]))==192,
             'full 192-configuration image gate incomplete')
        for name in ['real12','autogroup-control-real12']:
            result = json.loads((acceptance/name/'result.json').read_text())
            need(result.get('status')=='PASS' and result.get('tasks')==12 and result.get('simulator')=='vcs' and
                 result.get('main_commit')==MAIN and result.get('e203_commit')==CHILD and
                 result.get('outputs')==304128 and result.get('write_words')==608256 and len(result.get('layers',[]))==12,
                 'same frozen complete VCS real12 missing: '+name)
        deployment = json.loads((B/DEPLOY/'state.json').read_text())
        need(deployment.get('status')=='CAMPAIGN_LAUNCHED_NOT_QUALIFIED' and
             deployment.get('meta',{}).get('main')==MAIN and deployment.get('meta',{}).get('e203')==CHILD,
             'frozen deployment receipt differs')
        # This state is itself an exact original byte snapshot, not a reserialized substitute.
        add_bytes(ACCEPT+'/state.json',original_state_data)
        for prefix in [ACCEPT,DEPLOY]:
            root = B/prefix
            need(root.is_dir(),'campaign output directory missing: '+prefix)
            for path in sorted(files_under(root)):
                if member_name(path)==ACCEPT+'/state.json': continue
                snapshot_file(path,expected_raw)
            print('EXPORT87_PREFIX_SNAPSHOTTED',prefix,'payload',len(snapshot),'omitted',len(omitted),flush=True)
        found = {name[len(ACCEPT)+1:] for name in snapshot if name.startswith(ACCEPT+'/') and name!=ACCEPT+'/state.json'}
        found.update(row['path'][len(ACCEPT)+1:] for row in omitted if row['path'].startswith(ACCEPT+'/') and row.get('kind')!='symlink')
        need(found==set(expected_raw),'original terminal raw manifest paths were deleted or added')
        omission = dict(schema='xu-s2e-explicit-body-omissions-v1',roots=[ACCEPT,DEPLOY],
                        note='All paths are base-relative. Raw file bodies remain on server; hashes stream original bytes. Symlink SHA binds literal link bytes, not target content.',
                        count=len(omitted),bytes=sum(r['bytes'] for r in omitted),records=sorted(omitted,key=lambda r:r['path']))
        add_bytes(META+'/omitted-files.json',(json.dumps(omission,sort_keys=True,indent=2)+'\n').encode())
        source = Path(__file__).resolve()
        add_bytes(META+'/export_s2e87.py',source.read_bytes())
        summary = dict(schema='xu-s2e-server-full-export-v1',main=MAIN,e203=CHILD,
                       original_terminal_status=original['status'],original_state_sha256=hashlib.sha256(original_state_data).hexdigest(),
                       paired_cycles=original.get('paired_real12_cycles'),control_cycles=original.get('control_real12_cycles'),
                       delta_cycles=original.get('delta_cycles'),omitted_files=len(omitted),
                       limits='Complete development VCS evidence only; not PPA, full nominal150MHz, formal mapping, whole-SoC energy, official accuracy or retention.')
        add_bytes(META+'/snapshot.json',(json.dumps(summary,sort_keys=True,indent=2)+'\n').encode())
        records = [dict(path=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()) for name,data in sorted(snapshot.items())]
        with tarfile.open(str(OUTPUT),'x:xz') as tar:
            for name,data in sorted(snapshot.items()):
                info = tarfile.TarInfo(name);info.size=len(data);info.mode=0o644
                tar.addfile(info,io.BytesIO(data))
            data = (json.dumps(records,sort_keys=True,indent=2)+'\n').encode()
            info = tarfile.TarInfo('manifest.json');info.size=len(data);info.mode=0o644
            tar.addfile(info,io.BytesIO(data))
        count,sha256 = digest(OUTPUT)
        state.update(status='SNAPSHOT_COMPLETE_NOT_ADDITIONAL_QUALIFICATION',payload_count=len(records),
                     payload_bytes=sum(r['bytes'] for r in records),omitted_files=len(omitted),
                     bytes=count,sha256=sha256)
    except BaseException as error:
        state.update(status='FAIL',error=type(error).__name__+': '+str(error))
    finally:
        state['finished_epoch']=time.time();save()
    print('S2E_EXPORT87_DONE',json.dumps(state,sort_keys=True),flush=True)
    return 0 if state['status']=='SNAPSHOT_COMPLETE_NOT_ADDITIONAL_QUALIFICATION' else 1


if __name__=='__main__':
    if len(sys.argv)==1:
        need(not OUTPUT.exists() and not STATE.exists() and not DRIVER.exists(),'new export output/state/driver required')
        with DRIVER.open('x') as stream:
            process = subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'run'],
                                       stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        print('S2E_EXPORT87_STARTED',process.pid,flush=True)
        sys.exit(0)
    need(sys.argv[1:]==['run'],'only optional run argument is supported')
    sys.exit(run())
