package dotproduct

import chisel3._

class MacPEIO extends Bundle {
    val init: Bool = Input(Bool())
    val enable: Bool = Input(Bool())

    val x: SInt = Input(SInt(16.W))
    val w: SInt = Input(SInt(16.W))
    val bias: SInt = Input(SInt(40.W))

    val result: SInt = Output(SInt(48.W))
}

/**
 * 乘法计算单元，由 MacController 统一调度。
 * 计算一个 X 元素和一个 Y 元素的乘积。
 * （采用 IN16 量化，一个元素对应 16bit）
 *
 * Inputs:
 *  - x
 *  - w
 *  - bias
 *  - init:     控制 ACC <- bias
 *  - enable:   控制 ACC <- ACC + X * W
 *
 * Outputs:
 *  - result = ACC ( X * W + bias)
 */
/** accWidth defaults to the historical generic 48-bit accumulator. A narrower
 * instance is a bounded-dot-product specialization: its caller must ensure
 * that every partial sum fits, not just the final result. For signed16 inputs,
 * signed40 bias and at most 64 products, 41 bits cover the complete domain.
 * The public result remains signed48 through sign extension.
 */
class MacPE(accWidth: Int = 48) extends Module {
    override def desiredName: String = if (accWidth == 48) "MacPE" else s"MacPE_Acc${accWidth}"
    require(accWidth >= 40 && accWidth <= 48, "Accumulator must represent signed40 bias")

    val io: MacPEIO = IO(new MacPEIO)
    private val ACC: SInt = RegInit(0.S(accWidth.W)) // Only this internal accumulator is specialized

    when(io.init) {
        ACC := io.bias
    }.elsewhen(io.enable) {
        ACC := ACC + io.x * io.w
    }

    io.result := ACC


}
