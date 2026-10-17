package lineear

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import linear.LinearLayerEngine
import org.scalatest.funspec.AnyFunSpec

class LinearLayerFullTest extends AnyFunSpec with ChiselSim {

    describe("LinearLayerEngine 完整矩阵测试") {

        it("应自动计算 99x256 个输出并与参考结果一致") {

            simulate(new LinearLayerEngine(99, 32)) { dut =>

                // 使用确定性的不同数据，便于复现错误
                def xValue(row: Int, k: Int): Int =
                    (row * 3 + k * 5) % 31 - 15

                def wValue(group: Int, bank: Int, k: Int): Int =
                    (group * 7 + bank * 11 + k * 3) % 29 - 14

                def biasValue(group: Int, bank: Int): Int =
                    group * 19 + bank * 7 - 200

                // 独立计算参考结果
                def expectedResult(
                                          row: Int,
                                          group: Int,
                                          bank: Int
                                  ): BigInt = {
                    val dot = (0 until 64).map { k =>
                        BigInt(xValue(row, k)) *
                                BigInt(wValue(group, bank, k))
                    }.sum

                    dot + BigInt(biasValue(group, bank))
                }

                // 初始化
                dut.io.start.poke(false.B)
                dut.io.rowLoaded.poke(false.B)
                dut.io.resultReady.poke(false.B)

                dut.io.xLoadWen.poke(false.B)
                dut.io.xLoadAddr.poke(0.U)
                dut.io.xLoadData.poke(0.S)

                dut.io.wLoadWen.poke(false.B)
                dut.io.wLoadBank.poke(0.U)
                dut.io.wLoadAddr.poke(0.U)
                dut.io.wLoadData.poke(0.S)

                for (j <- 0 until 8) {
                    dut.io.bias(j).poke(0.S)
                }

                // 1. 加载完整 W：64x256
                for (group <- 0 until 32) {
                    for (bank <- 0 until 8) {
                        for (k <- 0 until 64) {
                            dut.io.wLoadWen.poke(true.B)
                            dut.io.wLoadBank.poke(bank.U)
                            dut.io.wLoadAddr.poke((group * 64 + k).U)
                            dut.io.wLoadData.poke(
                                wValue(group, bank, k).S
                            )
                            dut.clock.step()
                        }
                    }
                }
                dut.io.wLoadWen.poke(false.B)

                // 2. 启动整个矩阵任务
                dut.io.start.poke(true.B)
                dut.clock.step()
                dut.io.start.poke(false.B)

                var checked = 0

                // 3. 自动处理全部 99 行
                for (row <- 0 until 99) {

                    dut.io.rowLoadRequest.expect(true.B)
                    dut.io.row.expect(row.U)

                    // 加载当前行 X
                    for (k <- 0 until 64) {
                        dut.io.xLoadWen.poke(true.B)
                        dut.io.xLoadAddr.poke(k.U)
                        dut.io.xLoadData.poke(xValue(row, k).S)
                        dut.clock.step()
                    }
                    dut.io.xLoadWen.poke(false.B)

                    // 当前 X 行准备完成
                    dut.io.rowLoaded.poke(true.B)
                    dut.clock.step()
                    dut.io.rowLoaded.poke(false.B)

                    // 4. 自动遍历当前行的 32 个 group
                    for (group <- 0 until 32) {

                        // 模拟外部 Bias 存储器
                        for (bank <- 0 until 8) {
                            dut.io.bias(bank).poke(
                                biasValue(group, bank).S
                            )
                        }

                        var waited = 0

                        while (
                            !dut.io.resultValid.peek().litToBoolean &&
                                    waited < 100
                        ) {
                            dut.clock.step()
                            waited += 1
                        }

                        assert(
                            dut.io.resultValid.peek().litToBoolean,
                            s"Timeout: row=$row group=$group"
                        )

                        dut.io.row.expect(row.U)
                        dut.io.group.expect(group.U)

                        // 5. 逐元素检查全部 8 个结果
                        for (bank <- 0 until 8) {
                            val expected =
                                expectedResult(row, group, bank)

                            dut.io.result(bank).expect(expected.S)
                            checked += 1
                        }

                        // 6. 消费当前组结果，启动下一组
                        dut.io.resultReady.poke(true.B)
                        dut.clock.step()
                        dut.io.resultReady.poke(false.B)
                    }
                }

                // 所有组完成
                dut.io.done.expect(true.B)
                assert(checked == 99 * 256)
                println(
                    s"[PASS] Full matrix 99x256: " +
                            s"$checked outputs verified"
                )
                dut.clock.step()
                dut.io.done.expect(false.B)
            }
        }
    }
}
