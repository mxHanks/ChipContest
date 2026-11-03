"""Synthetic host parser tests; these never represent successful PT evidence."""
from decimal import Decimal
import copy
import json
from unittest.mock import patch
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('xu_compact_proto', Path(__file__).resolve().parents[2] / 'tools/ppa/xu_soc_pin_activity_audit.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class CompactPrototypeTests(unittest.TestCase):
    name = 'hier/generated.depth_bank[0].macro/A[0]'

    def text(self, phase='before', name=None):
        name = name or self.name
        return ('\t'.join(m.HEADER) + '\n' +
                '\t'.join((phase, name, name, '.25', 'file', '0', 'file', '.5', 'file')) + '\n')

    def parse(self, text, phase='before'):
        with tempfile.TemporaryDirectory() as temporary:
            p = Path(temporary) / 'pins.tsv'
            p.write_bytes(text.encode())
            return m.parse_compact(p, phase, {self.name})

    def pin(self, **extra):
        pin = dict(mapped_path=self.name, path='tb/dut/' + self.name, kind='PORT',
                   T0=50, T1=50, TX=0, TC=25, IG=0)
        pin.update(extra)
        return pin

    def test_literal_names_and_nine_fields_are_exact(self):
        rows = self.parse(self.text())
        self.assertEqual(set(rows), {self.name})
        self.assertEqual(rows[self.name]['toggle_rate_value'], Decimal('.25'))
        self.assertEqual(m.source_counts(rows)['toggle_rate'], {'file': 1})

    def test_bad_header_phase_names_and_rows_rejected(self):
        good = self.text()
        mutations = [good.replace('desired_name', 'name'), good.replace('before', 'after'),
            good.replace(self.name, self.name.replace('.', '/')), good.replace('\n', '\r\n'),
            good.rstrip('\n'), good + '\n', good + good.split('\n', 1)[1],
            good.replace('\t.25\tfile', '\t.25\tfile\textra')]
        for text in mutations:
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.parse(text)
        rows = good.splitlines(); fields = rows[1].split('\t'); fields[2] += 'wrong'
        with self.assertRaisesRegex(ValueError, 'desired/reported'):
            self.parse(rows[0] + '\n' + '\t'.join(fields) + '\n')

    def test_invalid_values_sources_and_sentinels(self):
        for value in ('NaN', 'Infinity', '-.1', '-2', ' 0', '1e999999999999999999999999'):
            with self.subTest(value=value), self.assertRaises((ValueError, ArithmeticError)):
                self.parse(self.text().replace('.25', value))
        with self.assertRaisesRegex(ValueError, 'unsupported query source'):
            self.parse(self.text().replace('\tfile', '\tinvented_source', 1))
        with self.assertRaisesRegex(ValueError, 'probability exceeds'):
            self.parse(self.text().replace('.5\tfile', '1.1\tfile'))
        row = self.parse(self.text().replace('.25\tfile', '-1\tUNINITIALIZED'))[self.name]
        result = m.observed_comparison(self.pin(), row, 100, '1e-9', '1e-9')
        self.assertEqual(result['observations']['toggle_rate']['comparison'], 'QUERY_UNINITIALIZED_REVIEW_REQUIRED')

    def test_known_formulas_use_actual_unit_and_no_automatic_tolerance(self):
        row = self.parse(self.text())[self.name]
        result = m.observed_comparison(self.pin(), row, 100, '1e-9', '1e-9')
        self.assertEqual(result['observations']['toggle_rate']['comparison'], 'DECIMAL_EXACT_EQUAL')
        result = m.observed_comparison(self.pin(), row, 100, '1e-9', '1e-12')
        self.assertNotEqual(result['observations']['toggle_rate']['delta'], '0.00')
        result = m.observed_comparison(self.pin(TC=26), row, 100, '1e-9', '1e-9')
        self.assertEqual(Decimal(result['observations']['toggle_rate']['delta_count_equivalent']), -1)
        self.assertIn('REVIEW_REQUIRED', result['observations']['toggle_rate']['comparison'])

    def test_unknown_and_glitch_do_not_receive_known_only_formula(self):
        row = self.parse(self.text())[self.name]
        for extra in (dict(TX=1), dict(TZ=1), dict(TB=1), dict(IG=1)):
            pin = self.pin(T0=50-sum(extra.get(k, 0) for k in ('TX','TZ','TB')), **extra)
            checked = m.checked_measurements(dict(pins=[pin]), {self.name}, 100)
            result = m.observed_comparison(checked[self.name], row, 100, '1e-9', '1e-9')
            self.assertIn('REVIEW_REQUIRED', result['classification'])
            self.assertEqual(result['raw_measurement'], pin)
            self.assertNotIn('expected', result['observations']['toggle_rate'])

    def test_measurement_statistics_and_completeness(self):
        for pin in (self.pin(T0=49), self.pin(TC=-1), self.pin(TX=True), self.pin(new_stat=0)):
            with self.subTest(pin=pin), self.assertRaises(ValueError):
                m.checked_measurements(dict(pins=[pin]), {self.name}, 100)
        with self.assertRaises(ValueError):
            m.checked_measurements(dict(pins=[self.pin(), self.pin()]), {self.name}, 100)
        with self.assertRaises(ValueError):
            m.checked_measurements(dict(pins=[]), {self.name}, 100)

    def test_same_values_with_default_source_still_need_review(self):
        before = self.parse(self.text())
        after = self.parse(self.text('after').replace('\tfile', '\tdefault'), 'after')
        self.assertEqual(len(m.phase_changes(before, after)), 1)
        result = m.observed_comparison(self.pin(), after[self.name], 100, '1e-9', '1e-9')
        self.assertEqual(result['observations']['toggle_rate']['comparison'], 'DECIMAL_EXACT_EQUAL')
        self.assertIn('REVIEW_REQUIRED', result['observations']['toggle_rate']['source_review'])

    def test_expected_input_identity_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'input'
            path.write_bytes(b'actual bytes\n')
            expected = dict(bytes=13, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(m.checked_identity(path, expected)['bytes'], 13)
            path.write_bytes(b'changed bytes')
            with self.assertRaises(ValueError):
                m.checked_identity(path, expected)
            link = path.with_name('link'); link.symlink_to(path)
            with self.assertRaises(ValueError):
                m.checked_identity(link, expected)





class EvidenceFixture:
    """A tiny *synthetic* exact one-macro receipt; never real EDA evidence."""
    def __init__(self, directory):
        self.directory = Path(directory)
        self.origin = '/synthetic/xu/pins/'
        self.macro = 'hier/literal.depth_bank[0].macro'
        self.pins = {self.macro + '/' + name for name in m.PIN_NAMES}
        fake = lambda name: dict(path='/synthetic/' + name, bytes=1, sha256=hashlib.sha256(name.encode()).hexdigest())
        self.netlist, self.sdc, self.library = (fake(name) for name in ('mapped.v', 'analysis.sdc', 'library.db'))
        self.saif, self.tool, self.original_log = (fake(name) for name in ('task-mapped.saif', 'pt_shell', 'original-pt.log'))
        self.canonical_saif = fake('canonical.saif')
        self.inventory = dict(schema='xu-mapped-sram-pin-inventory-v1', status='EXPORTED_REVIEW_PENDING',
            netlist=self.netlist, libraries=[self.library], provenance={'synthetic': True}, macro_count=1, pin_bit_count=67,
            macros=[dict(instance=self.macro, ref_name='RAMSP1024X16', lib_cell='synthetic/RAMSP1024X16',
                         pins=[dict(name=name, full_name=self.macro+'/'+name, direction='out' if name.startswith('Q[') else 'in')
                               for name in sorted(m.PIN_NAMES)])])
        self.measured = dict(pins=[dict(mapped_path=name, path='tb/dut/'+name, kind='PORT', T0=50,T1=50,TX=0,TC=25,IG=0)
                                  for name in sorted(self.pins)])
        self.tsv = {phase:'\t'.join(m.HEADER)+'\n'+''.join('\t'.join((phase,name,name,'.25','file','0','file','.5','file'))+'\n'
                    for name in sorted(self.pins)) for phase in ('before','after')}
        self.log = 'T-2022.03-SP5-1\n'+'\n'.join(m.MARKERS)+'\n'
        self.tcl = ('set_app_var link_path [list * {'+self.library['path']+'}]\n' +
                    'read_verilog {'+self.netlist['path']+'}\nsource {'+self.sdc['path']+'}\n' +
                    'if {![read_saif {'+self.saif['path']+'} -strip_path {tb/dut} -report_inconsistent_annotation inconsistent.rpt]} {error {SAIF annotation command failed}}\n' +
                    'get_switching_activity -toggle_rate -glitch_rate -static_probability\n'+
                    '\n'.join('puts {'+marker+'}' for marker in m.MARKERS)+'\n')
        self.units = 'Time_unit : 1e-09 Second\n'
        self.probe_status = m.COMPACT_STATUS
        self.original_status = 'PARTIAL_EXECUTED_REVIEW_PENDING'
        self.freeze = {record['path']:record['sha256'] for record in (self.library, self.netlist, self.sdc, self.canonical_saif)}
        self.files = {}

    def write(self, role, name, raw):
        raw = raw if isinstance(raw, bytes) else raw.encode()
        path=self.directory/name
        path.write_bytes(raw)
        self.files[role]=dict(local_path=str(path),origin_path=self.origin+name,**m.identity(raw))
        return dict(path=self.origin+name,**m.identity(raw))

    def dump(self, role, name, data):
        return self.write(role,name,json.dumps(data,sort_keys=True).encode()+b'\n')

    def build(self, mutate_prepared=None, mutate_execution=None, mutate_probe=None):
        self.files={}
        inventory=self.dump('inventory','inventory.json',self.inventory)
        measured=self.dump('measured','measured.json',self.measured)
        task=dict(task_id=0, directory='task_00', saif=self.saif, canonical_saif=self.canonical_saif, macro_names=[self.macro], measured_sram_pin_states=measured,
             activity_window=dict(begin=dict(tick=100),end=dict(tick=200),duration_ticks=100,timescale_seconds=1e-9),
             mapped_macro_bridge_receipt=dict(duration_ticks=100,timescale_seconds='1e-9',output_saif=self.saif,input_saif=self.canonical_saif))
        prepared=dict(schema='xu-soc-saif-power-prepared-v2',status='PARTIAL_PREPARED_REVIEW_PENDING',
             tasks=[task],mapped_sram_inventory=inventory,netlist=self.netlist,analysis_sdc=self.sdc,
             implementation=dict(libraries=[self.library]),strip_path='tb/dut')
        if mutate_prepared: mutate_prepared(prepared)
        prepared_id=self.dump('prepared','prepared.json',prepared)
        execution=dict(schema='xu-soc-saif-power-execution-v1',status=self.original_status, qualification='NOT_QUALIFIED',
             prepared=prepared_id, prepared_sha256_after=prepared_id['sha256'],
             tool=self.tool, tool_sha256_after=self.tool['sha256'], artifacts={'task_00/pt.log':self.original_log,'task_00/task-mapped.saif':self.saif,'task_00/measured-sram-pins.json':measured},
             tasks=[dict(task_id=0,execution=dict(returncode=0,log=self.original_log))],
             input_sha256_before=self.freeze,input_sha256_after=self.freeze)
        if mutate_execution: mutate_execution(execution)
        execution_id=self.dump('execution','execution.json',execution)
        artifacts={}
        for role,name in m.ARTIFACTS.items():
            raw={'probe_tcl':self.tcl,'pt_log':self.log,'tool_version':'T-2022.03-SP5-1\n','units':self.units,
                 'before':self.tsv['before'],'after':self.tsv['after']}[role]
            artifacts[name]=self.write(role,name,raw)
        probe=dict(status=self.probe_status,execution=dict(returncode=0,command=['pt_shell','-f','probe.tcl'],log=artifacts['pt.log']),
             artifacts=artifacts,original_prepared=prepared_id,original_execution=execution_id,
             netlist=self.netlist,analysis_sdc=self.sdc)
        if mutate_probe: mutate_probe(probe)
        self.dump('probe_result','probe-result.json',probe)
        request=dict(schema=m.REQUEST_SCHEMA,task_id=0,expected_macro_count=1,expected_pin_bit_count=67,
                     numeric_policy=m.NUMERIC_POLICY,files=self.files)
        self.request=self.directory/'request.json';self.request.write_text(json.dumps(request,sort_keys=True)+'\n')
        return self.request

    def output(self, name='review'):
        return self.directory/name


class CompactEvidenceTests(unittest.TestCase):
    def test_complete_synthetic_evidence_is_only_partial_review_not_qualification(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture=EvidenceFixture(temporary);request=fixture.build()
            result=m.audit_request(request,fixture.output())
            self.assertEqual(result['status'],'PARTIAL_KNOWN_UNRESOLVED_REVIEW_PENDING')
            self.assertEqual(result['qualification'],'NOT_QUALIFIED')
            self.assertEqual(result['scope'],dict(macro_count=1,pin_bit_count=67,input_pin_count=51,output_pin_count=16))
            self.assertEqual(result['phases']['before']['counts']['KNOWN_NO_GLITCH'],67)
            self.assertEqual(result['phase_change_count'],0)
            self.assertEqual((fixture.output()/'request.json').read_bytes(),request.read_bytes())
            self.assertEqual(len((fixture.output()/'pin-observations.jsonl').read_text().splitlines()),67)
            with self.assertRaisesRegex(ValueError,'new directory'):
                m.audit_request(request,fixture.output())

    def test_rebound_source_and_value_tampering_remain_explicit_findings(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture=EvidenceFixture(temporary)
            fixture.tsv['after']=fixture.tsv['after'].replace('.25\tfile','0\tdefault',1)
            result=m.audit_request(fixture.build(),fixture.output())
            self.assertEqual(result['phase_change_count'],1)
            counts=result['phases']['after']['counts']
            self.assertEqual(counts['REASON:toggle_rate:SOURCE_default'],1)
            self.assertEqual(counts['REASON:toggle_rate:KNOWN_BOUNDARY_DIFFERS'],1)
            self.assertEqual(result['qualification'],'NOT_QUALIFIED')

    def test_hash_byte_and_path_freeze_fail_closed(self):
        for mutation in ('byte','hash','symlink','parent_symlink','duplicate_json_key','missing_role'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                fixture=EvidenceFixture(temporary);request=fixture.build();data=json.loads(request.read_text())
                path=Path(data['files']['before']['local_path'])
                if mutation=='byte':path.write_bytes(path.read_bytes()+b'\n')
                elif mutation=='hash':data['files']['before']['sha256']='0'*64
                elif mutation=='symlink':
                    link=path.with_name('link.tsv');link.symlink_to(path);data['files']['before']['local_path']=str(link)
                elif mutation=='parent_symlink':
                    sub=path.parent/'symlink-dir';sub.symlink_to(path.parent,target_is_directory=True)
                    data['files']['before']['local_path']=str(sub/path.name)
                elif mutation=='missing_role':del data['files']['before']
                if mutation=='duplicate_json_key':request.write_text(request.read_text().replace('"task_id": 0','"task_id": 0, "task_id": 1'))
                else:request.write_text(json.dumps(data))
                with self.assertRaises(ValueError):m.audit_request(request,fixture.output())
                self.assertFalse((fixture.output()/'result.json').exists())

    def test_terminal_probe_and_original_receipt_required(self):
        for kind in ('probe_running','original_running','pt_exit','original_exit','missing_marker','duplicate_marker','error_log'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                fixture=EvidenceFixture(temporary);kwargs={}
                if kind=='probe_running':fixture.probe_status='RUNNING_REVIEW_PENDING_NOT_QUALIFIED'
                elif kind=='original_running':fixture.original_status='RUNNING_REVIEW_PENDING'
                elif kind=='pt_exit':kwargs['mutate_probe']=lambda d:d['execution'].update(returncode=1)
                elif kind=='original_exit':kwargs['mutate_execution']=lambda d:d['tasks'][0]['execution'].update(returncode=1)
                elif kind=='missing_marker':fixture.log=fixture.log.replace(m.MARKERS[0]+'\n','')
                elif kind=='duplicate_marker':fixture.log+=m.MARKERS[0]+'\n'
                elif kind=='error_log':fixture.log+='\tError: actual failure\n'
                with self.assertRaises(ValueError):m.audit_request(fixture.build(**kwargs),fixture.output())

    def test_semantic_identity_and_timing_units_cannot_be_rebound_into_agreement(self):
        for kind in ('different_netlist','different_sdc','different_library','input_mutated','duration','bridge_unit','query_unit','duplicate_unit'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                fixture=EvidenceFixture(temporary);kwargs={}
                if kind=='different_netlist':kwargs['mutate_probe']=lambda d:d.update(netlist=dict(fixture.netlist,sha256='0'*64))
                elif kind=='different_sdc':kwargs['mutate_probe']=lambda d:d.update(analysis_sdc=dict(fixture.sdc,path='/foreign/same-name.sdc'))
                elif kind=='different_library':fixture.inventory['libraries'][0]=dict(fixture.library,sha256='0'*64)
                elif kind=='input_mutated':kwargs['mutate_execution']=lambda d:d.update(input_sha256_after={})
                elif kind=='duration':kwargs['mutate_prepared']=lambda d:d['tasks'][0]['activity_window']['end'].update(tick=201)
                elif kind=='bridge_unit':kwargs['mutate_prepared']=lambda d:d['tasks'][0]['mapped_macro_bridge_receipt'].update(timescale_seconds='1e-12')
                elif kind=='query_unit':fixture.units='Time_unit : 1000 ps\n'
                elif kind=='duplicate_unit':fixture.units*=2
                with self.assertRaises(ValueError):m.audit_request(fixture.build(**kwargs),fixture.output())

    def test_reported_unit_changes_numeric_review_and_is_not_assumed_ns(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture=EvidenceFixture(temporary);fixture.units='Time_unit : 1e-12 Second\n'
            result=m.audit_request(fixture.build(),fixture.output())
            self.assertEqual(result['actual_library_time_unit_seconds'],'1E-12')
            self.assertEqual(result['phases']['before']['counts']['toggle_rate:CONVERSION_RESIDUAL_REVIEW_PENDING'],67)

    def test_unknown_tz_tb_and_glitch_are_preserved_in_jsonl(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture=EvidenceFixture(temporary)
            changes=(dict(T0=40,TX=10),dict(T0=40,TZ=10),dict(T0=40,TB=10),dict(IG=3))
            for pin,extra in zip(fixture.measured['pins'],changes):pin.update(extra)
            result=m.audit_request(fixture.build(),fixture.output())
            self.assertEqual(result['phases']['before']['counts']['UNKNOWN_OR_GLITCH_CONVERSION_REVIEW_REQUIRED'],4)
            records=[json.loads(line) for line in (fixture.output()/'pin-observations.jsonl').read_text().splitlines()]
            preserved={row['mapped_path']:row['raw_measurement'] for row in records}
            self.assertEqual(preserved,{p['mapped_path']:p for p in fixture.measured['pins']})
            for p in fixture.measured['pins'][:4]:
                row=next(row for row in records if row['mapped_path']==p['mapped_path'])
                self.assertNotIn('expected',row['phases']['before']['observations']['toggle_rate'])

    def test_exact_inventory_names_direction_measurement_dwell_and_query_parser(self):
        mutations=('foreign_pin','duplicate_pin','direction','reference','measured_dwell','measured_path','new_stat','wrong_phase','query_missing','query_duplicate')
        for kind in mutations:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                fixture=EvidenceFixture(temporary)
                if kind=='foreign_pin':fixture.inventory['macros'][0]['pins'][0]['full_name']+='foreign'
                elif kind=='duplicate_pin':fixture.inventory['macros'][0]['pins'][-1]=fixture.inventory['macros'][0]['pins'][0]
                elif kind=='direction':fixture.inventory['macros'][0]['pins'][0]['direction']='out'
                elif kind=='reference':fixture.inventory['macros'][0]['ref_name']='OTHER_SRAM'
                elif kind=='measured_dwell':fixture.measured['pins'][0]['TX']=1
                elif kind=='measured_path':fixture.measured['pins'][0]['path']='foreign/path'
                elif kind=='new_stat':fixture.measured['pins'][0]['arbitrary_stat']=0
                elif kind=='wrong_phase':fixture.tsv['before']=fixture.tsv['before'].replace('before','after',1)
                elif kind=='query_missing':fixture.tsv['before']='\n'.join(fixture.tsv['before'].splitlines()[:-1])+'\n'
                elif kind=='query_duplicate':fixture.tsv['before']+=fixture.tsv['before'].splitlines()[1]+'\n'
                with self.assertRaises(ValueError):m.audit_request(fixture.build(),fixture.output())

    def test_input_mutation_during_comparison_prevents_result_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture=EvidenceFixture(temporary);request=fixture.build();original=m.review_pin;called=[]
            def mutate_once(*args,**kwargs):
                if not called:
                    called.append(True)
                    path=Path(fixture.files['before']['local_path']);path.write_bytes(path.read_bytes()+b'\n')
                return original(*args,**kwargs)
            with patch.object(m,'review_pin',side_effect=mutate_once),self.assertRaisesRegex(ValueError,'identity differs'):
                m.audit_request(request,fixture.output())
            self.assertFalse((fixture.output()/'result.json').exists())
            self.assertEqual(json.loads((fixture.output()/'failure.json').read_text())['status'],'FAIL')

    def test_resigned_receipt_after_freezes_and_log_link_are_checked(self):
        for kind in ('prepared_after', 'tool_after', 'task_log', 'artifact_log', 'saif_after'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                fixture=EvidenceFixture(temporary)
                def mutate(execution):
                    if kind=='prepared_after':execution['prepared_sha256_after']='0'*64
                    elif kind=='tool_after':execution['tool_sha256_after']='0'*64
                    elif kind=='task_log':execution['tasks'][0]['execution']['log']=dict(fixture.original_log,sha256='0'*64)
                    elif kind=='artifact_log':execution['artifacts']['task_00/pt.log']=dict(fixture.original_log,path='/foreign/original-pt.log')
                    elif kind=='saif_after':
                        execution['artifacts']['task_00/task-mapped.saif']=dict(fixture.saif,sha256='0'*64)
                # build rebinds both original_execution hash and probe_result after
                # this mutation: rejection must be semantic, not a stale outer SHA.
                request=fixture.build(mutate_execution=mutate)
                with self.assertRaisesRegex(ValueError,'freeze differs|log/artifact|inputs changed|provenance identity differs'):
                    m.audit_request(request,fixture.output())

    def test_resigned_tcl_loading_other_sources_or_comment_bait_is_rejected(self):
        for kind in ('saif','strip','netlist','sdc','library','comment_bait','duplicate_read'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                fixture=EvidenceFixture(temporary)
                if kind=='saif':fixture.tcl=fixture.tcl.replace(fixture.saif['path'],'/foreign/task-mapped.saif')
                elif kind=='strip':fixture.tcl=fixture.tcl.replace('-strip_path {tb/dut}','-strip_path {foreign/dut}')
                elif kind=='netlist':fixture.tcl=fixture.tcl.replace(fixture.netlist['path'],'/foreign/mapped.v')
                elif kind=='sdc':fixture.tcl=fixture.tcl.replace(fixture.sdc['path'],'/foreign/analysis.sdc')
                elif kind=='library':fixture.tcl=fixture.tcl.replace(fixture.library['path'],'/foreign/library.db')
                elif kind=='comment_bait':
                    line=next(line for line in fixture.tcl.splitlines() if 'read_saif' in line)
                    fixture.tcl=fixture.tcl.replace(line,'# '+line+'\n'+line.replace(fixture.saif['path'],'/foreign/task-mapped.saif'))
                elif kind=='duplicate_read':fixture.tcl+='read_verilog {'+fixture.netlist['path']+'}\n'
                request=fixture.build()
                with self.assertRaisesRegex(ValueError,'actual Tcl bound'):
                    m.audit_request(request,fixture.output())

    def test_sentinel_source_contradiction_is_not_erased(self):
        name='hier/generate.dot[0]/A[0]'
        pin=dict(mapped_path=name,path='tb/dut/'+name,kind='PORT',T0=50,T1=50,TX=0,TC=25,IG=0)
        for value,source in (('-1','file'),('.25','UNINITIALIZED')):
            row=dict(toggle_rate=value,toggle_source=source,glitch_rate='0',glitch_source='file',static_probability='.5',static_source='file')
            row.update({field+'_value':m.decimal_value(row[field],field) for field in m.FIELDS})
            review=m.review_pin(pin,row,100,Decimal('1e-9'),Decimal('1e-9'))
            self.assertIn('toggle_rate:VALUE_SOURCE_SENTINEL_CONTRADICTION',review['review_reasons'])

    def test_decimal_print_interval_does_not_invent_count_precision_or_zero(self):
        name='hier/dot.macro/A[0]';pin=dict(mapped_path=name,path='tb/dut/'+name,kind='PORT',T0=50,T1=50,TX=0,TC=26,IG=0)
        row=dict(toggle_rate='.25',toggle_source='file',glitch_rate='0',glitch_source='file',static_probability='.5',static_source='file')
        row.update({field+'_value':m.decimal_value(row[field],field) for field in m.FIELDS})
        review=m.review_pin(pin,row,100,Decimal('1e-9'),Decimal('1e-9'))
        self.assertEqual(review['observations']['toggle_rate']['numeric_review'],'CONVERSION_RESIDUAL_REVIEW_PENDING')
        self.assertEqual(Decimal(review['observations']['toggle_rate']['delta_count_equivalent']),-1)
        row['toggle_rate']='0';row['toggle_rate_value']=Decimal(0)
        review=m.review_pin(pin,row,100,Decimal('1e-9'),Decimal('1e-9'))
        self.assertEqual(review['observations']['toggle_rate']['numeric_review'],'KNOWN_BOUNDARY_DIFFERS')


if __name__ == '__main__':
    unittest.main()
