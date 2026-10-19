# Official SRAM delivery point (currently empty)

No official SRAM functional model, pin specification, Liberty, LEF or area/power
table has been received. Do not put synthetic replacement PPA data here.

Keep received files byte-identical, record their license/version/SHA, and bind
them through an explicit build configuration. The required logical adapter is
`kwt_official_sram_adapter` (ports described in
`docs/OFFICIAL_SRAM_INTEGRATION.md`). Its absence intentionally makes backend 3
fail elaboration. This directory is a documented integration point, not a fake
official implementation.
