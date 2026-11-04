# xu mapped task00 public diagnostic 111

This is an independent successor to prepared102; original102 files are unchanged (four SHA256 identities in `origin102-identities.json`). It cannot claim full SoC functional, activity, 150 MHz, power, or scoring qualification. The exact final `$fatal` for all 60 pending original private observation paths is mandatory. No bypass flag exists.

Upload these four files together to the server Desktop:

- `xu_build_mapped_task00111.py`
- `xu_mapped_task00_vpi111.c`
- `xu_public_observer111.svh`
- `launch_mapped_task00111.py`

Run:

```bash
python3 "$HOME/Desktop/launch_mapped_task00111.py"
```

The launcher requires a fresh `~/Desktop/xu-score-optimization-20261102/mapped-task00-public-launch-20261104-111` and separate `mapped-task00-public-diagnostic-20261104-111`. The latter contains actual compiler/simulator logs and authoritative running/terminal state. An observation timeout does not authorize restart.

The exact original S2c task00 1 fs clock/reset/pad setup, frozen firmware, original/materialized tensors, complete shared memory contents, and 32 ITCM plus 256 shared preloads are preserved. Only the original permitted vendor `mem` destinations and passive TB observation registers receive VPI writes. No Q, ordinary DUT FF, reset or clock force is added. All 336 mapped macros independently check all 256 native rows: exact module and memory names, memory native type, 64-bit row type/size, repeatable row identity, unique rows, and any parent/scope/index metadata. Preload rechecks each destination against that checked row handle and reads back all aval/bval bits. Successful actual105 primitive evidence is additionally rehashed from seven original inputs and four complete raw compile/run cases; a receipt alone is insufficient.

The observer rejects X/Z shared or accelerator handshake after actual reset readiness, rejects clock X/Z after readiness, checks the original shared backpressure phase, enforces 33697 clear writes, 23232 X/W/bias source reads, 8192 W pairs, 3168 X pairs, 99 rows, 3168 result POPs, all 50688 result words and golden Y writes. The frozen first REQUEST and final Y response retirement ticks/cycles remain strict. Original private FF/FIFO/PLL/EXU checks are explicitly pending; these public interface checks do not discharge them.

`EvidenceRun` saves real child PID/process group, catches build/simulation failure, timeout, and interruption, terminates only its own child process group, records exact raw child log hashes, and rehashes all frozen input identities on every exit. It preserves the primary exception if a later input is missing or changes. Expected final private-gate failure is classified only when complete public markers, all 336 geometry summaries, exact boundaries/counts, and the single exact pending fatal are present; native simulation still exits nonzero.

`local-checks-v4` contains 38 host mechanism command checks, seven actual subprocess runner cases (success, nonzero compiler, missing executable, timeout including native descendant cleanup, changed input, missing input plus primary failure, KeyboardInterrupt), and 12 classifier negative cases. The mechanism-only geometry fixture exercises the actual C guard for RegArray/Reg and Memory/MemoryWord, and rejects row255 missing, wrong size/type, wrong owning name, aliased row, nonrepeatable identity, wrong parent, and wrong index. The 4-state clock callback and complete public transaction fixtures are local mechanism checks, not mapped VCS proof. `prepared-local-v3` validates exact captured source/config/inventory and generated source. The earlier `prepared-local-v2` intentionally remains a recorded failed preparation from an incorrect local inventory path; it is not a server run.

Actual mapped VCS task00 execution is the next step. No production code was edited and no root Git commit was made by this handoff.
