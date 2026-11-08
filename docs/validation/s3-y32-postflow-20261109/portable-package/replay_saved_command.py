#!/usr/bin/env python3
"""Print a relocated saved native simulation command, never execute it."""
from pathlib import Path
import argparse,json,shlex

def relocated(root,text):
 for row in json.loads((root/'path-map.json').read_text()):
  old=row['original_prefix']
  if text==old or text.startswith(old+'/'):
   return str(root/row['relative_prefix'])+text[len(old):]
 return text

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('campaign',help='relative campaign directory or its saved simulation.log')
 a=p.parse_args();root=Path(__file__).resolve().parent
 selected=root/a.campaign
 assert root in selected.resolve().parents and '..' not in Path(a.campaign).parts
 directory=selected if selected.is_dir() else selected.parent
 while not (directory/'result.json').is_file() and not (directory/'receipt.json').is_file():
  assert directory!=root,'no enclosing campaign result'
  directory=directory.parent
 if (directory/'result.json').is_file():
  result=json.loads((directory/'result.json').read_text())
  steps=[s for s in result['steps'] if s['name'].endswith('/simulation')]
 else:
  result=json.loads((directory/'receipt.json').read_text())
  steps=[dict(name='simulation',command=result['command'],cwd=result['cwd'])]
 if selected.is_file():steps=[s for s in steps if directory/(s['name']+'.log')==selected]
 assert steps,'no saved native simulation step'
 for step in steps:
  command=[]
  for token in step['command']:
   if token.startswith(('+TESTCASE=','+VECTORS=')):
    key,value=token.split('=',1);command.append(key+'='+relocated(root,value))
   else:command.append(relocated(root,token))
  print(json.dumps(dict(saved_status=result['status'],record=step['name'],
     output_note='Use a separate new output directory; preserve this original evidence read-only.',
     relocated_saved_cwd=relocated(root,step['cwd']),command=command),indent=2))
  print(shlex.join(command))
if __name__=='__main__':main()
