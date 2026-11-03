# xu independent64 VCS deployment

Requires the recorded32PE base commits available in the previous-source repository and child. This package contains no credentials. Extract into a new directory, verify its archive identity, and run:

```sh
python3 launch.py --source /absolute/new/ChipContest-s3-pe64-02 --out /absolute/new/s3-pe64-accept-02 --previous-source /absolute/server/ChipContest-s3-pe32-01
```

The default cross prefix is the previously measured server SiFive10.2 toolchain. Source, output and deployment directories must be new. The launcher checks exact GCC/VCS versions, full tracked file bytes and modes before/after, mandatory physical64 direct64/32/8 and boundary VCS, stock host/numeric/vector/doctor/legacy5/synthetic1/synthetic2/wide64-real12, plus four complete12 physical/schedule controls. Retention, full150MHz, mapping and fullSoC energy remain separate gates. Do not overwrite any32/default source or old raw capture.

For a local checkout-only validation use --prepare-only. That does not execute any EDA or establish server acceptance. Each invocation needs new source/output paths.
