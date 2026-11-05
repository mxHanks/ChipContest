# xu177/186 native query failure diagnosis206

The actual191 archive has SHA256
`44770417f09a4244cbeea5690b4f21923e5d641de365094010ca7eeaf7c998b3`
(13,216,384 bytes, 392 payload files, 367,456,367 payload bytes). `diagnose206.py`
verifies the archive and all extracted payload bytes, then replays the unchanged
177/186 worker guards. `original191/` preserves 17 selected original files and
their hashes; the full archive remains in the campaign evidence directory.

Both failures are query implementation compatibility errors:

* 177 completed native PT with rc0 and its completion marker. Its required
  `target-clock-reset.rpt` failed at `get_clocks -of_objects`: the installed
  T-2022.03-SP5-1 emitted `CMD-010`. The unchanged Python guard rejects this
  incomplete required report. The prior line successfully returned the pin's
  `clocks` attribute as native collection `_sel43136`; `target-native.rpt`
  lists `xu_hfextclk xu_plldiv_envelope` on the exact CK pin.
* 186 aborted with native rc1 and no completion marker on the same unsupported
  option. `static-metadata.tsv` and `query-status.tsv` are 0-byte partial files;
  no 9257-object metadata collection succeeded.
* 177's optional `annotated-check.rpt` separately reports `CMD-001`: installed
  PT forbids combining `-list_annotated` and `-list_not_annotated`.

These findings do not qualify either design, prove graph inequivalence, waive
coverage, or explain the mapped VCS notifier event. Some original177 timing
reports contain measured violating paths under the original own57 all-clock
propagated method; that independent timing evidence must remain visible and
must not be transferred to S2e155's different clock method.

Minimal follow-up: a **new207 namespace**, fresh output root, original153 native
slot. Keep both exact original mapped/SDC/clock methods; query each pin's native
`clocks` collection via `get_attribute`, validate/map each clock object and
record empty/unavailable attributes explicitly. Iterate pins separately before
unioning names. Split annotated/not-annotated queries into independent reports.
Keep the original required-report guards. No original177/186 file is edited.

Reproduction (from the worktree root, use a fresh output directory):

```sh
python3 -B build/xu-native-query-failure206/diagnose206.py \
  --evidence-root build/xu-score-resume-20261103/final191 \
  --archive build/xu-score-resume-20261103/xu-server-two-candidate-final-20261105-191.tar.xz \
  --sha256 44770417f09a4244cbeea5690b4f21923e5d641de365094010ca7eeaf7c998b3 \
  --out /tmp/xu206-fresh-replay
python3 -B -m unittest discover -s build/xu-native-query-failure206 -p test206.py
```

Success means only **original diagnostic failures reproduced**, always
`NOT_QUALIFIED`. Original server-only inputs are checked through the recorded
before/after receipts, not falsely described as locally rehashed bodies.
