# Final DMA4 + storage21 production PPA inputs

This flow freezes one production profile: original32bit SystemBus and CPU,
four-slot ordered ingress/DMA, W16 + bias1 + X16 + result21 SRAMs (54 internal,
374 full SoC), 64 MACs, and no `XU_SYSBUS_TEST_LOADER`. It does not inherit any
old353 or old374 area/timing result. All physical macros are enumerated and charged.

`prepare.py` uses the pinned353 input package only as the compile-source order,
physical adapters, library identity and unchanged SDC reference. Every production
RTL source is re-read from the final worktree (the physical SRAM adapters keep
their exact reference bytes), and only core/DMA/ingress may differ from that
reference. All production source hashes and the complete source SET are sealed.
The actual XML/hierarchy checks, rather than this expected geometry, decide if
the hardware contains the selected macro and PE counts.

Prepare the immutable source package after integration, then run its local
single-core XML preflight. These commands do not access EDA or proprietary DBs:

```sh
python3 -B experiments/s3-y32-final/ppa/prepare.py \
  --base /home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest/build/compliant32-20261113/ppa-native-r2 \
  --out build/s3-y32-final/ppa/production-r1
python3 -B build/s3-y32-final/ppa/production-r1/preflight.py \
  --out build/s3-y32-final/ppa/preflight-r1
```

The CPU production runner must consume this whole package, copying the complete
`source/` tree, `rtl.f` and defines exactly. After its full12 PASS, seal a NEW
package that keeps the exact same RTL bytes/defines and adds raw CPU evidence:

```sh
python3 -B experiments/s3-y32-final/ppa/prepare.py \
  --source-package build/s3-y32-final/ppa/production-r1 \
  --cpu-full12 build/s3-y32-final/validation/gpio-followups-r1/full12/result.json \
  --out build/s3-y32-final/ppa/cpu12-bound-r1
```

The two-package sequence avoids a circular CPU result/package hash. The final
manifest binds both the first source-package SHA and the complete production RTL
SET. `run_once.py --run` checks the actual same-source GPIO full12 raw log and
firmware/checker hashes before any native tool or library access. A package
without that evidence can only be reviewed/elaborated locally.

The sole coordinated native owner runs one stage at a time, at most2 cores:

```sh
python3 -B run_once.py --stage dc
python3 -B run_once.py --stage dc --run --allow-coordinated-busy-jobs \
  --coordination-note 'User coordinated one independent max2core job; existing jobs remain untouched.'
python3 -B run_once.py --stage pt --run --allow-coordinated-busy-jobs \
  --coordination-note 'User coordinated one independent max2core job; existing jobs remain untouched.'
```

Execute from the new sealed package on the authorized server. The runner has no
remote transport or credential access and never terminates preexisting jobs.
DC must produce its own nonempty `final.svf`, flushed with `set_svf -off`, in
addition to mapped.v/ddc/sdc, leaf inventory, module area and native reports. PT
binds those exact output hashes, including the SVF. The original150MHz SDC and
same two characterized DB hashes, `compile_ultra -no_autoungroup`, physical macro
dont-touch, boundary policy and max2core limit remain unchanged. PT's only SDC
compatibility transform is the pinned three `create_generated_clock -add` edits.

All constraint reports use8 significant digits, preserving tiny negative slack.
Full native coverage and all-violators include setup/hold/recovery/removal,
gating/pulse and electrical DRC; max/min paths for every native path group are
also retained. No constraints, timing exceptions or global clocks are relaxed.

After raw native outputs return, replay their identity and numerical evidence:

```sh
python3 -B experiments/s3-y32-final/ppa/review_native.py \
  --inputs build/s3-y32-final/ppa/cpu12-bound-r1 \
  --native /path/to/returned/final/candidate \
  --allow-omitted-alib-cache --out build/s3-y32-final/ppa/native-review-r1.json
```

`NATIVE_EVIDENCE_VERIFIED_NOT_QUALIFIED` means only that identity/report replay
succeeded. Violated timing checks, DRC and missing/untested coverage remain gate
failures. Even an empty native violation set needs an explicit clock/CDC/reset
and coverage disposition; this reviewer never declares qualification. Raw area
units do not establish mm² or official macro price. RTL→mapped formal proof and
fullSoC same-configuration activity/power are separate required evidence.
