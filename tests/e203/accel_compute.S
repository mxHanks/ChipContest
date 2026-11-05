.section .text.init
.globl _start
.option rvc

_start:
    j main

    # Testbench detects PC == 0x80000086.
    .org 0x86
write_tohost:
    j write_tohost


.section .text
.align 2

main:
    # Base address
    li t0, 0x10042000

    # --------------------------------------------------
    # 1. Load X[0..63] = 1
    # X_ADDR = 0x14, X_DATA = 0x18
    # --------------------------------------------------
    li t1, 1
    li t2, 0
    li t3, 64

x_load_loop:
    sw t2, 0x14(t0)
    sw t1, 0x18(t0)
    addi t2, t2, 1
    blt t2, t3, x_load_loop

    # --------------------------------------------------
    # 2. Load W[bank][0..63] = 1
    # W_BANK = 0x1C, W_ADDR = 0x20, W_DATA = 0x24
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
    # 3. Bias[j] = j for j = 0..7
    # BIAS_INDEX = 0x28, BIAS_LO = 0x2C
    # --------------------------------------------------
    li t2, 0
    li t3, 8

bias_loop:
    sw t2, 0x28(t0)
    sw t2, 0x2C(t0)
    addi t2, t2, 1
    blt t2, t3, bias_loop

    # Use output group 0
    sw zero, 0x10(t0)

    # Clear sticky DONE, then START
    li t1, 2
    sw t1, 0x0C(t0)

    li t1, 1
    sw t1, 0x08(t0)

    # --------------------------------------------------
    # 4. Poll STATUS.DONE (bit 1)
    # STATUS = 0x0C
    # --------------------------------------------------
    li t5, 100000

poll_done:
    lw t2, 0x0C(t0)
    andi t3, t2, 2
    bnez t3, verify_results

    addi t5, t5, -1
    bnez t5, poll_done

    # Timeout
    li gp, 5
    j write_tohost

    # --------------------------------------------------
    # 5. Verify result[j] = 64 + j
    # RESULT_INDEX = 0x34
    # RESULT_LO = 0x38
    # RESULT_HI = 0x3C
    # --------------------------------------------------
verify_results:
    li t2, 0
    li t3, 8

result_loop:
    sw t2, 0x34(t0)

    lw t4, 0x38(t0)
    addi t5, t2, 64
    bne t4, t5, fail_result

    # High 16 result bits should be zero.
    lw t6, 0x3C(t0)
    bnez t6, fail_result

    addi t2, t2, 1
    blt t2, t3, result_loop

    # PASS
    li gp, 1
    j write_tohost

fail_result:
    li gp, 4
    j write_tohost
