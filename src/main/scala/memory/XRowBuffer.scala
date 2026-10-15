package memory

import chisel3._

class XRowBufferIO extends Bundle {
    val wen: Bool = Input(Bool())
    val waddr: UInt = Input(UInt(6.W))
    val raddr: UInt = Input(UInt(6.W))
    val wdata: SInt = Input(SInt(16.W))
    val rdata: SInt = Output(SInt(16.W))
}

/**
 * Inputs:
 *  - wen: 写使能
 *  - waddr: 写入地址 0-63
 *  - wdata: 写入数据 16bit
 *  - raddr: 读取地址 0-63
 *
 * Outputs:
 *  - rdata: 读取的结果
 *
 * 当前使用同步写入，异步读取的方法
 */
class XRowBuffer extends Module {

    val io: XRowBufferIO = IO(new XRowBufferIO)

    // 保存一整行 X，共有 64 个元素
    private val data: Vec[SInt] = Reg(Vec(64, SInt(16.W))) // TODO 使用 SyncReadMem 来和 SRAM 对接

    when(io.wen) {
        data(io.waddr) := io.wdata
    }
    io.rdata := data(io.raddr)


}
