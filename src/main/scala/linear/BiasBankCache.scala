package linear

import chisel3._
import chisel3.util.{Cat, Fill}

class BiasBankCacheIO extends Bundle {
    val writeEnable = Input(Bool())
    val writeAddr = Input(UInt(8.W))
    val writeData = Input(UInt(40.W))
    val writeMask = Input(UInt(5.W))
    val readAddr = Input(UInt(8.W))
    val readData = Output(UInt(40.W))
    val group = Input(UInt(5.W))
    val bias = Output(Vec(8, SInt(40.W)))
}

/** xu per-task bias storage: eight banks of 32 signed40 entries (1,280 raw bytes).
  *
  * Data is deliberately not reset. Software must fill all 256 entries before
  * selecting this cache, and refill it for every task. The MMIO cache-enable
  * control resets to zero so the legacy bias path remains the reset behavior.
  * Each write-mask bit preserves or replaces one complete byte.
  */
class BiasBankCache extends Module {
    val io = IO(new BiasBankCacheIO)
    private val banks = Reg(Vec(8, Vec(32, UInt(40.W))))
    private val byteMask = Cat((4 to 0 by -1).map(i => Fill(8, io.writeMask(i))))
    private val writeGroup = io.writeAddr(7, 3)

    for (lane <- 0 until 8) {
        when(io.writeEnable && io.writeAddr(2, 0) === lane.U) {
            banks(lane)(writeGroup) :=
                (banks(lane)(writeGroup) & ~byteMask) | (io.writeData & byteMask)
        }
        io.bias(lane) := banks(lane)(io.group).asSInt
    }
    io.readData := banks(io.readAddr(2, 0))(io.readAddr(7, 3))
}
