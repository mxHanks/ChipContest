"""Generated area report Tcl against a boundary model, never a DC/PPA result."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('area_test_ppa', ROOT/'tools/scripts/xu_soc_ppa.py')
PPA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PPA)


class S3AcceleratorAreaTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='s3-area-classification-')
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.impl = dict(hardware_profile='s3-y32-bias-sram',
                         accelerator_area_scopes=PPA.hardware_profile('s3-y32-bias-sram')['area'])
        self.peripheral, self.nice = [item['pattern'] for item in self.impl['accelerator_area_scopes']]
        # Independently observed official adapter: SRAM + two inverters;
        # virtual logic_0/1 have missing area and no physical library candidate.
        self.cells = {
            self.peripheral: ('accel_icb_slave', '0', True, True),
            self.nice: ('e203_subsys_nice_core', '0', True, True),
            self.peripheral+'/mem_ext/macro': ('RAMSP1024X16', '9148.524414', False, True),
            self.peripheral+'/mem_ext/U3': ('CLKINV0_12TR40', '0.6384', False, True),
            self.peripheral+'/mem_ext/U4': ('CLKINV0_12TR40', '0.6384', False, True),
            self.peripheral+'/mem_ext/U5': ('**logic_0**', '', False, True),
            self.peripheral+'/mem_ext/U6': ('**logic_1**', '', False, True),
            self.nice+'/router': ('ROUTER_STD', '3.0', False, True),
        }
        self.libraries = ['sram/RAMSP1024X16', 'std/CLKINV0_12TR40', 'std/ROUTER_STD']

    def execute(self, label):
        script = 'set cells [dict create]\nset libraries [list '+ ' '.join(PPA.tcl(x) for x in self.libraries)+']\n'
        for name, (ref, area, hierarchy, mapped) in self.cells.items():
            script += ('dict set cells '+PPA.tcl(name)+' [dict create ref_name '+PPA.tcl(ref)+
                       ' area '+PPA.tcl(area)+' is_hierarchical '+str(hierarchy).lower()+
                       ' is_mapped '+str(mapped).lower()+']\n')
        script += r'''
proc get_cells {args} {
  set filter [lindex $args end]; set result {}
  dict for {name attrs} $::cells {
    regexp {full_name (==|=~) (\S+)} $filter unused operation pattern
    if {$operation eq "==" && $name ne $pattern} {continue}
    if {$operation eq "=~" && ![string match $pattern $name]} {continue}
    if {[regexp {ref_name =~ (\S+)} $filter unused pattern] &&
        ![string match $pattern [dict get $attrs ref_name]]} {continue}
    if {[string first {is_hierarchical == false} $filter]>=0 && [dict get $attrs is_hierarchical]} {continue}
    lappend result $name
  }; return $result
}
proc get_lib_cells {args} {
  set result {}; foreach name $::libraries {
    if {[string match [lindex $args end] $name]} {lappend result $name}
  }; return $result
}
proc get_attribute {object attribute} {return [dict get $::cells $object $attribute]}
proc get_object_name {object} {return $object}
proc sizeof_collection {objects} {return [llength $objects]}
proc foreach_in_collection {variable objects body} {
  foreach object $objects {uplevel 1 [list set $variable $object]; uplevel 1 $body}
}
'''
        script += PPA.guarded_tcl(PPA.accelerator_area_tcl(self.impl), 'HOST_AREA_MODEL_COMPLETE')
        path = self.directory/'area.tcl'; path.write_text(script)
        run = subprocess.run(['tclsh',str(path)],cwd=str(self.directory),stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True)
        evidence = os.environ.get('S3_AREA_TEST_EVIDENCE')
        if evidence:
            out = Path(evidence);out.mkdir(parents=True,exist_ok=True)
            (out/(label+'.tcl')).write_text(script)
            (out/(label+'.log')).write_text(run.stdout)
            for name in ['accelerator-area.tsv','virtual-constant.tsv']:
                if (self.directory/name).is_file():
                    shutil.copyfile(str(self.directory/name),str(out/(label+'-'+name)))
        return run

    def test_native_virtual_constants_are_classified_without_inventing_physical_area(self):
        run = self.execute('native-constant-positive')
        self.assertEqual(run.returncode,0,run.stdout)
        rows = [row.split('\t') for row in (self.directory/'accelerator-area.tsv').read_text().splitlines()]
        self.assertEqual(rows[0],['component','instance','leaf_count','area_library_units'])
        self.assertTrue(all(len(row)==4 for row in rows))
        self.assertEqual(rows[1][:3],['peripheral',self.peripheral,'5'])
        self.assertAlmostEqual(float(rows[1][3]),9149.801214,places=8)
        self.assertEqual(rows[2][:3],['nice_extension',self.nice,'1'])
        self.assertEqual(float(rows[2][3]),3.0)
        self.assertEqual(rows[3][2],'6')
        self.assertAlmostEqual(float(rows[3][3]),9152.801214,places=8)
        classified = [row.split('\t') for row in (self.directory/'virtual-constant.tsv').read_text().splitlines()]
        self.assertEqual(classified[0],['component','instance','reference','classification'])
        self.assertEqual({(row[0],row[1],row[2]) for row in classified[1:]},
                         {('peripheral',self.peripheral+'/mem_ext/U5','**logic_0**'),
                          ('peripheral',self.peripheral+'/mem_ext/U6','**logic_1**')})
        self.assertTrue(all(row[3]=='virtual_constant:is_mapped=true;library_candidates=0'
                            for row in classified[1:]))
        self.assertEqual(PPA.accelerator_area_tcl({}), '')

    def test_only_exact_mapped_native_constants_without_library_candidates_are_excluded(self):
        original = dict(self.cells)
        library = list(self.libraries)
        leaf = self.peripheral+'/mem_ext/U5'
        for label, value, candidates in [
            ('unknown-ref-missing-area', ('UNKNOWN_STD', '', False, True), []),
            ('constant-like-ref-missing-area', ('user_logic_0', '', False, True), []),
            ('unmapped-constant', ('**logic_0**', '', False, False), []),
            ('ambiguous-constant-library', ('**logic_0**', '', False, True),
             ['other0/**logic_0**','other1/**logic_0**']),
        ]:
            with self.subTest(label=label):
                self.cells = dict(original); self.cells[leaf] = value
                self.libraries = library + candidates
                run = self.execute(label)
                self.assertNotEqual(run.returncode,0,run.stdout)
                self.assertIn('XU_FATAL:',run.stdout)
                self.assertNotIn('HOST_AREA_MODEL_COMPLETE',run.stdout)

    def test_physical_missing_nonfinite_negative_and_nonpositive_scope_still_fail(self):
        original = dict(self.cells)
        for label, area in [('physical-missing',''),('physical-nan','NaN'),
                            ('physical-infinity','Inf'),('physical-negative','-0.1'),
                            ('nonpositive-nice-scope','0')]:
            with self.subTest(label=label):
                self.cells = dict(original)
                self.cells[self.nice+'/router'] = ('ROUTER_STD',area,False,True)
                run = self.execute(label)
                self.assertNotEqual(run.returncode,0,run.stdout)
                self.assertIn('XU_FATAL:',run.stdout)
                self.assertNotIn('HOST_AREA_MODEL_COMPLETE',run.stdout)


if __name__=='__main__':
    unittest.main()
