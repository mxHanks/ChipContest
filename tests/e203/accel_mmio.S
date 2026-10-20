.section .text.init
.globl _start
.option rvc

_start:
    # Test 1: read accelerator ID
    li   t0, 0x10042000
    lw   t1, 0(t0)
    li   t2, 0xACCE2030
    bne  t1, t2, fail_id

    # Test 2: write and read back scratch register
    li   t3, 0x12345678
    sw   t3, 4(t0)
    lw   t4, 4(t0)
    bne  t4, t3, fail_scratch

    # Both tests passed: x3 (gp) = 1
    li   gp, 1
    j    write_tohost

fail_id:
    li   gp, 2
    j    write_tohost

fail_scratch:
    li   gp, 3
    j    write_tohost

    # tb_top.v expects the test-ending PC to be 0x80000086.
    # Keep executing at that address until the testbench finishes.
    .org 0x86
write_tohost:
    j write_tohost
