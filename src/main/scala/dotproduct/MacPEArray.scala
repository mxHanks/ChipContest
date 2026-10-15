package dotproduct

import chisel3._

class MacPEArrayIO extends Bundle {
    // 控制信号
    val init: Bool = Input(Bool())
    val enable: Bool = Input(Bool())

    // 共享输入
    val x: SInt = Input(SInt(16.W))

    // 8 路独立输入
    val w: Vec[SInt] = Input(Vec(8, SInt(16.W)))
    val bias: Vec[SInt] = Input(Vec(8, SInt(40.W)))

    // 8 路独立结果
    val result: Vec[SInt] = Output(Vec(8, SInt(48.W)))
}

/**
 * 计算 1 个 X 元素和 8 个 W 元素的乘积。
 * 包含 8 个 PE 计算单元，能并行处理 (1 element) dot (8 elements)。
 * 其中 x 为 8 个 PE 共享，而 8 个 w 元素独立。
 * 状态受 MacController 控制。
 */
class MacPEArray extends Module {

    val io: MacPEArrayIO = IO(new MacPEArrayIO)

    private val pes: Seq[MacPE] = Seq.fill(8)(Module(new MacPE))

    for (i <- 0 until 8) {
        val pe = pes(i)
        pe.io.init := io.init
        pe.io.enable := io.enable
        pe.io.x := io.x
        pe.io.w := io.w(i)
        pe.io.bias := io.bias(i)
        io.result(i) := pe.io.result
    }


}
