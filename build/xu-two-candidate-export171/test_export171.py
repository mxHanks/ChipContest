#!/usr/bin/env python3
"""Local byte/path/live-snapshot mechanism checks; never runs remote/EDA."""
import ast
import hashlib
import io
import json
from pathlib import Path
import os
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import exporter171 as e
import check_unpack171 as c


def digest(raw):return hashlib.sha256(raw).hexdigest()


class Test171(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='xu171-host-');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.d=self.root/'Desktop';self.b=self.d/'xu-score-optimization-20261102';self.b.mkdir(parents=True)
        self.out=self.b/'evidence171.tar.xz'
        self.put(e.CONTROL+'/state.json',json.dumps(dict(controller_pid=os.getpid(),jobs={})).encode())
        self.put(e.UNKNOWN+'/state.json',b'{"status":"FAIL_OBSERVATION167_NOT_QUALIFIED"}\n')
        self.put(e.UNKNOWN+'/simulation.log',b'original Fatal: retained\n')
        self.put(e.POWER0+'/task_00/power.rpt',b'native small report\n')
        self.put(e.POWER0+'/task_00/sram-pins-before.rpt',b'pin original is never copied\n')
        self.put(e.POWER0+'/inventory/model.db',b'PRIVATE_LIBRARY_NEVER_COPY')

    def put(self,name,raw):
        p=self.b/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);return p

    def export(self):return e.export(self.b,self.d,self.out,16*1024*1024)

    def package(self,payload,entries=None,manifest_override=None):
        path=self.root/'crafted.tar.xz'
        rows=[dict(path=n,bytes=len(raw),sha256=digest(raw))for n,raw in payload]
        manifest=dict(schema='xu-two-candidate-export171-v1',qualification='NOT_QUALIFIED',files=rows,payload_files=len(rows),payload_bytes=sum(len(v)for _,v in payload))
        with tarfile.open(str(path),'w:xz')as t:
            for n,raw in payload:
                info=tarfile.TarInfo(n);info.size=len(raw);t.addfile(info,io.BytesIO(raw))
            for info,raw in entries or []:t.addfile(info,io.BytesIO(raw)if raw is not None else None)
            raw=(json.dumps(manifest).encode()if manifest_override is None else manifest_override)
            info=tarfile.TarInfo('manifest.json');info.size=len(raw);t.addfile(info,io.BytesIO(raw))
        return path

    def test_roundtrip_all_bytes_and_outer_sha(self):
        result=self.export();report,rows=c.inspect(self.out,result['sha256'])
        self.assertEqual(report['payload_files'],len(rows));self.assertTrue(report['expected_archive_sha256_verified'])
        target=self.root/'safe-extract';c.unpack(self.out,target,result['sha256'])
        self.assertEqual((target/e.UNKNOWN/'simulation.log').read_bytes(),b'original Fatal: retained\n')
        self.assertIn('FAIL_OBSERVATION167_NOT_QUALIFIED',(target/e.UNKNOWN/'state.json').read_text())
        snapshot=json.loads((target/'snapshot171.json').read_text())
        self.assertTrue(snapshot['all_copies_are_observations_not_terminal_freezes'])
        self.assertEqual(snapshot['live_process_observations'][0]['actual']['pid'],os.getpid())

    def test_pin_original_hash_only_and_library_not_selected(self):
        self.export();target=self.root/'read';c.unpack(self.out,target)
        snapshot=json.loads((target/'snapshot171.json').read_text());omitted=snapshot['omitted_originals']
        pin=e.POWER0+'/task_00/sram-pins-before.rpt';self.assertFalse((target/pin).exists())
        row=next(r for r in omitted if r['archive_path']==pin)
        self.assertEqual(row['observed_bytes_sha256'],digest((self.b/pin).read_bytes()))
        self.assertEqual(row['omission_reason'],'PIN_ORIGINAL_NEVER_PACKAGED')
        self.assertFalse((target/e.POWER0/'inventory/model.db').exists())

    def test_all_requested_groups_and_twelve_audit_summaries_selected(self):
        names=[e.CONTROL+'/events.jsonl',e.CONTROL+'/registrations/s2c_unknown167.json',
            e.CONTROL+'/runs/s2c_unknown167/worker.log','s2e-streamaudit164-registration-20261105-168.json',
            'two-candidate-registration-20261105-170.json',e.AUDIT+'/state.json',
            e.UNKNOWN+'/tb_private147.sv',e.UNKNOWN+'/xu_private147.c',e.UNKNOWN+'/vpi-build.log',
            e.UNKNOWN+'/vcs-build.log']
        names +=[e.AUDIT+'/task_%02d/summary.json'%i for i in range(12)]
        names +=[folder+'/'+n for folder in [e.POWER0,e.POWER12]for n in ['result.json','prepared.json','execution.json','summary.json','inventory/pt.log']]
        for name in names:self.put(name,b'original bytes retained\n')
        self.export();_,rows=c.inspect(self.out);self.assertTrue(set(names)<=set(rows))

    def test_above_limit_is_stream_hashed_without_copy(self):
        stage=self.root/'stage';stage.mkdir();p=self.put('large.log',b'large original')
        s=e.Snapshot(stage,self.b,self.d,2);s.add(p,'large.log')
        self.assertFalse((stage/'large.log').exists());self.assertEqual(s.omitted[0]['observed_bytes_sha256'],digest(b'large original'))

    def test_live_growth_copies_bounded_prefix_and_flags_change(self):
        p=self.put('mutable.log',b'original');stage=self.root/'stage';stage.mkdir();s=e.Snapshot(stage,self.b,self.d,1000)
        original_read=os.read;done=[]
        def growing(fd,n):
            if not done:
                done.append(True)
                with p.open('ab')as f:f.write(b' appended while reading')
            return original_read(fd,n)
        with patch.object(e.os,'read',side_effect=growing):s.add(p,'mutable.log')
        self.assertEqual((stage/'mutable.log').read_bytes(),b'original')
        self.assertFalse(s.captures[0]['metadata_unchanged_during_read'])
        self.assertIn('NOT_FROZEN',s.captures[0]['evidence_semantics'])

    def test_source_symlink_rejected_without_following(self):
        p=self.b/e.UNKNOWN/'simulation.log';p.unlink();secret=self.root/'secret';secret.write_text('NEVER_EXPORTED');p.symlink_to(secret)
        self.export();target=self.root/'read';c.unpack(self.out,target)
        s=json.loads((target/'snapshot171.json').read_text())
        self.assertTrue(s['rejected_sources']);self.assertFalse((target/e.UNKNOWN/'simulation.log').exists())

    def test_source_directory_symlink_rejected(self):
        source=self.b/e.CONTROL/'registrations';source.symlink_to(self.root,target_is_directory=True)
        self.export();target=self.root/'read';c.unpack(self.out,target)
        self.assertTrue(json.loads((target/'snapshot171.json').read_text())['rejected_sources'])

    def test_source_special_file_rejected_without_open_block(self):
        p=self.b/e.UNKNOWN/'simulation.log';p.unlink();os.mkfifo(str(p))
        self.export();target=self.root/'read';c.unpack(self.out,target)
        self.assertTrue(json.loads((target/'snapshot171.json').read_text())['rejected_sources'])

    def test_export_never_overwrites_archive(self):
        self.export();before=self.out.read_bytes()
        with self.assertRaises(ValueError):self.export()
        self.assertEqual(before,self.out.read_bytes())

    def test_extraction_never_overwrites_directory(self):
        self.export();target=self.root/'out';target.mkdir();(target/'keep').write_text('keep')
        with self.assertRaises(ValueError):c.unpack(self.out,target)
        self.assertEqual((target/'keep').read_text(),'keep')

    def test_wrong_outer_hash_rejected(self):
        self.export()
        with self.assertRaises(ValueError):c.inspect(self.out,'0'*64)

    def test_archive_symlink_rejected(self):
        self.export();link=self.root/'link.tar.xz';link.symlink_to(self.out)
        with self.assertRaises(ValueError):c.inspect(link)

    def test_traversal_absolute_and_noncanonical_paths_rejected(self):
        for name in ['../escape','/tmp/escape','x/../escape','x//file','./file','x\\file','private-manuals/doc']:
            with self.subTest(name=name):
                p=self.package([('snapshot171.json',b'{}'),(name,b'bad')])
                with self.assertRaises(ValueError):c.inspect(p)

    def test_links_and_directories_rejected(self):
        for kind in [tarfile.SYMTYPE,tarfile.LNKTYPE,tarfile.DIRTYPE]:
            info=tarfile.TarInfo('unsafe');info.type=kind;info.linkname='../outside'
            with self.subTest(kind=kind),self.assertRaises(ValueError):c.inspect(self.package([('snapshot171.json',b'{}')],[(info,None)]))

    def test_duplicate_member_rejected(self):
        with self.assertRaises(ValueError):c.inspect(self.package([('snapshot171.json',b'{}'),('snapshot171.json',b'{}')]))

    def test_unlisted_member_rejected(self):
        info=tarfile.TarInfo('unlisted.log');info.size=3
        with self.assertRaises(ValueError):c.inspect(self.package([('snapshot171.json',b'{}')],[(info,b'bad')]))

    def test_wrong_payload_hash_rejected(self):
        raw=json.dumps(dict(schema='xu-two-candidate-export171-v1',qualification='NOT_QUALIFIED',payload_files=1,payload_bytes=2,
            files=[dict(path='snapshot171.json',bytes=2,sha256='0'*64)])).encode()
        with self.assertRaises(ValueError):c.inspect(self.package([('snapshot171.json',b'{}')],manifest_override=raw))

    def test_duplicate_json_key_rejected(self):
        with self.assertRaises(ValueError):c.inspect(self.package([('snapshot171.json',b'{}')],manifest_override=b'{"schema":1,"schema":2}'))

    def test_file_parent_collision_rejected(self):
        with self.assertRaises(ValueError):c.inspect(self.package([('snapshot171.json',b'{}'),('a',b'a'),('a/b',b'b')]))

    def test_reserved_checker_outputs_rejected(self):
        for name in ['checked171.json','EXTRACTION_FAILED171.json/subfile']:
            with self.subTest(name=name),self.assertRaises(ValueError):c.inspect(self.package([('snapshot171.json',b'{}'),(name,b'bad')]))

    def test_missing_manifest_or_snapshot_rejected(self):
        with self.assertRaises(ValueError):c.inspect(self.package([('other.log',b'x')]))

    def test_python36_source(self):
        for name in ['exporter171.py','check_unpack171.py']:
            ast.parse((Path(__file__).parent/name).read_text(),feature_version=6)


if __name__=='__main__':unittest.main(verbosity=2)
