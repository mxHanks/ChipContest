
package linear

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import org.scalatest.funspec.AnyFunSpec

class LinearComputeCoreTest extends AnyFunSpec with ChiselSim {

    describe("LinearComputeCore 集成功能测试") {

        it("应正确从存储器读取数据，完成两组 8 路点积") {
            simulate(new LinearComputeCore) { dut =>

                // ========= 1. 初始化 =========
                dut.io.start.poke(false.B)
                dut.io.group.poke(0.U)

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

                // ========= 2. 加载 X =========
                // X[k] = k + 1
                for (k <- 0 until 64) {
                    dut.io.xLoadWen.poke(true.B)
                    dut.io.xLoadAddr.poke(k.U)
                    dut.io.xLoadData.poke((k + 1).S)
                    dut.clock.step()
                }

                dut.io.xLoadWen.poke(false.B)

                // ========= 3. 加载两组 W =========
                //
                // group 0:
                // W[k,j] = (k+1)*(j+1)
                //
                // group 1:
                // W[k,8+j] = -(k+1)*(j+1)
                //
                // Bank 内地址 = group*64 + k
                for (group <- 0 until 2) {
                    for (bank <- 0 until 8) {
                        for (k <- 0 until 64) {

                            val sign = if (group == 0) 1 else -1
                            val weight = sign * (k + 1) * (bank + 1)

                            dut.io.wLoadWen.poke(true.B)
                            dut.io.wLoadBank.poke(bank.U)
                            dut.io.wLoadAddr.poke((group * 64 + k).U)
                            dut.io.wLoadData.poke(weight.S)

                            dut.clock.step()
                        }
                    }
                }

                dut.io.wLoadWen.poke(false.B)

                // ========= 4. 定义启动并等待完成的方法 =========
                def runGroup(group: Int, bias: Int): Unit = {
                    dut.io.group.poke(group.U)

                    for (j <- 0 until 8) {
                        dut.io.bias(j).poke(bias.S)
                    }

                    // 发出一个周期的 start 脉冲
                    dut.io.start.poke(true.B)
                    dut.clock.step()
                    dut.io.start.poke(false.B)

                    // 等待 done，超时则测试失败
                    val maxCycles = 80
                    var cycles = 0

                    while (
                        cycles < maxCycles &&
                                !dut.io.done.peek().litToBoolean
                    ) {
                        dut.clock.step()
                        cycles += 1
                    }

                    assert(
                        dut.io.done.peek().litToBoolean,
                        s"group=$group: 超过 $maxCycles 周期仍未完成"
                    )

                    // ========= 5. 检查全部 8 路结果 =========
                    val sign = if (group == 0) 1 else -1

                    for (j <- 0 until 8) {
                        val expected =
                            sign * 89440L * (j + 1) + bias

                        dut.io.result(j).expect(expected.S)
                    }

                    println(
                        s"[PASS] group=$group, bias=$bias, " +
                                s"latency=$cycles cycles"
                    )

                    // DONE -> IDLE，为下一次启动做准备
                    dut.clock.step()
                    dut.io.done.expect(false.B)
                }

                // ========= 6. 执行两个测试场景 =========
                // group 0：正权重，Bias = 0
                runGroup(group = 0, bias = 0)

                // group 1：负权重，Bias = 100
                runGroup(group = 1, bias = 100)
            }
        }
    }
}
