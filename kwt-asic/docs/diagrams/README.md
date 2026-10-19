# KWT-1 工程流程与数据通路图册

版本：2026-10-15。图册描述当前迁移基线与冲奖作品的后续工程路线，不能将图中的目标或候选结构当作已经实现、测量或验收通过。

## 五张图怎么使用

| 页 | 内容 | 主要用途 | 矢量源 / 高清图 |
|---|---|---|---|
| 01 | 项目工程总流程 | 从需求到最终作品的主路线，建议先读 | [SVG](00-project-engineering-flow.svg) / [PNG](atlas-1.png) |
| 02 | 三人并行工程流程与交接门槛 | 分工、阶段目标、每日同步和交接 | [SVG](01-engineering-workflow.svg) / [PNG](atlas-2.png) |
| 03 | 主机、E203、共享 SRAM 与加速器数据通路 | 系统架构、软硬件边界、接口与完成语义 | [SVG](02-system-datapath.svg) / [PNG](atlas-3.png) |
| 04 | 双行权重复用与有序写回候选 | 解释16个MAC、权重广播、重排缓冲和回压 | [SVG](03-candidate-microarchitecture.svg) / [PNG](atlas-4.png) |
| 05 | 数值、RTL、SoC、工艺、实验和交付闭环 | 验收路线与证据组织；解释两种正确性 | [SVG](04-verification-release.svg) / [PNG](atlas-5.png) |

整套 [PDF](../../output/pdf/kwt-engineering-atlas.pdf) 为五页16:9矢量页面，中文字体已嵌入；PNG为2560×1440。可以直接将PNG放进16:9答辩幻灯片，也可以用SVG保持缩放清晰。

原生可编辑文件：[kwt-engineering-atlas.drawio](kwt-engineering-atlas.drawio)。用 diagrams.net / draw.io 打开，共五页，框、文字和连线均可编辑。SVG也保留文本和矢量图元；跨系统缺少中文字体时优先使用PDF或PNG。默认中文字体为Droid Sans Fallback/Noto Sans CJK SC，拉丁字形使用DejaVu Sans。

## 读图约定

- A负责E203、驱动、搬运、集成和完整窗口计时；B负责RTL、指定SRAM及工艺报告；C负责真实数据、数值模型、精度、位级核对和复现。
- 流程图中的D1–20是2026-10-15至11-03的内部排期，不是确认的官方截止日。D12未过资格门则集中修复，D16未验证的候选不进入提交，D17后只修影响验收的问题。
- 当前已通过的是迁移首版、独立8路核心、位精确模型和所列静音回放。正式数据精度、官方E203和指定工艺仍待验收。
- 本图册的已验收基线指 `src/rtl/kwt_linear_engine.sv` 默认8路版本。图册取用的状态快照中，新 `kwt_linear_engine_opt.sv` 单行流水优化候选仅有lint检查，不纳入本图册的已验收范围，也不表示双行架构已实现；后续优化进展另见工程当前记录。
- 系统图实线表示载荷或结果流，虚线表示控制/状态；金色框是正式待验收部分，紫色虚框包含优化候选。交叉线未画连接点时不表示汇合。
- 第04页全页为候选。W读取量下降约49.5%是循环结构推导，不是总线传输量、整机能耗或性能实测。图中6KiB为两组结果缓冲的逻辑容量，物理宏取整和面积另算。每次只向选定的空闲组填入数据、从选定的就绪组排出；99行的末组只输出最后一行的256项结果。
- 每层X都来自对应层Attention、残差和第一LayerNorm之后；12层是12项独立前馈任务，不将上一项Y直接用作下一项X。Golden只进入检查器。
- 第05页软件数值模型用于全样本误差评估；RTL/SoC回放用于逐位核对并可复核误差。正式误差按层跨全部样本汇总平方误差、浮点参考能量和元素数量后计算NRMSE，取12层最大值≤3%，不能平均各样本的NRMSE；分母RMS下限为1e-8。12个性能任务还需各自≤3%，所有解码输出必须有限。原始整数码用于逐位比较，解码值用于浮点误差；本地验证不等于通过官方600条评测。
- 系统DONE在全部输出写事务确认之后产生。完整窗口包含输入/参数装载、CPU调度、总线等待、计算和最终写回；不使用核心周期冒充端到端性能。
- 面积门槛≤2.25mm²对应新增计算逻辑、接口和内部SRAM宏的合计；复用E203、共享SRAM及固定总线外设的面积单列。150MHz必须由指定工艺、有效约束和时序报告证明。
- 功耗在同一冻结配置、同一完整任务窗口统计E203、互连、加速器和SRAM的动态与静态功耗；记录活动映射和覆盖，缺少模型的部分不能记零。吞吐量=任务数/总时间，每任务能耗=平均功耗×总时间/任务数。重叠模块的活跃时间不可直接相加为总时间。

第05页的对照配置含义：

| 配置 | 结构 | 归因目的 |
|---|---|---|
| V0 | 单行×8列，正式SoC/SRAM基线 | 确定合格基线 |
| V1 | 单行×16列 | 单纯增加MAC数量的收益 |
| V2 | 双行×8列，单组行重排缓冲 | 同样16个MAC下比较数据复用组织 |
| V3 | V2增加第二组缓冲，允许计算/写回重叠 | 重叠的收益和额外成本 |

## 修改与复现

生成脚本为 `scripts/docs/render_engineering_diagrams.py`，数据图元还保存在 `diagram-source.json`。脚本同时生成SVG、draw.io与PDF；直接修改draw.io后重新运行脚本会覆盖draw.io，因此建议选择一种编辑方式维护，保留另存版本。

依赖：Python、ReportLab、Droid Sans Fallback和DejaVu Sans字体；PNG导出使用Poppler `pdftoppm`。本次使用Codex自带Python/ReportLab和系统字体，未改项目推理/RTL环境。

```bash
# 在具有ReportLab的Python环境中执行
python3 scripts/docs/render_engineering_diagrams.py
pdftoppm -scale-to 2560 -png output/pdf/kwt-engineering-atlas.pdf docs/diagrams/atlas
```

PDF/PNG应在每次修改后重新检查文字、框线和箭头。图册完整包为 `kwt-engineering-atlas.zip`，其中包含PDF、PNG、SVG、draw.io、图元JSON、生成脚本、本说明和生成时参考文档快照。`manifest.json`保存交付文件与关键依据的SHA-256；它验证文件来源及完整性，不是RTL或比赛验收报告。`source_documents`绑定的是`sources/`中的生成时参考快照，不要求工程的PROGRESS、DECISION等活跃文件以后保持不变。

本次图册技术与视觉检查范围见 [REVIEW.md](REVIEW.md)。

完整包内保留相对目录。解压后在`docs/diagrams/`执行`sha256sum -c SHA256SUMS`可核对全部交付内容和参考快照；压缩包本身另由`kwt-engineering-atlas.zip.sha256`校验，避免自包含校验的循环依赖。

生成时依据快照：[进度](sources/PROGRESS.md)、[决策](sources/DECISION.md)、[最终作品方案](sources/docs/FINAL_WORK_PROPOSAL.md)、[三人20天计划](sources/docs/TEAM_PLAN_20_DAYS.md)、[赛题需求追溯](sources/docs/requirements/UNDERGRAD_REQUIREMENTS.md)、[基线核心协议](sources/src/rtl/README.md)。
