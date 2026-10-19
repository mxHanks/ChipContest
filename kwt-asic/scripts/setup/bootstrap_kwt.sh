#!/usr/bin/env bash
# Isolated legacy-model environment; no global Python or shell configuration.
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$project_root"
python3 -m venv .venv
if [[ ! -x .venv/bin/uv ]]; then
  .venv/bin/python -m pip install uv==0.13.1
fi
export UV_PYTHON_INSTALL_DIR="$project_root/.tools/python"
export UV_CACHE_DIR="$project_root/.tools/uv-cache"
.venv/bin/uv python install --no-bin 3.8.20
if [[ ! -f .venv-kwt/pyvenv.cfg ]]; then
  .venv/bin/uv venv --python 3.8.20 .venv-kwt
fi
if [[ -f env/requirements-kwt.lock ]]; then
  .venv/bin/uv pip sync --python .venv-kwt/bin/python --index-url https://pypi.org/simple env/requirements-kwt.lock
else
  .venv/bin/uv pip install --python .venv-kwt/bin/python --index-url https://pypi.org/simple -r env/requirements-kwt.in
fi
TF_CPP_MIN_LOG_LEVEL=2 OMP_NUM_THREADS=2 TF_NUM_INTRAOP_THREADS=2 TF_NUM_INTEROP_THREADS=1 \
  .venv-kwt/bin/python -c 'import tensorflow as tf, numpy as np; print("TensorFlow", tf.__version__, "NumPy", np.__version__)'
