package dotproduct


import chisel3._


class DotProductEngineIO extends Bundle {
    val start: Bool = Input(Bool())

    val x: SInt = Input(SInt(16.W))
    val w: Vec[SInt] = Input(Vec(8, SInt(16.W)))
    val bias: Vec[SInt] = Input(Vec(8, SInt(40.W)))

    val k: UInt = Output(UInt(6.W))
    val done: Bool = Output(Bool())
    val result: Vec[SInt] = Output(Vec(8, SInt(48.W)))
}

/**
 * 点积计算引擎。
 * 暂定为顶层模块。顶层需要接收数据和启动命令，也需要暴露计算进度和结果。
 */
class DotProductEngine extends Module {

    val io: DotProductEngineIO = IO(new DotProductEngineIO)

    // 创建 8 个 48 位寄存器，总计 384 bit。它们专门负责保存 上一轮 已经完成的计算结果
    private val resultReg = RegInit(VecInit(Seq.fill(8)(0.S(48.W))))

    private val controller = Module(new MacController)
    private val peArray = Module(new MacPEArray)

    // 控制器
    controller.io.start := io.start
    // 将控制器连接到计算阵列
    peArray.io.init := controller.io.init
    peArray.io.enable := controller.io.accumulate

    // Controller 通知捕获结果
    when(controller.io.capture) {
        resultReg := peArray.io.result
    }
    // 对外输出保存好的计算结果
    io.result := resultReg

    peArray.io.x := io.x
    peArray.io.w := io.w
    peArray.io.bias := io.bias

    io.k := controller.io.k
    io.done := controller.io.done

}
