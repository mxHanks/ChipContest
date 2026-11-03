package linear

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import org.scalatest.funspec.AnyFunSpec

class XuParallelAutoGroupCoreTest extends AnyFunSpec with ChiselSim {
    describe("xu single-W 32-lane 8-group producer") {
        it("backpressures two slots, retains all signed48 lanes, and returns to manual START") {
            simulate(new XuParallelAutoGroupCore(32)) { dut =>
                dut.io.start.poke(false.B)
                dut.io.rowStart.poke(false.B)
                dut.io.rowWide.poke(true.B)
                dut.io.rowPop.poke(false.B)
                dut.io.group.poke(0.U)
                dut.io.cacheEnable.poke(true.B)
                dut.io.cacheWriteEnable.poke(false.B)
                dut.io.cacheWriteAddr.poke(0.U)
                dut.io.cacheWriteData.poke(0.U)
                dut.io.cacheWriteMask.poke(31.U)
                dut.io.cacheReadAddr.poke(0.U)
                dut.io.xLoadWen.poke(false.B)
                dut.io.xLoadAddr.poke(0.U)
                dut.io.xLoadData.poke(0.S)
                dut.io.wLoadWen.poke(false.B)
                dut.io.wLoadBank.poke(0.U)
                dut.io.wLoadAddr.poke(0.U)
                dut.io.wLoadData.poke(0.S)
                for (lane <- 0 until 8) dut.io.bias(lane).poke(0.S)

                def x(row: Int, k: Int): Int =
                    if (k == 0) -32768 else if (k == 63) 32767 else row * 11 + k - 32
                def w(g: Int, lane: Int, k: Int): Int =
                    if (k == lane) -32768 else if (k == 63 - lane) 32767 else g * 97 - lane * 5 - k
                def bias(row: Int, col: Int): BigInt =
                    (if (col % 2 == 0) -(BigInt(1) << 39) else (BigInt(1) << 39) - 1) +
                        (if (col % 2 == 0) row + col else -row - col)
                def expected(row: Int, g: Int, lane: Int): BigInt =
                    bias(row, g * 32 + lane) + (0 until 64).map(k => BigInt(x(row, k)) * w((g * 32 + lane) / 8, lane % 8, k)).sum

                for (g <- 0 until 32; lane <- 0 until 8; k <- 0 until 64) {
                    dut.io.wLoadWen.poke(true.B)
                    dut.io.wLoadBank.poke(lane.U)
                    dut.io.wLoadAddr.poke((g * 64 + k).U)
                    dut.io.wLoadData.poke(w(g, lane, k).S)
                    dut.clock.step()
                }
                dut.io.wLoadWen.poke(false.B)
                for (row <- 0 until 2) {
                    for (k <- 0 until 64) {
                        dut.io.xLoadWen.poke(true.B)
                        dut.io.xLoadAddr.poke(k.U)
                        dut.io.xLoadData.poke(x(row, k).S)
                        dut.clock.step()
                    }
                    dut.io.xLoadWen.poke(false.B)
                    for (col <- 0 until 256) {
                        dut.io.cacheWriteEnable.poke(true.B)
                        dut.io.cacheWriteAddr.poke(col.U)
                        dut.io.cacheWriteData.poke((bias(row, col) & ((BigInt(1) << 40) - 1)).U)
                        dut.clock.step()
                    }
                    dut.io.cacheWriteEnable.poke(false.B)
                    dut.io.rowStart.poke(true.B)
                    dut.clock.step()
                    dut.io.rowStart.poke(false.B)
                    dut.clock.step(200)
                    dut.io.rowCount.expect(2.U)
                    dut.io.rowProduced.expect(2.U)
                    dut.io.rowRunning.expect(false.B)
                    for (lane <- 0 until 32) dut.io.rowResult(lane).expect(expected(row, 0, lane).S)
                    dut.clock.step(200)
                    dut.io.rowProduced.expect(2.U)
                    for (g <- 0 until 8) {
                        var wait = 0
                        while (!dut.io.rowValid.peek().litToBoolean && wait < 80) {
                            dut.clock.step()
                            wait += 1
                        }
                        dut.io.rowValid.expect(true.B)
                        dut.io.rowGroup.expect(g.U)
                        dut.io.rowRetired.expect(g.U)
                        for (lane <- 0 until 32) dut.io.rowResult(lane).expect(expected(row, g, lane).S)
                        // Both rapid draining and consumer stalls; head remains stable.
                        dut.clock.step(if (g % 3 == 0) 85 else 1)
                        for (lane <- 0 until 32) dut.io.rowResult(lane).expect(expected(row, g, lane).S)
                        dut.io.rowPop.poke(true.B)
                        dut.clock.step()
                        dut.io.rowPop.poke(false.B)
                    }
                    dut.io.rowActive.expect(false.B)
                    dut.io.rowProduced.expect(8.U)
                    dut.io.rowRetired.expect(8.U)
                    dut.io.rowCount.expect(0.U)
                }
                dut.io.group.poke(19.U)
                dut.io.start.poke(true.B)
                dut.clock.step()
                dut.io.start.poke(false.B)
                dut.clock.step(66)
                dut.io.done.expect(true.B)
                for (lane <- 0 until 8) dut.io.result(lane).expect(expected(1, 19 / 4, (19 % 4) * 8 + lane).S)
                dut.io.group.poke(20.U)
                dut.clock.step(3)
                for (lane <- 0 until 8) dut.io.result(lane).expect(expected(1, 19 / 4, (19 % 4) * 8 + lane).S)
            }
        }
    }
}
