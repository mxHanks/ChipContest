package linear

import chisel3._
import chisel3.util._

class BiasSramCacheIO extends Bundle {
    val writeEnable = Input(Bool())
    val writeReady = Output(Bool())
    val writeAddr = Input(UInt(8.W))
    val writeData = Input(UInt(40.W))
    val writeMask = Input(UInt(5.W))
    val readEnable = Input(Bool())
    val readReady = Output(Bool())
    val readAddr = Input(UInt(8.W))
    val readValid = Output(Bool())
    val readData = Output(UInt(40.W))
    val prefetch = Input(Bool())
    val group = Input(UInt(5.W))
    val prefetchDone = Output(Bool())
    val bias = Output(Vec(8, SInt(40.W)))
}

/** xu S1 candidate: eight 32x40 byte-masked, single-RW SRAM banks.
  *
  * Only the current 320-bit compute tile is retained in registers. A prefetch
  * takes priority over writes, which take priority over an MMIO read. Requests
  * rejected by ready MUST be held/retried by the caller. Each enabled read has
  * one cycle SRAM latency; prefetchDone follows tile capture one cycle later.
  * Unused banks have en=0. Contents and the tile deliberately have no reset.
  */
class BiasSramCache extends Module {
    val io = IO(new BiasSramCacheIO)
    private val tile = Reg(Vec(8, SInt(40.W)))
    private val prefetchValid = RegNext(io.prefetch, false.B)
    private val readFire = io.readEnable && io.readReady
    private val readLane = RegEnable(io.readAddr(2, 0), readFire)
    private val data = Wire(Vec(8, UInt(40.W)))

    io.writeReady := !io.prefetch
    io.readReady := !io.prefetch && !io.writeEnable
    io.readValid := RegNext(readFire, false.B)
    io.prefetchDone := RegNext(prefetchValid, false.B)
    io.readData := data(readLane)
    io.bias := tile

    for (lane <- 0 until 8) {
        val mem = SyncReadMem(32, Vec(5, UInt(8.W)))
        val write = io.writeEnable && io.writeReady && io.writeAddr(2, 0) === lane.U
        val read = readFire && io.readAddr(2, 0) === lane.U
        val address = Mux(io.prefetch, io.group,
            Mux(write, io.writeAddr(7, 3), io.readAddr(7, 3)))
        data(lane) := mem.readWrite(address, io.writeData.asTypeOf(Vec(5, UInt(8.W))),
            io.writeMask.asBools, io.prefetch || write || read, write).asUInt
        when(prefetchValid) { tile(lane) := data(lane).asSInt }
    }
}
