#!/usr/bin/env python3
"""Independent full-SVA startup-init candidate; generic development only."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys
ROOT=Path(__file__).resolve().parents[2]
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--repo',type=Path,default=ROOT);parser.add_argument('--out',type=Path,required=True)
 parser.add_argument('--profile',choices=['s3-y32-bias-sram','s3-y32-bias-registers'],required=True)
 parser.add_argument('--schedule',required=True);parser.add_argument('--layers',default='0')
 args=parser.parse_args(argv);repo=args.repo.resolve();out=args.out.resolve()
 sys.path.insert(0,str(repo/'tools/scripts'))
 adapter=load('s3_startup_activity',repo/'tools/ppa/s3_soc_activity_profile.py')
 campaign=load('s3_startup_campaign',repo/'tools/ppa/s3_task_campaign.py')
 class StartupExtension(adapter.S3ActivityExtension):
  EXTRA=adapter.S3ActivityExtension.EXTRA+['tools/ppa/s3_startup_init_verify.py','tools/ppa/s3_dtcm_unknown_observer.svh']
  def testbench(self,text,source,out,controls):
   text=super().testbench(text,source,out,controls)
   if text.count('\nendmodule')!=1:raise ValueError('startup monitor TB module anchor differs')
   return text.replace('\nendmodule','\n'+(source/'tools/ppa/s3_dtcm_unknown_observer.svh').read_text()+'\nendmodule',1)
  def inspect_task(self,log,task,item):
   result=super().inspect_task(log,task,item)
   matches=re.findall(r'^S3_DTCM_UNKNOWN_AUDIT_SUMMARY (.*)$',log,re.M)
   if len(matches)!=1 or len(re.findall(r'^S3_DTCM_UNKNOWN_AUDIT_PASS ',log,re.M))!=1:
    raise ValueError('missing exact DTCM active-unknown/epilogue proof')
   fields=dict(x.split('=',1)for x in matches[0].split())
   first=re.findall(r'^S3_CALLEE_FIRST_DEFINED index=(\d+) tick_fs=(\d+) value=([0-9a-fA-F]+)$',log,re.M)
   if len(first)!=12 or {int(row[0])for row in first}!=set(range(12)) or any(int(row[2],16)!=0 for row in first):
    raise ValueError('all twelve callee-saved registers need observed first-zero writes')
   if fields['unknown_writes']!='0' or fields['unknown_reads']!='0' or fields['pending']!='0' or fields['callee_seen']!='fff':
    raise ValueError('startup DTCM audit reported unknown/undrained state')
   result['startup_dtcm_audit']=fields
   return result
 model=repo/'tools/ppa/generic_ramsp_non_ppa.sv'
 extension=StartupExtension(repo,args.profile,model,adapter.load('_startup_ppa',repo/'tools/scripts/xu_soc_ppa.py').sha(model),'generic-prototype',args.schedule)
 return campaign.main(['--repo',str(repo),'--out',str(out),'--bias-kind','sram'if args.profile=='s3-y32-bias-sram'else'registers',
  '--schedule',args.schedule,'--layers',args.layers,'--simulator','vcs','--platform-assertions','--max-cycles','6000000'],extension=extension)
if __name__=='__main__':raise SystemExit(main())
