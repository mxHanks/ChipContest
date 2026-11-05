package linear

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import org.scalatest.funspec.AnyFunSpec
import scala.util.Random

class BiasBankCacheTest extends AnyFunSpec with ChiselSim {
    describe("xu full-bias cache") {
        it("keeps every bank and group distinct through masked writes and task refresh") {
            simulate(new BiasBankCache) { dut =>
                val mask40 = (BigInt(1) << 40) - 1
                val expected = Array.fill[BigInt](256)(0)
                val random = new Random(203)
                dut.io.writeEnable.poke(false.B)
                dut.io.writeAddr.poke(0.U)
                dut.io.writeData.poke(0.U)
                dut.io.writeMask.poke(0.U)
                dut.io.readAddr.poke(0.U)
                dut.io.group.poke(0.U)

                def signed(value: BigInt): BigInt =
                    if (value.testBit(39)) value - (BigInt(1) << 40) else value

                def write(addr: Int, value: BigInt, mask: Int): Unit = {
                    dut.io.writeEnable.poke(true.B)
                    dut.io.writeAddr.poke(addr.U)
                    dut.io.writeData.poke((value & mask40).U)
                    dut.io.writeMask.poke(mask.U)
                    dut.clock.step()
                    val expanded = (0 until 5).filter(i => (mask & (1 << i)) != 0)
                        .foldLeft(BigInt(0))((bits, i) => bits | (BigInt(255) << (8 * i)))
                    expected(addr) = (expected(addr) & (mask40 ^ expanded)) | (value & expanded)
                    dut.io.writeEnable.poke(false.B)
                    dut.io.readAddr.poke(addr.U)
                    dut.io.readData.expect(expected(addr).U)
                }

                def checkAll(): Unit = {
                    for (group <- 0 until 32) {
                        dut.io.group.poke(group.U)
                        for (lane <- 0 until 8)
                            dut.io.bias(lane).expect(signed(expected(group * 8 + lane)).S)
                    }
                }

                for (addr <- 0 until 256)
                    write(addr, if (addr == 0) BigInt(1) << 39 else
                        if (addr == 255) (BigInt(1) << 39) - 1 else BigInt(40, random), 31)
                checkAll()
                for (_ <- 0 until 256) write(random.nextInt(256), BigInt(40, random), random.nextInt(32))
                checkAll()
                // A second task replaces every entry, including the sign byte.
                for (addr <- 0 until 256) write(addr, -BigInt(addr + 1), 31)
                checkAll()
            }
        }
    }
}
