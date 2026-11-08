"""Check consecutive SRAM reads and ownership cancellation on real generated RTL."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest


class BiasGroupPipelineTests(unittest.TestCase):
    def test_continuous_reads_all_tags_invalidate_reset_backpressure_and_clear(self):
        if not shutil.which('iverilog') or not shutil.which('vvp'):
            self.skipTest('iverilog and vvp are required')
        root = Path(__file__).resolve().parents[2]
        perips = root / 'third-party/e203_hbirdv2/rtl/e203/perips'
        sources = [root / 'tests/e203/tb_bias_group_pipeline.sv',
                   *(perips / name for name in ('BiasSramPrefetch.sv',
                                                'Sram1024x16.sv', 'mem_1024x16.sv'))]
        log_dir = os.environ.get('XU_BIAS_PIPELINE_LOG_DIR')
        def save(name, text):
            if log_dir:
                path = Path(log_dir)
                path.mkdir(parents=True, exist_ok=True)
                (path / name).write_text(text)
        with tempfile.TemporaryDirectory(prefix='bias-group-pipeline-') as temporary:
            binary = Path(temporary) / 'pipeline.vvp'
            built = subprocess.run(['iverilog', '-g2012', '-s', 'tb_bias_group_pipeline',
                                    '-o', str(binary), *map(str, sources)],
                                   capture_output=True, text=True, timeout=60)
            save('compile.log', built.stdout + built.stderr)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            result = subprocess.run(['vvp', str(binary)], capture_output=True,
                                    text=True, timeout=60)
            output = result.stdout + result.stderr
            save('simulation.log', output)
            self.assertEqual(result.returncode, 0, output)
            self.assertRegex(output, r'BIAS_GROUP_PIPELINE_PASS tags=32 words_per_fill=24 '
                             r'stream_cycles=25 invalidation_stages=25 reset_stages=25 '
                             r'complete_fills=[1-9][0-9]* physical_reads=[1-9][0-9]* clear_words=768')
            self.assertNotRegex(output, r'(?i)\b(?:FATAL|FAIL(?:ED|URE)?)\b')


if __name__ == '__main__':
    unittest.main()
