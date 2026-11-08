# 状态轮询退避试验（诊断测量）

结论：已测试点没有周期收益。13拍等待仅减少状态事务，不能据此声明能量收益。默认0保留；所有改动只在poll-repo沙盒，未提交、未综合、未改主工作树或baseline-repo。

基线由父仓562a8c9 / 子模块6e2ec89复制；相关read-pop RTL的SHA与已有full12冻结source相同（baseline-provenance.json）。本次0拍被动观察重放精确复现payload564118、poll5049、clear198403。

| 等待参数（拍） | payload cycles | Δcycles | status polls | Δpolls | clear cycles | 首组poll/行 | 首组有效响应延迟 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 564118 | +0 | 5049 | +0 | 198403 | 20 | 120 |
| 2 | 564811 | +693 | 4653 | -396 | 198403 | 16 | 126 |
| 8 | 565504 | +1386 | 4059 | -990 | 198403 | 10 | 132 |
| 13 | 564118 | +0 | 3762 | -1287 | 198403 | 7 | 120 |

本次只跑原layer0，所有点使用同一输入向量、相同固件加载镜像SHA、150MHz/32.768kHz时钟刺激、external-pad-double-reset-v1、Verilator --assert、原背压及清空配方。每个点用新的原生进程，完整原始argv、源SHA、工具版本、日志SHA、native_exit保存在相应result.json/plan.json中。固件ELF的.strtab内临时对象文件名导致文件SHA可不同，加载verilog镜像SHA全部相同；elf-metadata-diff.log保留readelf对照。

## 机制与可证伪结果

额外1881poll全部发生在99行首组group0，每行19个空响应；group1..31共3069次调用全部只poll一次。状态command→response为固定5拍，零等待的空poll command间距6拍。group0 FIFO从空变非空发生在NICE请求后117拍；基线成功响应在请求后120拍，只有3拍可见余量。

预测小等待会降低事务数而推迟有效采样，相位匹配13拍（command间距19拍、6次空poll跨度114拍）可在同一成功响应拍上把首组20poll降成7poll。结果与预测一致。2/8拍将首组成功响应推迟至126/132拍，整行受原有7拍共享总线背压相位影响分别增加7/14拍；13拍保持120拍及全部payload周期。

ready_cycle记录FIFO空→非空的最后一次上升，仅对每行group0是当前head首次可用时刻；FIFO持续非空时不代表后续每个head的可用时刻。后续组的一次poll即成功，是无需额外轮询的直接证据。未从该字段推导后续head的精确余量。

## 实现与协议

POLL_BACKOFF_CYCLES是xu_nice_drain8的可综合elaboration参数，默认0。每个候选在NICE wrapper内实例化明确的常数字面量2/8/13；TB localparam只标注该值并与实例参数核对。没有用plusarg改变硬件。状态寄存器、错误码、Y32数值、drain8编码和group/row-state检查保持；只有已退休空状态响应且尚余poll额度时进入等待，poll_limit仍按已退休响应计数。等待期间不发命令、无在途请求；command valid及completion背压逻辑未变。原1024拍整机watchdog及协议计数检查全部保留。

Icarus先行验证0/2/4/8/13：各61例、817命令及817响应、32组、17个总线错误位置、alias错误及8个POP后写错误。每个空响应后严格验证等待N拍接口静默再重试；原poll_limit=1的长command/response背压及全部错误completion保持测试均通过。4拍只做单元验证，未跑整机；基于机制选择2/8及相位匹配13三个整机候选，避免无依据扩大扫描。

## 证据与限制

- backoff-0-r1、backoff-2、backoff-8、backoff-13保存每点冻结source、TB、固件、独立二进制、完整原始命令与日志。
- unit/results.json、unit/backoff-13-results.json记录单元参数、命令、native_exit及源SHA。
- summary.json / 每点poll-analysis.json提供结构化统计；analyze.py、run_sweep.py、write_report.py保留复算流程。
- 首次backoff-0使用多层defparam，Verilator以native_exit=1拒绝（Unsupported: defparam with more than one dot）；该失败目录与driver日志原样保留。随后显式实例参数成功，无关闭断言或force。
- poll-backoff-rtl-default0.patch只含默认0硬件实现；poll-backoff-candidate13.patch含13拍实例化用于复现等周期的低poll候选；poll-backoff-diagnostics.patch为单元与被动整机观察改动。

这些是二态开发同条件对照，非VCS、门级、面积、功耗或150MHz STA验收。未跑候选full12。13拍依赖本次固定生产与总线时序；不同背压或生产延迟可能推迟可用数据检测。即使状态读减少25.49%，也没有能量测量支持功耗收益。建议保留基线默认0，不以减少poll数宣称吞吐提升。
