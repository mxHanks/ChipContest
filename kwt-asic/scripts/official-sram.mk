# Separate intake entry preserves the frozen development Make/source identity.
SHELL := /bin/bash
PYTHON ?= python3
SRAM_STAGE ?= all
SRAM_PACKAGE ?= configs/official-sram-package.json
.PHONY: inspect-official-sram
inspect-official-sram:
	source env/activate.sh && $(PYTHON) -B scripts/verify/official_sram_inputs.py --manifest "$(SRAM_PACKAGE)" --stage "$(SRAM_STAGE)"
