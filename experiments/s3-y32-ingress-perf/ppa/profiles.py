"""Exact original1064 N3 development hardware, not production qualification."""
REGISTER_X = 'UNSUPPORTED_REGISTER_PROFILE'
SRAM_X = 'sysbus32-x-sram-353-dev-n3'
CORE_B41_SHA = '710b8e180652f49751769e152a3b3a9e6a35ba622fb4c3e2385dc5ffab241fcb'
PROFILES = {SRAM_X: dict(defines=['SYNTHESIS','DISABLE_SV_ASSERTION=1','XU_MATRIX_DMA','XU_MATRIX_DMA_SYSBUS32','XU_MATRIX_X_SRAM','XU_SYSBUS_TEST_LOADER'], internal_macros=33, geometry=dict(itcm=32,dtcm=32,shared=256,weights=16,bias=1,x=16,total_macros=353,engines=8,mac_pe=64))}
