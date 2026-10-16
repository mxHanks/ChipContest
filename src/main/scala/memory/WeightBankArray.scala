package memory

import chisel3._

class WeightBankArrayIO extends Bundle {
    // 写入端口
    val loadWen: Bool = Input(Bool())
    val loadBank: UInt = Input(UInt(3.W))
    val loadAddr: UInt = Input(UInt(11.W))
    val loadData: SInt = Input(SInt(16.W))

    // 8 个 Bank 共享读取地址
    val ren: Bool = Input(Bool())
    val raddr: UInt = Input(UInt(11.W))

    // 8 路并行输出
    val rdata: Vec[SInt] = Output(Vec(8, SInt(16.W)))
    val rvalid: Bool = Output(Bool())
}

/**
 * 存储所有的权重，包含八个 WeightBank
 */
class WeightBankArray extends Module {
    val io: WeightBankArrayIO = IO(new WeightBankArrayIO)

    // 创建 8 个独立的 WeightBank 实例
    private val banks = Seq.fill(8)(Module(new WeightBank))

    for (i <- 0 until 8) {
        val bank = banks(i)

        // 所有 Bank 共享读取请求
        bank.io.ren := io.ren
        bank.io.raddr := io.raddr

        // 只有被选中的 Bank 才能写入
        bank.io.wen := io.loadWen && (io.loadBank === i.U)

        // 所有 Bank 接收相同的写地址和写数据
        bank.io.waddr := io.loadAddr
        bank.io.wdata := io.loadData

        // 并行读取结果
        io.rdata(i) := bank.io.rdata
    }

    // 所有 Bank 使用相同的 ren 和读取时序 因此可以使用 banks(0) 的 rvalid
    io.rvalid := banks.head.io.rvalid
}