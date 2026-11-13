#!/usr/bin/env python3
"""Parse native documentation markers; availability never certifies a signature."""
import argparse,sys
from pathlib import Path
sys.dont_write_bytecode=True
from common import *
def main():
 p=argparse.ArgumentParser();p.add_argument('--log',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(not a.out.exists(),'new output required')
 s=probe_sections(a.log.read_text());version=re.findall(r'^\s*Version (\S+)',a.log.read_text(),re.M)
 dump(a.out,dict(schema='final374-fm-native-api-documentation-review-v1',status='DOCUMENTATION_PARSED_SIGNATURE_REVIEW_REQUIRED',log=record(a.log),native_versions=version,
  sections=[dict(kind=k,name=n,**v) for (k,n),v in s.items()],signature_certification=False,verification_run=False,
  missing=[dict(kind=k,name=n,**v) for (k,n),v in s.items() if not v['exists'] or v['returncode']!=0]))
 print('DOCUMENTATION_PARSED_NOT_API_SIGNATURE_APPROVAL')
if __name__=='__main__':main()
