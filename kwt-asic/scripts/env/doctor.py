#!/usr/bin/env python3
"""Read-only dependency/resource inventory; never installs or starts EDA jobs."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
TOOLS = {
    "python3": ["--version"],
    "gcc": ["--version"],
    "g++": ["--version"],
    "make": ["--version"],
    "cmake": ["--version"],
    "ninja": ["--version"],
    "verilator": ["--version"],
    "iverilog": ["-V"],
    "vvp": ["-V"],
    "yosys": ["-V"],
    "riscv32-unknown-elf-gcc": ["--version"],
    "riscv64-unknown-elf-gcc": ["--version"],
    "riscv64-linux-gnu-gcc": ["--version"],
    "git": ["--version"],
    "ssh": ["-V"],
}
HOST_REQUIRED = ("python3", "gcc", "g++", "make")
MODULES = ("pip", "numpy", "pytest", "torch", "onnx", "onnxruntime")


def run(argv: list[str], timeout: int = 10) -> dict:
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return {"returncode": result.returncode,
                "output": (result.stdout + "\n" + result.stderr).strip()[:16000]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"returncode": None, "output": str(exc)[:2000]}


def command_path(name: str) -> str | None:
    # Explicitly bounded project locations; no filesystem scan and no shell rc sourcing.
    candidates = [ROOT / ".venv/bin" / name,
                  ROOT / ".tools/bin" / name,
                  ROOT / ".tools/eda/usr/bin" / name,
                  ROOT / ".tools/usr/bin" / name,
                  ROOT / ".tools/iverilog/bin" / name,
                  ROOT / ".tools/verilator/bin" / name]
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return shutil.which(name)


def inspect_local() -> dict:
    found = {}
    for name, args in TOOLS.items():
        executable = command_path(name)
        if not executable:
            found[name] = {"status": "MISSING", "path": None}
            continue
        result = run([executable, *args])
        found[name] = {"status": "AVAILABLE" if result["returncode"] == 0 else "CHECK_FAILED",
                       "path": executable,
                       "version": result["output"].splitlines()[0] if result["output"] else "",
                       "returncode": result["returncode"]}
    python = command_path("python3") or sys.executable
    module_probe = run([python, "-c", "import importlib.util,json; "
                        f"print(json.dumps({{n: importlib.util.find_spec(n) is not None for n in {MODULES!r}}}))"])
    try:
        modules = json.loads(module_probe["output"])
    except json.JSONDecodeError:
        modules = {"probe_error": module_probe}
    disks = {}
    for target in (ROOT, Path("/tmp")):
        usage = shutil.disk_usage(target)
        disks[str(target)] = {"total_bytes": usage.total, "free_bytes": usage.free}
    memory = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            if key in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree"):
                memory[key + "_bytes"] = int(value.strip().split()[0]) * 1024
    except (OSError, ValueError):
        pass
    return {"platform": platform.platform(), "cpu_count": os.cpu_count(),
            "tools": found, "python_modules": {"interpreter": python, "modules": modules},
            "memory": memory, "disks": disks,
            "host_ready": all(found[n]["status"] == "AVAILABLE" for n in HOST_REQUIRED),
            "hdl_tool_available": found["verilator"]["status"] == "AVAILABLE" or
                                  (found["iverilog"]["status"] == "AVAILABLE" and
                                   found["vvp"]["status"] == "AVAILABLE")}


def inspect_remote(target: str) -> dict:
    # This is deliberately read-only, noninteractive, bounded, and opt-in.
    # It neither transfers project files nor reveals environment variables or key contents.
    source = """import json,os,platform,shutil,subprocess
names = %r
tools = {}
for name,args in names.items():
    executable = shutil.which(name)
    info = {'path': executable, 'status': 'MISSING'}
    if executable:
        try:
            r = subprocess.run([executable] + args, capture_output=True, text=True, timeout=6)
            lines = (r.stdout + '\\n' + r.stderr).strip().splitlines()
            info.update(status='AVAILABLE' if r.returncode == 0 else 'CHECK_FAILED', version=lines[0] if lines else '', returncode=r.returncode)
        except (OSError, subprocess.TimeoutExpired) as e:
            info.update(status='CHECK_FAILED', detail=str(e))
    tools[name] = info
usage = shutil.disk_usage(os.path.expanduser('~'))
print(json.dumps({'platform': platform.platform(), 'cpu_count': os.cpu_count(), 'tools': tools, 'home_free_bytes': usage.free}))
""" % TOOLS
    result = run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", target,
                  "python3 -c " + shlex.quote(source)], timeout=110)
    if result["returncode"] != 0:
        return {"target": target, "status": "UNAVAILABLE", "diagnostic": result["output"]}
    try:
        return {"target": target, "status": "REACHABLE", "inventory": json.loads(result["output"])}
    except json.JSONDecodeError:
        return {"target": target, "status": "UNPARSED", "diagnostic": result["output"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="Write the inventory JSON at this path.")
    parser.add_argument("--ssh", metavar="USER@HOST", help="Opt in to read-only BatchMode SSH inventory.")
    parser.add_argument("--require", choices=("host", "hdl"), default="host",
                        help="Fail if the requested minimum tools are unavailable (default: host).")
    args = parser.parse_args()
    report = {"schema": "kwt-migration-environment-v1",
              "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
              "scope": "Tool/resource discovery only; no proof of RTL/SoC correctness or contest closure.",
              "project_root": str(ROOT), "local": inspect_local()}
    if args.ssh:
        report["remote"] = inspect_remote(args.ssh)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    for name, info in report["local"]["tools"].items():
        print(f"{name:28} {info['status']:12} {info['path'] or '-'}")
    print("HOST_READY:", report["local"]["host_ready"])
    print("HDL_TOOL_AVAILABLE:", report["local"]["hdl_tool_available"])
    if args.ssh:
        print("REMOTE:", report["remote"]["status"])
    if args.json:
        print("REPORT:", args.json.resolve())
    ready = report["local"]["host_ready"]
    if args.require == "hdl":
        ready = ready and report["local"]["hdl_tool_available"]
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
