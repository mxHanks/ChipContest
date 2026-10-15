
import chisel3._
import dotproduct._
import chisel3.simulator.scalatest.ChiselSim
import org.scalatest.funspec.AnyFunSpec

class MacPEArrayTest extends AnyFunSpec with ChiselSim {

    describe("MacPEArray test") {

        // 通过
        it("应该能正确执行 8 路并行乘累加") {
            simulate(new MacPEArray) { dut =>

                // 1. 初始化：所有 PE 的 ACC = 0
                dut.io.init.poke(true.B)
                dut.io.enable.poke(false.B)
                dut.io.x.poke(0.S)

                for (i <- 0 until 8) {
                    dut.io.w(i).poke(0.S)
                    dut.io.bias(i).poke(0.S)
                }

                dut.clock.step()

                // 2. 执行一次并行乘累加
                // 共享 x = 2
                // PE0~7 的 w = 1~8
                dut.io.init.poke(false.B)
                dut.io.enable.poke(true.B)
                dut.io.x.poke(2.S)

                for (i <- 0 until 8) {
                    dut.io.w(i).poke((i + 1).S)
                }

                dut.clock.step()

                // 3. 关闭计算使能，检查结果
                dut.io.enable.poke(false.B)

                for (i <- 0 until 8) {
                    val expected = 2 * (i + 1)
                    dut.io.result(i).expect(expected.S)
                }

                // 4. 再等待一个周期，结果应该保持不变
                dut.clock.step()

                for (i <- 0 until 8) {
                    val expected = 2 * (i + 1)
                    dut.io.result(i).expect(expected.S)
                }
            }
        }
    }
}
