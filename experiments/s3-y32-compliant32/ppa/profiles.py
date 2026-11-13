"""Exact production configurations; geometry limits are never ranges."""
BASE_DEFINES = ['SYNTHESIS', 'DISABLE_SV_ASSERTION=1', 'XU_MATRIX_DMA', 'XU_MATRIX_DMA_SYSBUS32']
REGISTER_X = 'sysbus32-register-x-337'
SRAM_X = 'sysbus32-x-sram-353'
CORE_B41_SHA = '710b8e180652f49751769e152a3b3a9e6a35ba622fb4c3e2385dc5ffab241fcb'

PROFILES = {
    REGISTER_X: dict(defines=BASE_DEFINES, internal_macros=17,
        geometry=dict(itcm=32, dtcm=32, shared=256, weights=16, bias=1,
                      x=0, total_macros=337, engines=8, mac_pe=64)),
    SRAM_X: dict(defines=BASE_DEFINES + ['XU_MATRIX_X_SRAM'], internal_macros=33,
        geometry=dict(itcm=32, dtcm=32, shared=256, weights=16, bias=1,
                      x=16, total_macros=353, engines=8, mac_pe=64)),
}
