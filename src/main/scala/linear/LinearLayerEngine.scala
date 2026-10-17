
package linear

import chisel3._
import chisel3.util._

class LinearLayerEngineIO extends Bundle {
    // 总任务控制
    val start: Bool = Input(Bool())
    val done: Bool = Output(Bool())
    // 当前任务位置
    val row: UInt = Output(UInt(7.W))
    val group: UInt = Output(UInt(5.W))
    // X 行加载握手
    val rowLoadRequest: Bool = Output(Bool())
    val rowLoaded: Bool = Input(Bool())
    // X 加载接口
    val xLoadWen: Bool = Input(Bool())
    val xLoadAddr: UInt = Input(UInt(6.W))
    val xLoadData: SInt = Input(SInt(16.W))
    // W 加载接口
    val wLoadWen: Bool = Input(Bool())
    val wLoadBank: UInt = Input(UInt(3.W))
    val wLoadAddr: UInt = Input(UInt(11.W))
    val wLoadData: SInt = Input(SInt(16.W))
    // 当前 group 对应的 8 个 Bias
    val bias: Vec[SInt] = Input(Vec(8, SInt(40.W)))
    // 结果握手
    val resultValid: Bool = Output(Bool())
    val resultReady: Bool = Input(Bool())
    val result: Vec[SInt] = Output(Vec(8, SInt(48.W)))
}

/**
 * 线性层外层调度器。
 *
 * 自动遍历 numRows 行、numGroups 个输出列组。
 * 每组调用一次 LinearComputeCore，产生 8 个结果。
 *
 * 行数据由外部加载，结果通过 valid/ready 接口输出。
 */
class LinearLayerEngine(
                               numRows: Int = 99,
                               numGroups: Int = 32
                       ) extends Module {

    require(numRows >= 1 && numRows <= 99)
    require(numGroups >= 1 && numGroups <= 32)

    val io: LinearLayerEngineIO = IO(new LinearLayerEngineIO)

    private object State extends ChiselEnum {
        val idle, waitRow, launch, waitCompute, emit, done = Value
    }

    private val state = RegInit(State.idle)

    private val rowReg = RegInit(0.U(7.W))
    private val groupReg = RegInit(0.U(5.W))

    private val core = Module(new LinearComputeCore)

    // 将加载接口传递给计算核心
    core.io.xLoadWen := io.xLoadWen
    core.io.xLoadAddr := io.xLoadAddr
    core.io.xLoadData := io.xLoadData

    core.io.wLoadWen := io.wLoadWen
    core.io.wLoadBank := io.wLoadBank
    core.io.wLoadAddr := io.wLoadAddr
    core.io.wLoadData := io.wLoadData

    core.io.bias := io.bias
    core.io.group := groupReg

    // launch 状态持续一周期，产生 start 脉冲
    core.io.start := state === State.launch

    io.row := rowReg
    io.group := groupReg

    io.rowLoadRequest := state === State.waitRow
    io.resultValid := state === State.emit

    io.result := core.io.result
    io.done := state === State.done

    switch(state) {

        is(State.idle) {
            when(io.start) {
                rowReg := 0.U
                groupReg := 0.U
                state := State.waitRow
            }
        }

        // 等待外部把当前行 X 写入 XRowBuffer
        is(State.waitRow) {
            when(io.rowLoaded) {
                state := State.launch
            }
        }

        // 启动一次 8 路点积
        is(State.launch) {
            state := State.waitCompute
        }

        // 等待 DotProductEngine 计算结束
        is(State.waitCompute) {
            when(core.io.done) {
                state := State.emit
            }
        }

        // 等待外部接收这一组的 8 个结果
        is(State.emit) {
            when(io.resultReady) {
                when(groupReg === (numGroups - 1).U) {
                    groupReg := 0.U
                    when(rowReg === (numRows - 1).U) {
                        state := State.done
                    }.otherwise {
                        rowReg := rowReg + 1.U
                        state := State.waitRow
                    }
                }.otherwise {
                    groupReg := groupReg + 1.U
                    state := State.launch
                }
            }
        }

        // 全部计算完成
        is(State.done) {
            state := State.idle
        }
    }
}
