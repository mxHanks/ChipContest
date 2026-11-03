package linear

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import org.scalatest.funspec.AnyFunSpec

class XuParallelBank128Test extends AnyFunSpec with ChiselSim {
    describe("xu four-depth single-RW 32PE weight bank") {
        it("preserves all512 words and returns the sampled depth during back-to-back reads") {
            simulate(new XuParallelWeightBank(XuParallelGeometry(32, bank128 = true))) { dut =>
                dut.io.wen.poke(false.B)
                dut.io.ren.poke(false.B)
                dut.io.addr.poke(0.U)
                dut.io.data.poke(0.S)
                def value(addr: Int): Int = if (addr == 0) -32768 else if (addr == 511) 32767
                    else ((addr * 31337 + 12345) & 65535) - 32768
                // Interleave all four depths so a shared/dropped bank aliases immediately.
                for (low <- 0 until 128; depth <- Seq(2, 0, 3, 1)) {
                    val addr = depth * 128 + low
                    dut.io.wen.poke(true.B)
                    dut.io.addr.poke(addr.U)
                    dut.io.data.poke(value(addr).S)
                    dut.clock.step()
                }
                dut.io.wen.poke(false.B)
                dut.io.ren.poke(true.B)
                val addresses = Seq(127, 128, 255, 256, 383, 384, 511, 0) ++
                    (0 until 512).map(i => (i * 197 + 83) & 511)
                for (addr <- addresses) {
                    dut.io.addr.poke(addr.U)
                    dut.clock.step()
                    // Changing the next request cannot reroute the previous read's Q.
                    dut.io.addr.poke((addr ^ 384).U)
                    dut.io.result.expect(value(addr).S)
                }
                // Writes never require a second port or a read-modify-write cycle.
                dut.io.ren.poke(false.B)
                for (addr <- Seq(0, 127, 128, 255, 256, 383, 384, 511)) {
                    dut.io.wen.poke(true.B)
                    dut.io.addr.poke(addr.U)
                    dut.io.data.poke((-value(addr) - 1).S)
                    dut.clock.step()
                    dut.io.wen.poke(false.B)
                    dut.io.ren.poke(true.B)
                    dut.clock.step()
                    dut.io.result.expect((-value(addr) - 1).S)
                    dut.io.ren.poke(false.B)
                    dut.clock.step(2)
                }
            }
        }
    }
}
