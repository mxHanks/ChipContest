.section .init,"ax",@progbits
.global _start
_start:
  la sp, __stack_top
  la t0, trap_handler
  csrw mtvec, t0
  call main
.balign 4
trap_handler:
  csrr t1, mcause
  lui t0, 0xa0080
  addi t0, t0, -256
  ori t1, t1, 0x400
  sw t1, 4(t0)
1: j 1b
