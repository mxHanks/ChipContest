# Production N2 GPIO / CPU validation

The default profile keeps every production RTL byte and definition from the
sealed `ppa-native-r2` package. The selected storage profile explicitly overlays
two sealed RTL files and adds one feature definition, as described below.
`XU_SYSBUS_TEST_LOADER` is absent in both profiles. The production ingress has
two owners (CPU and DMA). Every SRAM macro uses the independent generic
functional model, including 32 ITCM and 32 DTCM macros: 353 total in the original
profile, 374 in the selected 21-result-macro profile. This does not establish
vendor SRAM timing, mapped equivalence, area, or power.

Only firmware is initialized into physical ITCM. No X, W, bias or output value
is initialized through a hierarchy access. The testbench drives 32 data bits on
the existing GPIOB pads and a toggle request on GPIOA[20]. CPU firmware enables
GPIOA[21:23] as ACK, READY and ERROR. It reads each word through the original
GPIO/APB interface, writes it through its original LSU, BIU and SystemBus, fences,
and acknowledges it only after the write response retires. The testbench checks
this retirement for all 15,040 words. Each source word is stable for three HF
edges before its request toggle and remains stable through ACK.

For every task, the CPU writes the Y poison pattern before timing, performs real
hardware clear, fences and publishes clear-complete only after its shared-memory
mailbox response retires. Input loading then begins. The principal input window
starts when the first tensor word is presented on GPIOB and ends at the last Y
write response; every GPIO handshake, CPU operation, scheduling delay and bus
wait in that interval is included. A second, conservative window starts with the
accepted clear command. After hardware DONE and a fence, the CPU reads all
25,344 Y words through the original SystemBus. The read-only testbench observer
compares every retired read response as well as every accelerator output write.

`check_results.py` rejects missing GPIO ACKs, premature clear/data/completion,
missing or duplicated physical macro instances, incomplete physical clear,
output count or numeric mismatches, and omitted endpoint waits. The original
profile proves 33,536 actual 16-bit clear writes (W 16,384, bias 768, X 16,384);
the selected profile also clears every result macro address. Both check the
required data-path and state zeros. Warmup is a
separate complete task to establish a publicly dirtied prestate; its cycles are
reported separately.

Launch a one-task build and simulation in a detached, one-shot local supervisor:

```bash
python3 -u -B experiments/s3-y32-compliant32/validation-gpio/launch.py \
  --state-dir build/compliant32-20261113/cpu-gpio-task0-r1-supervisor -- \
  --out build/compliant32-20261113/cpu-gpio-task0-r1 \
  --vectors build/compliant32-20261113/numeric/public-validation-600-evaluation-r1/vectors \
  --ppa-package build/compliant32-20261113/ppa-native-r2 \
  --tasks 1 --rows 8 --warmup --jobs 2
```

Only after that invocation is functionally PASS, reuse its exact source, ELF,
image and simulator using `--replay-from` instead of `--ppa-package`. Required
followups are `--tasks 12`, one task with `--first-source-stall 31`, and one task
with `--first-load-stall 31`. A replay never recompiles or accepts a build-only
origin. Maximum local build parallelism and affinity are both two CPUs.

Every output directory is new and never overwritten. Inspect `state.json`, the
recorded live child PID and process identity before deciding a job is terminal;
an expired tool observation is not permission to restart it. Failed attempts
retain their logs, result and exact source identity.

The selected result/bias storage repair is an explicit overlay, supplied with
`--storage-candidate build/compliant32-20261113/storage-macro/wide-candidate-r2`.
The original package remains the sealed production N2 baseline. The runner
records the two changed RTL files, all dependency hashes, the added
`XU_MATRIX_STORAGE_SRAM` definition and the selected physical observer. The
21-result-macro profile has 54 internal macros and 374 whole-SoC macros; the
3-result-macro fallback has 36 and 356. Old 353-macro results do not establish
either profile's cycles, clear work, area or timing.

For the 21-macro profile, every clear physically writes 55,040 16-bit words:
16,384 W, 768 bias, 16,384 X and 21,504 result words. The MMIO clear counter
excludes bias and therefore reports 54,272. Scalar result POPs retire 25,344
times; the compatible DMA MMIO group POP counter reports 3,168, once per eighth
column. Both are checked independently. No row/group result register array or
reusable bias cache is accepted as a replacement for these macros. Scalar
transaction and operand assembly registers remain disclosed.

After the selected single task is PASS, run the complete set in a detached
serial supervisor (one simulator CPU, no rebuild):

```bash
taskset -c 1 python3 -u -B experiments/s3-y32-compliant32/validation-gpio/launch.py \
  --followups \
  --state-dir build/compliant32-20261113/cpu-gpio-storage21-followups-r1-supervisor -- \
  --base build/compliant32-20261113/cpu-gpio-storage21-task0-r1 \
  --vectors build/compliant32-20261113/numeric/public-validation-600-evaluation-r1/vectors \
  --out build/compliant32-20261113/cpu-gpio-storage21-followups-r1
```

`receipt.json` records each active child PID, command, terminal result hash and
the full12/wait31 cycle differences. A failure stops the chain and is retained.
The `--replay-from` check verifies the completed base source, firmware and
binary before each run; preparation-only receipts cannot start this chain.

After all three followups are PASS, create the compact complete evidence bundle:

```bash
python3 -B experiments/s3-y32-compliant32/validation-gpio/package_evidence.py \
  --base build/compliant32-20261113/cpu-gpio-storage21-task0-r1 \
  --followups build/compliant32-20261113/cpu-gpio-storage21-followups-r1 \
  --vectors build/compliant32-20261113/numeric/public-validation-600-evaluation-r1/vectors \
  --out build/compliant32-20261113/cpu-gpio-storage21-delivery-r1
```

The packager first verifies the original source, binary, firmware, vectors and
every followup's binding. It then replays all four raw logs and independently
recomputes their integer MAC/RNE references. The archive contains all frozen RTL,
testbench, observers, firmware, vectors, commands and raw logs; generated C++ and
the simulator executable are rebuilt on demand. Its receipt distinguishes this
content/log verification from a new simulation or a PPA measurement.
