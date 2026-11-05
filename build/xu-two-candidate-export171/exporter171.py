#!/usr/bin/env python3
"""Read-only xu171 evidence snapshots. Never launches, stops or edits experiments."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tarfile
import tempfile
import time

CONTROL='unified-experiment-control-20261105-150'
AUDIT='s2e-native-pin-streamaudit-20261105-164'
UNKNOWN='s2c-passive-unknown-20261105-167'
POWER0='s2e-final155-power-preflight-20261105-166'
POWER12='s2e-final155-power12-20261105-166'
JOBS=['s2e_streamaudit164','s2c_unknown167','s2e_final155_preflight166','s2e_final155_power12_166']
BLOCKED={'.git','__pycache__','private-manuals','private-docs'}
CHUNK=1024*1024


def need(ok,message):
    if not ok:raise ValueError(message)


def safe_name(name):
    p=PurePosixPath(name)
    need(isinstance(name,str) and name and '\\' not in name and '\0' not in name and
         not p.is_absolute() and str(p)==name and not {'..','.'}&set(p.parts) and
         not BLOCKED&set(p.parts),'unsafe evidence name: '+str(name))
    return name


def encoded(value):
    return (json.dumps(value,sort_keys=True,indent=2)+'\n').encode('utf-8')


def stats(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mode=s.st_mode,
                mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns)


def sha_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb')as f:
        for block in iter(lambda:f.read(CHUNK),b''):h.update(block)
    return h.hexdigest()


class Snapshot:
    def __init__(self,stage,base,desktop,limit):
        self.stage=stage;self.base=base;self.desktop=desktop;self.limit=limit
        self.files={};self.captures=[];self.omitted=[];self.missing=[];self.rejected=[]

    def checked_source(self,path,anchor):
        path=Path(path);parts=path.relative_to(anchor).parts
        parent=anchor
        for piece in parts:
            need(piece not in BLOCKED,'blocked source component')
            parent=parent/piece
            need(not parent.is_symlink(),'source symlink rejected: '+str(parent))
        return path

    def add(self,path,name,anchor=None,omit=False):
        safe_name(name);need(name not in self.files,'duplicate evidence source: '+name)
        path=Path(path);anchor=anchor or self.base
        if not path.exists() and not path.is_symlink():
            self.missing.append(dict(path=str(path),archive_path=name));return
        row=dict(source_path=str(path),archive_path=name,capture_started_epoch=time.time(),
                 evidence_semantics='LIVE_FILE_SNAPSHOT_TERMINAL_STATUS_UNVERIFIED_NOT_FROZEN')
        destination=None;fd=None
        try:
            self.checked_source(path,anchor)
            need(stat.S_ISREG(path.lstat().st_mode),'source is not a regular file')
            fd=os.open(str(path),os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            before=os.fstat(fd);need(stat.S_ISREG(before.st_mode),'source is not a regular file')
            row['fd_before']=stats(before);left=before.st_size;h=hashlib.sha256();copied=0
            omitted=omit or before.st_size>self.limit
            if not omitted:
                destination=self.stage/name;destination.parent.mkdir(parents=True,exist_ok=True)
                output=destination.open('xb')
            else:output=None
            try:
                # Read only the initially observed length. A live growing log
                # cannot make this exporter chase EOF indefinitely.
                while left:
                    block=os.read(fd,min(CHUNK,left))
                    if not block:break
                    h.update(block);copied+=len(block);left-=len(block)
                    if output is not None:output.write(block)
            finally:
                if output is not None:output.close()
            row.update(fd_after=stats(os.fstat(fd)),bytes_observed=copied,observed_bytes_sha256=h.hexdigest())
            try:row['path_after']=stats(path.lstat())
            except OSError as error:row['path_after_error']=type(error).__name__+': '+str(error)
            row['metadata_unchanged_during_read']=(row['fd_before']==row['fd_after']==row.get('path_after') and copied==before.st_size)
            row['capture_finished_epoch']=time.time()
            if omitted:
                row['omission_reason']='PIN_ORIGINAL_NEVER_PACKAGED' if omit else 'ABOVE_SMALL_FILE_LIMIT'
                row['evidence_semantics']='OMITTED_ORIGINAL_BOUNDED_STREAM_HASH_SNAPSHOT_NOT_FROZEN'
                self.omitted.append(row)
            else:
                self.files[name]=dict(path=name,bytes=copied,sha256=h.hexdigest())
                self.captures.append(row)
        except (OSError,ValueError)as error:
            if destination is not None and destination.exists():destination.unlink()
            row.update(error=type(error).__name__+': '+str(error),capture_finished_epoch=time.time())
            self.rejected.append(row)
        finally:
            if fd is not None:os.close(fd)

    def generated(self,name,value):
        safe_name(name);need(name not in self.files,'duplicate generated evidence')
        raw=encoded(value);p=self.stage/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        self.files[name]=dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

    def names(self,root,prefix,names,anchor=None):
        for name in names:self.add(root/name,prefix+'/'+name,anchor)

    def tree(self,root,prefix,suffixes):
        if not root.exists():self.missing.append(dict(path=str(root),archive_path=prefix,kind='optional_directory'));return
        if root.is_symlink():self.rejected.append(dict(source_path=str(root),error='source directory symlink'));return
        try:self.checked_source(root,self.base)
        except (OSError,ValueError)as error:self.rejected.append(dict(source_path=str(root),error=str(error)));return
        for directory,dirs,files in os.walk(str(root),followlinks=False):
            good=[]
            for name in sorted(dirs):
                p=Path(directory)/name
                if name in BLOCKED:continue
                if p.is_symlink():self.rejected.append(dict(source_path=str(p),error='source directory symlink'))
                else:good.append(name)
            dirs[:]=good
            for name in sorted(files):
                p=Path(directory)/name
                if p.suffix in suffixes:self.add(p,prefix+'/'+str(p.relative_to(root)))


def process(pid):
    if type(pid)is not int or pid<=0:return None
    p=Path('/proc')/str(pid)
    try:
        before=(p/'stat').read_text();argv=(p/'cmdline').read_bytes();uid=p.stat().st_uid;after=(p/'stat').read_text()
        left=before.rsplit(')',1)[1].split();right=after.rsplit(')',1)[1].split()
        need(left[19]==right[19],'process identity changed during observation')
        return dict(pid=pid,uid=uid,start_ticks=int(left[19]),process_state=right[0],
                    argv=[v.decode('utf-8',errors='replace')for v in argv.split(b'\0')if v],observed_epoch=time.time())
    except (OSError,ValueError,IndexError):return None


def select(s):
    b=s.base;c=b/CONTROL
    s.names(c,CONTROL,['state.json','events.jsonl','SUMMARY.md','controller-launch.json','controller.log','driver.log','config.json'])
    s.tree(c/'registrations',CONTROL+'/registrations',{'.json'})
    for job in JOBS:s.tree(c/'runs'/job,CONTROL+'/runs/'+job,{'.json','.jsonl','.log','.txt'})
    for name in ['s2e-streamaudit164-registration-20261105-168.json','two-candidate-registration-20261105-170.json']:
        s.add(b/name,name)
    for name in ['xu-two-candidate-batch170-install.json','xu-two-candidate-register170.log','xu-register168.log','xu-register170.log']:
        s.add(s.desktop/name,'desktop/'+name,s.desktop)
    for folder,names in [('xu-two-candidate-batch170',['manifest170.json','register170.py','run170.py']+
        [job+'.json'for job in JOBS if job!='s2e_streamaudit164']+
        ['s2e_final155_preflight166-command.json','s2e_final155_power12_166-command.json'])]:
        s.names(s.desktop/folder,'desktop/'+folder,names,s.desktop)
    s.names(b/AUDIT,AUDIT,['state.json','failure.txt','driver.log'])
    for i in range(12):s.names(b/AUDIT/('task_%02d'%i),AUDIT+'/task_%02d'%i,['summary.json'])
    s.names(b/UNKNOWN,UNKNOWN,['state.json','adapter-plan147.json','tb_private147.sv','xu_private147.c',
        'xu_private147_bindings.h','xu_mapped_expected111.h','vpi-build.log','vcs-build.log','simulation.log','exception.log'])
    for folder in [POWER0,POWER12]:
        root=b/folder;s.names(root,folder,['result.json','prepared.json','execution.json','summary.json','exception.log'])
        s.names(root/'inventory',folder+'/inventory',['state.json','inventory.json','export.tcl','macro-pins.tsv','pt.log','version.rpt'])
        for i in range(12):
            task='task_%02d'%i;directory=root/task
            if not directory.exists():continue
            s.names(directory,folder+'/'+task,['pt.log','power.tcl','task-mapped-receipt.json'])
            for p in sorted(directory.glob('*.rpt')):
                s.add(p,folder+'/'+task+'/'+p.name,omit=p.name in ['sram-pins-before.rpt','sram-pins-after.rpt'])


def export(base,desktop,out,small_limit):
    base=Path(base).resolve();desktop=Path(desktop).resolve();out=Path(out).absolute()
    need(base.is_dir()and desktop.is_dir(),'base and desktop roots must exist')
    need(not out.exists()and not out.is_symlink(),'fresh archive path required')
    need(out.parent.is_dir()and not out.parent.is_symlink(),'existing regular output parent required')
    started=time.time();partial=out.with_name(out.name+'.partial171')
    need(not partial.exists()and not partial.is_symlink(),'old partial archive preserved; choose a fresh --out')
    try:
        with tempfile.TemporaryDirectory(prefix='xu171-snapshot-',dir=str(out.parent))as temporary:
            s=Snapshot(Path(temporary),base,desktop,small_limit);select(s)
            live=[]
            name=CONTROL+'/state.json'
            if name in s.files:
                try:
                    state=json.loads((s.stage/name).read_text())
                    live.append(dict(name='controller153',recorded_identity=state.get('controller_identity'),actual=process(state.get('controller_pid'))))
                    for job in JOBS:
                        row=state.get('jobs',{}).get(job,{})
                        live.append(dict(name=job,queue_status=row.get('status'),recorded_identity=row.get('worker_identity'),actual=process(row.get('pid'))))
                except (ValueError,TypeError,KeyError)as error:live.append(dict(error='controller copy is a partial/live snapshot: '+str(error)))
            s.generated('snapshot171.json',dict(schema='xu-two-candidate-snapshot171-v1',qualification='NOT_QUALIFIED',
                started_epoch=started,finished_observation_epoch=time.time(),base=str(base),desktop=str(desktop),
                all_copies_are_observations_not_terminal_freezes=True,captures=s.captures,omitted_originals=s.omitted,
                missing_at_observation=s.missing,rejected_sources=s.rejected,live_process_observations=live,
                exporter=dict(path=str(Path(__file__).resolve()),sha256=sha_file(Path(__file__))),
                status='EXPORTED_SNAPSHOT_WITH_REJECTIONS_NOT_QUALIFIED'if s.rejected else 'EXPORTED_READ_ONLY_SNAPSHOT_NOT_QUALIFIED'))
            manifest=dict(schema='xu-two-candidate-export171-v1',qualification='NOT_QUALIFIED',
                files=[s.files[n]for n in sorted(s.files)],payload_files=len(s.files),payload_bytes=sum(r['bytes']for r in s.files.values()),
                note='Manifest hashes bind copied bytes only. Inspect snapshot171.json for live source mutation/omission; no terminal qualification inferred.')
            with tarfile.open(str(partial),'x:xz')as archive:
                for name in sorted(s.files):archive.add(str(s.stage/name),arcname=name,recursive=False)
                raw=encoded(manifest);import io
                info=tarfile.TarInfo('manifest.json');info.size=len(raw);archive.addfile(info,io.BytesIO(raw))
            need(not out.exists()and not out.is_symlink(),'archive destination appeared during capture')
            # Link is no-clobber; source experiments remain untouched.
            os.link(str(partial),str(out));partial.unlink()
        result=dict(path=str(out),bytes=out.stat().st_size,sha256=sha_file(out),files=manifest['payload_files'],payload_bytes=manifest['payload_bytes'])
        print('XU171_READY '+json.dumps(result,sort_keys=True),flush=True);return result
    except BaseException as error:
        failure=out.with_name(out.name+'.failure171.json')
        if not failure.exists():
            with failure.open('xb')as f:f.write(encoded(dict(status='EXPORT171_FAILED_NOT_QUALIFIED',error=type(error).__name__+': '+str(error),partial_archive=str(partial),epoch=time.time())))
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__);d=Path.home()/'Desktop'
    p.add_argument('--base',type=Path,default=d/'xu-score-optimization-20261102')
    p.add_argument('--desktop',type=Path,default=d);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--small-file-limit',type=int,default=16*1024*1024)
    a=p.parse_args();need(a.small_file_limit>0,'positive small-file-limit required');export(a.base,a.desktop,a.out,a.small_file_limit)


if __name__=='__main__':main()
