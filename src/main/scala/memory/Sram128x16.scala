package memory

import chisel3._

/** Logical single-RW 128x16 bank, mapped separately to designated RAMSP128X16.
  * This is a behavioral memory, not an implementation of the technology cell.
  * Reads return in one cycle; disabled/write-cycle read data are unspecified.
  * Full 16-bit writes are the existing W ABI; no additional read port exists.
  */
class Sram128x16 extends Module {
    val io = IO(new Bundle {
        val en = Input(Bool())
        val isWrite = Input(Bool())
        val addr = Input(UInt(7.W))
        val wdata = Input(SInt(16.W))
        val rdata = Output(SInt(16.W))
    })
    private val mem = SyncReadMem(128, SInt(16.W))
    io.rdata := mem.readWrite(io.addr, io.wdata, io.en, io.isWrite)
}
