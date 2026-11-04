"""Offline gate tests for the future server's two complete VCS result comparison."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/scripts'))
import xu_s2e_server_accept as entry
import xu_firmware_contract as contract


class XuS2eServerTests(unittest.TestCase):
    def test_real_runtime_freeze_and_controlled_symlink_mutations(self):
        # This calls the real tracked-file inventory, not a mocked path list.
        frozen=entry.freeze_runtime()
        pm=entry.soc.E203/'riscv-tools/riscv-tests/env/pm/link.ld'
        self.assertEqual(frozen[str(pm)]['git_mode'],'120000')
        self.assertEqual(frozen[str(pm)]['target']['sha256'],entry.identity(pm.resolve())['sha256'])
        self.assertIn(str(entry.soc.E203/'tb/tb_top.v'),frozen)
        self.assertIn(str(entry.soc.E203/'riscv-tools/riscv-tests/isa/generated/rv32ui-p-add.verilog'),frozen)
        self.assertIn(str(entry.soc.E203/'riscv-tools/riscv-tests/isa/generated/rv32ui-p-add'),frozen)
        self.assertIn(str(entry.soc.ROOT/'tools/model/evaluate_kwt_dataset.py'),frozen)
        self.assertIn(str(entry.soc.ROOT/'model/fixed16_acc48.py'),frozen)
        with tempfile.TemporaryDirectory(prefix='xu-freeze-links-') as tmp:
            root=Path(tmp)/'controlled'
            root.mkdir()
            target=root/'target'
            target.write_bytes(b'original')
            link=root/'link'
            link.symlink_to('target')
            before=entry.identity(link,root)
            target.write_bytes(b'changed')
            self.assertNotEqual(before,entry.identity(link,root))
            link.unlink()
            link.symlink_to('./target')
            self.assertNotEqual(before['link_sha256'],entry.identity(link,root)['link_sha256'])
            outside=Path(tmp)/'outside'
            outside.write_bytes(b'outside')
            link.unlink()
            link.symlink_to(outside)
            with self.assertRaises(ValueError): entry.identity(link,root)
            link.unlink()
            link.symlink_to('link')
            with self.assertRaises((RuntimeError,OSError)): entry.identity(link,root)

    def test_untracked_ignored_runtime_input_is_rejected(self):
        # git --others deliberately has no --exclude-standard: ignored HDL is
        # still copied and compiled by the real make install wildcard.
        with mock.patch.object(entry,'command',return_value='rtl/e203/perips/xu-extra.sv\0') as called:
            with self.assertRaisesRegex(ValueError,'untracked E203 runtime input'):
                entry.freeze_runtime()
        self.assertEqual(called.call_args[0][0],
                         ['git','ls-files','--others','-z','--','rtl/','tb/'])

    def test_interruption_and_evidence_io_errors_persist_terminal_failure(self):
        for failure in ['interrupt','raw-identity','postflight-identity','new-runtime-input']:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory(prefix='xu-s2e-failure-') as temporary:
                root=Path(temporary)
                out=root/'output'
                compiler=root/'xu-gcc'
                compiler.write_text('offline tool placeholder')
                source=root/'source'
                source.write_text('unchanged')
                original_identity=entry.identity
                before={str(source):original_identity(source)}
                source_calls=[0]
                def frozen():
                    source_calls[0]+=1
                    if failure=='new-runtime-input' and source_calls[0]>1:
                        raise ValueError('injected added ignored HDL')
                    return copy.deepcopy(before)
                def identity(path,allowed_root=None):
                    path=Path(path)
                    if failure=='raw-identity' and path.name=='raw.log':
                        raise OSError('injected raw read failure')
                    if failure=='postflight-identity' and path==source:
                        raise OSError('injected postflight read failure')
                    return original_identity(path,allowed_root)
                def command(argv,cwd):
                    if argv[:2]==['git','rev-parse']:
                        return entry.E203_COMMIT if Path(cwd)==entry.soc.E203 else '1'*40
                    if argv[:2]==['git','status']: return ''
                    if argv[-1]=='--version': return 'xu gcc 10.2.0\n'
                    if argv[-1]=='-ID': return 'VCS Q-2020.03-SP2-6_Full64\n'
                    self.fail('unexpected command: '+repr(argv))
                def execute(*args,**kwargs):
                    (out/'raw.log').write_bytes(b'original raw bytes\n')
                    if failure=='interrupt': raise KeyboardInterrupt()
                    raise ValueError('offline deliberate stop before any VCS execution')
                argv=['xu_s2e_server_accept.py','--expected-main','1'*40,
                      '--expected-e203',entry.E203_COMMIT,'--vcs','/bin/true',
                      '--cross-prefix',str(root/'xu-'),'--out',str(out)]
                with mock.patch.object(sys,'argv',argv), \
                     mock.patch.object(entry,'command',side_effect=command), \
                     mock.patch.object(entry.soc,'verify_submodule',return_value=entry.E203_COMMIT), \
                     mock.patch.object(entry.shutil,'which',return_value='/bin/true'), \
                     mock.patch.object(entry,'freeze_runtime',side_effect=frozen), \
                     mock.patch.object(entry,'identity',side_effect=identity), \
                     mock.patch.object(entry,'verify_legacy_images',return_value={'status':'PASS','scope':'offline stub; no compilation'}), \
                     mock.patch.object(entry.accept,'execute_steps',side_effect=execute):
                    self.assertEqual(entry.main(),1)
                saved=json.loads((out/'state.json').read_text())
                self.assertEqual(saved['status'],'FAIL')
                self.assertIn('finished_epoch',saved)
                self.assertGreaterEqual(saved['finished_epoch'],saved['started_epoch'])
                self.assertEqual((out/'raw.log').read_bytes(),b'original raw bytes\n')
                if failure=='raw-identity': self.assertIn('raw_identity_errors',saved)
                if failure=='postflight-identity': self.assertIn('integrity_error',saved)
                if failure=='new-runtime-input': self.assertIn('runtime_inventory_error',saved)
                if failure=='interrupt': self.assertIn('KeyboardInterrupt',saved['error'])

    def record(self, paired):
        schedule=contract.PAIRED_HI_SCHEDULE if paired else 'bias-hw-autogroup-window'
        work=contract.task_contract(schedule)
        counters=dict.fromkeys(set(contract.PERFORMANCE_FIELDS)-{'layer','cycles'},0)
        counters.update(w_load=300000,x_load=100000,bias_load=200000,compute_wait=250000,
                        writeback=1000000,other=150000,busy=215424,mmio_reads=60000)
        for key in ['mac_fire','starts','dones','shared_reads','shared_writes','mmio_writes']:
            counters[key]=work[key]
        result=dict(status='PASS',mode='real',tasks=12,simulator='vcs',firmware_schedule=schedule,
                    firmware_opt='-O2',firmware_experiment='both-unroll-no-masks',
                    transaction_contract=work,outputs=304128,write_words=608256,
                    layers=[dict(layer=i,cycles=2000000,performance=dict(counters)) for i in range(12)],
                    result_activity=[dict(layer=i,legacy_words=25344 if paired else 50688,
                                          packed_words=12672 if paired else 0,logical_words=50688)
                                     for i in range(12)])
        for key in ['main_commit','e203_commit','source_sha256','runner_sha256','contract_sha256',
                    'versions','tools','vectors','fixture','simulator_sha256']:
            result[key]={'offline_mock_identity':key}
        return result

    def test_complete_same_physical_comparison_and_negative_controls(self):
        paired,control=self.record(True),self.record(False)
        rows,fields=entry.compare_real12(paired,control)
        self.assertEqual(len(rows),12)
        self.assertEqual(rows[0]['paired_result_reads'],38016)
        self.assertEqual(rows[0]['control_result_reads'],50688)
        mutations=[lambda p:p.update(tasks=11),lambda p:p.update(outputs=25344),
                   lambda p:p.update(simulator='iverilog'),lambda p:p.update(firmware_opt='-O3'),
                   lambda p:p.update(simulator_sha256='different'),
                   lambda p:p['layers'].reverse(),lambda p:p['result_activity'].pop(),
                   lambda p:p['result_activity'][0].update(logical_words=50687),
                   lambda p:p['layers'][0]['performance'].update(shared_writes=50687)]
        for mutate in mutations:
            bad=copy.deepcopy(paired)
            mutate(bad)
            with self.assertRaises(ValueError): entry.compare_real12(bad,control)


if __name__=='__main__': unittest.main()
