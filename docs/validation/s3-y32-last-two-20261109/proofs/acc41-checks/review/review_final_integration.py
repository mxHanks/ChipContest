#!/usr/bin/env python3
"""Final read-only independent review receipt; no simulation or production edit."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[4]
# This receipt is intentionally local to the reviewed root checkout.
REPO=Path('/home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest')
B=REPO/'build/last-two-20261109'
H=B/'acc41-checks/review'
D=B/'dma-repo/experiments/s3-y32-last-two/paired-nice'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def must(v,m):
 if not v:raise AssertionError(m)
# Independently compare all installed measured artifacts to frozen baseline.
base=read(B/'baseline-source-freeze.json')['source_sha256']; changed=[]
for name,digest in base.items():
 p=REPO/'tools/ppa/s3_task_campaign.py' if name=='campaign.py' else REPO/'third-party/e203_hbirdv2/rtl/e203'/name[4:] if name.startswith('rtl/') else REPO/name
 if sha(p)!=digest:changed.append(name)
must(not changed,'installed measured sources changed')
# Regenerated optional Scala integration must match prior tested module bytes.
generation=read(B/'root-integrated-generation-receipt.json')
must(generation['status']=='ALL_OPTIONAL_GENERATION_MATCHES','generation status')
for top,expected_count,prior in [('LinearAutoGroupCore',12,REPO/'third-party/e203_hbirdv2/rtl/e203/perips'),('LinearAutoGroupCore41',12,B/'acc41-repo/generated/LinearAutoGroupCore41'),('LinearRowPairPrototype',11,B/'rowpair-repo/generated/LinearRowPairPrototype')]:
 produced=B/'integrated-generation/generated'/top
 files=list(produced.glob('*.sv'));must(len(files)==expected_count,'generated count')
 for p in files:must(sha(p)==sha(prior/p.name),'generated differs '+str(p))
# Permanent acc41 runner source-only replay includes frozen copied testbench.
a=read(B/'integrated-acc41-replay-final/result.json')
must(a['status']=='ACC41_REPRODUCTION_PASS' and a['source_drift']==[],'permanent accumulator replay')
tb=B/'integrated-acc41-replay-final/tb_acc41.sv';must(sha(tb)==a['testbench_sha256'],'frozen testbench')
must(sha(tb)==sha(REPO/'experiments/s3-y32-last-two/acc41/tb_acc41.sv'),'replayed TB current')
runner=REPO/'experiments/s3-y32-last-two/acc41/run_acc41.py';runnertext=runner.read_text()
must('tb = out / "tb_acc41.sv"' in runnertext and 'assert sha(tb) == tb_sha' in runnertext,'runner TB freeze')
must('out.mkdir(parents=True, exist_ok=False)' in runnertext,'runner preserves old outputs')
# Author's final portable31 native outputs are independently checked against
# both all source bytes and all their recorded pass/failure/native statuses.
folder=B/'dma-checks/portable-final-r2';dma=read(folder/'result.json')
must(dma['pass'] and len(dma['runs'])==31 and dma['source_drift']==[],'31 final native passes')
must(len(dma['source_before'])==42,'42 source pins')
for name,digest in dma['source_before'].items():
 must(dma['source_after'][name]==digest and sha(Path(name))==digest,'final source pin '+name)
must(any(n.endswith('/rtl/e203/core/config.v') for n in dma['source_before']),'transitive config pin')
for run in dma['runs']:
 must(run['returncode']==0 and run['pass'] and run['marker_found'],'native result '+run['name'])
 text=(folder/(run['name']+'.log')).read_text();must(run['marker'] in text,'raw marker '+run['name'])
ni=(D/'xu_nice_drain8.v').read_text()
instruction=ni.split('wire instruction_ok =',1)[1].split('integer i;',1)[0]
must(instruction.count('!xu_direct_status[30]')==3,'legacy preflight isolation')
for source in (D/'xu_nice_drain8.v',D/'tb_nice_pair_errors.sv',D/'tb_rowpair_nice_real.sv',D/'rowpair_direct_bridge.v'):
 must(source.exists(),'permanent variant missing')
module=read(H/'rowpair-module-independent-verification.json')
must(module['pass_'] and module['cases']==10 and module['outputs_per_case']==25344,'independent rowpair data')
reviewed=[REPO/'src/main/scala/linear/LinearRowPairPrototype.scala',runner,REPO/'experiments/s3-y32-last-two/acc41/tb_acc41.sv',REPO/'experiments/s3-y32-last-two/rowpair/run_rowpair.py',REPO/'experiments/s3-y32-last-two/rowpair/verify_rowpair.py',REPO/'experiments/s3-y32-last-two/rowpair/rowpair_driver.cpp',REPO/'experiments/s3-y32-last-two/rowpair/generate_observer.py',*[D/n for n in ['xu_nice_drain8.v','run_probe.py','tb_nice_pair_errors.sv','tb_rowpair_nice_real.sv','rowpair_direct_bridge.v','README.md']]]
result={
 'status':'PASS_NO_HARDWARE_BLOCKER_FOUND',
 'scope':'Independent final code review plus read-only saved-evidence verification; no new full12 or module simulation executed by reviewer.',
 'reviewed_source_sha256':{str(p):sha(p) for p in reviewed},
 'installed_default_baseline':{'sources_checked':171,'changed':[],'MacPE_default':'48 bits','CPU_LSU_BIU_firmware_macros':'unchanged'},
 'integrated_generated_sv':{'default48_modules_match_baseline':12,'optional41_modules_match_tested_candidate':12,'rowpair_modules_match_tested_candidate':11},
 'rowpair_code_assessment':{
  'compute':'Two default48 eight-PE engines consume one shared weight array in lockstep. Group remains stable until enqueue; INIT consumes tagged bias next edge, then requests next group while MAC runs.',
  'tail':'secondRow is latched per launch; second engine start gated, outputSecond never advances on single-row mode. Odd row98 never emits row99.',
  'queue':'Two pair slots, four eight-lane bundles maximum. Single producer reserves by launch count<2. Row0 POP retains the pair slot; row1 POP retires it. Simultaneous enqueue/retire preserves count and distinct head/tail ownership.',
  'clear':'Accepts only idle/count0; resets both engines on clearFire, writes all16384 weights, both64-value X buffers, and shared768-word bias SRAM; clearDone waits all controllers. Results/tags are explicitly zeroed. Read-only physical observer checks per-address zero writes and nonzero prestate in development.',
  'public_contract':'Start and source writes require idle; active modifications assert. Prototype has no CPU/MMIO lifecycle or error-response ABI.'},
 'paired_nice_assessment':{
  'address':'33-bit request_end includes optional second-row1024 stride; row-aligned group offset and group+count<=32 enforce each row span. Prior independent210944-case algebra enumeration passed.',
  'identity':'bit30 marks exclusive pair route, old20/23/24 reject before side effects; bit11 row identity checked live and after capture; group tag preserved.',
  'ownership':'Stable eight-lane snapshot precedes later commit; first error aborts, POP cannot retry. Eight serial32-bit LSU writes wait each response; completion follows last response.',
  'validation':{'native_runs':31,'pinned_sources':42,'source_drift':[],'unit_cases':613,'write_error_positions':512,'count_tail_combinations':64,'reset_events':13,'real_mac_success_runs':10,'real_mac_error_indexes':[15,511]}},
 'permanent_acc41_assessment':{'status':'ACC41_REPRODUCTION_PASS','source_only_snapshot':True,'installed_RTL_written':False,'testbench_frozen_and_hash_checked':True,'prefix_bound_proof':'All65 prefixes and complete signed16/signed40 domain','generic48_contract':'600 consecutive products remain tested; fixed64 engine rejects40 elaboration'},
 'independent_rowpair_saved_verification':{'cases':10,'actual_raw48_outputs_per_case':25344,'Cplusplus_RNE_outputs_per_case':25344,'receipt_sha256':sha(H/'rowpair-module-independent-verification.json')},
 'resolved_review_findings':[
  'Comparator now requires each layer totals/window/entireclear equal, preventing aggregate cancellation.',
  'Fixed64 DotProductEngine rejects width40; valid default48/optional41 generated SV unchanged.',
  'Pair route rejects old drain opcodes upfront to prevent partial row0 consumption.',
  'Permanent accumulator runner copies and hashes TB before and after simulation.',
  'Portable paired runner pins transitive core/config.v and refuses output-directory reuse.'],
 'known_limits':[
  'Frozen pair TB stores vector path in1024 bits; README requires <=128 ASCII bytes, tested106. Use a shorter vectors path for relocation.',
  'Module timings exclude production CPU/LSU/fabric, source loading/clear as documented; they are not full-SoC speed measurements.',
  'Paired engine uses serial NICE LSU; it is not an independent DMA master and introduces no new bus requester.',
  'No synthesis, area, energy, STA or formal-clear qualification. Production clear policy REVIEW_PENDING and FIFO physical-zero UNPROVEN remain.'],
 'artifact_sha256':{str(p):sha(p) for p in [B/'root-integrated-generation-receipt.json',B/'root-optional-integration-freeze.json',B/'integrated-acc41-replay-final/result.json',folder/'result.json',H/'final-acc41-review.json']}}
(H/'final-integration-code-review.json').write_text(json.dumps(result,indent=2)+'\n')
print('FINAL_INTEGRATION_REVIEW_PASS installed171unchanged default12 optional41_12 rowpair11 module10cases DMA31runs_42pins no_hardware_blocker')
