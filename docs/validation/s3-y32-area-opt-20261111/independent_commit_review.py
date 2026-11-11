#!/usr/bin/env python3
"""Read-only review of committed selected-source identity. No generation, EDA or simulation."""
import hashlib,json,subprocess
from datetime import datetime,timezone
from pathlib import Path
R=Path(__file__).resolve().parents[3];W=R/'build/area-opt-20261111';C=R/'third-party/e203_hbirdv2'
PARENT='96fffcb2a4b2492fd2cfdecb88e164d2c67881ae';CHILD='ccdac30d92ecf40f14d0b78879b8711fb0b1cdd1';BASE='a80dd184536e0f2312c62768d5acf4ba1b01c34e'
TILE='rtl/e203/perips/LinearTileDmaCore.sv';EXPECTED='710b8e180652f49751769e152a3b3a9e6a35ba622fb4c3e2385dc5ffab241fcb'
MP={'experiment/GenerateTileCore.scala':'experiments/s3-y32-4k/core/GenerateTileCore.scala','experiment/LinearTileDmaCore.scala':'experiments/s3-y32-4k/core/LinearTileDmaCore.scala','src/main/scala/dotproduct/DotProductEngine.scala':'src/main/scala/dotproduct/DotProductEngine.scala','src/main/scala/dotproduct/MacPE.scala':'src/main/scala/dotproduct/MacPE.scala','src/main/scala/dotproduct/MacPEArray.scala':'src/main/scala/dotproduct/MacPEArray.scala'}
def git(repo,*args):return subprocess.check_output(['git','-C',str(repo),*args])
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(data):return hashlib.sha256(data).hexdigest()
def load(p):return json.loads(p.read_text())
def check(v,msg):
 if not v:raise ValueError(msg)
def main():
 out=W/'finalization/independent-selected-commit-review-r1.json';check(not out.exists(),'refuse overwrite')
 parent_changes=git(R,'diff-tree','--no-commit-id','--name-only','-r',PARENT).decode().splitlines();check(set(parent_changes)==set(MP.values())|{'third-party/e203_hbirdv2'} and len(parent_changes)==6,'parent implementation commit scope differs')
 child_changes=git(C,'diff-tree','--no-commit-id','--name-only','-r',CHILD).decode().splitlines();check(child_changes==[TILE],'child implementation commit scope differs')
 check(git(C,'rev-parse',CHILD+'^').decode().strip()==BASE,'child does not directly descend from published fallback')
 check(git(C,'diff','--name-only',BASE,CHILD).decode().splitlines()==[TILE],'selected child includes other source changes')
 entry=git(R,'ls-tree',PARENT,'third-party/e203_hbirdv2').decode().split();check(entry[:3]==['160000','commit',CHILD],'committed parent gitlink differs')
 cand=W/'candidates/b-raw41';gen=load(cand/'generation-result.json');cpu=W/'cpu/b-full12-r1';result=load(cpu/'result.json');manifest=load(cpu/'source-manifest.json')['files'];sel=load(W/'finalization/selection-r1.json')
 check(sha(cpu/'result.json')=='f33e2d404c31a0fe1b05b8fb50f8c566763e2810d44e5a6a57dd2e7e0b75f4fe','actual complete12 result differs')
 check(sha(cpu/'source-manifest.json')=='28092f88bae32165a68d4a52d240c346df44ec82ea0799c5b0def05278c7f414','actual complete12 source manifest differs')
 tile=git(C,'show',CHILD+':'+TILE);check(digest(tile)==EXPECTED==sha(cand/'install/LinearTileDmaCore.sv')==manifest['rtl/perips/LinearTileDmaCore.sv']==result['source_sha256']['rtl/perips/LinearTileDmaCore.sv']==sel['selected_installed_tile_sha256'],'committed/installed/CPU/selection tile hashes differ')
 check(tile==(C/TILE).read_bytes(),'working installed tile differs from selected commit')
 source_rows={}
 for src,dst in MP.items():
  committed=git(R,'show',PARENT+':'+dst);h=digest(committed)
  check(h==gen['snapshot_sources'][src]==sha(cand/'chisel'/src),'committed generator differs from actual measured snapshot '+dst)
  check(committed==(R/dst).read_bytes(),'working generator differs from committed '+dst)
  source_rows[dst]=h
 count=0
 for n,h in manifest.items():
  if not n.startswith('rtl/'):continue
  path='rtl/e203/'+n[4:]
  if n in {'rtl/perips/generic_ramsp_non_ppa.sv','rtl/perips/tile_physical_observer.sv'}:
   check(not (C/path).exists(),'simulation helper installed');continue
  check(digest(git(C,'show',CHILD+':'+path))==h,'committed child differs from measured CPU RTL '+n);count+=1
 check(count==165,'unexpected measured RTL census')
 for n,h in gen['generated_rtl'].items():check(sha(cand/'generated'/n)==h,'canonical generated fragment drift '+n)
 check(b'\n'.join((cand/'generated'/n).read_bytes() for n in gen['concat_order'])==tile,'committed tile not exact canonical newline concatenation')
 proof=load(cand/'packaging-proof/proof.json');check(proof['complete_ast_type_equal'] and proof['fallback3_byte_identical'] and proof['install_sha256']==EXPECTED,'packaging proof mismatch')
 check(gen['default11_byte_identical'],'default48 proof missing')
 defaults={p.name:sha(p) for p in (cand/'default').glob('*.sv')};check(len(defaults)==11,'default generated file count differs')
 baseline=R/'build/parallel4k-20261110/core-generated-r1';check(all(sha(baseline/n)==h for n,h in defaults.items()),'default48 generated files not byte-identical to published baseline')
 check(result['status']=='PASS' and result['principal_cycles']==428915 and result['outputs']==304128,'complete12 functional evidence differs')
 after=load(W/'finalization/b-after-source-commit-r2.json');check(after['parent_head']==PARENT and after['child_head']==CHILD and after['child_rtl_files_compared']==165 and after['status']=='IDENTITY_PASS_NO_NEW_SIMULATION_OR_PPA','root installation receipt not bound to source commits')
 report={'schema':'s3-areaopt-independent-selected-commit-source-review-v1','status':'PASS_AUTHORIZED_COMMIT_SCOPE_AND_MEASURED_SOURCE_IDENTITY','created_at_utc':datetime.now(timezone.utc).isoformat(),'new_generation_eda_or_simulation':False,'reviewer_script_sha256':sha(Path(__file__)),'parent_source_commit':PARENT,'child_source_commit':CHILD,'fallback_child':BASE,'parent_changed_paths':parent_changes,'child_changed_paths':child_changes,'parent_generator_sha256':source_rows,'parent_gitlink_matches_child':True,'selected_tile_sha256':EXPECTED,'measured_CPU_result_sha256':sha(cpu/'result.json'),'measured_CPU_source_manifest_sha256':sha(cpu/'source-manifest.json'),'committed_child_RTL_files_compared':count,'default48_generated11_byte_identity':True,'canonical_split_vs_concat_proof_sha256':sha(cand/'packaging-proof/proof.json'),'strict_installation_receipt_sha256':sha(W/'finalization/b-after-source-commit-r2.json'),'selection_receipt_sha256':sha(W/'finalization/selection-r1.json'),'scope':'Committed source objects and existing measured snapshots compared read-only; no new numeric/protocol, mapped equivalence, STA or contest qualification claim','remote_push_status':'NOT_CHECKED_BY_THIS_REVIEW','timing_verdict':'NOT_CLOSED_NATIVE_VIOLATIONS'}
 out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(report['status'],sha(out))
if __name__=='__main__':main()
