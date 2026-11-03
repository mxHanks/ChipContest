#!/usr/bin/env python3
"""Independent joint producer context; old candidate/common files stay frozen."""
import hashlib
import os
from pathlib import Path
import subprocess
import xu_candidate_activity_context as original

TOOL_ROOT=original.TOOL_ROOT
PROFILE=original.PROFILE
SCHEDULE=original.SCHEDULE
MAIN_COMMIT=original.MAIN_COMMIT
require=original.require
sha=original.sha
canonical=original.canonical
load=original.load
FROZEN_DERIVATION={
    'tools/ppa/xu_candidate_task_activity.py':'f6e08a5a67a31479b568bc73b99256769bf6e2f3aca1cc56c2afe759f3da2123',
    'tools/ppa/xu_candidate_activity_context.py':'fc9c606af89e34f189daefecaf106a00e30677f8b24386a60945c07e58ce4a4c',
    'tools/ppa/xu_candidate_sram_activity_alias.py':'840b362e04c7d06d014cf0e4520efc18c15705e1313c5e9ec184ed8b261c77b7',
    'tools/ppa/xu_saif_mapped_macros.py':'316599b0a5cd30203894eeaefdcbbdaf1ad91a7fb08a8d35bce7278549eb734c',
}


def identity(path):
    p=Path(path).absolute()
    require(p.is_file() and not p.is_symlink(),'joint input must be regular non-symlink file: '+str(p))
    return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size,mode=p.stat().st_mode&0o777)


def full_tool_identity():
    base=original.tool_identity()
    for name,digest in FROZEN_DERIVATION.items():
        require(sha(TOOL_ROOT/name)==digest,'old producer/bridge changed: '+name)
    raw=subprocess.check_output(['git','--no-replace-objects','ls-tree','-rz','HEAD'],cwd=str(TOOL_ROOT),stdin=subprocess.DEVNULL)
    records={}
    for row in raw.split(b'\0'):
        if not row:continue
        metadata,name=row.split(b'\t',1);mode,kind,oid=metadata.decode('ascii').split();name=os.fsdecode(name);p=TOOL_ROOT/name
        if mode=='160000':
            require(name=='third-party/e203_hbirdv2','unexpected tool gitlink')
            records[name]=dict(mode=mode,gitlink=oid,policy='unused tool child; all DUT sources come from separately frozen source root')
            continue
        require(kind=='blob','unexpected tool tree entry')
        if mode=='120000':
            require(p.is_symlink(),'tool symlink differs: '+name);data=os.fsencode(os.readlink(str(p)))
        else:
            require(mode in ('100644','100755') and p.is_file() and not p.is_symlink(),'tool file type differs: '+name)
            require(bool(p.stat().st_mode&0o111)==(mode=='100755'),'tool executable mode differs: '+name);data=p.read_bytes()
        require(hashlib.sha1(b'blob '+str(len(data)).encode('ascii')+b'\0'+data).hexdigest()==oid,'tool tracked bytes differ from committed Git: '+name)
        records[name]=dict(mode=mode,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
    return dict(schema='xu-joint-tool-context-v1',base=base,tracked_entries=len(records),tracked_worktree_manifest_sha256=canonical(records),
        fixed_derivation=FROZEN_DERIVATION,policy='independent clean tool checkout, every main tracked blob/mode/gitlink rehashed; original candidate/common helpers unchanged')


class Context(original.Context):
    def __init__(self,root):
        super().__init__(root)
        self.joint_tool=full_tool_identity()

    def recheck(self):
        super().recheck()
        require(self.joint_tool==full_tool_identity(),'joint producer identity changed during run')
