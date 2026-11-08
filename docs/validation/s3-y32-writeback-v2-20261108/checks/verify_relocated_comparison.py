from pathlib import Path
import hashlib,json,subprocess,sys
root=Path('/home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest')
h=root/'build/writeback-v2-20261108/handoff'
v=json.loads((h/'archive-verification.json').read_text())
u=Path(v['verification_directory'])/'s3-y32-writeback-v2-evidence'
reporter=u/'tools-current/s3_writeback_report.py'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(reporter)==v['final_reporter_sha256']==sha(root/'tools/analysis/s3_writeback_report.py')
changes=json.loads((u/'summaries/direct-source-differences.json').read_text())
out=h/'relocated-direct-comparison.json'
argv=[sys.executable,'-E','-B',str(reporter),str(u/'campaigns/read-pop-full12/result.json'),str(u/'campaigns/direct-full12/result.json'),'--allow-direct-transport','--out',str(out)]
for k,pair in changes.items(): argv+=['--expect-source-change',k+'='+pair['baseline_sha256']+':'+pair['candidate_sha256']]
with (h/'relocated-direct-comparison.log').open('w') as f:
 result=subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,check=False)
assert result.returncode==0,'strict relocated comparison failed'
got=json.loads(out.read_text());want=json.loads((root/'build/writeback-v2-20261108/direct-comparison.json').read_text())
for k in ['totals','layers','source_changes','firmware_identity']:
 assert got[k]==want[k],k
receipt={'status':'RELOCATED_STRICT_COMPARISON_PASS','scope':'Final archived reporter rehashes unpacked full campaigns; no simulator run','command':argv,'native_exit':result.returncode,'archive_sha256':v['archive_sha256'],'reporter_sha256':sha(reporter),'unpacked_comparison_sha256':sha(out),'original_comparison_sha256':sha(root/'build/writeback-v2-20261108/direct-comparison.json'),'log_sha256':sha(h/'relocated-direct-comparison.log'),'identical_to_original':['totals','layers','source_changes','firmware_identity'],'totals':got['totals']}
(h/'relocated-direct-comparison-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(receipt['status'],got['totals']['candidate']['payload_plus_clear_cycles'])
