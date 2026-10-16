package dotproduct

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import org.scalatest.funspec.AnyFunSpec

class DotProductEngineTest extends AnyFunSpec with ChiselSim {

    // 测试通过
    describe("点积顶层功能测试") {

        it("应该可以输出正确的计算结果") {
            simulate(new DotProductEngine) { dut =>

                // 1. 准备初始输入
                dut.io.start.poke(false.B)
                dut.io.x.poke(0.S)

                for (j <- 0 until 8) {
                    dut.io.w(j).poke(0.S)
                    dut.io.bias(j).poke((10 + j).S)
                }

                // 2. 启动计算：IDLE -> INIT
                dut.io.start.poke(true.B)
                dut.clock.step()
                dut.io.start.poke(false.B)

                // 3. 初始化 ACC：INIT -> RUN
                dut.clock.step()

                // 4. 进行 64 次乘累加
                for (k <- 0 until 64) {
                    dut.io.k.expect(k.U)
                    dut.io.done.expect(false.B)

                    // X[k] = (k % 4) - 1
                    dut.io.x.poke(((k % 4) - 1).S)

                    // 每个 PE 使用不同的 W
                    for (j <- 0 until 8) {
                        dut.io.w(j).poke((j + 1).S)
                    }

                    dut.clock.step()
                }

                // 5. RUN -> CAPTURE
                // 此时 ACC 已完成最后一次累加
                dut.io.done.expect(false.B)

                // CAPTURE -> DONE
                // 在这一时钟沿保存全部结果
                dut.clock.step()

                // 6. 检查完成标志和计算结果
                dut.io.done.expect(true.B)

                for (j <- 0 until 8) {
                    val expected = 42 + 33 * j
                    dut.io.result(j).expect(expected.S)
                }

                // 7. DONE -> IDLE
                dut.clock.step()
                dut.io.done.expect(false.B)

                // 检查结果缓冲区是否保持结果
                for (j <- 0 until 8) {
                    val expected = 42 + 33 * j
                    dut.io.result(j).expect(expected.S)
                }
            }
        }

        it("应该能以合理的时序发送预处理信号") {
            simulate(new DotProductEngine) { dut =>
                // 准备数据与发送开始信号
                dut.io.start.poke(true)
                dut.io.x.poke(0.S)
                for (j <- 0 until 8) {
                    dut.io.w(j).poke(0.S)
                    dut.io.bias(j).poke((10 + j).S)
                }
                dut.clock.step()

                // 进入 INIT 阶段
                dut.io.weightRen.expect(true.B)
                dut.io.weightReadK.expect(0.U)
                dut.clock.step()

                // 进入 RUN 阶段
                dut.io.k.expect(0.U)
                dut.io.weightRen.expect(true.B)
                dut.io.weightReadK.expect(1.U)
                dut.clock.step(64)

                // 运算完成
                dut.io.k.expect(63.U)
                dut.io.weightRen.expect(false.B)
            }
        }

    }
}
