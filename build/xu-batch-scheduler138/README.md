# xu eight-candidate queue138

This is an executable local-only freeze/adopt queue for the eight candidates identified by137. It preserves all original directories, mappings, source guards and results. The distributed runtime uses only `batch138.py` and `queue-plan138.json`; it has no dependency on an unarchived workstation path. The other files provide source receipts, reproducibility and host checks. No EDA or remote action was performed while preparing this bundle.

Each candidate queues: `freeze` → `adopt_own_fm` → `formal_activity12` → `full_soc_power12` → `qualification`. Freeze/adopt are runnable now without license availability. They hash every declared input twice, check actual source/tool HEAD and tracked cleanliness before/after, and bind the exact own-FM mapped/SVF chain and native success/passing log. S2d selects repair19;32PE selects repair21. These maps differ from the original area table. The remaining phases explicitly report `PENDING_IMPLEMENTATION`; no incompatible baseline/S2c/S2e collector is invoked. Completing the first two phases does not complete the user's energy objective or qualify a candidate.

| Candidate | Frozen input records |
|---|---:|
| baseline H1+H2 |369|
| S1 H2-only |320|
| S1 SRAM bias |327|
| S2b |320|
| S2d |330|
| 32PE |336|
| 64PE |344|
| compact32/128 |351|

Baseline's original PPA main remains unknown. Its known power06 source checkout and the returned original FM/RTL bodies are rehashed; the new actual manifest binds that source identity without inventing an original PPA commit. S2b's historical tool Git commit likewise remains explicit while its actual producer files and current checkout identity are recorded. Source/tool identity mismatch or missing input yields `PENDING_INPUT_OR_SOURCE_VERIFY` and blocks dependent adoption. Previous freeze attempts are retained. Retrying pending inputs requires `--retry-pending` after inspection; no native or orphaned job is automatically restarted.

Existing130/134/S2c57 are read-only adoptions of state and live `/proc` argv. The queue never launches, kills or rewrites them. An adopted live worker reserves the native slot between its individual tool calls, including the time130 spends rehashing reports. Native dispatch requires memory≥16GiB, available disk≥100GiB and conservative cap1, with a queue-wide RUNNING reservation and process lock. A read-only `lmutil lmstat` command with actual total/used feature lines can establish observed free capacity. `list_licenses` and `license_users` show checkouts and are not a quota/free-seat proof. No spare seats are claimed. Per root's continuation policy, `unknown_license_policy=exclusive_single` permits one diagnostic native job only after existing/adopted jobs exit; switch to `wait` in a newly frozen plan to require `WAIT_LICENSE_KNOWN`. The current plan contains no runnable native argv.

Minimal original-host commands after copying the entire directory into a fresh bundle directory:

```bash
xu_bundle=/absolute/deployed/xu-batch-scheduler138
xu_base=/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102
xu_queue="$xu_base/eight-candidate-freeze-queue-20261105-138"
python3 -B "$xu_bundle/check_bundle138.py"
python3 -B "$xu_bundle/batch138.py" validate --plan "$xu_bundle/queue-plan138.json"
python3 -B "$xu_bundle/batch138.py" init --plan "$xu_bundle/queue-plan138.json" --out "$xu_queue"
python3 -B "$xu_bundle/batch138.py" tick --out "$xu_queue" --execute
```

The last command actually freezes/adopts all eligible candidates once, writes full manifests and compact state, and then leaves missing activity/power/qualification adapters pending. It starts no native EDA with this plan. Run `tick --out "$xu_queue"` without `--execute` for a preview/refresh. Reusing an existing init output is rejected; a changed plan/worker is rejected. A future runnable phase needs a new frozen plan with exact argv, pinned inputs and a unique marker. Commands use `shell=False`. Native rc0/marker is still diagnostic review pending, not qualification.

The upload payload is every regular file named in `bundle-manifest138.json` plus that manifest. `check_bundle138.py` verifies the manifest, inventory137 snapshot hash, exact eight identities, own selected map/SVF inputs and all phase orderings. `test_guards138.py` uses temporary fixtures and fake processes only. `activity-adaptation145-research.md` records the next real implementation requirements; no empty queue phase is counted as a completed activity run.
