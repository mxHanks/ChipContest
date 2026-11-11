package dotproduct


import chisel3._


class DotProductEngineIO extends Bundle {
    val start: Bool = Input(Bool())

    val x: SInt = Input(SInt(16.W))
    val w: Vec[SInt] = Input(Vec(8, SInt(16.W)))
    val bias: Vec[SInt] = Input(Vec(8, SInt(40.W)))

    // 权重预取请求
    val weightRen: Bool = Output(Bool())
    val weightReadK: UInt = Output(UInt(6.W))

    val k: UInt = Output(UInt(6.W))
    val done: Bool = Output(Bool())
    val result: Vec[SInt] = Output(Vec(8, SInt(48.W)))
}

/**
 * 点积计算引擎。
 *
 * Inputs:
 *  - start         操控 controller 由 IDLE 进入 INIT 也就是拉高 start 到开始计算之间有一个空拍
 *  - x             1 个 16-bit 的 X 元素
 *  - w             8 个 16-bit 的 W 元素
 *  - bias          8 个 40-bit 的偏置量
 *
 * Outputs:
 *  - k         传出当前计算到了第几个元素，由 controller 提供
 *  - done      传出是否计算完成，由 controller 提供
 *  - result    8 个 48-bit 的计算结果
 *  - weightRen     向 权重存储器 发送 同步读取使能
 *  - weightReadK   指定要预取的权重序号（0~63）
 */
class DotProductEngine(accWidth: Int = 48, resultWidth: Int = 48) extends Module {
    require(resultWidth >= 41 && resultWidth <= 48, "Exact bounded completed results require at least41 bits")
    override def desiredName: String = if (accWidth == 48 && resultWidth == 48) "DotProductEngine"
      else s"DotProductEngine_Acc${accWidth}_Result${resultWidth}"
    require(accWidth >= 41 && accWidth <= 48, "64 signed16 products plus signed40 bias require at least 41 bits")

    val io: DotProductEngineIO = IO(new DotProductEngineIO)

    // 创建 8 个 48 位寄存器，总计 384 bit。它们专门负责保存 上一轮 已经完成的计算结果
    private val resultReg = RegInit(VecInit(Seq.fill(8)(0.S(resultWidth.W))))

    private val controller = Module(new MacController)
    private val peArray = Module(new MacPEArray(accWidth))

    // 控制器
    controller.io.start := io.start
    // 将控制器连接到计算阵列
    peArray.io.init := controller.io.init
    peArray.io.enable := controller.io.accumulate

    // Controller 通知捕获结果
    when(controller.io.capture) {
        if (resultWidth == 48) {
            resultReg := peArray.io.result
        } else {
            for (lane <- 0 until 8) {
                val bounded = peArray.io.result(lane)(resultWidth - 1, 0).asSInt
                assert(peArray.io.result(lane) === bounded.pad(48), "Completed result must fit selected signed storage")
                resultReg(lane) := bounded
            }
        }
    }
    // 对外输出保存好的计算结果
    if (resultWidth == 48) { io.result := resultReg }
    else { for (lane <- 0 until 8) io.result(lane) := resultReg(lane).pad(48) }

    peArray.io.x := io.x
    peArray.io.w := io.w
    peArray.io.bias := io.bias

    io.k := controller.io.k
    io.done := controller.io.done

    // 预读入部分，由于存储 W 的寄存器是同步读取，所以需要在上一拍写好读取信息
    io.weightReadK := Mux(controller.io.init, 0.U, io.k + 1.U)
    io.weightRen := controller.io.init || (controller.io.accumulate && (controller.io.k =/= 63.U))

}
