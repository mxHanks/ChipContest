#!/usr/bin/env python3
"""Regenerate optional accumulators and test every bounded-dot prefix.

Uses a new source-only build directory; installed production RTL is untouched.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def domain_proof():
    corners = [x * w for x in (-32768, 32767) for w in (-32768, 32767)]
    bmin, bmax = -(1 << 39), (1 << 39) - 1
    intervals = []
    for n in range(65):
        lo, hi = bmin + n * min(corners), bmax + n * max(corners)
        assert -(1 << 40) <= lo <= hi < (1 << 40)
        intervals.append(dict(products=n, lower=lo, upper=hi))
    return dict(method="Exact corner extrema and interval induction for all signed16 products and signed40 bias",
                prefixes=intervals, signed40_counterexample=dict(bias=bmax, x=1, w=1,
                exact=bmax + 1, signed40_wrap=bmin), scope="At most 64 enabled products since INIT; pauses preserve the prefix")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    repo, out = args.repo.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    snapshot = out / "chisel"
    shutil.copytree(repo / "src/main/scala", snapshot / "src/main/scala")
    shutil.copy2(repo / "project.scala", snapshot / "project.scala")
    pins = {str(p.relative_to(snapshot)): sha(p) for p in snapshot.rglob("*") if p.is_file()}
    records = []

    def run(command, name):
        with (out / (name + ".log")).open("x") as log:
            result = subprocess.run(command, cwd=snapshot, stdout=log, stderr=subprocess.STDOUT, timeout=300)
        records.append(dict(argv=command, cwd=str(snapshot), native_exit=result.returncode, log=name + ".log"))
        (out / "commands.json").write_text(json.dumps(records, indent=2) + "\n")
        if result.returncode:
            raise RuntimeError(name + " failed; see its preserved native log")

    for top in ("MacPE", "MacPE40Counterexample", "LinearAutoGroupCore", "LinearAutoGroupCore41"):
        run(["scala-cli", "run", ".", "--server=false", "--jvm", "system", "-M", "GenerateRTL", "--", top], "generate-" + top)
    baseline = snapshot / "generated/LinearAutoGroupCore"
    candidate = snapshot / "generated/LinearAutoGroupCore41"
    installed = repo / "third-party/e203_hbirdv2/rtl/e203/perips"
    changes = {}
    for path in baseline.glob("*.sv"):
        assert sha(path) == sha(installed / path.name), "Default generated RTL differs: " + path.name
        if sha(path) != sha(candidate / path.name):
            changes[path.name] = [sha(path), sha(candidate / path.name)]
    assert set(changes) == {"MacPE.sv"}, changes
    inputs = {"48": snapshot / "generated/MacPE/MacPE.sv",
              "41": candidate / "MacPE.sv",
              "40": snapshot / "generated/MacPE40Counterexample/MacPE.sv"}
    for suffix, source in inputs.items():
        text = source.read_text()
        assert text.count("module MacPE(") == 1
        (out / ("MacPE" + suffix + ".sv")).write_text(text.replace("module MacPE(", "module MacPE" + suffix + "(", 1))
    tb = out / "tb_acc41.sv"
    shutil.copy2(Path(__file__).with_name("tb_acc41.sv"), tb)
    tb_sha = sha(tb)
    binary = out / "prefix.vvp"
    run(["iverilog", "-g2012", "-s", "tb_acc41", "-o", str(binary), str(tb),
         *[str(out / ("MacPE" + width + ".sv")) for width in ("48", "41", "40")]], "compile-prefix")
    run(["vvp", str(binary)], "run-prefix")
    assert "ACC41_PREFIX_PASS" in (out / "run-prefix.log").read_text()
    drift = [name for name, digest in pins.items() if sha(snapshot / name) != digest]
    assert not drift, drift
    assert sha(tb) == tb_sha, "Frozen testbench changed during simulation"
    (out / "full-domain-proof.json").write_text(json.dumps(domain_proof(), indent=2) + "\n")
    result = dict(status="ACC41_REPRODUCTION_PASS", source_sha256=pins, source_drift=drift,
                  testbench_sha256=tb_sha, optional_changes=changes,
                  raw_register_bits=dict(before=384, after=328, reduction=56),
                  scope="Generated RTL prefix regression; no synthesis, area, energy or SoC speed claim")
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(result["status"])


if __name__ == "__main__":
    main()
