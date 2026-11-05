#!/usr/bin/env python3
"""Build the exact original-host campaign release; does not contact the server."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile

HERE=Path(__file__).resolve().parent
BUILD=HERE.parent
DESKTOP='/storage2/2026contest/server4/s4_23usr/Desktop'
DEPLOY=DESKTOP+'/xu-campaign-batch154'
BASE=DESKTOP+'/xu-score-optimization-20261102'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path,value):
    Path(path).write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')


def copy_file(source,dest):
    dest.parent.mkdir(parents=True,exist_ok=True)
    assert not dest.exists(),str(dest)
    shutil.copyfile(str(source),str(dest))


def copy_bundle(source,destination,manifest_name):
    manifest=json.loads((source/manifest_name).read_text())
    rows=manifest.get('files') or [dict(path=r['name'],bytes=r['bytes'],sha256=r['sha256']) for r in manifest['runtime_files']]
    assert rows and len(rows)==len({r['path'] for r in rows})
    for row in rows:
        path=Path(row['path'])
        assert not path.is_absolute() and '..' not in path.parts
        src=source/path
        assert src.is_file() and not src.is_symlink() and src.stat().st_size==row['bytes'] and sha(src)==row['sha256'],str(src)
        copy_file(src,destination/path)
    copy_file(source/manifest_name,destination/manifest_name)


def frozen(prefix,names):
    return [dict(path=DEPLOY+'/'+prefix+'/'+name,bytes=(HERE/prefix/name).stat().st_size,sha256=sha(HERE/prefix/name)) for name in names]


def direct(jobid,out,script,argv,deps,success,failure,inputs,native=True,result='state.json'):
    return dict(schema='xu-experiment-control150-job-v1',qualification='NOT_QUALIFIED',id=jobid,
        kind='launch',launch_mode='direct',native=native,dependencies=deps,
        process_contains=out,result_state=out+'/'+result,output_root=out,
        success_statuses=[success],failure_statuses=[failure],
        argv=['/bin/python3','-B','-u',DEPLOY+'/'+script]+argv,frozen_inputs=inputs)


def main():
    assert not (HERE/'release154.json').exists(),'release already frozen; build a new numbered release instead'
    mappings=[('xu-profile-activity145','activity145','bundle-manifest145.json'),
              ('xu-candidate-power146','power146','bundle-manifest146.json'),
              ('xu-mapped-private147','private147','manifest147.json'),
              ('xu-experiment-control153','control153','bundle-manifest153.json'),
              ('xu-s2e-timing155','timing155','manifest155.json'),
              ('xu-s2e-streamaudit156','streamaudit156','manifest156.json')]
    for source,destination,manifest in mappings:
        copy_bundle(BUILD/source,HERE/destination,manifest)
    copy_file(BUILD/'xu-experiment-enroll152/enroll152.py',HERE/'enroll152.py')
    jobs=HERE/'jobs';jobs.mkdir()
    baseline=json.loads((BUILD/'xu-score-resume-20261103/queue149/eight-candidate-freeze-queue-20261105-138/baseline_h1_h2/freeze.json').read_text())
    prefix=DESKTOP+'/xu-platform-eval-20261101-codex/sifive-rv32-c/bin/riscv64-unknown-elf-'
    toolchain=[{k:r[k] for k in ('path','bytes','sha256')} for r in baseline['after'] if r['path'] in [prefix+n for n in ('gcc','objcopy','objdump')]]
    assert len(toolchain)==3
    prepared=json.loads((BUILD/'xu-score-resume-20261103/terminal151/s2e-full-soc-power12-20261105-130/prepared.json').read_text())
    vcs='/eda/synopsys/vcs/vcs_2020.03-SP2-6/bin/vcs'
    toolchain.append(dict(path=vcs,sha256=prepared['input_sha256'][vcs]))
    for source,pattern in [(BUILD/'xu-profile-activity145-jobs154','activity145_*.json'),(BUILD/'xu-power146-jobs154','power146_*.json')]:
        paths=sorted(source.glob(pattern));assert len(paths)==8
        for path in paths:
            job=json.loads(path.read_text())
            if job['id'].startswith('activity145_'):
                job['argv'][job['argv'].index('--vcs')+1]=vcs
                job['argv'][job['argv'].index('--cross-prefix')+1]=prefix
                records={r['path']:r for r in job['frozen_inputs']}
                for row in toolchain:
                    assert row['path'] not in records or records[row['path']]['sha256']==row['sha256']
                    records[row['path']]=row
                job['frozen_inputs']=[records[p] for p in sorted(records)]
            if job['id']=='activity145_baseline_h1_h2':
                job['dependencies'].append(dict(id='s2e_streamaudit156',policy='terminal'))
            save(jobs/path.name,job)
    out=BASE+'/s2e-own-timing-repair-20261105-155'
    timing=direct('s2e_timing155',out,'timing155/resume155.py',['--out',out],
        [dict(id='baseline_rdc142',policy='terminal')],
        'EXECUTED_OWN_S2E_SAME_MAPPED_DC_PT_FULL_FM_NOT_QUALIFIED','FAILED_NOT_QUALIFIED',
        frozen('timing155',['resume155.py','xu_s2e_timing134.py','reset134.tcl']))
    out=BASE+'/s2c-private-native-20261105-147'
    private_manifest=json.loads((HERE/'private147/manifest147.json').read_text())
    private=direct('mapped_private147',out,'private147/xu_private147.py',['--run','--out',out],
        [dict(id='s2e_timing155',policy='terminal')],private_manifest['expected_terminal_status'],private_manifest['failure_status'],
        frozen('private147',[r['name'] for r in private_manifest['runtime_files']]))
    out=BASE+'/s2e-native-pin-streamaudit-20261105-156'
    stream_manifest=json.loads((HERE/'streamaudit156/manifest156.json').read_text())
    runtime=stream_manifest['runtime_files']
    if runtime and isinstance(runtime[0],dict):runtime=[r.get('path',r.get('name')) for r in runtime]
    stream=direct('s2e_streamaudit156',out,'streamaudit156/audit156.py',
        ['--campaign',BASE+'/s2e-full-soc-power12-20261105-130','--out',out],
        [dict(id='s2e_power130',policy='success'),dict(id='mapped_private147',policy='terminal')],
        'STREAM_AUDITED_24_ORIGINAL_REPORTS_NOT_QUALIFIED','FAIL_DIAGNOSTIC_NOT_QUALIFIED',
        frozen('streamaudit156',runtime+['manifest156.json']))
    for job in (timing,private,stream):save(jobs/(job['id']+'.json'),job)
    out=BASE+'/campaign-summary-20261105-154'
    dependencies=[dict(id=p.stem,policy='terminal') for p in sorted(jobs.glob('*.json'))]
    report=direct('zz_campaign_report154',out,'campaign154.py',['report','--report-out',out],dependencies,
        'COLLECTED_CAMPAIGN_DIAGNOSTICS_NOT_QUALIFIED','FAILED_REPORT_NOT_QUALIFIED',
        [dict(path=DEPLOY+'/campaign154.py',bytes=(HERE/'campaign154.py').stat().st_size,sha256=sha(HERE/'campaign154.py'))],native=False)
    save(jobs/(report['id']+'.json'),report)
    assert len(list(jobs.glob('*.json')))==20
    rows=[dict(path=str(p.relative_to(HERE)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(HERE.rglob('*')) if p.is_file() and '__pycache__' not in p.parts]
    release=dict(schema='xu-campaign-release154-v1',qualification='NOT_QUALIFIED',job_count=20,
        controller_sha256=sha(HERE/'control153/xu_experiments.py'),native_cap=1,
        entry=DEPLOY+'/campaign154.py',existing_controller_out=BASE+'/unified-experiment-control-20261105-150',files=rows)
    save(HERE/'release154.json',release)
    archive=BUILD/'xu-campaign-batch154.tar.xz'
    assert not archive.exists()
    with tarfile.open(str(archive),'x:xz') as tar:
        for row in rows+[dict(path='release154.json')]:
            path=HERE/row['path'];raw=path.read_bytes();member=tarfile.TarInfo(row['path']);member.size=len(raw)
            tar.addfile(member,io.BytesIO(raw))
    save(BUILD/'xu-campaign-release154-identity.json',dict(archive=str(archive),bytes=archive.stat().st_size,
        sha256=sha(archive),manifest_sha256=sha(HERE/'release154.json'),file_count=len(rows),job_count=20))
    print(json.dumps(dict(archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),
                         manifest_sha256=sha(HERE/'release154.json'),file_count=len(rows),job_count=20),sort_keys=True))


if __name__=='__main__':main()
