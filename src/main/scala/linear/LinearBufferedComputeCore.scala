package linear

import chisel3._
import chisel3.util.Cat
import dotproduct.DotProductEngine
import memory.{XRowBuffer, WeightBankArray}

class LinearBufferedComputeCoreIO extends LinearComputeCoreIO {
    val xLoadBank = Input(Bool())
    val xReadBank = Input(Bool())
}

/** xu S2d: two independent X rows, one unchanged 32KiB W array and eight PEs.
  * A bank is selected for every complete group; no row-copy cycle is needed.
  */
class LinearBufferedComputeCore extends Module {
    val io = IO(new LinearBufferedComputeCoreIO)
    private val xBuffers = Seq.fill(2)(Module(new XRowBuffer))
    private val weightBanks = Module(new WeightBankArray)
    private val engine = Module(new DotProductEngine)
    for ((bank, index) <- xBuffers.zipWithIndex) {
        bank.io.wen := io.xLoadWen && io.xLoadBank === (index != 0).B
        bank.io.waddr := io.xLoadAddr
        bank.io.wdata := io.xLoadData
        bank.io.raddr := engine.io.k
    }
    weightBanks.io.loadWen := io.wLoadWen
    weightBanks.io.loadAddr := io.wLoadAddr
    weightBanks.io.loadData := io.wLoadData
    weightBanks.io.loadBank := io.wLoadBank
    weightBanks.io.ren := engine.io.weightRen
    weightBanks.io.raddr := Cat(io.group, engine.io.weightReadK)
    engine.io.start := io.start
    engine.io.bias := io.bias
    engine.io.x := Mux(io.xReadBank, xBuffers(1).io.rdata, xBuffers(0).io.rdata)
    engine.io.w := weightBanks.io.rdata
    io.done := engine.io.done
    io.result := engine.io.result
}
