"""Reject incomplete queue/overlap evidence and prove universal accumulator range."""
import importlib.util
from pathlib import Path
import unittest

SPEC=importlib.util.spec_from_file_location('rowpair_bench',Path(__file__).resolve().parents[1]/'scripts/verify/run_rowpair_benchmark.py')
R=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)


def config(buffers=2,pipe=1,stalls='none'):
    return {'engine':'rowpair','lanes':8,'pipe_mul':pipe,'result_buffers':buffers,'tasks':2,'seed':77,'stalls':stalls}


def complete(c=None):
    c=c or config()
    # 49 normal pairs followed by one odd tail. Separate test arithmetic.
    compute_pair=32*(64+1+c['pipe_mul']+1)
    cycles=50*compute_pair+8+258+49*(17 if c['result_buffers']==2 else 531)
    stalls=7000 if c['stalls']=='random' else 0
    cycles+=stalls//2 if c['result_buffers']==2 else stalls
    return '\n'.join([f'PASS ROWPAIR_BENCH_TASK task={task} outputs=25344 core_cycles={cycles} load_words=22976 load_cycles=23000 output_stalls={stalls} x_reads=202752 w_reads=819200 b_reads=12800 window_cycles={cycles+23002} result_reads=25344 result_writes=25344 overlap_cycles={100 if c["result_buffers"]==2 else 0} buffer_wait_cycles={25 if stalls else 0}' for task in range(2)]+[f'PASS ROWPAIR_BENCH_SUITE tasks=2 outputs=50688 resets=3 illegal=3 input_bubbles={25 if stalls else 0} stalls={2*stalls} stable={2*stalls} busy_load_rejections=200000 full_window_cycles={2*(cycles+23010)}'])


class RowpairEvidenceTests(unittest.TestCase):
    def error(self, log, c=None, command=None):
        return R.check_completion(command or {'exit_code':0},log,c or config())[0]

    def test_four_configurations_with_and_without_backpressure(self):
        for b in (1,2):
            for p in (0,1):
                for s in ('none','random'):
                    c=config(b,p,s)
                    self.assertIsNone(self.error(complete(c),c))

    def test_mandatory_end_to_end_conservation(self):
        for before, after in [('result_writes=25344','result_writes=25600'),('result_reads=25344','result_reads=25343'),('x_reads=202752','x_reads=204800'),('w_reads=819200','w_reads=1622016'),('outputs=50688','outputs=50687'),('load_words=22976','load_words=22975')]:
            with self.subTest(before=before):
                self.assertIsNotNone(self.error(complete().replace(before,after)))

    def test_no_false_overlap_or_queue_coverage(self):
        self.assertIsNotNone(self.error(complete().replace('overlap_cycles=100','overlap_cycles=0')))
        c=config(stalls='random')
        self.assertIsNotNone(self.error(complete(c).replace('buffer_wait_cycles=25','buffer_wait_cycles=0'),c))

    def test_unmeasured_latency_and_false_pass(self):
        for change in [complete().replace('core_cycles=108299','core_cycles=108300'),complete().replace('core_cycles=108299','core_cycles=108298'),complete()+'\nFATAL: late failure',complete().split('\n',1)[1],complete().replace('task=1','task=0')]:
            self.assertIsNotNone(self.error(change))
        self.assertIsNotNone(self.error(complete(),command={'exit_code':0,'timed_out':True}))

    def test_accumulator_41_bits_preserves_all_legal_partial_sums(self):
        # All possible products lie within these exact signed endpoints.
        product_min=-32768*32767
        product_max=(-32768)*(-32768)
        for k in range(65):
            smallest=-(1<<39)+k*product_min
            largest=(1<<39)-1+k*product_max
            self.assertGreaterEqual(smallest,-(1<<40))
            self.assertLess(largest,1<<40)
        self.assertGreater((1<<39)-1+64*product_max,(1<<39)-1) # 40 bits cannot suffice.
        self.assertLess(-(1<<39)+64*product_min,-(1<<39))

    def test_invalid_architecture_rejected(self):
        for key,value in [('engine','opt'),('lanes',16),('pipe_mul',2),('result_buffers',0)]:
            c=config();c[key]=value
            with self.assertRaises(ValueError):R.expected_metrics(c)


if __name__=='__main__':unittest.main()
