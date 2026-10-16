package memory

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import org.scalatest.funspec.AnyFunSpec

class XRowBufferTest extends AnyFunSpec with ChiselSim {

    describe("测试 XRow 存储的功能是否正常") {
        it("应该正常的读写") {
            simulate(new XRowBuffer) { dut =>
                // 写入全部 64 个元素
                for (k <- 0 until 64) {
                    dut.io.wen.poke(true.B)
                    dut.io.waddr.poke(k.U)
                    dut.io.wdata.poke((k - 32).S)
                    dut.clock.step()
                }

                // 停止写入，再逐个读取和验证
                dut.io.wen.poke(false.B)

                for (k <- 0 until 64) {
                    dut.io.raddr.poke(k.U)
                    dut.io.rdata.expect((k - 32).S)
                }
            }

        }
    }
}
