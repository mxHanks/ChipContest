"""Independent output-layout and activity guards for the S2e transport experiment."""
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/scripts'))
import e203_soc as soc
import xu_firmware_contract as contract


class XuPairedHiContractTests(unittest.TestCase):
    def test_schedule_changes_only_result_read_work_and_requires_actual_records(self):
        old = contract.task_contract('bias-hw-autogroup-window')
        new = contract.task_contract(contract.PAIRED_HI_SCHEDULE)
        self.assertEqual({key: new[key] for key in old}, old)
        self.assertEqual(new['result_mmio_reads'], 38016)
        self.assertEqual(new['paired_hi_mmio_reads'], 12672)
        layers = [dict(layer=0, cycles=1000000)]
        valid = 'RESULT_TASK layer=0 legacy_words=25344 packed_words=12672 logical_words=50688\n'
        actual = soc.check_result_activity(valid, layers, contract.PAIRED_HI_SCHEDULE)
        self.assertEqual(actual[0]['legacy_words'] + actual[0]['packed_words'], 38016)
        for bad in ['', valid+valid, valid.replace('12672','12671'),
                    valid.replace('50688','50687'), valid.replace('25344','50688'),
                    valid.replace('layer=0','layer=1'), valid.replace('12672','-1')]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                soc.check_result_activity(bad, layers, contract.PAIRED_HI_SCHEDULE)
        with self.assertRaises(ValueError):
            soc.check_result_activity(valid, layers, 'bias-hw-autogroup-window')

    def test_real_firmware_pair_macro_restores_all_signed_hi_codes(self):
        if not shutil.which('cc'):
            self.skipTest('host C compiler required to execute the actual firmware macro')
        source = (soc.TESTS / 'firmware/accel.c').read_text()
        macro = re.search(r'^#define XU_READ_PAIRED_RESULT\(pair\).*?^\} while \(0\)$',
                          source, re.M | re.S).group(0)
        program = r'''
#include <stdint.h>
#include <stdio.h>
enum { ROW_POP=0xc8/4, PAIRED_HI_WINDOW=0x140/4 };
#define COLS 256u
#define XU_RESULT_WINDOW (0x100/4)
''' + macro + r'''
int main(void) {
    volatile uint32_t reg[0x150/4]={0}, y[16]={0};
    unsigned row=0, group=0;
    uint64_t expected[8];
    for (unsigned h=0; h<65536; ++h) {
        for (unsigned lane=0; lane<8; ++lane) {
            uint32_t hi=(h+lane*40503u)&65535u;
            uint32_t lo=0x87654321u ^ (h*17u+lane*0x1020304u);
            uint64_t raw=((uint64_t)hi<<32)|lo;
            expected[lane]=(hi&0x8000u) ? raw|0xffff000000000000ull : raw;
            reg[XU_RESULT_WINDOW+2*lane]=lo;
            if (lane%2) reg[PAIRED_HI_WINDOW+lane/2]|=hi<<16;
            else reg[PAIRED_HI_WINDOW+lane/2]=hi;
        }
        reg[ROW_POP]=0;
        for (unsigned pair=0; pair<4; ++pair) {
            XU_READ_PAIRED_RESULT(pair);
            if (reg[ROW_POP]!=(pair==3)) return 2;
        }
        for (unsigned lane=0; lane<8; ++lane) {
            uint64_t actual=((uint64_t)y[2*lane+1]<<32)|y[2*lane];
            if (actual!=expected[lane]) return 3;
        }
    }
    puts("XU_REAL_FIRMWARE_MACRO_PASS hi_codes=65536 canonical64_values=524288");
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='xu-paired-hi-C-') as tmp:
            code=Path(tmp)/'macro.c'
            code.write_text(program)
            binary=Path(tmp)/'macro'
            built=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-O2',
                                  str(code),'-o',str(binary)],stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,universal_newlines=True,timeout=30)
            self.assertEqual(built.returncode,0,built.stdout)
            actual=subprocess.run([str(binary)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                  universal_newlines=True,timeout=30)
            self.assertEqual(actual.returncode,0,actual.stdout)
            self.assertIn('canonical64_values=524288',actual.stdout)


if __name__ == '__main__':
    unittest.main()
