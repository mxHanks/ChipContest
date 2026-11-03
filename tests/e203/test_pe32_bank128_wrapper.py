"""Same actual wide/legacy wrapper acceptance on the independent four-depth W."""
import test_pe32_wrapper


class XuPe32Bank128WrapperTests(test_pe32_wrapper.XuPe32WrapperTests):
    environment = 'XU_PE32_BANK128_WRAPPER'
    bank128 = True
