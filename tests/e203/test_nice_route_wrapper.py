"""Actual NICE top compatibility/error/backpressure replay with original vendor SVA."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest


class XuNiceRouteWrapperTests(unittest.TestCase):
    def test_real_top_legacy_and_checked_decoder_owner_and_backpressure(self):
        self.assertIsNotNone(shutil.which('vcs'),'VCS is required to retain original vendor xchecker SVA')
        root=Path(__file__).resolve().parents[2]
        rtl=root/'third-party/e203_hbirdv2/rtl/e203'
        inputs=[root/'tests/e203/tb_xu_nice_route_wrapper.sv',rtl/'subsys/e203_subsys_nice_core.v',
                rtl/'subsys/xu_nice_drain8.v',rtl/'general/sirv_gnrl_dffs.v',rtl/'general/sirv_gnrl_xchecker.v']
        headers=[rtl/'core/e203_defines.v',rtl/'core/config.v']
        pins={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs+headers}
        log_directory=os.environ.get('XU_NICE_ROUTE_LOG_DIR')

        def save(name,content):
            if log_directory:
                out=Path(log_directory);out.mkdir(parents=True,exist_ok=True);(out/name).write_text(content)

        save('inputs.json',json.dumps(pins,indent=2,sort_keys=True)+'\n')
        with tempfile.TemporaryDirectory(prefix='xu-nice-route-') as temporary:
            binary=Path(temporary)/'simv'
            argv=['vcs','-full64','-sverilog','-timescale=1ns/1ps','+incdir+'+str(rtl/'core'),
                  '-top','tb_xu_nice_route_wrapper','-Mdir='+str(Path(temporary)/'csrc'),'-o',str(binary),*map(str,inputs)]
            built=subprocess.run(argv,cwd=temporary,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                 universal_newlines=True,timeout=180)
            save('compile.log',built.stdout)
            self.assertEqual(built.returncode,0,built.stdout)
            result=subprocess.run([str(binary)],cwd=temporary,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                  universal_newlines=True,timeout=60)
            save('simulation.log',result.stdout)
            self.assertEqual(result.returncode,0,result.stdout)
            marker='XU_NICE_ROUTE_WRAPPER_PASS unsupported=1024 descriptor_errors=1 legacy=4 drain=1 requests=1030 completions=1030 commands=29 responses=29'
            self.assertEqual(result.stdout.count(marker),1,result.stdout)
            self.assertEqual(len(re.findall(r'^NICE_ROUTE_LEGACY_COMPAT_PASS ',result.stdout,re.M)),4,result.stdout)
            self.assertNotRegex(result.stdout,re.compile(r'(?im)^\s*(?:Fatal:|Error:|FATAL:)|\b(?:FAIL|FAILED|FAILURE)\b'))
        self.assertEqual(pins,{path:hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in pins},
                         'NICE routing inputs changed during replay')


if __name__=='__main__':
    unittest.main()
