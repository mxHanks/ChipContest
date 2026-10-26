package memory

import chisel3.simulator.scalatest.ChiselSim
import org.scalatest.funspec.AnyFunSpec

class WeightBankArrayTest extends AnyFunSpec with ChiselSim {

    describe("测试 WeightBankArray 相关功能") {
        it("能否正常完成读写操作") {
            simulate(new WeightBankArray) { dut =>
                dut.io.ren.poke(false)
                // 循环写入测试用例
                for (i <- 0 until 8) {
                    dut.io.loadBank.poke(i)
                    dut.io.loadData.poke((i + 1) * 10)
                    dut.io.loadAddr.poke(0x000)
                    // 写入
                    dut.io.loadWen.poke(true)
                    dut.clock.step()
                    // 一个时钟周期只能写入一个 Bank
                }

                dut.io.loadWen.poke(false)
                dut.io.ren.poke(true)
                dut.io.raddr.poke(0)
                dut.clock.step()
                dut.io.rvalid.expect(value = true)
                for (i <- 0 until 8) {
                    dut.io.rdata(i).expect((i + 1) * 10)
                }
            }
        }

    }
}
