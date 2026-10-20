.section .text.init
.globl _start
.option rvc

_start:
    j main

    # E203 testbench watches PC = 0x80000086.
    .org 0x86
write_tohost:
    j write_tohost

.section .text
.align 2

main:
    li t0, 0x10042000

    # --------------------------------------------------
    # Load X[k] = 1, k = 0..63
    # --------------------------------------------------
    li t1, 1
    li t2, 0
    li t3, 64

x_load_one:
    sw t2, 0x14(t0)
    sw t1, 0x18(t0)
    addi t2, t2, 1
    blt t2, t3, x_load_one

    # --------------------------------------------------
    # Load all 8 banks: W[bank][k] = 1
    # --------------------------------------------------
    li t4, 0
    li t5, 8
    li s0, 64

weight_bank_loop:
    li t6, 0

weight_addr_loop:
    sw t4, 0x1C(t0)
    sw t6, 0x20(t0)
    sw t1, 0x24(t0)
    addi t6, t6, 1
    blt t6, s0, weight_addr_loop

    addi t4, t4, 1
    blt t4, t5, weight_bank_loop

    # --------------------------------------------------
    # Load Bias[j] = j, j = 0..7
    # --------------------------------------------------
    li t2, 0
    li t3, 8

bias_loop:
    sw t2, 0x28(t0)
    sw t2, 0x2C(t0)
    addi t2, t2, 1
    blt t2, t3, bias_loop

    # --------------------------------------------------
    # First run: X = 1; expect result[j] = 64 + j
    # --------------------------------------------------
    sw zero, 0x10(t0)       # GROUP = 0
    li t1, 2
    sw t1, 0x0C(t0)         # Clear sticky DONE
    li t1, 1
    sw t1, 0x08(t0)         # START

    li t5, 100000

poll_first:
    lw t2, 0x0C(t0)
    andi t3, t2, 2
    bnez t3, verify_first

    addi t5, t5, -1
    bnez t5, poll_first

    li gp, 5                # First run timeout
    j write_tohost

verify_first:
    li t2, 0
    li t3, 8

first_result_loop:
    sw t2, 0x34(t0)         # RESULT_INDEX

    lw t4, 0x38(t0)         # RESULT_LO
    addi t5, t2, 64
    bne t4, t5, fail_first

    lw t6, 0x3C(t0)         # RESULT_HI
    bnez t6, fail_first

    addi t2, t2, 1
    blt t2, t3, first_result_loop

    # --------------------------------------------------
    # Reload X[k] = 2; retain existing weights and bias
    # --------------------------------------------------
    li t1, 2
    li t2, 0
    li t3, 64

x_load_two:
    sw t2, 0x14(t0)
    sw t1, 0x18(t0)
    addi t2, t2, 1
    blt t2, t3, x_load_two

    # --------------------------------------------------
    # Second run: X = 2; expect result[j] = 128 + j
    # --------------------------------------------------
    li t1, 2
    sw t1, 0x0C(t0)         # Clear DONE
    li t1, 1
    sw t1, 0x08(t0)         # START again

    li t5, 100000

poll_second:
    lw t2, 0x0C(t0)
    andi t3, t2, 2
    bnez t3, verify_second

    addi t5, t5, -1
    bnez t5, poll_second

    li gp, 7                # Second run timeout
    j write_tohost

verify_second:
    li t2, 0
    li t3, 8

second_result_loop:
    sw t2, 0x34(t0)         # RESULT_INDEX

    lw t4, 0x38(t0)         # RESULT_LO
    addi t5, t2, 128
    bne t4, t5, fail_second

    lw t6, 0x3C(t0)         # RESULT_HI
    bnez t6, fail_second

    addi t2, t2, 1
    blt t2, t3, second_result_loop

    li gp, 1                # Both runs passed
    j write_tohost

fail_first:
    li gp, 4
    j write_tohost

fail_second:
    li gp, 6
    j write_tohost
