
package linear

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import org.scalatest.funspec.AnyFunSpec

class LinearLayerEngineTest extends AnyFunSpec with ChiselSim {

    describe("LinearLayerEngine 自动调度测试") {

        it("应自动遍历两行两组并正确输出结果") {
            simulate(new LinearLayerEngine(2, 2)) { dut =>

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

                // 模拟外部 Bias 存储器：
                // group 0: bias[j] = j
                // group 1: bias[j] = 100 + j
                def tick(): Unit = {
                    val group = dut.io.group.peek().litValue.toInt
                    for (j <- 0 until 8) {
                        dut.io.bias(j).poke((group * 100 + j).S)
                    }
                    dut.clock.step()
                }

                // 1. 加载两组权重
                // group 0 为正，group 1 为负
                for (group <- 0 until 2) {
                    for (bank <- 0 until 8) {
                        for (k <- 0 until 64) {
                            val sign = if (group == 0) 1 else -1
                            val weight = sign * (k + 1) * (bank + 1)

                            dut.io.wLoadWen.poke(true.B)
                            dut.io.wLoadBank.poke(bank.U)
                            dut.io.wLoadAddr.poke((group * 64 + k).U)
                            dut.io.wLoadData.poke(weight.S)
                            tick()
                        }
                    }
                }
                dut.io.wLoadWen.poke(false.B)

                // 2. 启动整个任务
                dut.io.start.poke(true.B)
                tick()
                dut.io.start.poke(false.B)

                // 3. 测试自动遍历两行
                for (row <- 0 until 2) {

                    dut.io.rowLoadRequest.expect(true.B)
                    dut.io.row.expect(row.U)

                    // 第一行 X[k]=k+1
                    // 第二行 X[k]=-(k+1)
                    val rowSign = if (row == 0) 1 else -1

                    for (k <- 0 until 64) {
                        dut.io.xLoadWen.poke(true.B)
                        dut.io.xLoadAddr.poke(k.U)
                        dut.io.xLoadData.poke((rowSign * (k + 1)).S)
                        tick()
                    }
                    dut.io.xLoadWen.poke(false.B)

                    // 通知控制器：当前行已加载完成
                    dut.io.rowLoaded.poke(true.B)
                    tick()
                    dut.io.rowLoaded.poke(false.B)

                    // 4. 每一行自动计算两组
                    for (group <- 0 until 2) {

                        var cycles = 0
                        while (
                            !dut.io.resultValid.peek().litToBoolean &&
                                    cycles < 90
                        ) {
                            tick()
                            cycles += 1
                        }
                        assert(
                            dut.io.resultValid.peek().litToBoolean,
                            s"row=$row group=$group 计算超时"
                        )
                        dut.io.row.expect(row.U)
                        dut.io.group.expect(group.U)

                        val weightSign = if (group == 0) 1 else -1

                        for (j <- 0 until 8) {
                            val expected =
                                rowSign * weightSign * 89440L * (j + 1) +
                                        group * 100 + j

                            dut.io.result(j).expect(expected.S)
                        }
                        println(
                            s"[PASS] row=$row group=$group " +
                                    s"latency=$cycles cycles"
                        )

                        // 接收当前组结果，允许下一组开始
                        dut.io.resultReady.poke(true.B)
                        tick()
                        dut.io.resultReady.poke(false.B)
                    }
                }

                // 5. 全部结果接收完成
                dut.io.done.expect(true.B)
                tick()
                dut.io.done.expect(false.B)
            }
        }
    }
}
