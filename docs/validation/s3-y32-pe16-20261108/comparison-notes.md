# 16 PE single-layer comparison

The read-only `compare_pe16.py` was run successfully against
`writeback-v2-20261108/direct-task0-phase/result.json` and
`pe16-20261108/pe16-task0/result.json`. Its output is `comparison.json`.
It does not modify either frozen campaign or invoke a simulator.

The script copies and retains the saved-artifact checks from the production
writeback reporter, with a separate explicit physical 16-PE loader. The
production reporter's fixed 8-PE work profile was not treated as applicable.
Only these exact six source-hash pairs/additions are accepted:

- `campaign.py`: record the mandatory physical observer result in JSON.
- `rtl/perips/LinearAutoGroupCore.sv`: paired computation with original external grouping.
- `rtl/perips/PairComputeCore.sv`: new physical pair of eight-lane engines.
- `tests/e203/tb_accel_soc.sv`: independently observe both physical engines.
- `tools/scripts/e203_soc.py`: enforce the explicit physical marker.
- `tools/scripts/xu_firmware_contract.py`: physical PE/work contract only.

All source, raw log, vector, ELF load-segment and image identities were
rechecked. Tool versions, compiler macros, normalized command arguments,
clocks, reset protocol, clear recipe and physical clear work match. Loaded
firmware and its Verilog byte image are identical. Raw ELF hashes differ only
in data outside the identical load contract.

| Metric | Direct 8 PE | Paired 16 PE | Change |
| --- | ---: | ---: | ---: |
| Payload cycles | 453259 | 469191 | +15932 (+3.514988%) |
| Physical clear cycles | 198403 | 198403 | 0 |
| Payload + clear | 651662 | 667594 | +15932 (+2.444826%) |
| Clear-to-source gap | 102 | 102 | 0 |
| Physical groups | 3168 | 1584 | -1584 |
| Physical MAC cycles | 202752 | 101376 | -101376 |
| Logical MAC work | 1622016 | 1622016 | 0 |

Phase changes are compute wait +13860, writeback +1676 and other +396;
weight, input and bias loading are unchanged. Status queries increase by 2376.
Compute/writeback overlap decreases by 85338; FIFO full wait increases by 1877.
Those overlap counters are not additive phase durations.

The comparison script also rejected four in-memory negative controls:
changed firmware image hash, changed ELF load contract, an unapproved CPU RTL
source change and changed compiler configuration. No evidence file was edited
for these controls.

This result applies to this paired computation / two-result-slot prototype on
original layer 0. It does not establish that every 16-PE architecture is slower.
The output matches all 25344 expected Y values, and both physical engines show
zero control synchronization errors. This remains Verilator 2-state development
evidence; no synthesis, area, power, STA, VCS/gate qualification or full12 run
was performed for this prototype.
