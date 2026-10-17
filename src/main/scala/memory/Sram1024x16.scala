
package memory

import chisel3._

class Sram1024x16IO extends Bundle {
    val en: Bool = Input(Bool())
    val isWrite: Bool = Input(Bool())

    val addr: UInt = Input(UInt(10.W))
    val wdata: SInt = Input(SInt(16.W))

    val rdata: SInt = Output(SInt(16.W))
    val rvalid: Bool = Output(Bool())
}

/**
 * 1024×16 单端口 SRAM 行为模型。
 *
 * en=0: 不进行存储器访问
 * en=1, isWrite=0: 同步读取
 * en=1, isWrite=1: 同步写入
 *
 * 读取请求在时钟上升沿被采样，随后一个周期 rvalid 有效。
 *
 * 当前仅为行为模型，还没有映射到真正的 SRAM Macro
 */
class Sram1024x16 extends Module {
    val io: Sram1024x16IO = IO(new Sram1024x16IO)

    private val mem = SyncReadMem(1024, SInt(16.W))

    io.rdata := mem.readWrite(
        io.addr,
        io.wdata,
        io.en,
        io.isWrite
    )

    io.rvalid := RegNext(
        io.en && !io.isWrite,
        false.B
    )
}
