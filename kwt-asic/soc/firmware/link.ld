OUTPUT_ARCH(riscv)
ENTRY(_start)
MEMORY { ILM (rx) : ORIGIN = 0x80000000, LENGTH = 64K
         DLM (rw) : ORIGIN = 0x90000000, LENGTH = 64K }
SECTIONS {
 .text : { KEEP(*(.init)) *(.text*) *(.rodata*) } > ILM
 .data : { *(.sdata*) *(.data*) } > DLM
 .bss (NOLOAD) : { *(.sbss*) *(.bss*) *(COMMON) } > DLM
 __stack_top = ORIGIN(DLM) + LENGTH(DLM) - 16;
}
