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
class MacPE extends Module {

    val io: MacPEIO = IO(new MacPEIO)
    private val ACC: SInt = RegInit(0.S(48.W)) // 存储当前的和

    when(io.init) {
        ACC := io.bias
    }.elsewhen(io.enable) {
        ACC := ACC + io.x * io.w
    }

    io.result := ACC


}
