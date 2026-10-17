package memory

import chisel3._

class WeightBankIO extends Bundle {
    // 写入接口
    val wen: Bool = Input(Bool())
    val waddr: UInt = Input(UInt(11.W))
    val wdata: SInt = Input(SInt(16.W))

    // 读取接口
    val ren: Bool = Input(Bool())
    val raddr: UInt = Input(UInt(11.W))

    val rdata: SInt = Output(SInt(16.W))
    val rvalid: Bool = Output(Bool())
}

/**
 * 我们使用 8 个 PE，所以需要把权重分到 8 个 Bank。一个 Bank 对应一个固定的 PE
 *
 * 例如
 *  - Bank0 存储 0列, 8列, 16列, ... ,248列
 *  - Bank1 存储 1列, 9列, 17列, ..., 249列
 *
 * 也就是，每个 Bank 存储： 64行*32列=2048 个 IN16 元素，即 4096Byte
 *
 * Bank 按照列顺序排列。
 *
 * 对于 raddr 的说明：需要表示第几组(0-7一组,8-15一组,以此类推共有32组)，以及组内的第几个。
 * 用高 5 位表示组，用低 6 位表示第几个，刚好十一位。
 */
class WeightBank extends Module {
    val io: WeightBankIO = IO(new WeightBankIO)

    // 存储规则：每列连续存储，第k组列的第j个元素位置在 64k+j 处 (k, j 都从 0 开始)
    // private val mem = SyncReadMem(2048, SInt(16.W))
    // 暂定 SRAM 规格：1024×16，单端口 1RW
    private val sram0 = Module(new Sram1024x16)
    private val sram1 = Module(new Sram1024x16)

    assert(!(io.ren && io.wen), "Read and write cannot happen simultaneously!") // 不能用中文 不然报错

    // 写入时使用写地址，否则使用读地址
    private val addr: UInt = Mux(io.wen, io.waddr, io.raddr)
    val enable: Bool = io.wen || io.ren

    private val select: Bool = addr(10) // 高一位决定了读取哪一块 mem

    // 两块 SRAM 共享的信号
    for (sram <- Seq(sram0, sram1)) {
        sram.io.addr := addr(9, 0)
        sram.io.wdata := io.wdata
        sram.io.isWrite := io.wen
    }

    // 每次只使能其中一块 SRAM
    sram0.io.en := (io.wen || io.ren) && !select
    sram1.io.en := (io.wen || io.ren) && select

    // 读取结果晚一个周期出现
    // 选择信号也必须保持相同的时序
    private val delayedSelect =
        RegNext(io.raddr(10), false.B)

    io.rdata := Mux(
        delayedSelect,
        sram1.io.rdata,
        sram0.io.rdata
    )

    io.rvalid := Mux(
        delayedSelect,
        sram1.io.rvalid,
        sram0.io.rvalid
    )

}