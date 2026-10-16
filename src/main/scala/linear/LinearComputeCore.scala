package linear

import chisel3._
import chisel3.util.Cat
import dotproduct.DotProductEngine
import memory.{XRowBuffer, WeightBankArray}

class LinearComputeCoreIO extends Bundle {
    // 计算控制
    val start: Bool = Input(Bool())
    val group: UInt = Input(UInt(5.W))

    // XRowBuffer 加载接口
    val xLoadWen: Bool = Input(Bool())
    val xLoadAddr: UInt = Input(UInt(6.W))
    val xLoadData: SInt = Input(SInt(16.W))

    // WeightBankArray 加载接口
    val wLoadWen: Bool = Input(Bool())
    val wLoadBank: UInt = Input(UInt(3.W))
    val wLoadAddr: UInt = Input(UInt(11.W))
    val wLoadData: SInt = Input(SInt(16.W))

    // 偏置量
    val bias: Vec[SInt] = Input(Vec(8, SInt(40.W)))

    // 计算结果
    val done: Bool = Output(Bool())
    val result: Vec[SInt] = Output(Vec(8, SInt(48.W)))
}

/**
 * 线性层计算核心（Linear Compute Core）。
 *
 * 负责整合输入数据缓冲区、权重存储阵列和 8 路并行点积引擎，
 * 完成矩阵乘法中的一组 8 个输出元素的计算。
 *
 * == 计算功能 ==
 *
 * 对于指定的输入行 X 和输出列组 group，计算：
 *
 * Y[j] = Bias[j] + Σ(k=0..63) X[k] * W[k, 8*group+j]
 *
 * 其中：
 *   - k     ∈ [0, 63]：点积内部的元素索引
 *   - j     ∈ [0, 7] ：PE 编号
 *   - group ∈ [0, 31]：当前输出列组
 *
 * 每次计算产生 8 个 48-bit 有符号结果。
 *
 * == 内部模块 ==
 *
 * 1. XRowBuffer
 *    - 保存当前输入行的 64 个 INT16 元素
 *    - 使用组合读取，根据当前 k 提供 X[k]
 *    - 同一行 X 可以在不同 group 之间重复使用
 *
 * 2. WeightBankArray
 *    - 包含 8 个独立 WeightBank
 *    - 每个 Bank 存储 2048 个 INT16 权重
 *    - 8 个 Bank 共享读取地址，并行输出 8 个权重
 *    - 使用 SyncReadMem，同步读取延迟为一个时钟周期
 *
 * 3. DotProductEngine
 *    - 包含 MacController 和 8 个 MacPE
 *    - 控制 64 次乘累加运算
 *    - 在 INIT 阶段初始化累加器并预取首个权重
 *    - 在 RUN 阶段连续执行 64 次乘累加
 *    - 在 CAPTURE 阶段保存 8 个计算结果
 *
 * == 工作流程 ==
 *
 * 1. LOAD：
 * 外部通过 xLoad* 和 wLoad* 接口分别写入 X 和 W。
 *
 * 2. START：
 * 外部设置 group 和 bias，向 start 发送启动脉冲。
 *
 * 3. INIT：
 * 初始化 8 个累加器，同时预取 W[0]。
 *
 * 4. RUN：
 * XRowBuffer 根据当前 k 读取 X[k]。
 * WeightBankArray 提供上一周期预取的 8 个权重。
 * 8 个 PE 同时执行 ACC += X[k] * W[k]。
 * 计算当前元素时预取下一元素的权重。
 *
 * 5. CAPTURE：
 * DotProductEngine 将计算结果保存到结果寄存器。
 *
 * 6. DONE：
 * done 有效，外部可以读取 result。
 *
 * == 接口约束 ==
 *
 *  - 每次 start 只计算指定 group 的 8 个输出元素。
 *  - 当前模块不负责自动切换 group 或输入行。
 *  - 必须在计算开始前完成所需 X、W 数据的加载。
 *  - 计算期间应保持 group 稳定，不修改参与计算的存储数据。
 *  - bias 必须在 INIT 周期保持有效。
 *  - start 应在引擎空闲时发出一个时钟周期的脉冲。
 *  - 当前设计假设权重读取具有固定的一周期延迟，
 *    尚未使用 WeightBankArray.rvalid 进行流水线停顿控制。
 *  - done 为短暂的完成状态信号，不是持续保持的完成标志。
 *
 * == 数据宽度 ==
 *
 *  - X       : 16-bit signed
 *  - W       : 16-bit signed
 *  - Bias    : 40-bit signed
 *  - Result  : 48-bit signed
 *
 * 当前实现为单组点积计算核心，后续可通过增加外层调度控制器，
 * 实现完整的 99×64 与 64×256 矩阵乘法。
 */
class LinearComputeCore extends Module {
    val io: LinearComputeCoreIO = IO(new LinearComputeCoreIO)

    private val xBuffer = Module(new XRowBuffer)
    private val weightBanks = Module(new WeightBankArray)
    private val engine = Module(new DotProductEngine)

    // 外部加载 X：将输入行写入 XRowBuffer
    xBuffer.io.wen := io.xLoadWen
    xBuffer.io.waddr := io.xLoadAddr
    xBuffer.io.wdata := io.xLoadData


    // weightBankArray 写入部分
    weightBanks.io.loadWen := io.wLoadWen
    weightBanks.io.loadAddr := io.wLoadAddr
    weightBanks.io.loadData := io.wLoadData
    weightBanks.io.loadBank := io.wLoadBank
    // WeightBankArray 同步读取当前要用的 8 个元素


    // 连接计算控制和数据读取
    engine.io.start := io.start
    engine.io.bias := io.bias

    // 根据当前计算索引 k，组合读取 X[k]
    xBuffer.io.raddr := engine.io.k

    // 提前一个周期请求权重，地址为 group(5 bit) + k(6 bit)
    weightBanks.io.ren := engine.io.weightRen
    weightBanks.io.raddr := Cat(io.group, engine.io.weightReadK)

    // 将存储器读取结果送入 8 路 PE 阵列
    engine.io.x := xBuffer.io.rdata
    engine.io.w := weightBanks.io.rdata

    // 连接 done 和 result
    io.done := engine.io.done
    io.result := engine.io.result
}