import copy
import json
import hashlib
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import activity145
import observer145
import macro145
import context145
import build_jobs145


class Protocol145(unittest.TestCase):
    def test_final_input_receipt_cannot_omit_or_change_native_compile_chain(self):
        executable=dict(path='/tools/vcs',sha256='a'*64,bytes=13)
        version=dict(path='/out/simulator/vcs-version.log',sha256='b'*64,bytes=29)
        binary=dict(path='/out/simulator/soc',sha256='c'*64,bytes=41)
        config=dict(native_compiler=dict(executable=executable,version_log=version))
        frozen=[executable,version,binary]
        activity145.check_native_freeze(config,binary,frozen)
        for index in range(3):
            with self.assertRaises(ValueError):activity145.check_native_freeze(config,binary,frozen[:index]+frozen[index+1:])
        changed=copy.deepcopy(frozen);changed[0]['sha256']='f'*64
        with self.assertRaises(ValueError):activity145.check_native_freeze(config,binary,changed)
        with self.assertRaises(ValueError):activity145.check_native_freeze(dict(native_compiler=None),binary,frozen)

    def test_external_vectors_must_match_every_original_fixture_tensor(self):
        tensors=('x.mem','w.mem','bias.mem','y.mem')
        manifest=dict(files={'layer_%02d/%s'%(i,name):'%064x'%(1+i*4+j)
                             for i in range(12) for j,name in enumerate(tensors)})
        validated=[dict(layer=i,sha256={name:manifest['files']['layer_%02d/%s'%(i,name)] for name in tensors})
                   for i in range(12)]
        context145.check_fixture_manifest(manifest,validated)
        altered=copy.deepcopy(validated);altered[11]['sha256']['y.mem']='0'*64
        extra=copy.deepcopy(validated);extra[0]['sha256']['other.mem']='0'*64
        duplicate=copy.deepcopy(validated);duplicate[11]=duplicate[10]
        for changed in (altered,extra,duplicate,validated[:11]):
            with self.assertRaises(ValueError):context145.check_fixture_manifest(manifest,changed)

    def test_official_model_identity_rejects_valid_but_different_module(self):
        pinned=context145.vendor_model_records()
        self.assertEqual(set(pinned),{'RAMSP1024X16','RAMSP128X16'})
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'RAMSP1024X16.v'
            original=b'module RAMSP1024X16; endmodule\n'
            path.write_bytes(original)
            frozen=dict(RAMSP1024X16=dict(sha256=hashlib.sha256(original).hexdigest(),bytes=len(original)))
            with patch.object(context145,'vendor_model_records',return_value=frozen):
                self.assertEqual(context145.check_vendor_model('RAMSP1024X16',path)['selected']['bytes'],len(original))
                path.write_bytes(original+b'// different supplied model\n')
                with self.assertRaises(ValueError):context145.check_vendor_model('RAMSP1024X16',path)
            # A syntactically valid local stub never matches the original138 SHA.
            with self.assertRaises(ValueError):context145.check_vendor_model('RAMSP1024X16',path)

    def test_queue_receipts_are_complete_and_hash_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);own=root/'p';own.mkdir()
            selected=dict(path='/frozen/mapped.v',sha256='a'*64)
            chain=[dict(path='/frozen/original.svf',sha256='b'*64)]
            source=dict(main_commit='c'*40,child_commit='d'*40)
            inputs=[dict(path='/frozen/body.v',sha256='e'*64,bytes=7,symlink_target=None)]
            frozen=dict(candidate='p',status='FROZEN_REVIEW_PENDING_NOT_QUALIFIED',before=inputs,after=inputs,
                        errors=[],source=source,selected_mapped=selected,ordered_svf_inputs=chain)
            adopted=dict(status='OWN_FM_ADOPTED_CONDITIONAL_REVIEW_PENDING',selected_mapped=selected,ordered_svf_inputs=chain)
            for name,data in [('freeze.json',frozen),('adopt-own-fm.json',adopted)]:
                (own/name).write_text(json.dumps(data))
            candidate=dict(id='p',source=source)
            planned=dict(freeze_inputs=inputs,selected_mapped=selected,ordered_svf_inputs=chain)
            observed=build_jobs145.receipt_inputs(root,Path('/server/queue'),candidate,planned)
            self.assertEqual({r['path'] for r in observed},{'/frozen/body.v','/server/queue/p/freeze.json','/server/queue/p/adopt-own-fm.json'})
            self.assertEqual(observed[-2]['sha256'],context145.sha(own/'freeze.json'))
            changed=copy.deepcopy(frozen);changed['after']=[]
            (own/'freeze.json').write_text(json.dumps(changed))
            with self.assertRaises(ValueError):build_jobs145.receipt_inputs(root,Path('/server/queue'),candidate,planned)

    def test_eight_recipes_have_exact_protocol_counts(self):
        for profile in activity145.context.SCHEDULES:
            writes=observer145.recipe(profile)
            expected=32928 if profile=='s1_h2_only' else 33639 if profile=='s2d' else 33697
            self.assertEqual(len(writes),expected)
            self.assertEqual(sum(a==0x24 for a,_ in writes),16384)
            self.assertEqual(sum(a==0x48 for a,_ in writes),0 if profile=='s1_h2_only' else 256)
            if profile=='s1_h2_only':self.assertFalse(any(a==0x40 for a,_ in writes))
            if profile=='s2d':
                self.assertEqual(writes[-70:-68],[(0x40,1),(0xd0,1)])
                self.assertEqual(sum(a==0xdc for a,_ in writes),64)
                self.assertFalse(any(a==0x18 for a,_ in writes))
                self.assertEqual(writes[-2:],[(0xd0,0),(0x40,0)])

    def make_physical(self,profile):
        inventory=json.loads((Path(__file__).parent/'inventory137.snapshot.json').read_text())
        groups=next(c for c in inventory['candidates'] if c['id']==profile)['ppa']['memory_groups']
        macros=[];lines=[]
        for group in groups:
            if not group['name'].startswith('accelerator'):continue
            for index in range(group['count']):
                scope='tb_xu_soc_ppa.dut.u_accel_icb_slave.g_'+group['name']+'.m_%d.xu_pin_probe'%index
                ref=group['macro_ref'];widths=macro145.PIN_WIDTHS[ref]
                macros.append(dict(probe_scope=scope,instance=scope.rsplit('.',1)[0],group=group['name'],ref_name=ref,pin_widths=widths))
                depth=32 if group['name']=='accelerator_bias' else 128 if profile=='compact32_128' else 512 if profile=='pe32' else 256 if profile=='pe64' else 1024
                mask=255 if group['name']=='accelerator_bias' and index%3==2 else 65535
                for stage,tick in ((0,10),(1,110)):
                    for address in range(depth):
                        lines.append('XU_MACRO_WRITE145 ref=%s scope=%s tick_fs=%d stage=%d addr=%x data=0000 mask=%04x'%(ref,scope,tick,stage,address,mask))
        xbuffers=[dict(probe_scope='tb_xu_soc_ppa.dut.u_accel_icb_slave.x_%d.xu_x_probe'%i) for i in range(2 if profile=='s2d' else 1)]
        def xevent(scope,tick,stage,address,data):
            for kind,delta in (('WRITE',0),('ECHO',1)):
                lines.append('XU_X_%s145 scope=%s tick_fs=%d stage=%d addr=%d data=%04x'%(kind,scope,tick+delta,stage,address,data))
        for x in xbuffers:
            for a in range(64):xevent(x['probe_scope'],10,0,a,0)
        for i in range(6336):xevent(xbuffers[(i//64)%len(xbuffers)]['probe_scope'],110,1,i%64,i%65536)
        return SimpleNamespace(id=profile),dict(macros=macros,memory_groups=groups,x_buffers=xbuffers),'\n'.join(lines),dict(begin=dict(tick=100),end=dict(tick=200))

    def test_physical_reachable_geometry_for_every_layout(self):
        for profile in activity145.context.SCHEDULES:
            ctx,inventory,log,window=self.make_physical(profile)
            receipt=activity145.physical_check(ctx,log,inventory,window)
            self.assertEqual(receipt['macro_groups']['accelerator_weights']['logical_reachable_bits'],262144)
            self.assertEqual(receipt['x_clear_words'],128 if profile=='s2d' else 64)

    def test_missing_duplicate_nonzero_and_late_physical_clear_rejected(self):
        ctx,inventory,log,window=self.make_physical('pe32')
        lines=log.splitlines()
        cases=['\n'.join(lines[1:]),log+'\n'+lines[0],log.replace('data=0000 mask=ffff','data=0001 mask=ffff',1),
               log.replace('tick_fs=10 stage=0','tick_fs=100 stage=0',1),log.replace('XU_X_ECHO145','DROP_X_ECHO145',1)]
        for case in cases:
            with self.assertRaises(ValueError):activity145.physical_check(ctx,case,inventory,window)

    def test_db_actual_bank_swap_is_rejected(self):
        ctx,inventory,log,window=self.make_physical('s2d')
        # Swap payload bank names without touching clear coverage or echo pairing.
        log='\n'.join(line.replace('.x_0.','.wrong.') if 'stage=1' in line and 'XU_X_' in line else line for line in log.splitlines())
        with self.assertRaises(ValueError):activity145.physical_check(ctx,log,inventory,window)


if __name__=='__main__':unittest.main()
