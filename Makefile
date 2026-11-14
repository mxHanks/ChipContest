.PHONY: help verify ingress vectors check-vectors cpu mapped

PYTHON ?= python3
OUT ?= build/1064
JOBS ?= 2

help:
	@echo '1064 candidate: make verify | ingress | vectors | check-vectors | cpu | mapped'
	@echo 'Generated directories must not exist; override OUT=build/another-run as needed.'

verify:
	$(PYTHON) -B tools/current.py verify --submodule

ingress:
	$(PYTHON) -B tools/current.py ingress

vectors:
	$(PYTHON) -B tools/current.py vectors --out $(OUT)/vectors

check-vectors:
	$(PYTHON) -B tools/current.py check-vectors --vectors $(OUT)/vectors

cpu:
	$(PYTHON) -B tools/current.py cpu --vectors $(OUT)/vectors --out $(OUT)/full12 --tasks 12 --jobs $(JOBS)

mapped:
	$(PYTHON) -B tools/current.py unpack-mapped --out $(OUT)/final-mapped
