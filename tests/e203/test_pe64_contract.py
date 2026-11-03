"""Independent 64PE physical variant, legacy 8/32 schedules, and real MAC work."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/scripts'))
import e203_soc as soc
import xu_firmware_contract as contract
import xu_perf_report as perf
import server_accept as accept

class XuPe64ContractTests(unittest.TestCase):
    schedule='bias-hw-pe64-autogroup-window'
    def test_64_work_contract_and_legacy_widths(self):
        wide=contract.task_contract(self.schedule)
        self.assertEqual((wide['starts'],wide['dones'],wide['mac_fire'],wide['mmio_writes']),
                         (396,396,25344,12725))
        self.assertEqual(wide['macs'],1622016)
        self.assertEqual((wide['shared_reads'],wide['shared_writes']),(23232,50688))
        for schedule,pes,beats,starts,writes in [(self.schedule,64,25344,396,12725),
                ('bias-hw-pe32-autogroup-window',32,50688,792,13121),
                ('bias-hw-autogroup-window',8,202752,3168,15497)]:
            self.assertEqual(contract.physical_pes('pe64',schedule),64)
            c=contract.task_contract(schedule)
            self.assertEqual((c['mac_fire'],c['starts'],c['mmio_writes']),(beats,starts,writes))
            row='PE_TASK layer=0 physical_pes=64 mac_beats='+str(beats)+' lane_macs=1622016 useful_macs=1622016\n'
            self.assertEqual(soc.check_pe_activity(row,[dict(layer=0,cycles=1000000)],schedule,'pe64')[0]['lane_macs'],1622016)
            for wrong in [row.replace('physical_pes=64','physical_pes=32'),
                          row.replace('lane_macs=1622016','lane_macs=6488064'),row+row,'']:
                with self.assertRaises(ValueError):soc.check_pe_activity(wrong,[dict(layer=0,cycles=1000000)],schedule,'pe64')
        flags=contract.compiler_defines(contract.configuration(self.schedule,'-O2','both-unroll-no-masks'))
        for name in ['PE64','PACK32','AUTO_GROUP','BIAS_CACHE','RESULT_WINDOW']:
            self.assertIn('-DXU_HARDWARE_'+name+'=1',flags)
        self.assertFalse(any('PE64' in f for f in contract.compiler_defines(contract.configuration())))
        for variant in ['pe8','pe32','bogus']:
            with self.assertRaises(ValueError):contract.physical_pes(variant,self.schedule)
    def test_server_every_step_same_variant_and_required_direct_vcs(self):
        steps=accept.acceptance_steps(Path('/tmp/xu-pe64-new'),'rv-','vcs',firmware_schedule=self.schedule,accel_variant='pe64')
        for name,command,_ in steps:
            if name=='host':self.assertIn('XU_PE64_WRAPPER_SIM=vcs',command)
            elif name!='numeric':self.assertEqual(command[command.index('--accel-variant')+1],'pe64')
        self.assertIn('+define+XU_ACCEL_PE64=1',soc.vcs_build_command(Path('/tmp/xu'),Path('/tmp/rtl.f'),[],False,'pe64'))
        self.assertNotIn('+define+XU_ACCEL_PE32=1',soc.vcs_build_command(Path('/tmp/xu'),Path('/tmp/rtl.f'),[],False,'pe64'))
    def test_report_requires_same_physical_geometry_and_useful_work(self):
        counters=dict.fromkeys(set(contract.PERFORMANCE_FIELDS)-{'layer','cycles'},0)
        counters.update(w_load=1000000,busy=26928,mmio_reads=50688,
                        **{k:v for k,v in contract.task_contract(self.schedule).items()if k in counters})
        source=dict(status='PASS',mode='real',tasks=1,outputs=25344,write_words=50688,
                    firmware_schedule=self.schedule,accel_variant='pe64',
                    layers=[dict(layer=0,cycles=1000000,firmware_cycles=1000071,performance=counters)],
                    pe_activity=[dict(layer=0,physical_pes=64,mac_beats=25344,lane_macs=1622016,useful_macs=1622016)])
        summary=perf.summarize(source,150)
        self.assertEqual((summary['pes'],summary['conditional_peak_gmac_per_second']),(64,9.6))
        self.assertEqual(summary['source_identity']['accel_variant'],'pe64')
        for change in [lambda x:x.pop('pe_activity'),lambda x:x.update(accel_variant='pe32'),
                       lambda x:x['pe_activity'][0].update(lane_macs=6488064)]:
            bad=copy.deepcopy(source);change(bad)
            with self.assertRaises(ValueError):perf.summarize(bad,150)
    def test_original_generated_and_chisel_files_remain_frozen(self):
        import subprocess
        root=Path(__file__).resolve().parents[2]
        for relative in ['src/main/scala/linear/XuParallelCore.scala']:
            expected=subprocess.check_output(['git','show','94ce6f0:'+relative],cwd=root)
            self.assertEqual((root/relative).read_bytes(),expected)
        child=root/'third-party/e203_hbirdv2'
        tracked=subprocess.check_output(['git','ls-tree','-r','--name-only','fc3977d','rtl/e203/perips'],cwd=child,universal_newlines=True).splitlines()
        frozen=[p for p in tracked if p.endswith('.sv')or p.endswith('/xu_pe32_icb_slave.v')or p.endswith('/accel_icb_slave.v')]
        for relative in frozen:
            expected=subprocess.check_output(['git','show','fc3977d:'+relative],cwd=child)
            self.assertEqual((child/relative).read_bytes(),expected,relative)

if __name__=='__main__':unittest.main()
