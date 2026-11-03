package linear

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import org.scalatest.funspec.AnyFunSpec

class XuParallel64AutoGroupCoreTest extends AnyFunSpec with ChiselSim {
    describe("xu independent 64PE producer with 8/32/64 contracts") {
        it("maps all W exactly once, preserves signed48 outputs and stalls all three modes") {
            simulate(new XuParallel64AutoGroupCore) { dut =>
                dut.io.start.poke(false.B); dut.io.rowStart.poke(false.B)
                dut.io.rowMode.poke(2.U); dut.io.rowPop.poke(false.B)
                dut.io.group.poke(0.U); dut.io.cacheEnable.poke(true.B)
                dut.io.cacheWriteEnable.poke(false.B); dut.io.cacheWriteAddr.poke(0.U)
                dut.io.cacheWriteData.poke(0.U); dut.io.cacheWriteMask.poke(31.U)
                dut.io.cacheReadAddr.poke(0.U); dut.io.xLoadWen.poke(false.B)
                dut.io.xLoadAddr.poke(0.U); dut.io.xLoadData.poke(0.S)
                dut.io.wLoadWen.poke(false.B); dut.io.wLoadBank.poke(0.U)
                dut.io.wLoadAddr.poke(0.U); dut.io.wLoadData.poke(0.S)
                for (lane <- 0 until 8) dut.io.bias(lane).poke(0.S)
                var width = 8
                var observedMacs = BigInt(0)
                def step(n: Int = 1): Unit = for (_ <- 0 until n) {
                    val fire = dut.io.macFire.peek().litToBoolean
                    dut.io.laneMacs.expect((if (fire) width else 0).U)
                    observedMacs += dut.io.laneMacs.peek().litValue
                    dut.clock.step()
                }
                def x(row: Int, k: Int): Int =
                    if (k == 0) -32768 else if (k == 63) 32767 else row * 11 + k - 32
                def w(col: Int, k: Int): Int = {
                    val lane = col % 8
                    if (k == lane) -32768 else if (k == 63 - lane) 32767 else (col / 8) * 97 - lane * 5 - k
                }
                def bias(row: Int, col: Int): BigInt =
                    (if (col % 2 == 0) -(BigInt(1) << 39) else (BigInt(1) << 39) - 1) +
                        (if (col % 2 == 0) row + col else -row - col)
                def expected(row: Int, col: Int): BigInt =
                    bias(row, col) + (0 until 64).map(k => BigInt(x(row, k)) * w(col, k)).sum
                for (g <- 0 until 32; lane <- 0 until 8; k <- 0 until 64) {
                    dut.io.wLoadWen.poke(true.B); dut.io.wLoadBank.poke(lane.U)
                    dut.io.wLoadAddr.poke((g * 64 + k).U)
                    dut.io.wLoadData.poke(w(g * 8 + lane, k).S); step()
                }
                dut.io.wLoadWen.poke(false.B)
                for (mode <- Seq(2, 1, 0); row <- 0 until 2) {
                    width = if (mode == 2) 64 else if (mode == 1) 32 else 8
                    val groups = 256 / width
                    dut.io.rowMode.poke(mode.U)
                    for (k <- 0 until 64) {
                        dut.io.xLoadWen.poke(true.B); dut.io.xLoadAddr.poke(k.U)
                        dut.io.xLoadData.poke(x(row, k).S); step()
                    }
                    dut.io.xLoadWen.poke(false.B)
                    for (col <- 0 until 256) {
                        dut.io.cacheWriteEnable.poke(true.B); dut.io.cacheWriteAddr.poke(col.U)
                        dut.io.cacheWriteData.poke((bias(row, col) & ((BigInt(1) << 40) - 1)).U); step()
                    }
                    dut.io.cacheWriteEnable.poke(false.B); dut.io.rowStart.poke(true.B)
                    step(); dut.io.rowStart.poke(false.B)
                    // Live input changes must not alter this owned row's mode.
                    dut.io.rowMode.poke(((mode + 1) % 3).U)
                    step(200); dut.io.rowCount.expect(2.U); dut.io.rowProduced.expect(2.U)
                    dut.io.rowRunning.expect(false.B); step(200); dut.io.rowProduced.expect(2.U)
                    for (g <- 0 until groups) {
                        var wait = 0
                        while (!dut.io.rowValid.peek().litToBoolean && wait < 80) { step(); wait += 1 }
                        dut.io.rowValid.expect(true.B); dut.io.rowGroup.expect(g.U)
                        dut.io.rowRetired.expect(g.U)
                        val offset = (g % (64 / width)) * width
                        for (lane <- 0 until width) dut.io.rowResult(offset + lane).expect(expected(row, g * width + lane).S)
                        step(if (g % 3 == 0) 85 else 1)
                        for (lane <- 0 until width) dut.io.rowResult(offset + lane).expect(expected(row, g * width + lane).S)
                        dut.io.rowPop.poke(true.B); step(); dut.io.rowPop.poke(false.B)
                    }
                    dut.io.rowActive.expect(false.B); dut.io.rowProduced.expect(groups.U)
                    dut.io.rowRetired.expect(groups.U); dut.io.rowCount.expect(0.U)
                }
                width = 8
                dut.io.group.poke(19.U); dut.io.start.poke(true.B); step()
                dut.io.start.poke(false.B); step(66); dut.io.done.expect(true.B)
                for (lane <- 0 until 8) dut.io.result(lane).expect(expected(1, 19 * 8 + lane).S)
                dut.io.group.poke(20.U); step(3)
                for (lane <- 0 until 8) dut.io.result(lane).expect(expected(1, 19 * 8 + lane).S)
                assert(observedMacs == 6 * 256 * 64 + 8 * 64)
            }
        }
    }
}
