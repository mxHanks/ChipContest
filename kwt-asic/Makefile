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

.PHONY: synth-memory-blackbox synth-logic synth-ff-reference synth-ff-full-reference setup-opensta sta-logic
.PHONY: synth-minimum-reference synth-counter-hold-reference synth-slew-reference
synth-minimum-reference:
	@test -n "$(MAPPING_REPORT)" || { echo 'Set MAPPING_REPORT to the accepted original mapping'; exit 2; }
	source env/activate.sh && $(PYTHON) scripts/synth/run_sram_minimum_candidate.py --mapping-report "$(MAPPING_REPORT)"
synth-counter-hold-reference:
	@test -n "$(MAPPING_REPORT)" || { echo 'Set MAPPING_REPORT to the structural minimum-delay candidate'; exit 2; }
	source env/activate.sh && $(PYTHON) scripts/synth/run_sram_counter_hold_candidate.py --mapping-report "$(MAPPING_REPORT)"
synth-slew-reference:
	@test -n "$(MAPPING_REPORT)" || { echo 'Set MAPPING_REPORT to the structural counter-hold candidate'; exit 2; }
	source env/activate.sh && $(PYTHON) scripts/synth/run_sram_resize_candidate.py --mapping-report "$(MAPPING_REPORT)"
synth-cap-reference:
	@test -n "$(MAPPING_REPORT)" -a -n "$(CAP_REPORT)" -a -n "$(CAP_TARGETS)" || { echo 'Set MAPPING_REPORT, CAP_REPORT and CAP_TARGETS to the bound measured candidate inputs'; exit 2; }
	source env/activate.sh && $(PYTHON) scripts/synth/run_sram_cap_candidate.py --mapping-report "$(MAPPING_REPORT)" --cap-report "$(CAP_REPORT)" --targets "$(CAP_TARGETS)"
check-reference-electrical:
	@test -n "$(STA_REPORT)" || { echo 'Set STA_REPORT to the completed actual macro-cut partial-STA result.json'; exit 2; }
	source env/activate.sh && $(PYTHON) scripts/verify/reference_electrical/run.py --sta-report "$(STA_REPORT)"
synth-memory-blackbox:
	source env/activate.sh && $(PYTHON) scripts/synth/run_memory_blackbox.py --timeout 300
synth-logic:
	source env/activate.sh && $(PYTHON) scripts/synth/run_memory_blackbox.py --include-interface --map-logic --timeout 300
synth-ff-reference:
	source env/activate.sh && $(PYTHON) scripts/synth/run_memory_ff_reference.py --map-logic --timeout 120
# Explicit opt-in: makes the otherwise dangerous full-capacity FF expansion visible.
synth-ff-full-reference:
	@test "$(ALLOW_FULL_FF)" = "1" || { echo 'Full FF expansion requires ALLOW_FULL_FF=1'; exit 2; }
	source env/activate.sh && $(PYTHON) scripts/synth/run_memory_ff_reference.py --full-engine --allow-full-ff --timeout 120 --memory-limit-mib 4096
setup-opensta:
	$(PYTHON) scripts/setup/bootstrap_opensta.py --download
sta-logic:
	@test -n "$(MAPPING_REPORT)" || { echo 'Set MAPPING_REPORT to the successful matching blackbox mapping result.json'; exit 2; }
	source env/activate.sh && $(PYTHON) scripts/synth/run_memory_partial_sta.py --mapping-report "$(MAPPING_REPORT)" --timeout 120

.PHONY: test-memory
test-memory:
	source env/activate.sh && $(PYTHON) scripts/verify/run_memory_tests.py

# Post-synthesis zero-delay replay uses an explicit accepted mapping identity.
MAPPED_TASKS ?= 12
MAPPED_REUSE ?=
.PHONY: test-mapped test-mapped-negative test-mapped-checker
test-mapped:
	@test -n "$(MAPPING_REPORT)" || { echo 'Set MAPPING_REPORT to the accepted full-interface result.json'; exit 2; }
	source env/activate.sh && $(PYTHON) $(if $(strip $(MAPPED_REUSE)),scripts/verify/run_sram_mapped_replay.py,scripts/verify/run_sram_mapped.py) --mapping-report "$(MAPPING_REPORT)" --tasks "$(MAPPED_TASKS)" --vectors-dir "$(SRAM_VECTORS)" $(if $(strip $(MAPPED_REUSE)),--reuse-build "$(MAPPED_REUSE)")
test-mapped-negative:
	@test -n "$(MAPPED_REUSE)" || { echo 'Set MAPPED_REUSE to a completed positive replay result.json'; exit 2; }
	source env/activate.sh && $(PYTHON) scripts/verify/run_sram_mapped_negative.py --positive-report "$(MAPPED_REUSE)"
test-mapped-checker:
	source env/activate.sh && $(PYTHON) scripts/verify/run_mapped_checker_tests.py

# SRAM-isolated candidate; the migration-v0.2 and original rowpair targets above
# remain available. A full matrix regression runs sequentially (HDL jobs <= 2).
SRAM_VECTORS ?= sim/vectors/kwt-silence-v1
.PHONY: test-linear test-linear-ff test-icb test-soc test-soc-full regress
test-icb:
	source env/activate.sh && $(PYTHON) scripts/verify/run_sram_icb.py
test-linear:
	source env/activate.sh && $(PYTHON) scripts/verify/run_sram_engine.py --tasks 12 --vectors-dir "$(SRAM_VECTORS)" --stalls random
test-linear-ff:
	source env/activate.sh && $(PYTHON) scripts/verify/run_sram_engine.py --backend ff --tasks 12 --vectors-dir "$(SRAM_VECTORS)" --stalls random
test-soc:
	source env/activate.sh && $(PYTHON) scripts/verify/run_sram_soc.py --tasks 2 --vectors-dir "$(SRAM_VECTORS)"
test-soc-full:
	source env/activate.sh && $(PYTHON) scripts/verify/run_sram_soc.py --tasks 12 --vectors-dir "$(SRAM_VECTORS)"
regress:
	$(MAKE) test
	$(MAKE) test-memory
	source env/activate.sh && $(PYTHON) scripts/verify/run_sram_regression.py --vectors-dir "$(SRAM_VECTORS)" --include-soc
