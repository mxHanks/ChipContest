# Original1064 development candidate: N3 physical PPA

The selected source is child5470c56 / parent1aceb3d, with the original64PE,
sixteen-X-SRAM core, four-slot ingress and DMA, and no storage21 overlay.
The old sealed package was N2/PW1 and cannot represent the measured N3 loader.
This new package activates `XU_SYSBUS_TEST_LOADER` and exposes its existing10
ICB ports (106bits) at the PPA top. The other158 compiled-source files and the full159-file order are
preserved. CPU/LSU/BIU/original fabric RTL are unchanged; all N3 ingress logic and
original result/bias register storage remain charged. This is a development
candidate, without SDK/production1000 qualification.

The measured CPU model used289 RAMSP models plus behavioral CPU RAM; native PPA
uses353 physical macros (CPU64 + shared256 + W16 + bias1 + X16). Adding SYNTHESIS
and using physical CPU SRAM adapters are explicit implementation/model differences.
The1064.3506 number remains a conditional150MHz development measurement, not a
STA result or a new physical-silicon measurement.

`prepare.py` stages only pinned inputs into a new directory. Local XML must prove
353 macros,64PE, eight engines, actual N3/PW2 and all106 loader interface bits.
DC/PT use the exact original150MHz SDC and DB identities; all new data ports fall
under its existing all_inputs/all_outputs IO budgets. No timing relaxation is
added. User subsequently authorized multicore for speed: cap8, eight Linux CPUs
while reserving at least two other allowed CPUs, and one own EDA stage at a time.
Native host-options reports and actual affinity are retained.

The DC run creates and explicitly flushes its own nonempty final.svf; it is a
required output and bound as input to same-map PT. Compilation remains
`compile_ultra -no_autoungroup`; source/area/timing/formal/power status is never
inherited from old353 or final374. Raw reports and known failed gates remain
visible. Report writing starts when actual DC completes and need not wait for
all later signoff stages.
