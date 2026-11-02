package linear

import chisel3._
import chisel3.simulator.scalatest.ChiselSim
import org.scalatest.funspec.AnyFunSpec

class BiasSramCacheTest extends AnyFunSpec with ChiselSim {
    describe("xu synchronous bias SRAM contract") {
        it("preserves bytes across banks and groups and arbitrates prefetch, writes and readback") {
            simulate(new BiasSramCache) { dut =>
                val mask40 = (BigInt(1) << 40) - 1
                val expected = Array.tabulate(256)(a => (BigInt(a) * 0x123456789L ^ mask40) & mask40)
                dut.io.prefetch.poke(false.B)
                dut.io.group.poke(0.U)
                dut.io.writeEnable.poke(false.B)
                dut.io.writeAddr.poke(0.U)
                dut.io.writeData.poke(0.U)
                dut.io.writeMask.poke(0.U)
                dut.io.readEnable.poke(false.B)
                dut.io.readAddr.poke(0.U)
                dut.clock.step()

                def write(addr: Int, value: BigInt, mask: Int): Unit = {
                    dut.io.writeEnable.poke(true.B)
                    dut.io.writeAddr.poke(addr.U)
                    dut.io.writeData.poke(value.U)
                    dut.io.writeMask.poke(mask.U)
                    dut.io.writeReady.expect(true.B)
                    dut.clock.step()
                    dut.io.writeEnable.poke(false.B)
                }
                def read(addr: Int): Unit = {
                    dut.io.readEnable.poke(true.B)
                    dut.io.readAddr.poke(addr.U)
                    dut.io.readReady.expect(true.B)
                    dut.clock.step()
                    dut.io.readValid.expect(true.B)
                    dut.io.readData.expect(expected(addr).U)
                    dut.io.readEnable.poke(false.B)
                    dut.clock.step()
                    dut.io.readValid.expect(false.B)
                }
                for (a <- 0 until 256) write(a, expected(a), 31)
                // All 32 byte-mask combinations, including no-op and high byte.
                for (mask <- 0 until 32; a <- Seq(0, 7, 8, 127, 128, 247, 248, 255)) {
                    val value = (BigInt(mask + 1) * 0x09fedcba87L) & mask40
                    val selected = (0 until 5).filter(i => (mask & (1 << i)) != 0)
                        .map(i => BigInt(255) << (8 * i)).foldLeft(BigInt(0))(_ | _)
                    write(a, value, mask)
                    expected(a) = (expected(a) & ~selected) | (value & selected)
                    read(a)
                }
                for (a <- 0 until 256) read(a)

                // Retry the read rejected by prefetch; drop the rejected write
                // and verify that it never changed the prefetched bank.
                for (g <- Seq(0, 15, 16, 31)) {
                    dut.io.group.poke(g.U)
                    dut.io.prefetch.poke(true.B)
                    dut.io.readEnable.poke(true.B)
                    dut.io.readAddr.poke((255 - g * 8).U)
                    dut.io.writeEnable.poke(true.B)
                    dut.io.writeAddr.poke((g * 8).U)
                    dut.io.writeData.poke(0.U)
                    dut.io.writeMask.poke(31.U)
                    dut.io.writeReady.expect(false.B)
                    dut.io.readReady.expect(false.B)
                    dut.clock.step()
                    dut.io.prefetch.poke(false.B)
                    dut.io.writeEnable.poke(false.B)
                    dut.io.readValid.expect(false.B)
                    dut.io.prefetchDone.expect(false.B)
                    dut.clock.step() // capture tile while another bank is read
                    dut.io.prefetchDone.expect(true.B)
                    dut.io.readValid.expect(true.B)
                    dut.io.readData.expect(expected(255 - g * 8).U)
                    for (lane <- 0 until 8) {
                        val raw = expected(g * 8 + lane)
                        val signed = if (raw.testBit(39)) raw - (BigInt(1) << 40) else raw
                        dut.io.bias(lane).expect(signed.S)
                    }
                    dut.io.readEnable.poke(false.B)
                    dut.clock.step(3)
                    // The rejected write did not corrupt the prefetched bank.
                    read(g * 8)
                }

                // Hold a rejected write until ready. Its acceptance coincides
                // with tile capture: compute must retain the pre-write tile.
                for (g <- Seq(0, 15, 16, 31)) {
                    val addr = g * 8 + 7
                    val before = expected.clone()
                    val value = expected(addr) ^ mask40
                    val selected = BigInt("ff00ff00ff", 16)
                    dut.io.group.poke(g.U)
                    dut.io.prefetch.poke(true.B)
                    dut.io.writeEnable.poke(true.B)
                    dut.io.writeAddr.poke(addr.U)
                    dut.io.writeData.poke(value.U)
                    dut.io.writeMask.poke(21.U)
                    dut.io.writeReady.expect(false.B)
                    dut.clock.step()
                    dut.io.prefetch.poke(false.B)
                    dut.io.prefetchDone.expect(false.B)
                    dut.io.writeReady.expect(true.B)
                    dut.clock.step() // Accept the held write and capture the old tile.
                    dut.io.writeEnable.poke(false.B)
                    expected(addr) = (expected(addr) & ~selected) | (value & selected)
                    dut.io.prefetchDone.expect(true.B)
                    for (lane <- 0 until 8) {
                        val raw = before(g * 8 + lane)
                        val signed = if (raw.testBit(39)) raw - (BigInt(1) << 40) else raw
                        dut.io.bias(lane).expect(signed.S)
                    }
                    read(addr)
                    // The readback of updated SRAM must leave the old tile intact.
                    for (lane <- 0 until 8) {
                        val raw = before(g * 8 + lane)
                        val signed = if (raw.testBit(39)) raw - (BigInt(1) << 40) else raw
                        dut.io.bias(lane).expect(signed.S)
                    }
                }

                // Writes also outrank reads without a prefetch, including when
                // the requested addresses occupy different banks.
                val writeAddr = 123
                val readAddr = 124
                val value = expected(writeAddr) ^ mask40
                dut.io.writeEnable.poke(true.B)
                dut.io.writeAddr.poke(writeAddr.U)
                dut.io.writeData.poke(value.U)
                dut.io.writeMask.poke(31.U)
                dut.io.readEnable.poke(true.B)
                dut.io.readAddr.poke(readAddr.U)
                dut.io.writeReady.expect(true.B)
                dut.io.readReady.expect(false.B)
                dut.clock.step()
                expected(writeAddr) = value
                dut.io.readValid.expect(false.B)
                dut.io.writeEnable.poke(false.B)
                dut.io.readReady.expect(true.B)
                dut.clock.step() // Accept the read held across the write.
                dut.io.readValid.expect(true.B)
                dut.io.readData.expect(expected(readAddr).U)
                dut.io.readEnable.poke(false.B)
                dut.clock.step()
                dut.io.readValid.expect(false.B)
                read(writeAddr)
            }
        }
    }
}
