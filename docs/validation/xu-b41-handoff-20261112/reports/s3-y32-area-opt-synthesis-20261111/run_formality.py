#!/usr/bin/env python3
"""Verify the selected B RTL against its completed Design Compiler mapping."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import runpy
import socket
import subprocess
import time

SOURCE = Path("/tmp/codex-area-opt-20261111-x0hlpsm0/candidate-b-r3/candidate")
FM = Path("/eda/synopsys/fm/fm_2020.09-SP5/bin/fm_shell")
TOP = "xu_soc_dma64_ppa_top"
PINNED = {
    "package-files.json": "a6ac0c36ecf3616cee2aa80b547f187929b48ec01fa1b4df6a50145d81a9cf3c",
    "execution.json": "6267e323667d2af1907618b5d9b2f06e37b87e9901957e184bae14694dcdbcf6",
    "default.svf": "0cca5e0ed2512d199c615f78c22d957fa35febcfae811a6295e512316e327370",
    "mapped.v": "db0a26348aea34a9c1e0e3bbdcd8e0e28082a543fa5aaf5b81b88c162540f11c",
}
MARKER = "XU_B41_RTL_TO_MAPPED_EQUIVALENCE_PASSED"


def sha(path):
    with path.open("rb") as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1048576), b""):
            digest.update(block)
        return digest.hexdigest()


def check(path, expected):
    if not path.is_file() or sha(path) != expected:
        raise RuntimeError("Missing or changed input: " + str(path))


def limits():
    cpus = sorted(os.sched_getaffinity(0))[:2]
    os.sched_setaffinity(0, cpus)
    resource.setrlimit(resource.RLIMIT_AS, (16 * 1024**3, 16 * 1024**3))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    if socket.gethostname().split(".")[0] != "RDserver04" or Path.home().name != "s4_23usr":
        raise RuntimeError("Run on the team's competition server")
    out = args.out.resolve()
    out.mkdir(mode=0o700)
    for name, digest in PINNED.items():
        check(SOURCE / name, digest)
    manifest = json.loads((SOURCE / "package-files.json").read_text())
    execution = json.loads((SOURCE / "execution.json").read_text())
    if execution["status"] != "SYNTHESIS_COMPLETE_NOT_QUALIFIED" or execution["returncode"] != 0:
        raise RuntimeError("Expected the completed candidate B mapping")
    for name, digest in manifest.items():
        check(SOURCE / name, digest)
    libraries = execution["libraries"]
    for library in libraries:
        check(Path(library["path"]), library["sha256"])
    heavy_jobs = runpy.run_path(str(SOURCE / "run_once.py"))["heavy_jobs"]

    rel = (SOURCE / "rtl.f").read_text().split()
    if len(rel) != 158 or any(name not in manifest for name in rel):
        raise RuntimeError("Unexpected compile source list")
    filelist = out / "rtl.f"
    filelist.write_text("".join(str(SOURCE / name) + "\n" for name in rel))
    inc = ["core", "perips", "perips/apb_i2c", "general", "subsys", "soc"]
    flags = " ".join(
        ["+define+SYNTHESIS+DISABLE_SV_ASSERTION=1+XU_MATRIX_DMA+XU_MATRIX_DMA64"]
        + ["+incdir+" + str(SOURCE / "source/rtl" / subdir) for subdir in inc]
        + ["-f", str(filelist)]
    )
    tcl = out / "check.tcl"
    lines = ["set synopsys_auto_setup true"]
    lines.extend("read_db -technology_library {" + lib["path"] + "}" for lib in reversed(libraries))
    lines += [
        "set_svf {" + str(SOURCE / "default.svf") + "}",
        "read_sverilog -container r -vcs {" + flags + "}",
        "set_top r:/WORK/" + TOP,
        "read_verilog -container i {" + str(SOURCE / "mapped.v") + "}",
        "set_top i:/WORK/" + TOP,
        "match",
        "set result [verify]",
        "report_black_boxes",
        "report_unmatched_points",
        "report_failing_points",
        "report_aborted_points",
        "if {!$result} {exit 1}",
        "puts {" + MARKER + "}",
        "exit 0",
    ]
    tcl.write_text("\n".join(lines) + "\n")
    command = ["timeout", "-k", "30s", "1800s", "nice", "-n", "10", str(FM), "-f", str(tcl)]
    started = time.time()
    with (out.parent / "eda.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        active = heavy_jobs()
        if active:
            raise RuntimeError("Same-account EDA slot occupied: " + str(active))
        with (out / "native.log").open("xb") as log:
            proc = subprocess.Popen(command, cwd=str(out), stdout=log, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, preexec_fn=limits)
            (out / "pid").write_text(str(proc.pid) + "\n")
            status = proc.wait()
    for name, digest in PINNED.items():
        check(SOURCE / name, digest)
    log = (out / "native.log").read_text(errors="replace")
    passed = status == 0 and MARKER in log.splitlines() and "Verification SUCCEEDED" in log
    result = {
        "scope": "Selected 64 PE B RTL versus original DC mapped.v using original SVF and SRAM macro boundary",
        "status": "FM_VERIFIED_REVIEW_SCOPE" if passed else "FM_INCOMPLETE_OR_FAILED",
        "native_exit": status,
        "elapsed_seconds": round(time.time() - started, 3),
        "sha256": PINNED,
        "input_manifest_count": len(manifest),
        "libraries": libraries,
        "tool_sha256": sha(FM),
        "script_sha256": sha(tcl),
        "log_sha256": sha(out / "native.log"),
        "command": command,
    }
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(result["status"], status, out, flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
