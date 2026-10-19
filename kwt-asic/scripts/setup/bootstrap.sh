#!/usr/bin/env bash
# Project-local setup for Ubuntu 24.04 x86_64. Does not use sudo or modify apt state.
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$project_root"
python3 -m venv .venv
mkdir -p .tools/downloads .tools/eda .tools/bin
if [[ "${1:-}" == "--download" ]]; then
  . /etc/os-release
  [[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 && "$(uname -m)" == x86_64 ]] || {
    echo 'These pinned packages require Ubuntu 24.04 x86_64; use native tools on other hosts.' >&2; exit 2;
  }
  (cd .tools/downloads && apt-get download iverilog=12.0-2build2 verilator=5.020-1)
fi
python3 - <<'PY'
import hashlib
from pathlib import Path
expected = {
 'iverilog_12.0-2build2_amd64.deb': 'f19394cee05ad526e0eb3873bc6c17a5828f56df17fbe2db40cb66513a2d4667',
 'verilator_5.020-1_amd64.deb': 'bb74ca8c32c73eb903ee91da64c8b58cfbe095c229967a95782108afb67bb3ca',
}
for name, digest in expected.items():
 p = Path('.tools/downloads') / name
 if not p.exists():
  raise SystemExit('Missing '+str(p)+'; rerun bootstrap.sh --download or use native tools.')
 if hashlib.sha256(p.read_bytes()).hexdigest() != digest:
  raise SystemExit('SHA256 mismatch: '+str(p))
PY
dpkg-deb -x .tools/downloads/iverilog_12.0-2build2_amd64.deb .tools/eda
dpkg-deb -x .tools/downloads/verilator_5.020-1_amd64.deb .tools/eda
ln -sfn ../../../bin/verilator_bin .tools/eda/usr/share/verilator/bin/verilator_bin
ln -sfn ../../../bin/verilator_bin_dbg .tools/eda/usr/share/verilator/bin/verilator_bin_dbg
cat > .tools/bin/iverilog <<'SH'
#!/usr/bin/env bash
set -euo pipefail
tool_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../eda" && pwd)"
exec "$tool_root/usr/bin/iverilog" -B "$tool_root/usr/lib/x86_64-linux-gnu/ivl" "$@"
SH
cat > .tools/bin/vvp <<'SH'
#!/usr/bin/env bash
set -euo pipefail
tool_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../eda" && pwd)"
exec "$tool_root/usr/bin/vvp" -M "$tool_root/usr/lib/x86_64-linux-gnu/ivl" "$@"
SH
cat > .tools/bin/verilator <<'SH'
#!/usr/bin/env bash
set -euo pipefail
tool_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../eda" && pwd)"
export VERILATOR_ROOT="$tool_root/usr/share/verilator"
exec "$tool_root/usr/bin/verilator" "$@"
SH
chmod +x .tools/bin/iverilog .tools/bin/vvp .tools/bin/verilator
.tools/bin/iverilog -V > .tools/iverilog-version.txt 2>&1
.tools/bin/verilator --version
echo 'Environment ready. Run: source env/activate.sh'
