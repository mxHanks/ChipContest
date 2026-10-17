package memory

import chisel3.simulator.scalatest.ChiselSim
import org.scalatest.funspec.AnyFunSpec

class WeightBankTest extends AnyFunSpec with ChiselSim {

    describe("对单个 WeighBank 进行功能测试") {

        it("应该可以按照规定的时序读出和写入") {
            simulate(new WeightBank) { dut =>

                // 初始化：先禁止读写
                dut.io.wen.poke(false)
                dut.io.ren.poke(false)
                dut.io.raddr.poke(0)

                // 写入 -123 到地址 0x145
                dut.io.wdata.poke(-123)
                dut.io.waddr.poke(0x145)
                dut.io.wen.poke(true)

                dut.clock.step()

                // 结束写入，开始读取
                dut.io.wen.poke(false)
                dut.io.raddr.poke(0x145)
                dut.io.ren.poke(true)

                dut.clock.step()

                // 检查同步读取结果
                dut.io.rvalid.expect(value = true)
                dut.io.rdata.expect(-123)

                // 结束读取
                dut.io.ren.poke(false)
                dut.clock.step()

                dut.io.rvalid.expect(value = false)
            }
        }


        it("应该正确完成写入、连续读取和跨 SRAM 边界访问") {

            simulate(new WeightBank) { dut =>

                // 1. 初始化
                dut.io.wen.poke(false)
                dut.io.waddr.poke(0)
                dut.io.wdata.poke(0)

                dut.io.ren.poke(false)
                dut.io.raddr.poke(0)

                // 2. 测试数据：覆盖两块 SRAM 的边界
                val testData = Seq(
                    0 -> 11,
                    1 -> 22,
                    1023 -> -123,
                    1024 -> 456,
                    1025 -> -789,
                    2047 -> 1234
                )

                // 3. 写入测试数据
                for ((addr, value) <- testData) {

                    dut.io.ren.poke(false)
                    dut.io.wen.poke(true)

                    dut.io.waddr.poke(addr)
                    dut.io.wdata.poke(value)

                    dut.clock.step()
                }

                // 4. 停止写入
                dut.io.wen.poke(false)
                dut.io.ren.poke(false)
                dut.clock.step()

                dut.io.rvalid.expect(value = false)

                // 5. 连续读取，重点测试 SRAM0 / SRAM1 切换
                val readSequence = Seq(
                    1023 -> -123, // SRAM0 最后一个地址
                    1024 -> 456, // SRAM1 第一个地址
                    1025 -> -789,
                    0 -> 11, // 切回 SRAM0
                    2047 -> 1234, // SRAM1 最后一个地址
                    1 -> 22,
                    1024 -> 456,
                    1023 -> -123
                )

                for ((addr, expected) <- readSequence) {

                    dut.io.raddr.poke(addr)
                    dut.io.ren.poke(true)

                    // 同步读取：时钟沿后数据有效
                    dut.clock.step()

                    dut.io.rvalid.expect(value = true)
                    dut.io.rdata.expect(expected)

                    println(
                        s"[PASS] addr=$addr, expected=$expected"
                    )
                }

                // 6. 停止读取，检查 rvalid 清零
                dut.io.ren.poke(false)
                dut.clock.step()

                dut.io.rvalid.expect(value = false)
            }
        }
    }

}
