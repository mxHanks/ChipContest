# 16 PE＋共享权重＋独立 DMA：服务器综合结果（2026-11-09）

**综合映射及原始证据交付完成；当前约束下时序和设计规则未闭合，150 MHz 实现频率及正式资格未验证。** 本次使用服务器 Synopsys Design Compiler T-2022.03-SP5-5、SMIC S40 SS0.99V125°C 标准单元及 SRAM 库。成功映射运行于上海时间16:29:26—16:43:13，返回码0，输入无漂移。

## 面积与范围

顶层为 `xu_soc_ppa_top`，包含 CPU/TCM、原外围 fabric、新 DMA/仲裁器、512KiB共享存储端点和两行×八列核心；不是仅计算核心的面积。面积保留**库面积单位**：原生 `report_units` 没有声明面积量纲，不据此换算芯片面积。

| 范围 | 标准单元面积 | SRAM宏面积 | 合计 |
|---|---:|---:|---:|
| 完整数字SoC | 254,647.8648 | 3,083,052.72752 | 3,337,700.592142 |
| DMA/双行核心子树（已含于上行） | 106,848.0504 | 155,524.915038 | 262,372.965438 |
| 新仲裁器（已含于首行） | 274.512 | 0 | 274.512 |

共有111,978个标准单元叶实例、337个SRAM宏和217个原生常量；逐叶求和与 `area.rpt` 一致。宏组成：ITCM32＋DTCM32＋共享存储256＋权重16＋bias1。映射前后 CPU、外围 fabric、DMA、仲裁器、两个8PE引擎及上述宏数量均匹配。SRAM容量和宏数量未因第二路计算增加。无同条件8PE综合基线，**25%净增面积预算未验证**；不引用历史版本面积作差。

## 时序与设计规则

SDC采用HF6.666666667ns、LF30517.578125ns、JTAG100ns及保守divider envelope；未添加false path、multicycle或clock-group切断。时间单位为ns、电容为pF。I/O约束为工程假设，尚非板级/赛题签核契约。

| 原生DC结果 | 数值 | 含义 |
|---|---:|---|
| setup最差裕量 | −366.30566406ns | HF时钟到GPIOA[27]调试时钟输出，经过 `inspect_core_clk`；其中高扇出缓冲贡献约372.125ns |
| hold最差裕量 | −0.13472036ns | bias `writeWord_reg[1]/[5]` 到SRAM数据口；到达0.359328ns，要求0.494048ns |
| QOR汇总hold违例 | 104 | 工具汇总；多个时钟组条目不能重复解释为独立物理路径 |
| 设计规则 | 3条max-transition、2条max-cap | 仍未闭合，包含DMA核心网络 |

最差setup主要受调试时钟输出、高扇出延迟模型影响，**不能由−366ns反推MAC最高频率**。原始报告中一条DMA MAC控制到累加器路径仅有约+0.000421ns裕量，也不能据此承诺布线后150MHz。未做CTS、布局布线或寄生参数提取；DC报告不能代替独立STA。

时钟告警保留：TIM-276提示HF/LF周期比超过展开上限，部分跨域路径可能未约束；TIM-128/141涉及门控时钟；TIM-099报告20,557个时钟脚受多个时钟驱动。原采集脚本中的 `check_timing -verbose` 和 `get_clocks -of_objects` 不受此DC版本支持，端点文件仅有表头；其 `REGISTER_CLOCK_PINS=1`、`NO_CLOCK_ENDPOINTS=0` **不是覆盖证明**。已从同一DDC补采兼容报告（仅读取网表，未重新映射），18项输出哈希全部匹配、工具无Error。导出22,754个寄存器时钟脚及337个SRAM时钟脚，SRAM无缺脚；脚存在不等于时钟关联和覆盖已证明。原生 `check_timing` 明确报告AON的 `bootrom_deglitch/T_8_reg/D`、`dwakeup_deglitch/T_8_reg/D` 两个端点未约束，TIM-276仍在。补报[原件](../build/server-dma-synth-20261109/native/r3-post/post.tar.gz)和[检查结果](../build/server-dma-synth-20261109/native/r3-post/extracted/xu-dma-synth-20261109-r3-post/check_timing.rpt)均保留。

因此，原完整12层的1,188.718 task/s仍是**按150MHz换算的功能仿真吞吐**，此次综合未将其升级为已验证实现频率下的正式成绩。

## 源码、失败记录与证据

功能来源为完整12层R2冻结源码，而非仅按当前gitlink重新搜集。父提交 `66cd66da3d2416c6b2f7cc8f3f45f87aa609ffbf`，E203提交 `79c8af1cd92589ddeb3f49edb5b9e4454fcf8efa`；保留三项已验证生成RTL覆盖。功能结果SHA256为 `47a7c6de0d16280d95d9d329114e9f117fd835d0ac83b96b22c7c7912ebec62a`（304,128个输出）。

- R1：旧接口未实例化文件在分析阶段触发VER-956，未进入映射。
- R2：外围DMA连线声明顺序触发VER-262，未进入映射。
- R3：158个分析文件，排除未实例化的旧接口文件；仅调整DMA及外围连线声明顺序。两项独立等价证明分别1907/1907和3519/3519通过、0未证明。表达式/状态逻辑未改；这些证明不是整个映射SoC的等价签核。

R3输入清单SHA256：`8802336d24a74e1554b80417740ae0fad3e0e2dfa4d58b0c5191445ad42d5a3b`。
标准库SHA256：`f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723`。
SRAM库SHA256：`c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f`。

[完整服务器原件](../build/server-dma-synth-20261109/native/r3-full/full.tar.gz)（15,300,427B，SHA256 `e6643810b04a7149fd96096ef386c7530059dee35e1780585c786a372fbff7bc`）包含源清单、网表、DDC、SVF、报告和最终文件封存清单。[本地核验](../build/server-dma-synth-20261109/review/final-full-r3.json)确认223个封存文件完整、面积一致、所有输入无漂移。运行器对 `launcher.log` 的哈希在最终状态追加前记录；原凭据不改写，外部最终封存逐字节核实了唯一追加内容。

[执行与复现说明](../experiments/s3-y32-dma-day/server-synth/README.md)；[综合网表](../build/server-dma-synth-20261109/native/r3-full/extracted/candidate/mapped.v)；[面积原件](../build/server-dma-synth-20261109/native/r3-full/extracted/candidate/area.rpt)；[setup原件](../build/server-dma-synth-20261109/native/r3-full/extracted/candidate/dc-setup.rpt)；[hold原件](../build/server-dma-synth-20261109/native/r3-full/extracted/candidate/dc-hold.rpt)。

FTP接受上传但拒绝下载，原件经已授权VNC通道回传，逐块及整文件SHA256核验。交付中不含凭据或工艺库二进制。服务器临时剪贴板发送设置已恢复为0，仅本轮启动的vncconfig进程已退出；结束时未观察到本账号重型EDA作业。未推送、未发PR。

[本地完整交付包](../build/server-dma-synth-20261109/handoff/s3-y32-dma-server-synth-evidence.tar.gz)与[解包核验凭据](../build/server-dma-synth-20261109/handoff/receipt.json)保留所有尝试、声明等价证明、服务器原件及独立复核。

下一步应先审查时钟输出/门控/跨域契约并补全独立STA，再处理bias SRAM hold及DRC；在完整覆盖下检查MAC裕量。映射后功能等价、SRAM PVT/EMA适用性、功耗和正式赛题资格均仍需独立验证。原流程查询设计属性 `is_black_box` 在此DC中不受支持，该项守卫无效；映射后逐叶 `is_mapped`/正面积核验、库引用与宏数量检查仍有实际证据，不能据绿色完成标记宣称所有检查通过。
