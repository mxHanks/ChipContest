# 队友器件库与面积流程审计

审计日期：2026-10-17（Asia/Shanghai）。对象为本地 `ChipContest/` 的提交 `30e737ca37bc7d3077db1877ee89072ac4dfc723`；审计只读原仓库，未改动其源文件和冻结报告，未运行重型 EDA。入口已依次阅读 `quickstart.md`、README、面积脚本、SRAM/WeightBank/LinearComputeCore 源码和两个冻结综合日志。

**结论：这个仓库提供了可立即复用的 Nangate45 参考标准单元库及同步 SRAM 行为接口，可以推进本地映射对照。仓库没有提供组委会指定的 SRAM 工艺宏、完整标准单元签核材料或正式时序约束。面积、150 MHz 和功耗的比赛验收仍未成立。** 用户已明确“尚未拿到”组委会相关材料；本审计不把参考资产升级为正式资产。

## 1. 实际资产及适用范围

| 资产 | 实际内容 | 可支持的工作 | 不能证明的内容 |
|---|---|---|---|
| `assets/libs/nangate45/NangateOpenCellLibrary_typical.lib` | 6,692,032 字节、135 个标准单元；没有 SRAM 单元 | Yosys/ABC 标准单元映射、同库同约束的面积比较；配合 STA 的参考时序 | 指定工艺面积、指定 SRAM 面积/延迟/功耗、真实全系统能耗 |
| `src/main/scala/memory/Sram1024x16.scala` | Chisel `SyncReadMem`，1024×16、单端口 1RW 行为 | 功能仿真、同步请求/返回接口、宏替换入口 | 工艺宏及其 CE/WE 极性、Q 保持、面积和时序表 |
| `WeightBank.scala` | 每 bank 两个 1024×16，带片选和一拍返回选择 | 2048 深度 bank 的可复用译码思路 | 已映射到比赛指定宏 |
| `reports/baseline/*_nangate45.log` | Yosys 0.52 的历史综合完整结束日志 | 历史参考面积、DFF/MUX 膨胀定位 | 与当前生成 RTL 的可验证绑定；综合后功能、STA、功耗 |
| SDC、SRAM `.lib/.db/.lef`、宏功能 Verilog | 在本次检出的主仓库资产中缺失 | 继续以显式待接入口准备流程 | 缺失项不能按零或理想器件填入正式验收表 |

Nangate 文件自身声明 typical/TypTyp、1.10 V、25 °C；时间单位 `1ns`、漏电单位 `1nW`、电流 `1mA`、电容 `1fF`。包含组合时序、触发器时序、内部功耗和漏电表，但仅拥有这些表并不等于已经得到设计功耗。

OpenROAD 的 [Nangate45 平台说明](https://raw.githubusercontent.com/The-OpenROAD-Project/OpenROAD-flow-scripts/master/flow/platforms/nangate45/README.md) 将其用于研究、测试和 EDA 流程探索，并说明该参考库不用于制造。该说明不能证明组委会采用同一工艺。赛题要求另见当前工程需求 U09/U11/U12/U27：指定 16×128、16×1024、16×4096 宏、150 MHz、完整增量面积及系统窗口功耗。

本地 Liberty 未显式给出 `area_unit`。公开同名库的 [LEF](https://raw.githubusercontent.com/The-OpenROAD-Project/OpenROAD-flow-scripts/master/flow/platforms/nangate45/lef/NangateOpenCellLibrary.macro.lef) 中 AND2_X1 为 0.76×1.4 µm，与本地 AND2_X1 的 `area=1.064` 对应，因此把该参考库数值解释为 µm²有可核对的依据。正式指定库仍需单独确认面积单位。标准单元面积之和也不是含利用率/布线余量的芯片外框面积。

第三方来源记录尚需补齐：队友只提交了 Liberty，未提交同目录许可或下载来源说明。公开 OpenROAD 平台附 [Apache-2.0 LICENSE](https://raw.githubusercontent.com/The-OpenROAD-Project/OpenROAD-flow-scripts/master/flow/platforms/nangate45/LICENSE)，但本地文件头还保留原 Nangate 声明。后续分发应记录本地字节的具体取得路径、版本及对应许可，保留原声明；不能仅凭同名认定字节和分发包完全相同。本审计不更改原文件。

## 2. 冻结面积报告揭示的主要问题

| 历史顶层 | 日志映射面积（参考 µm²） | 参考 mm² | 关键统计 |
|---|---:|---:|---|
| DotProductEngine | 22,889.832000 | 0.022889832 | 18,023 cells；779 DFF_X1 |
| LinearComputeCore | 2,159,601.598019 | 2.159601598 | 951,271 cells；263,958 DFF_X1；295,146 MUX2_X1 |

两份日志均有 `End of script`，Yosys 版本为 0.52。其最终 `$scopeinfo` 为元数据、面积未知，须在新的证据记录中解释或剔除这种非硬件条目。冻结报告未一并提交映射网表、输入生成 RTL 哈希、约束或后仿真结果；因此保留为历史数据，不能替代当前源码重跑结果。

LinearComputeCore 的 263,958 个 DFF_X1 与 262,144 bit 权重以及行缓存/控制寄存器的数量级一致。`synth -noabc -flatten` 默认经过存储展开；最终 memory 为 0，DFF/MUX 数极大。**首要面积瓶颈是用标准单元实现整份权重存储。** 不能由此声称宏版会超标或已经达标；宏面积必须另取得。

2.1596 mm² 仅是该历史顶层在参考库中的展开映射值，其覆盖范围包括一行 X 和权重，外部提供 bias；它不等于最终 99 行输入缓存、全部 bias 存储、结果缓存、新增 ICB/搬运接口及 SRAM 宏之和。与 2.25 直接比较会混淆实现和统计边界。

## 3. `area_eval.sh` 的流程缺口

脚本可执行面积映射，但当前仅执行：`read_verilog` → `hierarchy` → `synth -noabc -flatten` → `dfflibmap` → `abc -liberty` → `stat -liberty`。

- 没有指定时钟周期、输入驱动、输出负载或 I/O 延迟；`abc` 也没有 `-D` 和 `-constr`。因此报告不能说明 150 MHz。Yosys [0.33 ABC 源码及帮助](https://raw.githubusercontent.com/YosysHQ/yosys/yosys-0.33/passes/techmap/abc.cc) 明确 `-D` 单位为 ps；约束文件的负载为 fF。即使补 `-D 6666.667`，ABC 映射目标仍需独立 STA 验证。
- 没有 SRAM 映射/黑盒规则，完整权重会被展开。比较宏候选时应保留真实宏实例和周边译码，不能先展开再手动追加宏面积。
- 没有保存 netlist、JSON、输入/库/工具 SHA、命令退出码记录；固定 `reports/<TOP>_nangate45.log` 路径会覆盖前次运行。应由本工程新 runner 管理唯一运行目录，保留原脚本供原样复现。
- 只做综合过程中的结构检查，没有映射后功能验证和 `check`/未映射硬件单元的显式拒绝门槛。
- 无 VCD/SAIF 活动、无功耗计算、无 E203 和互连活动、无全部 SRAM 功耗表，不能推导 mW 或任务能耗。

本地现有 Yosys 为 0.33，队友冻结日志为 0.52。新旧数字须注明工具差异；同轮对照必须使用相同的工具/Liberty/约束和明确相同的比较范围。

## 4. SRAM wrapper 可复用的接口证据

`Sram1024x16.scala:6–43` 提供的逻辑契约为：隐含模块时钟/复位，`en`、`isWrite`、`addr[9:0]`、signed `wdata[15:0]`、signed `rdata[15:0]`、`rvalid`。

| 条件 | 事务和输出约束 |
|---|---|
| en=0 | 无存储访问；不得消费 rdata 的无效值 |
| en=1、isWrite=1 | 时钟沿同步写；rvalid 下一拍为 0 |
| en=1、isWrite=0 | 时钟沿采样读请求，下一拍 rvalid 有效 |
| reset | rvalid 清零；模型没有整块 SRAM 内容复位 |

`WeightBank.scala:38–75` 用两片 1024×16 形成 2048 深度，读写不并发并有 assert；第 10 位选片，低 10 位送宏，只打开目标片 `en`；将读片选延迟一拍再选择输出。该约束适合当前装载与计算分阶段的 W bank。不得把逻辑上独立的读写端口误认为物理双端口。

注意 `SyncReadMem` 在无有效读和写周期不保证可消费的读值，不能在正式宏适配中凭空要求 Q 保持或读写同址模式。物理适配还需确认：CE/WE/OE 极性、时钟边沿、读延迟、写掩码、掉电/睡眠管脚、冲突语义、setup/hold/cycle 和功耗模式。`rvalid` 是外围逻辑，不应假定物理宏自带该管脚。

融合时应复用此**同步事务契约与深度级联方法**，在新路径分别实现仿真模型与综合宏实例；综合清单排除行为 mock。当前工程 rowpair 的偶/奇 X 各一读、W 广播两行、双结果缓冲一组写另一组读，可以由多个独立 SP 宏实现，具体数量和面积仍须按当前真实布局核算。

两个工程的权重布局存在接口差异：队友 bank 内地址为 `group*64+k`；当前 rowpair/banked 内部为 `k*32+group`。对外应统一以 `W[k,c]` 为真值，并由显式转换决定 bank/片选/地址；直接复制 bank 内容会转置存储布局。此问题独立于 signed 16-bit 元素本身。

## 5. 最小可执行参考流程

优先执行两个范围，并始终标记 `reference-Nangate45`：

1. **原样参考复跑：**生成 DotProductEngine RTL 后，执行 `bash tools/scripts/area_eval.sh DotProductEngine`，保存完整日志与生成 RTL/Liberty/工具哈希。这个顶层小，可快速确认原工具链和本地库解析；完整 LinearComputeCore 展开面积复跑耗时和内存较大，且不解决宏映射问题，应单独排队。
2. **新引擎的逻辑对照：**以固定 16/16/40/48 数值契约比较单行 8 路、有/无乘积流水、双行 16-MAC 等候选。将存储替换为有明确参数和实例统计的 opaque 边界，保留地址/使能/返回流水及译码逻辑；先输出“逻辑面积，SRAM 未计”。opaque 结构的时序不能推广到穿过 SRAM 的路径。若采用 `$mem_v2` 导出而未实现物理宏级联，其读输出保持、级联 mux 和接口包装成本也尚未完整计入。

参考综合脚本应显式读取文件集、先做结构检查和 `memory_dff/memory_collect`，核对各存储的端口/容量，再转换为受控宏边界，最后映射剩余逻辑；拒绝未解释的通用硬件单元和未列入预算的黑盒。输出网表/JSON、逻辑面积、各类存储实例与未计物理量，避免把未映射内存的零面积混进总面积。

最低限度参考 STA 可用如下 Tcl 骨架。**这是待填真实边界条件的模板，未在本审计执行。** `report_checks` 有结果也必须同时检查约束覆盖、所有时序组、setup/hold 及未链接实例；缺少宏 Liberty 时，只能报告无存储的小核心或明确切开的组合段。

```tcl
read_liberty <固定的-Nangate45-typical.lib>
read_verilog <同次综合的-mapped.v>
link_design <top>
read_sdc <同配置-reference.sdc>
check_setup
report_checks -path_delay max -group_path_count 10
report_checks -path_delay min -group_path_count 10
report_wns
report_tns
```

SDC 应显式创建 6.666666667 ns 时钟；输入/输出延迟、输入 transition、输出 capacitance、时钟 uncertainty 必须记录设定依据，不能用全部零的理想边界获得正式 PASS。异步复位例外应限于 reset 端点和已说明的复位释放机制，不得用全局 false path 遮掉关键路径。Nangate typical 加理想互连可用于开发路径定位；指定库/PVT和赛题允许的互连/负载条件下重新跑后才能用于比赛。

[OpenSTA 官方说明](https://raw.githubusercontent.com/The-OpenROAD-Project/OpenSTA/master/README.md) 说明其读取网表、Liberty、SDC、SPEF 以及 VCD/SAIF 活动。应固定实际采用版本，按该版本支持命令执行，不能把当前网页功能等同于旧版二进制能力。reference STA 或仅核心 VCD 也不能替代 12 任务装载—CPU 调度—最后写回确认窗口。

正式总面积继续为：`A_core_logic + A_new_interface_logic + Σ(count_macro × A_macro)`，每个实例只计一次；复用 E203/共享 SRAM/固定外设另列面积，其动态和静态功耗仍进入系统窗口。缺失指定库和宏模型时，正式结论保持 BLOCKED；参考结果继续指导乘法流水、累加反馈、bank 输出选择及高扇出广播优化。

## 6. 本次关键文件校验

以下为审计时字节绑定；后续重跑另立报告，不覆盖历史文件。

| 文件 | SHA-256 |
|---|---|
| NangateOpenCellLibrary_typical.lib | `8d540a4d4cf6d09d27c87ad067857a9c0c2eeb023ab7a56e058cd3113db4e9b1` |
| quickstart.md | `3a13905e67e1b8f6e8075179a7ddfc64001e0519abbfa35fd9bafc97916ec4b0` |
| README.md | `5215361e0fde0c220b2d7a34f87acc1a40a83abdc7d1270f6850043b6a52f670` |
| tools/scripts/area_eval.sh | `0653b22e0e41d1fc7b60ddc3c29cc0dce4ec7525eaccf4d0afd948b986b1c210` |
| Sram1024x16.scala | `1a9439641b5ec46a5d8f680d999d3beb2d6b9b2e4a1175b4337cd47084f90006` |
| WeightBank.scala | `e1022f966a7c07b47573824c337aa145fda9666f827e408323442fb15c4a2ed8` |
| baseline/DotProductEngine_nangate45.log | `abb0ed571528a771bf26daa93f70df1ec743b1cf6490c2ab08e48afc16389525` |
| baseline/LinearComputeCore_nangate45.log | `fe06962bb88cda086f1731ac2bca914396dd26942141864ea8dae3a025daf19f` |

状态：库/接口/历史日志静态审计 **PASS**；参考综合重跑由集成主流程记录；本审计的参考 STA/宏适配/PPA **NOT_RUN**；比赛指定工艺/PPA **BLOCKED**。
