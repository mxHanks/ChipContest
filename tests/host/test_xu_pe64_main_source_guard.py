"""Repeat every real object/index/mode/symlink mutation for the exact64 profile."""
import test_xu_pe32_main_source_guard as guard_fixture


class XuPe64MainSourceGuardTest(guard_fixture.XuPe32MainSourceGuardTest):
    PROFILE = 's3-pe64'
    MAIN_PIN_ATTRIBUTE = 'PE64_MAIN_COMMIT'
