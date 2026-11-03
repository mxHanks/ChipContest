from pathlib import Path
import hashlib,json,subprocess,tarfile
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent/'deployment-code-02';O.mkdir(exist_ok=False)
refs=[('main',R,'94ce6f0f54fffdd590ff9a3ebad0197ec0fd9114','286b95a4e0b05b78f39ef4d648d1f922e684d7fc'),('child',R/'third-party/e203_hbirdv2','fc3977d0a6d5f85fbfd871fd9439c01c9acab5f5','7aae96776e116d5e95d6ebb49d29a5fccce04ab9')]
record=dict(schema='xu-pe64-code-deployment-v1',qualification='NOT_QUALIFIED',note='Frozen independent 64PE implementation. Local screening evidence separately archived; server VCS/full12/mapped PPA/formal energy pending.',repositories={})
for name,repo,base,commit in refs:
 p=O/(name+'.bundle');subprocess.run(['git','bundle','create',str(p),'HEAD','^'+base],cwd=repo,check=True,stdout=subprocess.DEVNULL)
 subprocess.run(['git','bundle','verify',str(p)],cwd=repo,check=True,stdout=subprocess.DEVNULL)
 raw=p.read_bytes();record['repositories'][name]=dict(base=base,commit=commit,bundle=p.name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
raw=(R/'build/xu-s3-pe64-local-20261103/source-final.json').read_bytes();(O/'source-final.json').write_bytes(raw);record['source_manifest']=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
(O/'deployment.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
(O/'README.md').write_text('''# xu independent64 code deployment\n\nRequires the exact recorded32PE base commits in local repositories. Clone the32 server worktree into a new independent directory, initialize/clone its child separately, verify both bundle SHA values from deployment.json, then fetch/check out the recorded new commits. Never overwrite the32 source. This archive contains no credentials.\n\nRun in the new clean64 tree with actual server cross prefix:\n\n```sh\npython3 tools/scripts/server_accept.py --help\npython3 tools/scripts/server_accept.py --sim vcs --cross-prefix /absolute/server/riscv64-unknown-elf- --firmware-schedule bias-hw-pe64-autogroup-window --firmware-opt=-O2 --firmware-experiment both-unroll-no-masks --accel-variant pe64 --out /absolute/new/xu-pe64-accept\n```\n\nThen run same64 physical RTL full12 controls using32 and8 schedules, and the independent physical32/8 controls. No local result establishes server/physical qualification. Full taskclear/request activity needs the new formal collector configured for64; oldbaseline/wrapper power is not compatible. Expected physical W macros64, logical32KiB/physical128KiB, fullSoC expected384 macros pending actual mapping.\n''')
archive=O.parent/'xu-s3-pe64-code-20261103-02.tar.xz'
with tarfile.open(archive,'w:xz')as tar:
 for p in sorted(O.iterdir()):tar.add(p,arcname=p.name,recursive=False)
raw=archive.read_bytes();print(json.dumps(dict(path=str(archive),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),repositories=record['repositories']),indent=2))
