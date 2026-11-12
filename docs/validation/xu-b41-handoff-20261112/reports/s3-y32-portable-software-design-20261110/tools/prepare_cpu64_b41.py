#!/usr/bin/env python3
"""Prepare the three accepted software candidates for the B41 strict CPU test."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1] / "hardware64-r1"
PARENT = "96fffcb2a4b2492fd2cfdecb88e164d2c67881ae"
BASE = "a80dd184536e0f2312c62768d5acf4ba1b01c34e"
CHILD = "ccdac30d92ecf40f14d0b78879b8711fb0b1cdd1"
TILE = "rtl/e203/perips/LinearTileDmaCore.sv"
BENCH_TILE = "rtl/perips/LinearTileDmaCore.sv"
TILE_SHA = "710b8e180652f49751769e152a3b3a9e6a35ba622fb4c3e2385dc5ffab241fcb"
NAMES = ("tight-O2", "phased_64_fast4-O2", "backoff_8_256_fast4-O2")

REPLAY = r"""        for name, build_receipt in prepared['software'].items():
            image = ROOT/'firmware'/name/'dma64_soc'
            if sha(image) != build_receipt['elf_sha256'] or sha(image.with_suffix('.verilog')) != build_receipt['image_sha256']:
                raise ValueError('Changed B41 replay firmware: ' + name)
            argv = ['taskset','-c',str(cpu),str(binary),f'+TESTCASE={image}',
                    f'+VECTORS={ROOT}/vectors','+TASKS=12','+ROWS=8','+WARMUP=1',
                    '+MAX_CYCLES=20000000','+FIRST_SOURCE_STALL=0','+DUMPWAVE=0']
            print('B41_CPU64_FULL12_START',name,flush=True)
            log = out/(name+'.log')
            raw = run(argv,out,log,900)
            measured = checker.check_log(raw,12,8,True)
            timeline = measurements(checker,raw,measured)
            record['variants'][name] = dict(measurements=measured,timeline=timeline,argv=argv,
                firmware_image_sha256=sha(image.with_suffix('.verilog')),log_sha256=sha(log))
            save(out/'result.json',record)
            print('B41_CPU64_FULL12_PASS',name,measured['outputs'],measured['principal_cycles'],
                  measured['including_gap_cycles'],flush=True)
"""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    return sha(path.read_bytes())


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def read(path):
    return json.loads(path.read_text())


def git(repo, *argv):
    return subprocess.check_output(["git", "-C", str(repo), *argv])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-repo", type=Path, required=True)
    parser.add_argument("--child-repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    published = ROOT / "strict-input-r2"
    seal = read(published / "prepared.json")
    for line in (published / "INPUT.sha256").read_text().splitlines():
        expected, name = line.split("  ", 1)
        path = published / name
        if digest(path) != expected:
            raise ValueError("Frozen strict input changed: " + name)
    gitlink = git(args.parent_repo, "ls-tree", PARENT, "third-party/e203_hbirdv2").decode()
    if f"160000 commit {CHILD}\t" not in gitlink:
        raise ValueError("B41 source does not pin the requested E203 revision")
    delta = git(args.child_repo, "diff-tree", "-r", "--no-commit-id", "--name-only", BASE, CHILD)
    if delta.decode().splitlines() != [TILE]:
        raise ValueError("B41 changes more than the selected tile")
    old = git(args.child_repo, "show", BASE + ":" + TILE)
    new = git(args.child_repo, "show", CHILD + ":" + TILE)
    if sha(old) != seal["source_sha256"][BENCH_TILE] or sha(new) != TILE_SHA:
        raise ValueError("RTL tile does not bind to the accepted strict test")
    builds = ROOT / "candidates-r3"
    build_receipts = read(builds / "result.json")["builds"]
    software = {}
    for name in NAMES:
        directory = builds / name
        receipt = build_receipts[name]
        if digest(directory / "dma64_soc") != receipt["elf_sha256"] or \
           digest(directory / "dma64_soc.verilog") != receipt["image_sha256"]:
            raise ValueError("Candidate identity changed: " + name)
        software[name] = {key: receipt[key] for key in ("elf_sha256", "image_sha256", "optimization", "text_bytes")}
        software[name]["selected_config_sha256"] = digest(directory / "selected_config.h")

    out = args.out.resolve()
    out.mkdir(mode=0o700)
    for name in ("source", "firmware", "vectors"):
        shutil.copytree(published / name, out / name)
    shutil.copyfile(published / "run_native.py", out / "run_native.py")
    (out / "source" / BENCH_TILE).write_bytes(new)
    actual = {p.relative_to(out / "source").as_posix(): digest(p)
              for p in (out / "source").rglob("*") if p.is_file()}
    expected = dict(seal["source_sha256"], **{BENCH_TILE: TILE_SHA})
    if actual != expected:
        raise ValueError("Unexpected strict source delta")
    for name in NAMES:
        (out / "firmware" / name).mkdir()
        for file in ("dma64_soc", "dma64_soc.verilog", "selected_config.h"):
            shutil.copyfile(builds / name / file, out / "firmware" / name / file)
    original = (published / "run_strict.py").read_text()
    start = original.index("        argv=['taskset'")
    end = original.index("        if {str(p.relative_to(source))", start)
    runner = original[:start] + REPLAY + original[end:]
    runner = runner.replace("print('CPU64_STRICT_FULL12_PASS',measured['outputs'],measured['principal_cycles'],measured['including_gap_cycles'],flush=True)",
                            "print('B41_CPU64_CAMPAIGN_PASS',len(record['variants']),flush=True)")
    compile(runner, "run_strict.py", "exec")
    (out / "run_strict.py").write_text(runner)
    save(out / "prepared.json", dict(seal, parent_revision=PARENT, child_revision=CHILD,
        source_sha256=actual, software=software, upstream_strict_manifest_sha256=digest(published/"INPUT.sha256"),
        original_tile_sha256=sha(old), selected_tile_sha256=TILE_SHA,
        scope="Three frozen firmware images against B41 CPU RTL, full12 plus warmup; no mapped or energy claim"))
    pins = [(p.relative_to(out).as_posix(), digest(p)) for p in out.rglob("*") if p.is_file()]
    manifest = out / "INPUT.sha256"
    manifest.write_text("".join(f"{d}  {n}\n" for n, d in sorted(pins)))
    print("B41_STRICT_INPUT_PREPARED", len(pins), digest(manifest), out)


if __name__ == "__main__":
    main()
