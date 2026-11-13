# xu B41 项目接续进度

## 当前执行 · 官方 32-bit 工程迁移

2026-11-12 用户已明确将工程完成置于 PPT 之前，并选择“合规材料先行、严格分层，未验收不宣称”。本段是当前有效进度；下方旧门级/功耗记录保留作历史交接，不改变其原始结论。

| 状态 | 步骤 | 当前结果 |
|---|---|---|
| completed | 官方约束审计 | 已从官方 Q&A 与实施方案确认：原 System Bus 必须保持 32-bit；DMA 必须走共享 SRAM 规定路径；禁止 DMA64/128、TCM 绕过、独立 SRAM 写口、TB-only preload 与 direct stream；完整 99×256 Y 输出、加载时间和 600 样本要求均已列入合规矩阵。 |
| completed | 32-bit DMA 适配器实现 | 已生成 `output/xu-b41-20261112/rtl/xu_matrix_dma32_tile.sv`。保留 64PE/41-bit 计算核，W/X/bias/Y 均通过原生 32-bit beat 传输；无 64-bit 外部端口。 |
| completed | 独立向量验证 | 12 个冻结 layer 全部通过，逐位比较 25,344 个 Y32；每层统计 `reads=11872, writes=25344, x=3168, w=8192, bias=512, y=25344`。该结果标记为 `LOCAL_32BIT_ADAPTER_PASS`，不是官方 SoC 验收。 |
| completed | 接入完整 E203/SoC 32-bit 路径 | 已复制隔离的 `output/xu-b41-20261112/official32/source`，使用 `XU_MATRIX_DMA`、不定义 `XU_MATRIX_DMA64`、`EXTERNAL_SYSMEM=1`，并在 `e203_subsys_perips.v` 接入 `xu_matrix_dma32_tile`；frozen source 未改写。 |
| completed | 全 SoC 32-bit 展开烟测 | Verilator 全 RTL lint/build 完成并运行 `OFFICIAL32_SOC_ELAB_PASS`。该测试覆盖完整 `e203_soc_top` 的 32-bit 端口形状和模块展开；仍不等于官方固件、协议、时序或功耗验收。 |
| completed | 自有服务器 staging | official32 包已传到 t7920：`/work/leo/chipcontest-xu-own155-diagnosis-20261105/b41-official32-20261112/official32`；远端核对 341 个 RTL 文件及 build/testbench/adapter SHA 与本机一致。新增 `pack32.py`、`BUILD-MANIFEST.md`、`manifest-sha256.txt` 也已同步并逐项核对。t7920 当前没有 Verilator/iverilog，因此不把远端 staging 误报成已复跑。 |
| in_progress | 自有服务器可迁移回归准备 | 普通工程文件、冻结输入和交接包已集中在 t7920；本机继续执行需要 Verilator 的回归，远端仅做 staging、传输和可用工具检查，官方 VNC 不参与这些普通编译。 |
| in_progress | 全 SoC 32-bit 功能/协议仿真 | 已加入原生 32-bit 外部端点诊断夹具并成功展开；独立 TB 的 AON/shared-memory 复位未释放，严格记录 `LOCAL_32BIT_SOC_RESET_GATE_BLOCKED commands=0 shared_rst=0`，不计作传输通过。下一步使用既有项目复位/固件启动环境或官方原生环境复跑。 |
| pending | 官方服务器执行 | `cats-linux/cats-compute` 只指向 CATS-R4；VNC `ic4h22.nicu.cn:15923` 可达，FTP `icdesigns0.nicu.cn:18888` 当前返回连接池 421。官方目录仍为 `/tmp/xu-b41-close-20261111-r1`，确认必要动作后才走 VNC/FTP。 |
| pending | 交付封存 | 32-bit 源码、打包脚本、manifest、日志和提交清单待全 SoC 结果后统一封存；未完成的门级、STA、功耗、600 样本精度不提前宣称。 |

## 当前执行 · 最终网表门级与全 SoC 功耗

2026-11-12 用户提供更新的交接文档，要求继续完成项目。现场信息以恢复连接后的原生结果为准，交接文档提供定位线索。当前无原生计划工具，使用下表维护进度。

| 状态 | 步骤 | 当前结果 |
|---|---|---|
| completed | 恢复中断连接并核对现场 | 同一 StrictHostKeyChecking=yes 回环隧道已恢复，本机 SSH PID 15259，RFB 003.008 握手通过。用户已完成认证，服务器 2026-11-13 07:38 确认官方工作区 3 可用，旧控制器和重任务已自然排空，原 eda.lock 可取得。 |
| completed | 完成复位、观察映射诊断及短回归 | 官方库 BDD 已证明 14 位复位 D 恒为 0（312 节点），独立功能副本 SHA `2d2a23089d62d7c3c27e98ef20fc156dc15df7a260927d106ba5490806523a0c`。快照保留 484/556 个物理可见位，其余 72 位无非声明引用。首次物理清零通过：18,176 次写入、1,027 周期。随后已证明 DMA 仲裁器地址 20 个信号位、12 个零常量位及 8 个全一掩码位的实际连接，观察映射保留完整比较与 85 处 fatal；编译 40.800 秒退出 0。短回归 r3 为 20.814 秒，越过 checker 135 与 DMA fabric identity，首次 Y 写在 16619381671395 fs 触发 “Y mismatch layer=0 index=x”，仍 0 任务、0 warmup；原生确认核心输出行号复位有效时仍 X、FIFO 存储结果已知；已将证明扩展至 17 位并生成新副本 SHA `d8e1c611016b0baa943115078ad49f6e0a147980a7e9fe13df5d3e5827da95ac`，独立编译 41.623 秒退出 0；90.016 秒受限短回归到时退出 124，无 fatal，已检查 4,008 笔 Y 写，仍 0 完整任务、0 warmup。短回归不作为 full12 通过。物理网表原 SHA 保留。 |
| in_progress | 完成三固件门级、全 SoC 能耗及版本绑定 | tight、phased、backoff 均已完成 12/12 正式任务及 1 个 warmup，无 fatal，三份 verified-binding 均已封存；backoff 独立 R3 复核通过（payload 416,580、软件控制窗口 430,176 周期）。功耗 PID 160819 已完成门级前置和边界活动检查，正在同窗执行 tight-O2-ss 原生导入；固定工作点队列 PID 173281 继续等待功耗自然终态。 |
| pending | 核验物理资格并更新交付材料 | 三段 Formality、原约束四工况 STA、电气、SRAM 模型与面积已审阅并绑定。保留已通过证据，不重复运行；完成 4 个低频 unknown 的工作点范围说明，回填三固件功耗及能量选型，重建报告 PDF 并封存交付清单。 |

## 已完成 · GitHub 交接材料发布

2026-11-12 用户已明确批准将 501 文件补充包公开发布至 mxHanks/ChipContest，分支 feature/xu-b41-handoff-20261112。补充包 SHA256 为 f494c03a766cef578774a79653a540fa2291102733de7e6289e6e8bbcfe5cea7。

| 状态 | 步骤 | 当前结果 |
|---|---|---|
| completed | 准备、校验并确认公开载荷 | 272 项冻结输入、35 件原件 SHA 保留，两项离线复算 PASS。用户已批准确定的补充包、源码、证据与路径信息公开上传。 |
| completed | 写入交接分支并提交 | 已从批准的补充包写入展开文件，复制原包和 SHA 文件，Git 索引逐项字节核对通过，生成提交 5c52517。 |
| completed | 推送并核对远端 | 提交 5c525177b652f46d9f8233a0bc64a95c35309ab2 已推送。GitHub API 确认分支提交及全部 503 个关联文件的 blob ID，重新取回补充包的 SHA 与批准值一致。 |

最终硬件网表、等价和电气闭合、门级功能与全 SoC 能耗的接续任务见 docs/xu-b41-handoff-20261112.md。队友继续官方现场验收。

## 连接与控制器修正

用户已手动解锁 Mac，官方工作区 3 恢复。整体副本等价脚本随后只启动了一次，PID 295350，已自然结束；回执、原生日志、脚本及两端网表 SHA 已核对，58,337 个比较点通过，范围审阅完成。

R14 缩进错误使锁仅覆盖预检；新 FM 与门级出现过并发。未停止原门级或功耗控制器。已补持原目录锁，并为 R15 增加原生进程名检测与锁内运行的 AST 检查，保留此事件与全部原日志。后续按实际原生终态接续，不以已启动或局部通过作为完成。

已创建报告源稿 `output/xu-b41-20261112/B41-作品设计报告.md` 与 `report-data.json`。门级、功耗、能量及选型尚未完成的字段保留待测，不作为最终 PDF 或资格报告。

## 本轮新增独立核验

- RTL → 双角基线的接续 r2：58,332 个比较点通过，恢复检查点、回执、脚本和日志 SHA 一致；18 个参考未匹配位已定位。基线 → 最终物理同为 58,332 passing；功能副本整体为 58,337 passing。范围见 `FORMAL-AUDIT.md`。
- 厂商 SRAM 预检：全 1,024 地址与 4 个四态未知字通过，compile/run 均退出 0，模型/测试台/工具/日志 SHA 一致；门级 430 个展开 CPU 断言的启动边界已记录，见 `CHECKER-MODEL-AUDIT.md`。
- 最终网表面积独立展开为 206,980 个叶实例、352 种引用、337 个 SRAM，全部匹配官方 LEF。新增计价面积 0.508327099038 mm²；把全 SoC 标准单元均计入新增预算的保守上界为 0.65290172150 mm²，低于 2.25 mm²。官方独立复算回执为 `xu-final-area-audit-20261113-r1.json`。
- 服务器 00:39：R15 tight 已通过 warmup 与 10/12 个正式任务，当前仍在运行；此前 VCD 约 62.92 GiB、剩余 747.19 GiB。原生 clear 观察为 1,027 物理周期，主 TB clear 窗口为 1,028 周期，两种边界分别保留。不把局部通过记为完整验收。四工况 12 份电气原报告已逐一核对，三类违例均为 0，官方审阅回执 `xu-electrical-audit-20261113-r1.json` 保留报告 SHA。
- 已生成 5 页 PDF 工程审阅稿 `output/pdf/B41-作品设计报告.pdf`，完成逐页渲染检查并修正架构图重叠。实测门级、功耗及固件选型仍待完成后回填，当前不是最终冻结版。

## 后续补查已准备，尚未启动

- 官方 `xu-workload-qualification-r1.py`，4,954 字节，SHA 前缀 4ec9f51e：保持原 SDC，重新采集原四工况及四个未知端点的实际输入锥/时钟；随后以任务期间固定的 bootrom_n=0、dwakeup_n=1、erst_n=1 做独立工作点补充检查。它不更改原网表、原约束或原报告。脚本绑定旧控制器的进程开始标识，旧门级和功耗未自然终态则拒绝启动；AST 确认原生 run 在 eda.lock 内。
- 官方 `xu-b41-power-payload-r1.py`，6,314 字节，SHA 前缀 0fca06fa：服务器本地由既有功耗脚本适配，单独测量 12 段 payload；原 clear+payload 结果保留。除旧控制器自然排空外，还要求三份 R15 verified-binding、相同配置及三份原功耗 output_sha256 齐全才可启动；流式验证 VCD SHA。AST 确认实际 run 在锁内，时间段每任务仅两个端点。
- 两个脚本均只是准备完成，未启动、未取得原生结果；按现有门级与功耗完成后串行接续。

## 最新原生里程碑 · 服务器 2026-11-13 00:50

tight-O2 独立审阅回执为官方 `xu-gate-independent-20261113-r1/tight-O2.json`，SHA256 `1c91297b765b337dd2bd02b0432aed63686b8812d70d6a805b71ec23115be834`。12 任务 payload 合计 416,580 周期，主 TB clear 12,336 周期，principal 428,916 周期，gap 528 周期；这些是原生窗口复算，不以理想频率换算代替实际时间。波形 97,571,429,543 字节，控制器封存 SHA256 `44caf59b71ace97b6c7d32f947783e894727761d97be65cd4a7dcab743f28c64`，后续 payload 补测将独立流式重验。最初审阅在绑定文件写入未完成时遇到空 JSON，未改文件；封存完成后重读并通过。当前没有已验收功耗、能量或固件选型。

服务器 00:56，扩展独立复算 r2 通过全部 clear 脏前态、物理夹具字段、逐批有效行数与软件计时。169 批为 156 批 8 行、13 批尾部 3 行；软件完整控制窗口合计 429,864 周期，与冻结 RTL 一致。r1 错把 TB firmware_cycles 合计命名为 software_control_cycles，r2 已明确区分 429,744 和 429,864；原 r1 回执保留。最终采用的 r2 回执及综合导出哈希见 `FINAL-ARTIFACTS.md`。

原功耗仍在导入波形。另已准备窗口副本提取工具，7 项独立语义测试通过，覆盖精确边界、间隙状态恢复、X/Z、别名、实数及截断拒绝。官方原 VCD 头部只读检查为 187,574 个唯一标识符、8,540 个别名，别名位宽无差异、时间单位 1 fs。工具仅已写入，未裁剪正式波形、未中断原功耗；原件始终保留。

## 认证恢复后的真实终态与接续 · 服务器 07:38

原功耗 `xu-power-20261112-r1/tight-O2-ss/receipt.json` 为 native_exit=124、complete=false、seconds=2400.007，SHA256 `bd765e8f210b9faf07e9e6e92ada22d31f81ce133b6b0d97eebf9d55940eb479`。R15 因 `/proc/299096/stat` 已消失而退出；不是新一次门级失败。两份待测固件目录和绑定均不存在，未重复运行 tight 或中断旧进程。

已同步 `prepare_window_vcd_r2.py`，7,784 字节，SHA256 `fab52887895df2f59f8a1c2231be2649f8464c53af0a5cd197080765cd62ef42`，与本机新入口及计数检查版本一致。提取器源码 SHA 同原已测试版本。旧作业排空后只启动一次窗口流程 PID 136718，先独立重验原波形，再提取原 24 段的完整信号与事件；输出独立位于 `xu-windowed-vcd-20261113-r1/tight-O2`。尚未取得新功耗结果。

## 当前优先级与实际接续 · 服务器 08:05

用户要求优先做完本版，允许跳过不必要验证。保留完整门级、评分计时窗口功耗、必要时序范围说明和交付封存；跳过已通过项目的重复验证、额外波形裁剪开发以及可选的 clear+payload 重复功耗测量。

窗口原型已自然退出 1：原 VCD SHA 独立校验通过，提取器随后拒绝 `$dumpoff`，只有未验收的头部 partial 文件，没有正式输出或成功回执。原 TB 已仅在正式任务 clear 到最后 Y 后一周期打开 dump；继续裁剪收益有限，停止该方案。

R16 由未修改的 R15 在服务器本地适配，7,910 字节，SHA256 `c44f7a62da04ce9dbb4b52fec6023c1e4d9d265cd59fe479bffb0b0f4e28ee0a`。复核相同 95 份输入、五项配置 pin、tight 原生日志及独立 r2 回执后复用第一份结果。仅移除对已退出功耗控制器的依赖，另两份完整任务和错误检查、20,000,000 周期上限、锁内原生执行均保留。输出沿用尚不存在的 R15 campaign 路径，并以独立 R16 preflight、适配清单及控制器日志记录接续身份。

08:04:53 启动前本账号无 EDA 重任务、锁可取得、磁盘余量 670.36 GiB。08:05 确认控制器 PID 156004、原生 simv PID 156023，`phased_64_fast4-O2` 正在运行，`backoff_8_256_fast4-O2` 随后串行执行。当前仍只有一份固件完成，未把启动记为通过。

08:10 已排队必要功耗控制器 PID 160819，脚本 `xu-b41-power-payload-r3.py` 为 4,664 字节、SHA256 `46e2c0586463fdbcc7fbc3d47ae99b7e30706a327787c4c429d8e9b87f0629d5`。它绑定当前 R16 的进程开始标识，等待两份完整终态和绑定文件后，再串行测量三固件 12 段 payload。原生 run 位于锁内第 61 行；仅在厂商 SAIF 与原生 VCD 边界活动属性一致时使用 SAIF，且逐份要求 DURATION 精确匹配，否则回退保留原 VCD 的直接导入。08:11 确认功耗只在等待，当前唯一 EDA 重任务仍为门级 simv；phased 已通过 1 个正式任务和 warmup，无 fatal。

08:18 phased 已通过 3/12 正式任务及 warmup，无 fatal；另外两份分别为 tight 已验收、backoff 尚待串行启动。08:19 已排队最后的固定任务工作点时序补查 PID 173281，包装器 SHA256 `87aecaa2f22f0b9a0cc65131adcb90c5133db85a8bad9216d7ecc15ba772efb3`。它等待 R16 与功耗的具体进程开始标识全部自然终态、实际重任务排空后，执行已准备的原版 `xu-workload-qualification-r1.py`；保持原约束和物理网表，只补查任务期间固定引脚对应的 4 个低频 unknown。08:19:54 已确认两份队列均只等待，唯一 EDA 仍为 simv。
