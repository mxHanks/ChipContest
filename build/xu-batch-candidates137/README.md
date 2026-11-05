# xu batch candidates137 — returned-evidence draft

This local inventory identifies exactly eight candidates with independent mapped evidence, in ledger order: H1+H2 baseline, S1 remove full bias cache, S1 SRAM bias, S2b packed W/X, S2d double X buffer, 32PE/1024, 64PE/1024, and compact32/128. S2c and S2e are existing continuations; S2a has no independent mapped/area receipt in the reviewed ledger and is excluded explicitly. Every candidate remains `NOT_QUALIFIED` and `PENDING_SERVER_INPUT_VERIFY`.

`candidates137.json` records source main/child, server source/tool/PPA roots, exact prepared/execution local identities, source-manifest fingerprints, tool script hashes, libraries, original analysis SDC, original mapped hash, own conditional FM mapped/SVF chain, activity availability, and missing obligations. Its 20 original local JSON inputs are independently hashed; original commercial DB/mapped/SVF bodies remain server-receipt identities rather than locally rehashed bytes. `build_inventory137.py` deterministically regenerates this draft without network, EDA, or source mutation.

| Candidate | Source main / child prefix | Original mapped prefix | Own conditional FM target | Original accelerator area mm² |
|---|---|---|---|---:|
| H1+H2 | fc25468 / f49a5fc (later power06 source freeze) | 0f4898ba | original | 0.2857860337 |
| S1 H2-only | 23992eb / 434628c | 45ea28b8 | original | 0.1785626035 |
| S1 SRAM bias | b6f5075 / eee4150 | b20516c5 | original | 0.2469499369 |
| S2b | a2a1f07 / d5faa5e | 953738d2 | original | 0.2869364304 |
| S2d | 3af4db9 / dd692c1 | 02524054 | repair19 `7f1c1efa…` | 0.3036302710 |
| 32PE | 94ce6f0 / fc3977d | ca1d17a9 | repair21 `8aa1d86f…` | 0.5186033811 |
| 64PE | 3443fad / 7aae967 | 3e503963 | original | 0.9184209509 |
| compact32/128 | f75880d / 52cfbea | 7a69a121 | original | 0.5752035631 |

The baseline original PPA main/tool commit was not located in returned original PPA evidence. Its original mapped/SVF/FM identities are known. The later power06 freeze explicitly uses main `fc25468f33ae1da4e1bdddbb6c94e001a1c2a04e` and child `f49a5fc914971426bd4530db39e270a84b41139f`; this must not be retroactively renamed as the original PPA producer. Baseline collector main is separately `26f14f64c4f0d58822412932f365d086ed0d273c`. Its original-PPA replay remains pending until the exact source/tool is verified. The S2b PPA tool Git commit is likewise unresolved; exact executed script hashes are retained.

S2d/32PE repair FM must not prove original-map energy or silently replace original-map area. Baseline116 is another explicitly recorded mapped identity and needs its own energy if selected. All eight have unresolved complete 150MHz, SRAM modes/PVT/hold/read behavior, required full validation workload, and same-configuration energy obligations. Existing baseline12 RTL activity is a separate formal clear/REQUEST window; the original development cycles are not that window. Most other candidates have only development VCS and PPA with `activity=null`. The baseline336 collector, strict S2c collector, and strict S2e collector are not generic candidate collectors; S1 SRAM bias/32PE/64PE/compact32 need their actual macro inventories and matching schemas.

Current 130/134 and continued S2c are adopted, never restarted or marked successful by this inventory. `power130-independent-review.md` preserves the prior read-only progress135 assessment and exact next audit requirements. A future scheduler must keep license availability unknown until directly verified, guard memory/disk, preserve per-candidate dependency order and fresh output directories, and keep candidates with missing exact inputs pending. This directory itself starts no queue or server job.

```bash
python3 -B build/xu-batch-candidates137/build_inventory137.py
python3 -B build/xu-batch-candidates137/check_inventory137.py
```
