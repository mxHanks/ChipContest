# xu mapped task00 public diagnostic 111 — local handoff

This archive preserves the existing local111 v4 records and the four files uploaded for the first independent server execution. It contains no actual mapped task00 server execution result. Nothing here establishes full functional, activity, energy or 150 MHz qualification. All 60 original private observations remain pending behind the mandatory final fatal.

The adapter independently checks all 336 mapped macros and every one of their 256 native rows, including exact owning module/memory, native type, row width, unique and repeatable identities, and available parent/scope/index metadata. Actual105 primitive proof is an additional runtime prerequisite. Preloads are restricted to the original 32 ITCM plus 256 shared memories; all aval/bval bits are read back. No Q or ordinary DUT FF writes are introduced.

Unknown shared/MMIO handshake and clock X/Z faults after actual reset readiness are rejected. The public observer checks the original clear, complete X/W/bias upload, 99 rows, all 50688 result reads and golden writes, frozen REQUEST/Y-retirement boundaries, and 23232 source reads. These checks do not discharge physical FF clear, FIFO ownership, clock-control or EXU observations.

Raw local logs preserve 38 mechanism command checks, seven actual runner cases and 12 classifier negative cases. They are host mechanisms and fixtures, not mapped VCS. `prepared-local-v3` contains the exact generated TB, inventory header, adapter plan and identity records; external captured TB/config/inventory/firmware/vector bodies are identified rather than duplicated. Vendor source and proprietary models are absent. Four local compiled objects are omitted with identities in `omitted-local-compiled-objects.json` and can be regenerated from the included source fixtures. The preserved earlier prepared-v1 TB/header are the exact existing mechanism-fixture inputs, not a second preparation result.

Verify this archive offline, without invoking EDA tools:

```bash
python3 /home/mxhanks/Projects/ChipContest-xu-score-opt/docs/validation/xu-mapped-task00-local111-20261105/check-evidence.py
```

To reproduce the host mechanisms, copy `tools/` into a fresh writable directory on a host with Python, GCC, Icarus Verilog and `/usr/include/iverilog`, then run `python3 local_checks111.py` from that copy. It creates a fresh `local-checks-v4/` and intentionally refuses to overwrite an existing run. Original absolute paths in the recorded raw logs are retained.

The server handoff uses the four helpers `xu_build_mapped_task00111.py`, `xu_mapped_task00_vpi111.c`, `xu_public_observer111.svh`, and `launch_mapped_task00111.py`, copied together to Desktop. Run:

```bash
python3 "$HOME/Desktop/launch_mapped_task00111.py"
```

The launcher creates isolated `mapped-task00-public-launch-20261104-111` and `mapped-task00-public-diagnostic-20261104-111` directories under the existing server campaign root, and records real process IDs. An observation timeout never authorizes restart. See `tools/README.md` for exact source identities, frozen paths, failure handling and scope. The original102 files were not edited; their four identities are preserved in `tools/origin102-identities.json`.
