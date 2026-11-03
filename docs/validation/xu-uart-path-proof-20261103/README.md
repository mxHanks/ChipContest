# xu 固定 UART 发送数据 latch 的功能边界证明

结论为 **`FUNCTIONAL_BOUNDARY_PROVED_NOT_TIMING_QUALIFIED`**。固定生产 RTL 和 Chisel 均未修改。本证据补足 UART latch 的数据可观察性论证；它不能免除 STA 检查，不能把 24 个 latch 的未测检查改报为已通过。

## 实际使用的源和边界

生产 RTL 子仓提交为 `f49a5fc914971426bd4530db39e270a84b41139f`，运行时主仓提交为 `c12d89f`。`result.json` 冻结全部输入源的完整 SHA-256、大小和实际命令；运行前后逐文件复核未变。

`uart_boundary.sv` 实例化原 `sirv_gnrl_icb2apb`、完整 `apb_uart_sv`（包含原 RX、TX、两个 FIFO、interrupt）和原 `sirv_ResetCatchAndSync_2` → `sirv_AsyncResetRegVec_129` → 20 个 `sirv_AsyncResetReg`。APB 地址宽度为 32，TX/RX FIFO 深度均为原值 16。

这是固定 SoC 的非 lockstep 选择：`e203_subsys_main.v` 原连接将 `bus_rst_n`、`per_rst_n` 都接 `main_rst_n`，而 bridge/UART 同接 `hfclk`；`e203_subsys_perips.v` 原 UART bridge 使用 `bus_rst_n`，UART 使用 `rst_n`。两份原连接文件也在输入哈希中。边界将选中后的 UART ICB 口暴露给刺激，省略 CPU、fabric、时钟门控及其他外设；它不是完整 SoC 仿真或全芯片形式证明，也没有虚构两套可独立操作的复位协议。

## 已验证的功能性质

1. **完整源四态仿真**：8 个种子，每个 433 个真实 ICB 请求；请求在 stall 期间保持 valid/payload，响应随机 backpressure，395 个相邻请求间不插 idle。每次运行都达到 9 次 full FIFO 丢弃、16–33 次 DLAB 写、50–67 次 clear、7 次共同异步复位，并逐次检查真实 reset catch 恰在 20 个上升沿后释放。未 force FIFO、ready、UART 状态、latch 或 reset catch。
2. **独立 FIFO scoreboard**：逐沿核对 occupancy、两个 pointer、全部 16×8 存储。每次真实 `fifo_tx_valid` 必须恰为当拍被接收的非 DLAB THR write；真实有效 data 必须等于当拍 `cmd_wdata[7:0]`。full 时不写入；clear 清 pointer/count，但若同沿原写门仍有效，存储按原 RTL 继续写，未替换成自创 FIFO 语义。
3. **完整 UART 反事实比较**：另生成一份派生 UART，仅在 invalid 分支用每周期改变的任意 byte 代替旧 latch data，valid 分支保持当前请求 byte。原副本保留原 latch，包括最初 16 个关闭且 data 为 X 的周期。逐周期比较 ICB 输出、串行 TX、event、main reset、UART 寄存器以及全部 TX FIFO 存储；8 个种子均一致。这是有限四态覆盖，RX 输入保持 idle，并非完整 UART 协议正确性证明。
4. **实际源锥一步不干扰 miter**：Yosys 从上述全部真实源执行 `proc; flatten; opt; memory_map; opt`，输出 `actual-boundary.json`。生成器检查唯一 8-bit latch 的 Q 确实连接 `uart.fifo_tx_data`，并检查全部状态 cell 为同一个上升沿时钟。按真实 `$adff`、`$adffe`、`$sdffce` 参数展开 85 个状态 cell、465 个状态位的下一状态函数；复位和 enable 优先级保持原语义。没有手写替代 UART/FIFO 状态机。

   两份源锥共享任意当前非 latch 状态和全部输入，旧 latch byte 独立任意。仅以理想透明 latch 的采样边界函数 `Q = active_EN ? D : old` 展开真实 `$dlatch` 的 D/EN。SAT 对所有这些已定义输入证明：两份非 latch 下一状态相同、边界可观察输出相同、每个真实 FIFO 存储写入的 D 必为当前请求 byte、valid data 必为当前 byte。比较使用 `$eqx` 保留源锥无关 undef 的同一性；这不是穷尽四态或透明窗口的电气证明。

   因此，若两实例的非 latch 状态相同，仅旧 latch byte 不同，一步之后仍相同；共同复位提供状态相等的起点。功能模型的归纳结论不要求旧 latch byte 取零或已初始化。
5. **真实 bridge 不变量基例和归纳**：从同一实际源状态方程证明 reset 后 `!(apb_enable_r && rsp_valid)`，且该不变量一步保持。以该不变量为前提，证明 `fifo_tx_valid == (cmd_valid && cmd_ready && !cmd_read && THR && !DLAB)`，没有把任意 APB 刺激冒称合法 ICB。

## 检查器的负例

- 派生生产源把有效 byte 异或 1：四态 scoreboard 在第一笔 THR 写报 `FIFO sampled stale byte`。
- 刺激故意改变尚未接收的 ICB payload：合法性检查报 `illegal stimulus changed a stalled ICB request`。
- 源锥 miter 故意翻转 latch enable：SAT 给出 `next_state_equal=0` 反例。
- 源锥 miter 故意取消 FIFO memory 写门控：SAT 给出 invalid 旧值流入状态的反例。

两个 SAT 反例的原始日志与 VCD 均保留。所有负例只生成到输出目录，固定源不变。`prototype-observations.tar.xz` 另外保留早期工具问题：未关闭不支持的 immediate assert 时 Icarus 编译失败，以及 testbench 编译顺序令原 `#1` DFF 延时继承默认单位造成的 watchdog。最终命令先编译含 `timescale 1ns/1ps` 的 testbench，原 DFF 的 `#1` 未被删除；这些旧原型日志不作为最终源验收。

## 复现和证据

需要 Icarus Verilog 12.0、Yosys 0.52 和 Python 3。实际版本输出在归档中。功能仿真为 10 ns 周期；它没有宣称 150 MHz 合格。

```sh
cd /home/mxhanks/Projects/ChipContest-xu-uart-path-proof
python3 docs/validation/xu-uart-path-proof-20261103/run_proof.py \
  --out build/xu-uart-path-proof-20261103/reproduce-01
python3 docs/validation/xu-uart-path-proof-20261103/verify_evidence.py
```

原始最终归档 `raw/xu-uart-source-proof-run09.tar.xz` 含 36 个文件、111,548 bytes，SHA-256 为 `3608cc4a9f0cbfc6f3171b3b6fe47fa2b8560c3ccf808b40b76639fd2af0ca76`。包含源 JSON、三个 miter JSON、实际 `.ys` 命令、编译产物、8 份仿真日志、4 个负例日志和两个 VCD。`raw/run09-manifest.json` 逐文件冻结哈希和大小；原始日志含原 UART 仿真的二进制字符输出，保留原字节。

仍需独立解决：透明 latch D/EN 的 setup/hold 与开闭窗口、完整 SoC 时序约束和未测项审计、实际映射 latch 的源锥对应、CDC/RDC、MTBF 及板级复位释放协议。本证明不产生 false path、multicycle、case analysis 或任何 STA waiver。

`raw/xu-uart-source-proof-run08.tar.xz` 保留上一轮完整结果；09 轮进一步要求负向 SAT 必须产生真实 FAIL marker 和非空反例 VCD，防止工具异常被误判为预期反例。两轮源功能结论一致，最终生产者以 09 轮冻结哈希为准。
