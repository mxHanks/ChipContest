"""Actual C/VPI sparse-joint microbenchmarks; no server or energy qualification."""
import copy
import importlib.util
import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
DIR=ROOT/'tools/ppa/xu_joint_activity'
spec=importlib.util.spec_from_file_location('xu_joint_audit',DIR/'xu_sram_joint_audit.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
EVIDENCE=Path(os.environ['XU_JOINT_TEST_EVIDENCE']) if os.environ.get('XU_JOINT_TEST_EVIDENCE') else None


def preserve(name,data):
    if EVIDENCE:
        EVIDENCE.mkdir(parents=True,exist_ok=True)
        (EVIDENCE/name).write_text(data)


def run(command,cwd,name):
    result=subprocess.run(command,cwd=str(cwd),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True,timeout=120)
    preserve(name,json.dumps(dict(command=command,cwd=str(cwd),returncode=result.returncode))+'\n'+result.stdout)
    return result


class TruthTests(unittest.TestCase):
    def test_all_256_known_clock_modes_are_exact_partition(self):
        arcs=json.loads(audit.LEDGER.read_text())['arcs'][13:55]
        self.assertEqual(len(arcs),42)
        for values in itertools.product((0,1),repeat=8):
            state=dict(zip(audit.CONTROL,values))
            actual=[audit.condition(a['when'],state) for a in arcs]
            self.assertEqual(sum(actual),1,state)

    def test_four_state_false_masks_unknown_without_erasing_it(self):
        state={n:2 for n in audit.CONTROL};state['RET1N']=0
        self.assertEqual(audit.condition('!RET1N',state),1)
        self.assertEqual(audit.condition('RET1N & CEN',state),0)
        self.assertEqual(audit.condition('RET1N & !CEN & GWEN & EMA[0]',state),0)
        state['RET1N']=1
        self.assertEqual(audit.condition('RET1N & CEN',state),2)
        self.assertEqual(audit.condition('RET1N & GWEN',state),2)
        state['GWEN']=3
        self.assertEqual(audit.condition('RET1N & GWEN',state),2)


@unittest.skipUnless(shutil.which('cc') and shutil.which('iverilog') and shutil.which('vvp') and Path('/usr/include/iverilog/vpi_user.h').is_file(),'actual C compiler/Icarus/VPI headers required')
class ActualVPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='xu-joint-vpi-');cls.path=Path(cls.temp.name)
        command=['cc','-std=c99','-D_POSIX_C_SOURCE=200809L','-fPIC','-Wall','-Wextra','-Wshadow','-Wstrict-prototypes','-Werror','-O2','-I/usr/include/iverilog','-shared',str(DIR/'xu_sram_joint_vpi.c'),'-o',str(cls.path/'xu_sram_joint_vpi.vpi'),'-L/usr/lib/x86_64-linux-gnu','-lvpi','-lveriuser']
        r=run(command,cls.path,'c-vpi-build.log')
        if r.returncode:raise AssertionError(r.stdout)
        command=['iverilog','-g2012','-s','tb_xu_sram_joint_micro','-o',str(cls.path/'micro.vvp'),str(ROOT/'tests/ppa/tb_xu_sram_joint_micro.sv')]
        r=run(command,cls.path,'micro-build.log')
        if r.returncode:raise AssertionError(r.stdout)
        cls.results={};cls.raw={}
        for mode in range(4):
            prefix=cls.path/('mode-%d'%mode)
            command=['vvp','-M'+str(cls.path),'-mxu_sram_joint_vpi',str(cls.path/'micro.vvp'),'+OUT='+str(prefix),'+MODE='+str(mode)]
            r=run(command,cls.path,'mode-%d-simulation.log'%mode)
            if r.returncode or 'XU_JOINT_REJECT' in r.stdout:raise AssertionError(r.stdout)
            for kind in ('stats','simultaneous'):
                p=Path(str(prefix)+'.'+kind+'.jsonl');preserve('mode-%d.%s.jsonl'%(mode,kind),p.read_text())
            if mode<3:
                cls.results[mode]=audit.audit(str(prefix)+'.stats.jsonl',str(prefix)+'.simultaneous.jsonl')
                cls.raw[mode]=[json.loads(s) for s in Path(str(prefix)+'.stats.jsonl').read_text().splitlines()]
                preserve('mode-%d-audit.json'%mode,json.dumps(cls.results[mode],sort_keys=True,indent=2)+'\n')
        preserve('producer-source-sha256.json',json.dumps([audit.identity(p) for p in (DIR/'xu_sram_joint_vpi.c',DIR/'xu_sram_joint_audit.py',audit.LEDGER,ROOT/'tests/ppa/tb_xu_sram_joint_micro.sv',ROOT/'tests/ppa/tb_xu_sram_joint_scale.sv',ROOT/'tests/host/test_xu_sram_joint_activity.py')],sort_keys=True,indent=2)+'\n')

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_actual_continuous_edges_and_standby_unknown_q_are_preserved(self):
        d=self.results[0];m=d['macros'][0]
        self.assertEqual(d['window']['duration_ticks'],524000000)
        self.assertEqual(m['pin_transitions']['CLK'],[0,258,1,0,258,0,0,0,0,0,0,1,1,0,0,0])
        self.assertEqual(m['pin_dwell']['CLK'],[265000000,257000000,1000000,1000000])
        q=m['arcs'][105]
        self.assertEqual(q['when'],'RET1N & GWEN')
        self.assertGreaterEqual(q['pin_joint_dwell'][1][2],3000000)
        self.assertEqual(q['pin_joint_dwell'][1][2],134000000)
        self.assertEqual(q['conditional_transitions'],[[1,1,1,0,1],[1,1,2,1,1]])
        self.assertEqual(m['arcs'][55]['condition_dwell_false_true_unknown'],[523000000,1000000,0])
        # 3ns initial + 256ns known GWEN=1 modes + 1ns matching + 2ns final.
        self.assertEqual(m['arcs'][56]['condition_dwell_false_true_unknown'],[259000000,262000000,3000000])
        self.assertEqual(len(m['arcs']),121)

    def test_same_timestamp_active_inactive_nba_and_boundary_replay(self):
        side=[json.loads(s) for s in (self.path/'mode-0.simultaneous.jsonl').read_text().splitlines()]
        events=next(r for r in side if r.get('tick')==525000000)['events']
        self.assertEqual([e['port'] for e in events],['CLK','CLK','CLK','D','D','Q','CEN','Q'])
        self.assertEqual([e['new'] for e in events if e['port']=='CLK'],['1','0','1'])
        self.assertEqual([e['new'] for e in events if e['port']=='Q'],['1000100010001000','0100010001000100'])
        self.assertEqual([e['callback_ordinal'] for e in events],list(range(1,9)))
        boundary=next(r for r in side if r.get('tick')==526000000)
        self.assertTrue(boundary['boundary'])
        self.assertEqual(boundary['events'][-1]['port'],'CEN')
        self.assertEqual(side[-1]['callback_ordinal'],3)

    def test_equal_marginals_different_correlations_remain_different(self):
        a,b=(self.results[i]['macros'][0] for i in (1,2))
        self.assertEqual(a['pin_dwell']['CEN'],b['pin_dwell']['CEN'])
        self.assertEqual(a['pin_dwell']['GWEN'],b['pin_dwell']['GWEN'])
        self.assertEqual(a['pin_dwell']['CEN'],[2000000,2000000,0,0])
        self.assertNotEqual(a['control_joint_dwell'],b['control_joint_dwell'])
        self.assertNotEqual(a['arcs'][13]['condition_dwell_false_true_unknown'],b['arcs'][13]['condition_dwell_false_true_unknown'])

    def test_incomplete_capture_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'incomplete capture'):
            audit.audit(self.path/'mode-3.stats.jsonl',self.path/'mode-3.simultaneous.jsonl')

    def test_actual_352_instances_complete_all_joint_and_unknown_q_counters(self):
        binary=self.path/'scale.vvp'
        command=['iverilog','-g2012','-s','tb_xu_sram_joint_scale','-o',str(binary),str(ROOT/'tests/ppa/tb_xu_sram_joint_micro.sv'),str(ROOT/'tests/ppa/tb_xu_sram_joint_scale.sv')]
        result=run(command,self.path,'scale352-build.log');self.assertEqual(result.returncode,0,result.stdout)
        prefix=self.path/'scale352'
        result=run(['vvp','-M'+str(self.path),'-mxu_sram_joint_vpi',str(binary),'+OUT='+str(prefix)],self.path,'scale352-simulation.log')
        self.assertEqual(result.returncode,0,result.stdout);self.assertNotIn('XU_JOINT_REJECT',result.stdout)
        value=audit.audit(str(prefix)+'.stats.jsonl',str(prefix)+'.simultaneous.jsonl')
        self.assertEqual(value['macro_count'],352)
        self.assertEqual(value['window']['duration_ticks'],100000000)
        for macro in value['macros']:
            self.assertEqual(macro['pin_transitions']['CLK'][1],100)
            self.assertEqual(macro['pin_transitions']['CLK'][4],100)
            self.assertEqual(macro['arcs'][105]['pin_joint_dwell'][1][2],100000000)
        summary={k:value[k] for k in ('status','macro_count','arc_count_per_macro','simultaneous_records','inputs')}
        summary['all_macro_clock_rises']=35200;summary['all_macro_clock_falls']=35200
        summary['every_q_bit_when_true_unknown_ticks']=100000000
        preserve('scale352-audit-summary.json',json.dumps(summary,sort_keys=True,indent=2)+'\n')
        for kind in ('stats','simultaneous'):
            preserve('scale352.'+kind+'.jsonl',Path(str(prefix)+'.'+kind+'.jsonl').read_text())

    def test_actual_vpi_rejects_wrong_real_pin_roles_and_wrong_precision(self):
        original=(ROOT/'tests/ppa/tb_xu_sram_joint_micro.sv').read_text()
        cases=[('wrong_pin_role',original.replace('dut.CEN,dut.CLK,dut.D','dut.CLK,dut.CEN,dut.D'),'named actual macro ports'),
            ('wrong_precision',original.replace('`timescale 1ns/1fs','`timescale 1ns/1ps'),'global 1fs precision')]
        for name,text,rejected in cases:
            source=self.path/(name+'.sv');source.write_text(text);binary=self.path/(name+'.vvp')
            result=run(['iverilog','-g2012','-s','tb_xu_sram_joint_micro','-o',str(binary),str(source)],self.path,name+'-build.log')
            self.assertEqual(result.returncode,0,result.stdout)
            result=run(['vvp','-M'+str(self.path),'-mxu_sram_joint_vpi',str(binary),'+OUT='+str(self.path/name),'+MODE=0'],self.path,name+'-simulation.log')
            self.assertIn('XU_JOINT_REJECT',result.stdout)
            self.assertIn(rejected,result.stdout)
            self.assertNotIn('XU_JOINT_COMPLETE',result.stdout)

    def test_resigned_semantic_tampering_is_rejected(self):
        cases=[]
        x=copy.deepcopy(self.raw[0]);x[1]['pin_dwell'][0][0]-=1;cases.append(('raw_dwell',x))
        x=copy.deepcopy(self.raw[0]);x[1]['pin_transitions'][11][1]-=1;cases.append(('raw_edges',x))
        x=copy.deepcopy(self.raw[0]);x[1]['projection_dwell'][0][1]-=1;cases.append(('joint_dwell',x))
        x=copy.deepcopy(self.raw[0]);x[1]['projection_dwell'].append(x[1]['projection_dwell'][0]);cases.append(('duplicate_sparse',x))
        x=copy.deepcopy(self.raw[0]);x[1]['projection_transitions'].pop();cases.append(('missing_joint_edge',x))
        x=copy.deepcopy(self.raw[0]);x[0]['duration_ticks']+=1;cases.append(('duration',x))
        x=copy.deepcopy(self.raw[0]);x[-1]['complete']=False;cases.append(('incomplete_footer',x))
        x=copy.deepcopy(self.raw[0]);x[0]['macro_count']=2;cases.append(('macro_count',x))
        x=copy.deepcopy(self.raw[0]);x[1]['pin_dwell'][0][0]=-1;cases.append(('negative',x))
        for name,records in cases:
            with self.subTest(name=name):
                damaged=self.path/(name+'.jsonl');damaged.write_text(''.join(json.dumps(x)+'\n' for x in records))
                with self.assertRaises(ValueError):audit.audit(damaged,self.path/'mode-0.simultaneous.jsonl')
        side=[json.loads(s) for s in (self.path/'mode-0.simultaneous.jsonl').read_text().splitlines()]
        for mode in ('old','ordinal','count','extra_macro'):
            x=copy.deepcopy(side)
            r=next(r for r in x if r.get('tick')==525000000)
            if mode=='old':r['events'][0]['old']='x'
            elif mode=='ordinal':r['events'][1]['callback_ordinal']=r['events'][0]['callback_ordinal']
            elif mode=='count':x.remove(r)
            else:r['macro']='unexpected'
            p=self.path/('bad-side-'+mode+'.jsonl');p.write_text(''.join(json.dumps(r)+'\n' for r in x))
            with self.assertRaises(ValueError):audit.audit(self.path/'mode-0.stats.jsonl',p)
        preserve('negative-case-summary.json',json.dumps(dict(semantic_rejections=len(cases)+4,cases=[n for n,_ in cases]+['sidecar-old','sidecar-ordinal','sidecar-count','sidecar-extra-macro']))+'\n')


if __name__=='__main__':unittest.main()
