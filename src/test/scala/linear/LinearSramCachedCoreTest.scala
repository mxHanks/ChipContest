package linear

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import org.scalatest.funspec.AnyFunSpec

class LinearSramCachedCoreTest extends AnyFunSpec with ChiselSim {
    describe("xu SRAM cached compute core") {
        it("selects legacy or per-group signed40 biases without changing MAC results") {
            simulate(new LinearSramCachedCore) { dut =>
                dut.io.start.poke(false.B)
                dut.io.group.poke(0.U)
                dut.io.cacheEnable.poke(false.B)
                dut.io.cacheWriteEnable.poke(false.B)
                dut.io.cacheWriteAddr.poke(0.U)
                dut.io.cacheWriteData.poke(0.U)
                dut.io.cacheWriteMask.poke(31.U)
                dut.io.cacheReadAddr.poke(0.U)
                dut.io.cacheReadEnable.poke(false.B)
                dut.io.xLoadWen.poke(false.B)
                dut.io.xLoadAddr.poke(0.U)
                dut.io.xLoadData.poke(0.S)
                dut.io.wLoadWen.poke(false.B)
                dut.io.wLoadBank.poke(0.U)
                dut.io.wLoadAddr.poke(0.U)
                dut.io.wLoadData.poke(0.S)
                for (lane <- 0 until 8) dut.io.bias(lane).poke((lane - 7).S)

                for (k <- 0 until 64) {
                    dut.io.xLoadWen.poke(true.B)
                    dut.io.xLoadAddr.poke(k.U)
                    dut.io.xLoadData.poke((k - 32).S)
                    dut.clock.step()
                }
                dut.io.xLoadWen.poke(false.B)
                val groups = Seq(0, 15, 16, 31)
                for (group <- groups; lane <- 0 until 8; k <- 0 until 64) {
                    dut.io.wLoadWen.poke(true.B)
                    dut.io.wLoadBank.poke(lane.U)
                    dut.io.wLoadAddr.poke((group * 64 + k).U)
                    dut.io.wLoadData.poke((group - lane - k).S)
                    dut.clock.step()
                }
                dut.io.wLoadWen.poke(false.B)

                def bias(task: Int, addr: Int): BigInt = {
                    if (addr == 0) -(BigInt(1) << 39) + task
                    else if (addr == 255) (BigInt(1) << 39) - 1 - task
                    else BigInt((if (addr % 2 == 0) 1 else -1) * (task * 1000 + addr))
                }
                for (task <- 0 until 2) {
                    for (addr <- 0 until 256) {
                        dut.io.cacheWriteEnable.poke(true.B)
                        dut.io.cacheWriteAddr.poke(addr.U)
                        dut.io.cacheWriteData.poke((bias(task, addr) & ((BigInt(1) << 40) - 1)).U)
                        dut.clock.step()
                    }
                    dut.io.cacheWriteEnable.poke(false.B)
                    for (enabled <- Seq(false, true); group <- groups) {
                        dut.io.cacheEnable.poke(enabled.B)
                        dut.io.group.poke(group.U)
                        dut.io.start.poke(true.B)
                        dut.clock.step()
                        dut.io.start.poke(false.B)
                        var cycles = 0
                        while (!dut.io.done.peek().litToBoolean && cycles < 85) {
                            // Unrelated readback must never replace the compute tile.
                            dut.io.cacheReadEnable.poke((cycles % 3 == 0).B)
                            dut.io.cacheReadAddr.poke(((255 - group * 8) & 255).U)
                            dut.clock.step()
                            cycles += 1
                        }
                        assert(dut.io.done.peek().litToBoolean, s"group $group timed out")
                        assert(cycles == (if (enabled) 68 else 66), s"unexpected latency $cycles")
                        dut.io.cacheReadEnable.poke(false.B)
                        for (lane <- 0 until 8) {
                            val dot = (0 until 64).map(k => (k - 32) * (group - lane - k)).sum
                            val initial = if (enabled) bias(task, group * 8 + lane) else BigInt(lane - 7)
                            dut.io.result(lane).expect((initial + dot).S)
                        }
                        dut.clock.step()
                        dut.io.done.expect(false.B)
                    }
                }
            }
        }
    }
}
