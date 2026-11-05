# Shared candidate formal activity145: verified adaptation seams

Read-only source investigation, not a completed collector. Preserve old baseline/S2c/S2e guards and historical evidence. Existing `xu_soc_task_activity.py` is strict f49a5fc/baseline336; `xu_candidate_task_activity.py` is strictS2c; `xu_s2e_task_activity.py` is strictown89/109. Existing `xu_soc_saif_power.py` accepts baseline collector schema/exact336 and is not a seven-candidate power adapter. Old VCD-power rejectsPE32/64/compact32 and does not supply formal clear/request semantics.

The minimal shared implementation has three modules: a frozen profile/context registry; a task runner with common TB shell plus profile-specific ABI observer and clear recipe; and full macro inventory/alias mapping with an independently checked RTL-elaboration to mapped-macro bijection. Reuse `materialize_task`, `CLEAR_WINDOW_DECLARATIONS`, nominal LF clock, `base.generate_tb`, existing activity inspection and SAIF parsing algorithms. Use private imports of each candidate's own contract/soc/TB/firmware configuration/checkers, as the existing Context does. Keep physical_pes separate from logical group_width. A hand-listed336 macro set or probe-only explicit macro_paths is not proof of complete enumeration; joint-VPI registration checks have useful scope/name/width checks but themselves do not enumerate modules and hardcode67bits.

Registry fields must freeze main/child/profile, tool dependencies, physical variant/defines, schedule, source/adapters, actual macro groups/pins, upload layout, clear scope/commit paths, START/CTRL/STATUS/POP addresses, response retirement masks, lane/group widths, FIFO ownership paths, expected MAC activity, and idle-scope policy. Existing build_command only adds ARM_UD_MODEL; registry must supply XU_ACCEL_PE32/PE64/BANK128 and the candidate source/adapters. Current early root firmware contract is not a substitute for the candidate's own compiler_defines/check_log/check_performance/check_pe_activity.

| Candidate ABI | Row/control/result behavior requiring own observer |
|---|---|
| H2/SRAM/S2b manual8 | result0x80; noPOP; manual START per8-lane group |
| PE32 | rowd0/d4/d8; result200;8groups/row |
| PE64 | rowe0/e4/e8; result400;4groups/row |
| S2d | DBd0/d4/d8/dc/e0/e4; result200; tagged submit plus two64X banks |
| S2c continued | rowc0/c4/c8; result100 |
| S2e continued | packedHI140..14c; one response retires high16 of two lanes; keep separate from PACK32 upload |

H2 has no256-entry bias cache (CAP58550002), so clear16384W+64X+8legacy bias. Its bias-dtcm-window makes DTCM active; baseline's static DTCM declaration must be removed. SRAM-bias needs actual BiasSramCache.mem*_ext.RW0_en/wmode/addr/wmask commit checks and prefetch exclusion rather than cached-register checks. It adds24 RAMSP128X16 macros.

The32/64PE legacy W interface preserves8×2048 words. For32PE, physicalbank={addr[7:6],legacybank}, physicaladdr={addr[10:8],addr[5:0]};64PE usesbank={addr[8:6],legacybank}, addr={addr[10:9],addr[5:0]}. The same16384-word clear covers reachable physical W locations, but needs a passive physical commit proof. Unused1024 macro padding addresses are not MMIO-clearable and must not be described as fully zeroed physical capacity. Compact32 maps the reachable512logical depth to four128-depth slices and must verify registered return slice and mixed macro schemas.

S2d's old64X clear reaches only bank0. A valid recipe enables cache then DB mode, writes both64X banks without submit/descriptor/compute ownership, exits DB and restores cache-off. Prove exact actual physical commits, tagged row conservation and final DB_CTRL=0 retirement within the task window. FIFO reset proves empty ownership; payload without reset is not physically cleared. Prove all produced/read/retired data is fresh.

Every task remains a fresh TASKS=1 VCS process, CPU-only clear through the original MMIO interface, original include-wrapper firmware, full numerical scoreboard and actual accelerator clock/reset edge checks. Window is first source REQUEST through finalY response RETIRE. Do not preload W/X/bias, patch DUT state, suppress timing checks, or treat directory preparation as execution. New evidence is needed for every clear commit recipe, physical W/X bank bijection, expected MAC counts, FIFO/DB ownership, complete elaborated macro list, mixed macro pin normalization and mapped activity relocation. Only after these pass should own12-task power run on the same selected mapped hash.
