#!/usr/bin/env bash
# Pinned project-local Yosys/ABC, Ubuntu 24.04 x86_64; no sudo or apt installation.
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$project_root"
if [[ $# -gt 1 || ( $# -eq 1 && "$1" != --download ) ]]; then
  echo 'Usage: bootstrap_synth.sh [--download]' >&2
  exit 2
fi
. /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 && "$(uname -m)" == x86_64 ]] || {
  echo 'Pinned tools require Ubuntu 24.04 x86_64; use host-native Yosys on other platforms.' >&2
  exit 2
}
mkdir -p .tools/downloads .tools/synth .tools/bin
if [[ "${1:-}" == --download ]]; then
  (cd .tools/downloads && apt-get download yosys=0.33-5build2 yosys-abc=0.33-5build2)
fi
python3 - <<'PY'
import hashlib
from pathlib import Path
packages = {
    'yosys_0.33-5build2_amd64.deb': '94247f2157ec6ce63c6638326e419975d911ace5356b3dc276d1d8b36659efbd',
    'yosys-abc_0.33-5build2_amd64.deb': '916ba59b6ca6dd1b6b927c7364357c2801ccb85db7eb3ca858ac9a856270fa44',
}
for name, expected in packages.items():
    path = Path('.tools/downloads') / name
    if not path.is_file():
        raise SystemExit('Missing '+str(path)+'; rerun with --download.')
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit('SHA256 mismatch: '+str(path))
PY
dpkg-deb -x .tools/downloads/yosys_0.33-5build2_amd64.deb .tools/synth
dpkg-deb -x .tools/downloads/yosys-abc_0.33-5build2_amd64.deb .tools/synth
cat > .tools/bin/yosys <<'SH'
#!/usr/bin/env bash
set -euo pipefail
tool_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../synth" && pwd)"
# Yosys 0.33 locates data relative to its executable; invoke the binary in
# its extracted usr/bin prefix, whose sibling share directory is checked here.
yosys_share="$tool_root/usr/share/yosys"
[[ -r "$yosys_share/simlib.v" ]] || { echo 'Missing local Yosys share tree' >&2; exit 1; }
export PATH="$tool_root/usr/bin:$PATH"
exec "$tool_root/usr/bin/yosys" "$@"
SH
cat > .tools/bin/yosys-abc <<'SH'
#!/usr/bin/env bash
set -euo pipefail
tool_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../synth" && pwd)"
exec "$tool_root/usr/bin/yosys-abc" "$@"
SH
chmod +x .tools/bin/yosys .tools/bin/yosys-abc
ldd .tools/synth/usr/bin/yosys > .tools/synth/yosys-ldd.txt
ldd .tools/synth/usr/bin/yosys-abc > .tools/synth/abc-ldd.txt
if rg -q 'not found' .tools/synth/yosys-ldd.txt .tools/synth/abc-ldd.txt; then
  echo 'Missing shared-library dependencies; see .tools/synth/*-ldd.txt.' >&2
  exit 1
fi
.tools/bin/yosys -V > .tools/synth/yosys-version.txt
.tools/bin/yosys-abc -c version > .tools/synth/abc-version.txt
.tools/bin/yosys -Q -T -p 'help memory_collect' > .tools/synth/memory-collect-help.txt
printf 'Project-local synthesis tools ready: '
cat .tools/synth/yosys-version.txt
