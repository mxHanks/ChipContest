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
    private val mem = SyncReadMem(2048, SInt(16.W))

    when(io.wen) {
        mem.write(io.waddr, io.wdata)
    }

    //    io.rvalid := io.ren
    //    io.rdata := mem(io.raddr)

    private val readData: SInt = mem.read(io.raddr, io.ren)
    io.rdata := readData
    // 这里 RegNext 会把 ren 延迟一个时钟周期，并在复位时将有效标志初始化为 false。
    /*
    相当于写了
    val validReg = RegInit(false.B)
    validReg := io.ren
    io.rvalid := validReg
     */
    io.rvalid := RegNext(io.ren, false.B)

}