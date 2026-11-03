"""Actual four-depth bank test; designated model is a separate mandatory server gate."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class XuPe32Bank128MemoryTest(unittest.TestCase):
    def run_bank(self, model=None):
        backend = os.environ.get('XU_PE32_BANK128_WRAPPER_SIM', 'iverilog')
        self.assertIn(backend, ('iverilog', 'vcs'))
        required = ['vcs'] if backend=='vcs' else ['iverilog','vvp']
        missing = [name for name in required if not shutil.which(name)]
        if missing:
            if 'XU_PE32_BANK128_WRAPPER_SIM' in os.environ:
                self.fail('explicit bank128 simulator unavailable: '+', '.join(missing))
            self.skipTest('bank128 simulation needs '+', '.join(missing))
        root=Path(__file__).resolve().parents[2]
        perips=root/'third-party/e203_hbirdv2/rtl/e203/perips'
        sources=[root/'tests/e203/tb_xu_pe32_bank128.sv',perips/'XuParallelWeightBank32Bank128.sv',perips/'Sram128x16.sv']
        sources += [root/'tools/ppa/xu_weight128_sram_adapter.sv',model] if model else [perips/'mem_128x16.sv']
        kind='bank-designated-macro' if model else 'bank-generated'
        with tempfile.TemporaryDirectory(prefix='xu-pe32-bank128-') as temporary:
            directory=Path(temporary);binary=directory/('simv' if backend=='vcs' else 'sim.vvp')
            argv=(['vcs','-full64','-sverilog','-timescale=1ns/10ps','-top','tb_xu_pe32_bank128',
                   '+define+DISABLE_SV_ASSERTION=1','-Mdir='+str(directory/'csrc')]
                  if backend=='vcs' else ['iverilog','-g2012','-s','tb_xu_pe32_bank128'])
            if model: argv += ['+define+ARM_UD_MODEL' if backend=='vcs' else '-DARM_UD_MODEL']
            argv += ['-o',str(binary)] + [str(path) for path in sources]
            for name,command in [('compile.log',argv),('simulation.log',[str(binary)] if backend=='vcs' else ['vvp',str(binary)])]:
                result=subprocess.run(command,cwd=str(directory),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                      universal_newlines=True,timeout=600)
                log_root=os.environ.get('XU_PE32_BANK128_WRAPPER_LOG_DIR')
                if log_root:
                    out=Path(log_root)/kind;out.mkdir(parents=True,exist_ok=True)
                    record=dict(argv=command,cwd=str(directory),backend=backend,designated_model=None)
                    if model: record['designated_model']=dict(path=str(model),sha256=hashlib.sha256(model.read_bytes()).hexdigest())
                    (out/name).write_text(json.dumps(record)+'\n'+result.stdout)
                self.assertEqual(result.returncode,0,result.stdout)
            self.assertEqual(result.stdout.count('XU_PE32_BANK128_PASS logical_words=512 depths=4 writes=520 reads=524 unknown_reads=4 selected_enable=1 latency=1'),1,result.stdout)
            self.assertNotRegex(result.stdout,r'\b(?:FATAL|FAIL(?:ED|URE)?)\b')

    def test_generated_full_depth_boundaries_and_single_rw(self):
        self.run_bank()

    def test_designated_ramsp128_model(self):
        name=os.environ.get('XU_PE32_BANK128_MACRO_MODEL')
        if not name:
            if os.environ.get('XU_PE32_BANK128_WRAPPER_SIM')=='vcs':
                self.fail('server bank128 acceptance requires XU_PE32_BANK128_MACRO_MODEL')
            self.skipTest('designated RAMSP128X16 model is server-only; not a macro pass')
        model=Path(name)
        self.assertTrue(model.is_file() and not model.is_symlink(),'regular designated SRAM model required')
        self.run_bank(model)
