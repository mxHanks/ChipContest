package linear

import chisel3._
import chisel3.simulator.Exceptions.AssertionFailed
import chisel3.simulator.scalatest.ChiselSim
import org.scalatest.funspec.AnyFunSpec

class LinearAutoGroupCoreTest extends AnyFunSpec with ChiselSim {
    describe("xu autonomous 32-group producer") {
        for (sram <- Seq(true, false)) it(s"backpressures two slots, retains signed48 lanes, and returns to manual START (SRAM=$sram)") {
            simulate(new LinearAutoGroupCore(useBiasSram = sram)) { dut =>
                dut.io.biasSramCapability.expect((if (sram) BigInt("42530001", 16) else BigInt(0)).U)
                dut.io.start.poke(false.B)
                dut.io.rowStart.poke(false.B)
                dut.io.rowPop.poke(false.B)
                dut.io.group.poke(0.U)
                dut.io.cacheEnable.poke(true.B)
                dut.io.cacheWriteEnable.poke(false.B)
                dut.io.cacheReadEnable.poke(false.B)
                dut.io.cacheRspReady.poke(true.B)
                dut.io.cacheInvalidate.poke(false.B)
                dut.io.cacheClearValid.poke(false.B)
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
                    bias(row, g * 8 + lane) + (0 until 64).map(k => BigInt(x(row, k)) * w(g, lane, k)).sum

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
                        var commandWait = 0
                        while (!dut.io.cacheCmdReady.peek().litToBoolean && commandWait < 100) {
                            dut.clock.step(); commandWait += 1
                        }
                        dut.io.cacheCmdReady.expect(true.B)
                        dut.clock.step()
                        dut.io.cacheWriteEnable.poke(false.B)
                        var responseWait = 0
                        while (!dut.io.cacheRspValid.peek().litToBoolean && responseWait < 100) {
                            dut.clock.step(); responseWait += 1
                        }
                        dut.io.cacheRspValid.expect(true.B)
                        dut.io.cacheRspError.expect(false.B)
                        dut.clock.step() // successful response retirement, then next descriptor
                    }
                    dut.io.cacheWriteEnable.poke(false.B)
                    dut.io.rowStart.poke(true.B)
                    dut.clock.step()
                    dut.io.rowStart.poke(false.B)
                    dut.clock.step(200)
                    dut.io.rowCount.expect(2.U)
                    dut.io.rowProduced.expect(2.U)
                    dut.io.rowRunning.expect(false.B)
                    for (lane <- 0 until 8) dut.io.rowResult(lane).expect(expected(row, 0, lane).S)
                    dut.clock.step(200)
                    dut.io.rowProduced.expect(2.U)
                    for (g <- 0 until 32) {
                        var wait = 0
                        while (!dut.io.rowValid.peek().litToBoolean && wait < 150) {
                            dut.clock.step()
                            wait += 1
                        }
                        dut.io.rowValid.expect(true.B)
                        dut.io.rowGroup.expect(g.U)
                        dut.io.rowRetired.expect(g.U)
                        for (lane <- 0 until 8) dut.io.rowResult(lane).expect(expected(row, g, lane).S)
                        // Both rapid draining and consumer stalls; head remains stable.
                        dut.clock.step(if (g % 3 == 0) 85 else 1)
                        for (lane <- 0 until 8) dut.io.rowResult(lane).expect(expected(row, g, lane).S)
                        dut.io.rowPop.poke(true.B)
                        dut.clock.step()
                        dut.io.rowPop.poke(false.B)
                    }
                    dut.io.rowActive.expect(false.B)
                    dut.io.rowProduced.expect(32.U)
                    dut.io.rowRetired.expect(32.U)
                    dut.io.rowCount.expect(0.U)
                }
                dut.io.group.poke(19.U)
                dut.io.start.poke(true.B)
                dut.clock.step()
                dut.io.start.poke(false.B)
                var manualWait = 0
                while (!dut.io.done.peek().litToBoolean && manualWait < 150) {
                    dut.clock.step(); manualWait += 1
                }
                dut.io.done.expect(true.B)
                for (lane <- 0 until 8) dut.io.result(lane).expect(expected(1, 19, lane).S)
            }
        }
        for (operation <- Seq("invalidate", "mode switch")) {
            it(s"rejects a $operation on the real manual compute INIT edge") {
                val failure = intercept[AssertionFailed] {
                    simulate(new LinearAutoGroupCore(useBiasSram = true)) { dut =>
                        dut.io.start.poke(false.B)
                        dut.io.rowStart.poke(false.B)
                        dut.io.rowPop.poke(false.B)
                        dut.io.group.poke(0.U)
                        dut.io.cacheEnable.poke(true.B)
                        dut.io.cacheWriteEnable.poke(false.B)
                        dut.io.cacheReadEnable.poke(false.B)
                        dut.io.cacheRspReady.poke(true.B)
                        dut.io.cacheInvalidate.poke(false.B)
                        dut.io.cacheClearValid.poke(false.B)
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
                        def waitFor(condition: => Boolean, what: String): Unit = {
                            var cycles = 0
                            while (!condition && cycles < 100) { dut.clock.step(); cycles += 1 }
                            assert(condition, s"$what timed out before illegal-control injection")
                        }
                        // Initialize the exact group that INIT will sample.
                        // This test terminates at INIT, before any MAC can use X/W.
                        for (lane <- 0 until 8) {
                            dut.io.cacheWriteEnable.poke(true.B)
                            dut.io.cacheWriteAddr.poke(lane.U)
                            dut.io.cacheWriteData.poke((lane + 3200).U)
                            waitFor(dut.io.cacheCmdReady.peek().litToBoolean, "bias write ready")
                            dut.clock.step(); dut.io.cacheWriteEnable.poke(false.B)
                            waitFor(dut.io.cacheRspValid.peek().litToBoolean, "bias write response")
                            dut.io.cacheRspError.expect(false.B)
                            dut.clock.step()
                        }
                        dut.io.start.poke(true.B); dut.clock.step(); dut.io.start.poke(false.B)
                        waitFor(dut.io.computeStart.peek().litToBoolean, "actual compute launch")
                        dut.clock.step() // MacController enters INIT; takeBias is now asserted.
                        dut.io.computeStart.expect(false.B)
                        if (operation == "invalidate") dut.io.cacheInvalidate.poke(true.B)
                        else dut.io.cacheEnable.poke(false.B)
                        dut.clock.step(2) // must fail at INIT, not silently lose the demand
                    }
                }
                val expectedMessage = if (operation == "invalidate")
                    "Bias invalidation requires an idle scheduler and no START"
                else "Bias mode switch requires an idle scheduler and no START"
                assert(failure.simulatorOutput.contains(expectedMessage),
                    s"Unexpected assertion instead of the $operation contract: ${failure.simulatorOutput}")
            }
        }
    }
}
