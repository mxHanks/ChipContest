# Final 64 PE candidate server package

This package is prepared locally. It has not been uploaded, synthesized or timed.
It binds the complete CPU full12 R2 result (304,128 exact Y32 outputs) to the
same frozen hardware, with the explicitly documented SRAM model replacements.
The CPU result is a cycle measurement, not proof of achieved 150 MHz frequency.

The runner defaults to an input-hash review only:

```sh
python3 run_once.py
```

Actual synthesis is explicit and refuses any earlier execution/output directory:

```sh
python3 run_once.py --run
```

The runner uses the previously measured DC executable and the exact same
SS/0.99 V/125 C standard-cell and RAMSP1024X16 libraries, pinned by SHA-256.
It uses at most two cores, blocks new runs after November 10, 2026 23:59 Shanghai,
and terminates only its own process group at that deadline. It rejects other
same-account simulation/EDA executables by default. Only after explicit user
resource coordination may `--coordinated-simv-pid 90373` allow the already running
simulation; it does not allow concurrent EDA jobs. No credentials are included.

The synthesis top is `xu_soc_dma64_ppa_top`; defines are `SYNTHESIS`,
`DISABLE_SV_ASSERTION=1`, `XU_MATRIX_DMA`, and `XU_MATRIX_DMA64`.
Hierarchy is checked before and after mapping: 64 PE, 8 engines, 16 W SRAM,
1 bias SRAM, 32 ITCM SRAM, 32 DTCM SRAM, 256 shared SRAM, total 337 macros.
Every mapped leaf is inventoried. Charged area conservatively includes all DMA
logic and its 17 internal SRAM, new arbiter logic, and all modified endpoint
standard logic; reused shared SRAM macros are reported separately.

The unchanged reference full-SoC SDC is provisional. No false paths, clock groups,
multicycle exceptions, ideal networks or relaxed checks are added. Mapping
completion is expressly **not** a timing PASS or contest qualification. Native
setup, hold, constraint, clock and area reports are retained for inspection.
Standalone STA, mapped functional equivalence, authoritative area units / SRAM
price table, official shared-interface eligibility, and full clock/reset/IO
contract still require validation. Library area units must not be presented as
mm² or a 2.25 mm² PASS without that evidence.

Rebuild locally from the sealed preparation directory with `prepare_package.py`.
Do not overwrite an old package or modify `package-files.json` to accept drift.
