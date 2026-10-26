OUTPUT_ARCH(riscv)
ENTRY(_start)
MEMORY {
  ITCM (rx) : ORIGIN = 0x80000000, LENGTH = 64K
  DTCM (rw) : ORIGIN = 0x90000000, LENGTH = 64K
}
SECTIONS {
  .text : { *(.text.init) *(.text .text.*) *(.rodata .rodata.*) } > ITCM
  .data : { *(.data .data.*) } > DTCM
  .bss (NOLOAD) : {
    . = ALIGN(4); __bss_start = .;
    *(.bss .bss.*) *(COMMON)
    . = ALIGN(4); __bss_end = .;
  } > DTCM
  __stack_top = ORIGIN(DTCM) + LENGTH(DTCM) - 16;
  ASSERT(SIZEOF(.data) == 0, "startup does not copy initialized DTCM data")
}
