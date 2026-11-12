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
2:
    # Define the incoming ABI callee-saved state before C saves it to DTCM.
    # Real instructions keep valid SRAM writes/epilogue loads free of X.
    li s0, 0
    li s1, 0
    li s2, 0
    li s3, 0
    li s4, 0
    li s5, 0
    li s6, 0
    li s7, 0
    li s8, 0
    li s9, 0
    li s10, 0
    li s11, 0
    call main
    mv gp, a0
    j write_tohost
    .org 0x86
.globl write_tohost
write_tohost:
    j write_tohost
