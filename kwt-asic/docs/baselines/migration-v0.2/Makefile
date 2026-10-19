SHELL := /bin/bash
PYTHON := python3
RELEASE := migration-v0.2
KWT_EXPORT ?= artifacts/runs/kwt-export-$(shell date -u +%Y%m%dT%H%M%S)-$(shell cat /proc/sys/kernel/random/uuid | cut -c1-8)
.PHONY: help setup setup-kwt doctor verify host rtl linear linear-four-state linear-real export-kwt test fetch-kwt harness checkpoint package
help:
	@echo 'setup: project-local tools; doctor: inventory; verify/host/rtl: cumulative validation'
	@echo 'harness: check task evidence; checkpoint/package: create source snapshots'
	@echo 'linear/linear-four-state: new full-shape RTL; test: software and runner tests; fetch-kwt: pinned model files'
	@echo 'linear-real: replay bundled 12-layer silence vectors; setup-kwt/export-kwt: restore original model and regenerate'
setup:
	bash scripts/setup/bootstrap.sh --download
setup-kwt:
	bash scripts/setup/bootstrap_kwt.sh
doctor:
	source env/activate.sh && $(PYTHON) scripts/env/doctor.py --require hdl --json artifacts/environment.json
verify:
	source env/activate.sh && $(PYTHON) scripts/verify/run_checks.py --tier static
host:
	source env/activate.sh && $(PYTHON) scripts/verify/run_checks.py --tier host
rtl:
	source env/activate.sh && $(PYTHON) scripts/verify/run_checks.py --tier rtl --jobs 2
linear:
	source env/activate.sh && $(PYTHON) scripts/verify/run_linear.py --tasks 12
linear-four-state:
	source env/activate.sh && $(PYTHON) scripts/verify/run_linear.py --simulator iverilog --tasks 2
linear-real:
	source env/activate.sh && $(PYTHON) scripts/verify/run_exported_linear.py --vectors-dir sim/vectors/kwt-silence-v1 --source-root vendor/kwt1-237e4097
export-kwt:
	TF_CPP_MIN_LOG_LEVEL=2 PYTHONDONTWRITEBYTECODE=1 .venv-kwt/bin/python scripts/model/export_kwt.py --source vendor/kwt1-237e4097 --output "$(KWT_EXPORT)"
test:
	$(PYTHON) -B -m unittest discover -s tests -v
fetch-kwt:
	$(PYTHON) scripts/model/fetch_kwt.py --fetch
harness:
	$(PYTHON) scripts/harness.py validate
checkpoint:
	$(PYTHON) scripts/harness.py checkpoint --label $(RELEASE)
package:
	$(PYTHON) scripts/harness.py package --label $(RELEASE)
