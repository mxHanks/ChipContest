import chisel3.simulator.scalatest.ChiselSim
import org.scalatest.funspec.AnyFunSpec
import memory._

class WeightBankTest extends AnyFunSpec with ChiselSim {

    describe("对单个 WeighBank 进行功能测试") {
        it("应该可以按照规定的时序读出和写入") {
            simulate(new WeightBank) { dut =>
                // 准备工作
                dut.io.wdata.poke(-123)
                dut.io.waddr.poke(0x145)
                // 写入
                dut.io.wen.poke(true)
                dut.clock.step()

                // 准备读出
                dut.io.raddr.poke(0x145)
                // 读出
                dut.io.ren.poke(true)

                // 检验
                dut.clock.step()
                dut.io.rvalid.expect(value = true)
                dut.io.rdata.expect(-123)

            }
        }
    }

}
