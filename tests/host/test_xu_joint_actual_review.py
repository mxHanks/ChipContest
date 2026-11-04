"""xu actual byte evidence and streaming-sidecar corruption rejection checks."""
import copy,importlib.util,json,sys,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2];TOOLS=ROOT/'tools/ppa/xu_joint_activity';sys.path.insert(0,str(TOOLS))
import xu_sram_joint_actual_review as review
import xu_joint_sidecar_stream_review as stream
import xu_pt_joint_actual48_review as pt
EVIDENCE=ROOT/'docs/validation/xu-score-joint-actual36-48-offline-20261104'

class ActualEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=review.ManifestInput(EVIDENCE/'raw',EVIDENCE/'original-export-manifest.json');cls.source.verify_all()
        cls.raw=cls.source(review.P36+'task_00/task-joint.stats.jsonl');cls.meta,cls.rows,cls.footer,cls.header=review.stats_parts(cls.raw)

    def test_actual336_integer_audit_preserves_invalid_original_header(self):
        r,_=review.review36(self.source)
        self.assertEqual((r['macro_count'],r['total_arc_instances']),(336,40656))
        self.assertEqual(r['Q_hold']['proven_hold_macros'],168)
        self.assertEqual(r['Q_hold']['closed_Q_internal_arcs'],2688)
        self.assertEqual(r['Q_hold']['stable_absolute_unknown_Q_pins'],2656)
        self.assertEqual(r['Q_initial_resolution']['conditional_rise_bounds'],[8357710,8358025])
        self.assertEqual(r['Q_initial_resolution']['conditional_fall_bounds'],[8357671,8358380])
        self.assertFalse(r['Q_initial_resolution']['other_nonbinary_edge_pins'])
        self.assertEqual(self.header['begin_transaction_observed'],'task-joint')
        self.assertEqual(self.header['utf8']['invalid_start'],350)
        self.assertEqual(bytes.fromhex(self.header['raw_header_hex']),self.raw.splitlines()[0])
        self.assertFalse(r['missing_evidence']['simultaneous_sidecar_present_locally'])

    def test_counter_corruption_rejected_by_independent_projection_marginals(self):
        row=copy.deepcopy(self.rows[0]);row['pin_dwell'][0][0]+=1
        ledger=review.parse(review.audit.LEDGER.read_bytes())
        with self.assertRaisesRegex(ValueError,'dwell duration differs'):
            review.audit.audit_macro(row,self.meta['duration_ticks'],ledger['arcs'])

    def test_zero_dwell_unknown_control_edge_breaks_hold(self):
        ledger=review.parse(review.audit.LEDGER.read_bytes())
        macros=[review.audit.audit_macro(r,self.meta['duration_ticks'],ledger['arcs']) for r in self.rows]
        held=next(m for m in macros if review.classify_hold([m],self.meta['duration_ticks'])['proven_hold_macros'])
        held=copy.deepcopy(held);held['pin_transitions']['GWEN'][2]=1
        r=review.classify_hold([held],self.meta['duration_ticks'])
        self.assertEqual(r['closed_Q_internal_arcs'],0)
        self.assertIn('GWEN_UNKNOWN_STATE_OR_ZERO_DWELL_EDGE',r['rows'][0]['rejection_reasons'])

    def test_actual48_full_query_review_and_reject_real_error(self):
        r=pt.review(self.source)
        self.assertEqual(r['queries']['numeric_mismatches'],0)
        self.assertEqual(r['queries']['total_rows'],606)
        def bad(name):
            b=self.source(name)
            return b+b'\nXU_JOINT_CONDITIONAL_API_REJECT real error\n' if name.endswith('/pt.log') else b
        with self.assertRaisesRegex(ValueError,'actual PT error/reject'):
            pt.review(bad)

    def test_actual48_value_and_missing_row_are_rejected(self):
        for corruption in ('value','missing'):
            def bad(name):
                b=self.source(name)
                if name.endswith('/conditional-queries.tsv'):
                    ls=b.splitlines(keepends=True)
                    if corruption=='missing':return b''.join(ls[:-1])
                    ls[1]=ls[1].replace(b'0.494275',b'0.594275');return b''.join(ls)
                return b
            with self.assertRaises(ValueError):pt.review(bad)

class StreamSubset(unittest.TestCase):
    def fixture(self):
        initial='0'*67;final=initial[:10]+'1'+initial[11:]
        m=dict(macro='m',final_state_lsb_ports=final,callback_events=1,pin_transitions=[[0]*16 for _ in range(67)])
        m['pin_transitions'][10][1]=1
        rows=[dict(macro='m',begin_tick=10,callback_ordinal=1,initial_state_lsb_ports=initial),
            dict(macro='m',tick=20,boundary=True,pre_state_lsb_ports=initial,events=[dict(callback_ordinal=2,port='CEN',old='0',new='1')]),
            dict(macro='m',end_tick=20,callback_ordinal=3,final_state_lsb_ports=final)]
        return m,rows

    def test_stream_subset_original_boundary_bytes_and_flow(self):
        m,rows=self.fixture()
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'raw.jsonl';out=Path(t)/'boundaries.jsonl';raw=[(json.dumps(r)+'\n').encode('ascii') for r in rows];p.write_bytes(b''.join(raw))
            r=stream.review_stream(p,dict(start_tick=10,end_tick=20,begin_callback_ordinal=1,end_callback_ordinal=3),[m],1,out)
            self.assertEqual(r['boundary_lines'],2);self.assertEqual(r['sparse_callback_events'],1)
            self.assertEqual(out.read_bytes(),raw[0]+raw[-1]);self.assertEqual(p.read_bytes(),b''.join(raw))

    def test_stream_old_state_corruption_is_rejected(self):
        m,rows=self.fixture();rows[1]['events'][0]['old']='x'
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'raw.jsonl';p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with self.assertRaisesRegex(ValueError,'old state differs'):
                stream.review_stream(p,dict(start_tick=10,end_tick=20,begin_callback_ordinal=1,end_callback_ordinal=3),[m],1,Path(t)/'boundaries')

if __name__=='__main__':unittest.main()
