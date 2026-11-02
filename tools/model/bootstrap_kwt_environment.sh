#!/usr/bin/env bash
# xu: reproducible legacy inference tools in a new directory; no global install.
set -euo pipefail
if [[ $# != 1 ]]; then
  echo "Usage: bash tools/model/bootstrap_kwt_environment.sh /new/isolated/environment-root" >&2
  exit 2
fi
xu_model_repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
xu_model_env=$(realpath -m -- "$1")
if [[ -e "$xu_model_env" ]]; then
  echo "Refusing existing environment directory: $xu_model_env" >&2
  exit 2
fi
mkdir -p -- "$xu_model_env"
python3 -m venv "$xu_model_env/bootstrap"
"$xu_model_env/bootstrap/bin/python" -m pip install --disable-pip-version-check \
  --index-url https://pypi.org/simple uv==0.13.1 > "$xu_model_env/bootstrap.log" 2>&1
export UV_PYTHON_INSTALL_DIR="$xu_model_env/python"
export UV_CACHE_DIR="$xu_model_env/uv-cache"
"$xu_model_env/bootstrap/bin/uv" python install --no-bin 3.8.20 > "$xu_model_env/python-install.log" 2>&1
"$xu_model_env/bootstrap/bin/uv" venv --python 3.8.20 "$xu_model_env/venv-kwt" > "$xu_model_env/venv-create.log" 2>&1
"$xu_model_env/bootstrap/bin/uv" pip sync --python "$xu_model_env/venv-kwt/bin/python" \
  --index-url https://pypi.org/simple "$xu_model_repo/tools/model/requirements-kwt-py38.lock" \
  > "$xu_model_env/dependency-sync.log" 2>&1
"$xu_model_env/venv-kwt/bin/python" "$xu_model_repo/tools/model/record_kwt_environment.py" \
  --lock "$xu_model_repo/tools/model/requirements-kwt-py38.lock" \
  --out "$xu_model_env/environment.json" > "$xu_model_env/environment-audit.log" 2>&1
TF_CPP_MIN_LOG_LEVEL=2 OMP_NUM_THREADS=2 TF_NUM_INTRAOP_THREADS=2 TF_NUM_INTEROP_THREADS=1 \
  "$xu_model_env/venv-kwt/bin/python" -c \
  'import tensorflow as tf, numpy as np, tensorflow_addons as tfa; print("IMPORT_PASS", tf.__version__, np.__version__, tfa.__version__)' \
  > "$xu_model_env/dependency-import.log" 2>&1
cat "$xu_model_env/environment-audit.log" "$xu_model_env/dependency-import.log"
echo "xu inference interpreter: $xu_model_env/venv-kwt/bin/python"
