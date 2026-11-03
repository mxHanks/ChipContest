"""Same actual wide/legacy wrapper acceptance on the independent four-depth W."""
import os
from pathlib import Path
import test_pe32_wrapper


class XuPe32Bank128WrapperTests(test_pe32_wrapper.XuPe32WrapperTests):
    environment = 'XU_PE32_BANK128_WRAPPER'
    bank128 = True

    def test_designated_ramsp128_wrapper_both_abis(self):
        name = os.environ.get('XU_PE32_BANK128_MACRO_MODEL')
        if not name:
            if os.environ.get(self.environment + '_SIM') == 'vcs':
                self.fail('server bank128 wrapper acceptance requires XU_PE32_BANK128_MACRO_MODEL')
            self.skipTest('designated RAMSP128X16 model is server-only; not a macro pass')
        model = Path(name)
        self.assertTrue(model.is_file() and not model.is_symlink(),
                        'regular designated SRAM model required')
        self.run_real_single_w_array_both_abis(model)
