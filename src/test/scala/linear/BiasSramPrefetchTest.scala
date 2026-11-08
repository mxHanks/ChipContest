package linear

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import org.scalatest.funspec.AnyFunSpec
import scala.util.Random

class BiasSramPrefetchTest extends AnyFunSpec with ChiselSim {
    describe("S3 single-macro bias transactions and tagged prefetch") {
        it("preserves every byte mask, holds snapshots, retries invalidation, and clears real storage") {
            simulate(new BiasSramPrefetch) { dut =>
                val mask40 = (BigInt(1) << 40) - 1
                val expected = Array.fill[BigInt](256)(0)
                val random = new Random(3203)
                dut.io.computeActive.poke(false.B)
                dut.io.invalidate.poke(false.B)
                dut.io.clearValid.poke(false.B)
                dut.io.hostValid.poke(false.B)
                dut.io.hostRead.poke(true.B)
                dut.io.hostAddr.poke(0.U)
                dut.io.hostData.poke(0.U)
                dut.io.hostMask.poke(0.U)
                dut.io.rspReady.poke(false.B)
                dut.io.groupReqValid.poke(false.B)
                dut.io.groupReqTag.poke(0.U)
                dut.io.groupTake.poke(false.B)

                def waitFor(condition: => Boolean, limit: Int, what: String): Unit = {
                    var cycles = 0
                    while (!condition && cycles < limit) { dut.clock.step(); cycles += 1 }
                    assert(condition, s"$what timed out after $cycles cycles")
                }
                def signed(value: BigInt): BigInt =
                    if (value.testBit(39)) value - (BigInt(1) << 40) else value
                def begin(read: Boolean, addr: Int, data: BigInt = 0, mask: Int = 31): Unit = {
                    dut.io.hostRead.poke(read.B)
                    dut.io.hostAddr.poke(addr.U)
                    dut.io.hostData.poke((data & mask40).U)
                    dut.io.hostMask.poke(mask.U)
                    dut.io.hostValid.poke(true.B)
                    waitFor(dut.io.hostReady.peek().litToBoolean, 200, "host command")
                    dut.clock.step()
                    dut.io.hostValid.poke(false.B)
                    // The accepted descriptor must survive changes on every input.
                    dut.io.hostAddr.poke(((addr + 113) % 256).U)
                    dut.io.hostData.poke((mask40 ^ (data & mask40)).U)
                    dut.io.hostMask.poke((mask ^ 31).U)
                    dut.io.hostRead.poke((!read).B)
                }
                def finish(error: Boolean = false): BigInt = {
                    waitFor(dut.io.rspValid.peek().litToBoolean, 200, "host response")
                    dut.io.rspError.expect(error.B)
                    val snapshot = dut.io.rspData.peek().litValue
                    for (_ <- 0 until 3) {
                        dut.clock.step()
                        dut.io.rspValid.expect(true.B)
                        dut.io.rspError.expect(error.B)
                        dut.io.rspData.expect(snapshot.U)
                    }
                    dut.io.rspReady.poke(true.B)
                    dut.clock.step()
                    dut.io.rspReady.poke(false.B)
                    snapshot
                }
                def write(addr: Int, data: BigInt, mask: Int): Unit = {
                    begin(false, addr, data, mask)
                    finish()
                    val bytes = (0 until 5).filter(i => (mask & (1 << i)) != 0)
                        .foldLeft(BigInt(0))((value, i) => value | (BigInt(255) << (i * 8)))
                    expected(addr) = (expected(addr) & (mask40 ^ bytes)) | (data & bytes)
                }
                def read(addr: Int): Unit = { begin(true, addr); assert(finish() == expected(addr)) }
                def request(group: Int): Unit = {
                    dut.io.groupReqTag.poke(group.U)
                    dut.io.groupReqValid.poke(true.B)
                    waitFor(dut.io.groupReqReady.peek().litToBoolean, 200, "group request")
                    dut.clock.step()
                    dut.io.groupReqValid.poke(false.B)
                }
                def checkGroup(group: Int): Unit = {
                    waitFor(dut.io.groupValid.peek().litToBoolean, 200, "group fill")
                    dut.io.groupTag.expect(group.U)
                    dut.io.groupEpoch.expect(dut.io.epoch.peek().litValue.U)
                    for (lane <- 0 until 8)
                        dut.io.groupBias(lane).expect(signed(expected(group * 8 + lane)).S)
                }
                def take(): Unit = {
                    dut.io.groupTake.poke(true.B); dut.clock.step(); dut.io.groupTake.poke(false.B)
                }

                // Every legal physical entry is initialized before any partial write.
                for (addr <- 0 until 256) {
                    val value = if (addr == 0) BigInt(1) << 39 else
                        if (addr == 255) (BigInt(1) << 39) - 1 else BigInt(40, random)
                    write(addr, value, 31)
                }
                for (addr <- 0 until 256; mask <- 0 until 32) {
                    write(addr, BigInt(40, random), mask)
                    read(addr)
                }
                // Retire the old read and accept a different read on exactly
                // the same edge. Its descriptor must not inherit the old word
                // index or partially assembled payload.
                begin(true, 23)
                waitFor(dut.io.rspValid.peek().litToBoolean, 200, "first consecutive read")
                dut.io.rspData.expect(expected(23).U)
                dut.io.hostRead.poke(true.B)
                dut.io.hostAddr.poke(219.U)
                dut.io.hostData.poke(0.U)
                dut.io.hostMask.poke(31.U)
                dut.io.hostValid.poke(true.B)
                dut.io.rspReady.poke(true.B)
                dut.io.hostReady.expect(true.B)
                dut.io.rspValid.expect(true.B)
                dut.clock.step() // old response retirement + new command acceptance
                dut.io.hostValid.poke(false.B)
                dut.io.rspReady.poke(false.B)
                dut.io.hostAddr.poke(0.U)
                dut.io.hostRead.poke(false.B)
                assert(finish() == expected(219), "New read reused the retired read descriptor")
                // A held response cannot monopolize the SRAM port or alter its snapshot.
                begin(true, 91)
                waitFor(dut.io.rspValid.peek().litToBoolean, 200, "held read")
                val held = dut.io.rspData.peek().litValue
                request(0); checkGroup(0)
                dut.clock.step(60) // finish prefetch of group 1 while current is owned
                checkGroup(0)
                dut.io.rspData.expect(held.U)
                assert(finish() == expected(91))
                take()
                for (group <- 1 until 32) {
                    request(group); checkGroup(group)
                    dut.clock.step(if (group % 3 == 0) 55 else 1)
                    checkGroup(group); take()
                }

                request(7)
                dut.clock.step(7)
                dut.io.invalidate.poke(true.B); dut.clock.step(); dut.io.invalidate.poke(false.B)
                checkGroup(7) // stale in-flight fill is discarded and the demand retried
                val before = dut.io.epoch.peek().litValue
                dut.io.computeActive.poke(true.B)
                begin(false, 56, 0, 31); finish(error = true)
                dut.io.epoch.expect(before.U)
                checkGroup(7)
                dut.io.computeActive.poke(false.B)
                take()

                // A legal host update invalidates an already prefetched next group.
                write(64, BigInt("fe12345678", 16), 31)
                request(8); checkGroup(8); take()

                // Reset cancels protocol ownership but does not erase the macro.
                request(11); checkGroup(11)
                dut.reset.poke(true.B); dut.clock.step(2); dut.reset.poke(false.B)
                dut.io.groupValid.expect(false.B)
                dut.io.rspValid.expect(false.B)
                request(11); checkGroup(11); take()

                dut.io.clearValid.poke(true.B)
                waitFor(dut.io.clearReady.peek().litToBoolean, 200, "clear acceptance")
                dut.clock.step(); dut.io.clearValid.poke(false.B)
                waitFor(dut.io.clearDone.peek().litToBoolean, 800, "768-word clear")
                for (addr <- 0 until 256) { expected(addr) = 0; read(addr) }
                for (group <- 0 until 32) { request(group); checkGroup(group); take() }
            }
        }
    }
}
