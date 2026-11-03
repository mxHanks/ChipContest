# xu 全 SoC 时序源代码审查与 UART 子引理

本目录记录固定平台源代码审查，以及实际 Yosys 0.52 的有限 Boolean SAT 子引理。**没有取得完整150MHz时序资格，没有应用时序例外，没有修改平台 RTL。**

实际 APB_ADDR_WIDTH=32 的原五个 UART 源经 `proc` 提取，每个 UART 有一个8位数据 latch。依原21个组合单元提取其使能/valid锥，所有当前寄存器状态作为任意输入，SAT证明两态输入下：**latch透明使能当且仅当 fifo_tx_valid，D为PWDATA[7:0]**。根任务在全新 `uart-source-recheck-03` 目录重新提取并运行 SAT，也通过，完整提取JSON与原结果语义相同。两次原始日志、脚本和JSON以无重复成员的archive保存，文件未正规化。

这只说明一个Boolean关系，不证明有效APB写入的透明传播、mapped latch时序、FIFO采样、脉冲宽度或物理可靠性。24个UART E pin仍不能据此从untested中删除。实际库/约束与有效消费路径还需完整审查。

`source-review.md`明确区分历史15/07与待取得的08当前结果：历史存在真实SRAM同沿D hold、clock-gating hold、24UART no_clock，以及ERST→PMU两级raw异步置位释放。只看到08最差removal仍为−0.121483ns，不能反推其余端点已经修好。报告列出每类需要的原文和最小后续步骤，不添加未提供的外部reset相位或MTBF合同。

重放须新输出目录，先核对 `result.json` 五个原源SHA，再拷贝原extract.ys并仅将write_json目的目录改成新目录；执行 `yosys -s <新extract.ys>`，再将prove-enable.py复制到新目录运行。该脚本拒绝覆写现有SAT日志。此证明使用Yosys 0.52，不是服务器DC/PT或全SoC等价证据。
