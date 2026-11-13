# Original1064 N3 native PPA evidence

Status: DC and same-map PT/loader-IO collection complete; **not timing closed or
qualified**. PT has467 violated timing checks,1973 electrical violations and29335
untested checks. No ECO or map change was applied to this report snapshot.

The source is parent1aceb3d / child5470c56, independent of final374 GPIO integration
and old353 timing results. The sealed186-input package uses N3/PW2 TEST_LOADER top
ports,353 physical SRAM macros, original150MHz constraints/libraries and
`compile_ultra -no_autoungroup`. CPU1064.3506 used289 functional RAMSP models plus
behavioral CPU SRAM; that physical-model difference and development-loader role
remain explicit. Input catalog SHA256:
`96fbf8088cb2b94cc5bd682e09b9ec126762bd6c2dd54aad32caea854fb416ed`.

- `prepare/`: sealed input/source/define/profile identity and local structural
  result. No vendor DB/lib or credentials.
- `native-start/`: verified8-member initial native receipt and host observation,
  explicitly a partial startup snapshot.
- `native-dc/`: DC completed18:40:41–19:09:55 Beijing,1754.145s,cap8/affinity0..7,
  RC0/no source drift/errors/missing required output. Verified26-member summary,
  actual353-leaf geometry and area. Raw area units are not converted to mm².
- `native-map/`: complete18,320,772-byte curated archive;116 catalog files plus
  catalog verified locally. Actual map/DDC/SDC/own final.svf byte hashes match DC
  and both subsequent PT bindings. Includes original DC and first failed PT
  reports/logs/receipts, not WORK/alib/cache/vendor libraries/raw vectors.
- `native-pt/`: new19.769s same-map PT collection,RC0/no drift/errors/missing
  required reports. Original PT failed because `report_host_options` is absent;
  only the report command was replaced by native-proven `report_host_usage
  -verbose` in a new directory. The original failure remains intact. Curated
 64-member catalog,46 native execution outputs and full coverage/violator counts
  were SHA/byte verified. The independent review reconciles467 coverage
  violations with455 worst/context timing path blocks and1973 separate DRCs.
- `native-io/`: same map/SDC,106 actual loader port bits × min/max =212 bounded
  full-clock-expanded reports, all with numeric returned paths. All returned
  slacks MET; this is not all-clock/transition/exception/CDC or complete IO proof.
 231 catalog files and223 native execution outputs verified.
- `eco-prep/`: offline preparation only, **not executed** and no result inherited.

DC worst setup−366.30566406ns and PT worst max−5.18605757ns are different path/model
observations to the debug clock output; they are not an ECO improvement. PT
worst min−0.13472039ns; no SPEF was read and all177700 nets were unannotated.
The envelope clock contract and `XU_PROPAGATE_CLOCKS=0` remain unchanged. Raw
coverage includes constant-disabled/no-clock/unknown checks; no return code or
zero setup-violation subtotal proves closure.

The main report is `docs/s3-y32-ingress-perf-synthesis-report-20261113.md`.
`../s3-y32-ingress-perf-report-20261113/native-{dc,pt,io}-for-report.json` binds its
native numbers. Formal mapped equivalence, same353/N3 full-task activity/power,
production-loader/storage qualification and official600 evaluation are not
established. `SHA256SUMS` pins every published file in this evidence directory.
