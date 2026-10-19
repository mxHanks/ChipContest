#!/usr/bin/env python3
"""Extract the pinned small Debian OpenSTA package into .tools; no global install."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
NAME = "opensta_0~20191111gitc018cb2+dfsg-1.1_amd64.deb"
URL = "https://deb.debian.org/debian/pool/main/o/opensta/" + NAME
SHA = "070f1da9b307cc9273453ea50e7dffbadf1b95ee8712f2430f518bc7008e4e10"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--download", action="store_true")
    args = p.parse_args()
    package = ROOT/".tools/downloads"/NAME
    package.parent.mkdir(parents=True, exist_ok=True)
    if not package.is_file():
        if not args.download:
            p.error("pinned package missing; rerun with --download")
        subprocess.run(["curl", "-fL", "--connect-timeout", "15", "--max-time", "120", URL, "-o", str(package)], check=True)
    if hashlib.sha256(package.read_bytes()).hexdigest() != SHA:
        raise SystemExit("FAIL: downloaded OpenSTA package SHA mismatch; refusing extraction")
    target = ROOT/".tools/opensta"
    target.mkdir(parents=True, exist_ok=True)
    subprocess.run(["dpkg-deb", "-x", str(package), str(target)], check=True, timeout=30)
    binary = target/"usr/bin/sta"
    version = subprocess.run([str(binary), "-version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, timeout=15).stdout.strip()
    manifest = {"status": "PASS", "source": URL, "package_sha256": SHA, "version": version,
                "binary": str(binary), "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                "scope": "reference STA tool only; not a PDK or official competition library",
                "license": "GPL-3; package copyright/license retained under .tools/opensta/usr/share/doc"}
    (target/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    print(json.dumps(manifest))


if __name__ == "__main__": main()
