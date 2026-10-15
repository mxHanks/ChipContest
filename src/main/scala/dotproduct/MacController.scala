package dotproduct

import chisel3._
import chisel3.util._

/**
 * 状态机
 *  - IDLE: 等待开始
 *  - INIT: 初始化寄存器为 0，转载 bias
 *  - RUN: 进行 64 次运算
 *  - CAPTURE: 将 8 个 ACC 结果保存到缓冲期
 *  - DONE: 发出完成脉冲，返回 IDLE
 */
private object ControllerState extends ChiselEnum {
    val IDLE, INIT, RUN, CAPTURE, DONE = Value
}

/**
 * 状态机
 *  - IDLE: 等待开始
 *  - INIT: 初始化寄存器为 0，转载 bias
 *  - RUN: 进行 64 次运算
 *  - CAPTURE: 将 8 个 ACC 结果保存到缓冲期
 *  - DONE: 发出完成脉冲，返回 IDLE
 */
class MacControllerIO extends Bundle {
    // 外部启动信号
    val start: Bool = Input(Bool())

    // 发送给全部 PE
    val init: Bool = Output(Bool())
    val accumulate: Bool = Output(Bool())

    // 当前参与计算的元素编号
    val k: UInt = Output(UInt(6.W))

    // 通知结果缓冲区保存 PE 的结果
    val capture: Bool = Output(Bool())

    // 整组计算完成
    val done: Bool = Output(Bool())
}

class MacController extends Module {
    val io: MacControllerIO = IO(new MacControllerIO)

    private val state = RegInit(ControllerState.IDLE)
    private val kReg = RegInit(0.U(6.W))

    // 根据状态产生控制信号
    io.init := state === ControllerState.INIT
    io.accumulate := state === ControllerState.RUN
    io.capture := state === ControllerState.CAPTURE
    io.done := state === ControllerState.DONE

    io.k := kReg

    switch(state) {
        is(ControllerState.IDLE) {
            when(io.start) {
                kReg := 0.U
                state := ControllerState.INIT
            }
        }

        is(ControllerState.INIT) {
            state := ControllerState.RUN
        }

        is(ControllerState.RUN) {
            when(kReg === 63.U) {
                state := ControllerState.CAPTURE
            }.otherwise {
                kReg := kReg + 1.U
            }
        }

        is(ControllerState.CAPTURE) {
            state := ControllerState.DONE
        }

        is(ControllerState.DONE) {
            state := ControllerState.IDLE
        }
    }
}