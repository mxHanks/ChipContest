#!/usr/bin/env bash
# Source in Bash: source env/activate.sh. No persistent/global configuration changes.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    echo "Use: source env/activate.sh" >&2
    exit 1
fi

_kwt_project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
for _kwt_bin_dir in "${_kwt_project_root}/.tools/bin" "${_kwt_project_root}/.venv/bin"; do
    if [[ -d "${_kwt_bin_dir}" ]]; then
        case ":${PATH}:" in
            *":${_kwt_bin_dir}:"*) ;;
            *) export PATH="${_kwt_bin_dir}:${PATH}" ;;
        esac
    fi
done
if [[ -d "${_kwt_project_root}/.venv" ]]; then
    export VIRTUAL_ENV="${_kwt_project_root}/.venv"
fi
unset _kwt_bin_dir _kwt_project_root
