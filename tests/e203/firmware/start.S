.section .text.init
.globl _start
.option rvc
_start:
    la sp, __stack_top
    la t0, __bss_start
    la t1, __bss_end
1:  bgeu t0, t1, 2f
    sw zero, 0(t0)
    addi t0, t0, 4
    j 1b
2:  call main
    mv gp, a0
    j write_tohost
    .org 0x86
.globl write_tohost
write_tohost:
    j write_tohost
