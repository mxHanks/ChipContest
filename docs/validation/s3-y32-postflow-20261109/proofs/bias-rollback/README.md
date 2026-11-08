# Bias pipeline rollback

This package restores only the exact four-file frozen bias pipeline patch. It first checks every current file against `bias8-logs/source-hashes.json`; any later edit causes refusal before writing. Original Scala and generated Bias SV are packaged in `before/`; the two added tests are removed. It does not reset Git, change other files, erase simulation evidence, or run tools.

Dry run on the isolated 8 PE experiment:

```bash
python3.12 build/postflow-20261108/bias-rollback/rollback.py \
 --repo /home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest/build/postflow-20261108/bias8-repo
```

Append `--apply` to perform the restoration. Substitute the 16 PE sandbox or a later integrated workspace as `--repo` only if that workspace still contains these exact frozen four files. The same two original bias files were shared by the 8 PE and 16 PE baselines. No rollback was executed during evidence preparation.

The forward patch remains at `bias8-logs/bias-prefetch.patch`. Keep this directory alongside `bias8-logs/source-hashes.json` when relocating the rollback package.
