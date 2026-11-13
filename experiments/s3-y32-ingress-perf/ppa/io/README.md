# Fixed-map loader IO observations

This prepares a separate read-only PT run for the original1064 N3 map. It does not edit or rerun DC, ECO, original RTL, libraries, SDC or the completed collector. The first111 load/update lines are byte-identical to the native-proven fixed collector.

```sh
python3 experiments/s3-y32-ingress-perf/ppa/io/prepare.py \
  --baseline build/ingress-perf-20261113/ppa-dev-n3-r2 \
  --fixed-collector build/ingress-perf-20261113/pt-recollect-r1/pt_collect.tcl \
  --out build/ingress-perf-20261113/loader-io-r2
```

The remote EDA owner copies the four small files plus `package-files.json` to a new bundle directory. With `XU_IO_BASELINE` set to the existing immutable remote DC directory, `python3 run.py --stage pt --run` verifies the exact original186-input catalog, native DC receipt, own map/SVF/SDC/library output identities, bundle hashes and Linux/native cap8. It refuses output-directory overwrite. An existing same-account heavy job requires the inherited explicit coordination flags.

The collector independently checks the actual106 loader bits and actual membership in `all_inputs`/`all_outputs` (71in/35out). For each bit it writes bounded min and max `report_timing` with full expanded clocks and `max_paths1/nworst1`. The tool may return a path per group, so the TSV retains actual header/numeric-slack counts and the minimum returned slack with its corresponding path group/type/headers. It also records input/output external-delay text. `NO_PATH_REPORTED`, paths without numeric slack, partial numeric contexts and unparsed reports are explicit. Full raw path headers are the clock evidence; no guessed `timing_path`/`port` attributes or `get_timing_paths` APIs are used.

`loader-io-observations.tsv`, `io-status.txt`,212 raw reports, host usage, clocks and check_timing are review artifacts. Bounded returned paths do not cover every clock context, transition polarity, exception, unconstrained path, CDC or reset scenario. A completed observation stage is neither complete IO qualification nor STA closure. No fallback creates a numeric slack or timing PASS for `NO_PATH`.
