.section .text.init
.globl _start
.option rvc

_start:
    j main

    # E203 testbench watches PC == 0x80000086.
    .org 0x86
write_tohost:
    j write_tohost

.section .text
.align 2

main:
    li t0, 0x10042000

    # --------------------------------------------------
    # 1. Load X[k] = 1, k = 0..63.
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
    # 2. Load weights:
    # GROUP 0: W[bank][k] = 1, address k
    # GROUP 1: W[bank][k] = 2, address 64 + k
    # --------------------------------------------------
    li s0, 0
    li s1, 8
    li s2, 64
    li t1, 1
    li t6, 2

weight_bank_loop:
    li t2, 0

weight_k_loop:
    sw s0, 0x1C(t0)       # W_BANK

    # GROUP 0: address 0..63
    sw t2, 0x20(t0)       # W_ADDR
    sw t1, 0x24(t0)       # W_DATA = 1

    # GROUP 1: address 64..127
    addi t3, t2, 64
    sw t3, 0x20(t0)       # W_ADDR
    sw t6, 0x24(t0)       # W_DATA = 2

    addi t2, t2, 1
    blt t2, s2, weight_k_loop

    addi s0, s0, 1
    blt s0, s1, weight_bank_loop

    # --------------------------------------------------
    # 3. Set Bias[j] = j, j = 0..7.
    # BIAS_INDEX = 0x28, BIAS_LO = 0x2C
    # --------------------------------------------------
    li t2, 0
    li t3, 8

bias_loop:
    sw t2, 0x28(t0)
    sw t2, 0x2C(t0)
    addi t2, t2, 1
    blt t2, t3, bias_loop

    # --------------------------------------------------
    # 4. Start GROUP 0.
    # CTRL = 0x08, STATUS = 0x0C, GROUP = 0x10.
    # STATUS.DONE is bit 1 and is write-one-to-clear.
    # --------------------------------------------------
    sw zero, 0x10(t0)

    li t1, 2
    sw t1, 0x0C(t0)       # Clear DONE

    li t1, 1
    sw t1, 0x08(t0)       # START

    li t5, 100000

poll_group0:
    lw t2, 0x0C(t0)
    andi t3, t2, 2
    bnez t3, check_group0

    addi t5, t5, -1
    bnez t5, poll_group0

    li gp, 5               # Timeout waiting for GROUP 0
    j write_tohost

    # --------------------------------------------------
    # 5. Check GROUP 0: result[j] == 64 + j.
    # RESULT_INDEX = 0x34, RESULT_LO = 0x38,
    # RESULT_HI = 0x3C.
    # --------------------------------------------------
check_group0:
    li t2, 0
    li t3, 8

check_group0_loop:
    sw t2, 0x34(t0)

    lw t4, 0x38(t0)
    addi t5, t2, 64
    bne t4, t5, fail_group0

    lw t6, 0x3C(t0)
    bnez t6, fail_group0

    addi t2, t2, 1
    blt t2, t3, check_group0_loop

    # --------------------------------------------------
    # 6. Start GROUP 1 without reloading X or Bias.
    # --------------------------------------------------
    li t1, 1
    sw t1, 0x10(t0)       # GROUP = 1

    li t1, 2
    sw t1, 0x0C(t0)       # Clear DONE

    li t1, 1
    sw t1, 0x08(t0)       # START

    li t5, 100000

poll_group1:
    lw t2, 0x0C(t0)
    andi t3, t2, 2
    bnez t3, check_group1

    addi t5, t5, -1
    bnez t5, poll_group1

    li gp, 7               # Timeout waiting for GROUP 1
    j write_tohost

    # --------------------------------------------------
    # 7. Check GROUP 1: result[j] == 128 + j.
    # --------------------------------------------------
check_group1:
    li t2, 0
    li t3, 8

check_group1_loop:
    sw t2, 0x34(t0)

    lw t4, 0x38(t0)
    addi t5, t2, 128
    bne t4, t5, fail_group1

    lw t6, 0x3C(t0)
    bnez t6, fail_group1

    addi t2, t2, 1
    blt t2, t3, check_group1_loop

    li gp, 1               # Both groups passed
    j write_tohost

fail_group0:
    li gp, 4
    j write_tohost

fail_group1:
    li gp, 6
    j write_tohost
