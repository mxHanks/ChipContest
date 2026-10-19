# 当前进度

更新时间：2026-10-19，Asia/Shanghai。目标：本科KWT-1第一前馈层，保留migration-v0.2和原rowpair基线，建立可替换SRAM并逐步完成真实数值、E203、指定工艺150MHz/增量面积<2.25mm²/完整窗口能耗验收。

当前阶段：**可迁移CPU v2与新版交接包恢复均已完成开发验收**。新行为基线`085210…8f007ab7/result.json`与显式新报告/平台的v2 `090411…6c7a24d6/result.json`均12层原生exit0，各304128输出/608256写响应/12ACK及恢复。两者同静音workload、开发窗口均21261300周期；同机共享工具/独立平台目录，不称另一OS验证。6CLI门槛与324主机检查通过；旧1830来源及RTL/FW/Golden/入口保留。正式宏/平台/PPA仍BLOCKED。负责人记录27：`docs/USER_CHANGELOG.md`。

GitHub交接准备（2026-10-19）：新增`docs/handoff/GITHUB_HANDOFF_20261019.md`及667文件清单，建议放主仓库`ChipContest/kwt-asic/`，保留E203子模块不变。按清单独立复制的324主机检查/static原生exit0；说明及命令独立只读复核，无clone/commit/push或新CPU/EDA。原始收据`artifacts/diagnostics/20261019-github-handoff/final-v1/result.json`，负责人记录28。目录/分支为待团队采用的方案，非远端已完成状态。

最新交接包`artifacts/releases/20261019T012341Z-3268eb-sram-development-cpu-v2-20261019/sram-development-cpu-v2-20261019.tar.gz`含666文件/36400172源码字节；独立目录逐文件SHA、324主机检查、静态入口及默认缺材料0HDL门槛通过，收据`docs/runs/portable-cpu-release-20261019.json`。包不含工具/平台/数据集/原始run，接收者按`SRAM_CPU_REBUILD.md`重建自己的CPU证据；不是另一OS/完整EDA环境认证。收据在打包后保存，包内manifest和随后checkpoint分别定义字节状态。此前620文件/204检查包保留历史身份，不扩大其结论。

## 当前已接受证据

| 范围 | 状态 | 证据与限制 |
|---|---|---|
| 迁移基线、原8路/优化rowpair、固定模型和Golden | PASS：已存历史证据 | 原492文件无缺失；原RTL/Golden/固件/平台未改。详见README、OPTIMIZATION_V1/V2；核心PASS不等于比赛验收 |
| 完整4445条validation软件开发精度 | PASS：开发范围 | 最大聚合NRMSE0.0132799%，最差样本层0.0195401%，零裁剪；非600条官方冻结评测/全验证集RTL回放 |
| 新SRAM原语/bank/共享模型 | PASS：功能 | 67案例（25正常+42预期拒绝）、7组匹配；20逻辑bank/415744bit，72容量原语/462848bit。当前`025313…304dae63/result.json` |
| 候选ICB协议 | PASS：开发接口 | 组合环已修；两后端各1完整+1abort任务、193938事务、86响应保持检查。`020523…e6432c66/result.json`；不含CPU SoC |
| SRAM核心及总入口 | PASS：功能 | 当前`025315…76c3780b/result.json`20阶段，新核心76任务/1926144输出、另原版12任务、ICB与完整12层SoC；外层`025310…sram-full-entry`原生exit0 |
| 含接口BLACKBOX预综合 | PASS：参考结构/映射 | 72 opaque、16MAC、44120标准单元、0.055476428mm²标准逻辑；`020610…173fe72f/result.json`。不含宏/复用平台 |
| 全FF结构对照 | PASS：历史结构 | 429231寄存位、26801个宽字RTLIL mux、21pmux、0memory；非全FF门级面积/STA，非真实SRAM指标 |
| 局部STA | 已覆盖参考路径PASS | 第四候选`045325…1f542ca4/result.json`，setup最差+4.652084ns、data hold+0.001379ns、removal+0.055262ns；原SDC/统计wireload/ideal clock。宏边界未知，正式全路径BLOCKED；原FAIL仍保留 |
| 缓冲映射实验 | PASS：参考映射 | cleanup修复实际全网通过，46026标准单元、0.056997416mm²（不含宏）；`022812…501ae448/result.json`。原失败和诊断保留 |
| 执行记录/主机工具 | PASS：工具 | 当前324测试及make verify，新增43项可迁移基线/原生/平台清单/预检范围检查；`portable-cpu/gates-v1/result.json`原生命令完整。620文件包/204测试是此前源码快照，未包括新预检工具，不扩大其恢复结论 |
| 参考综合网表功能 | PASS：所测12层零延迟 | 第四ECO`045551…mapped-replay-a9782263/result.json`，304128输出、1873549响应、9756保持检查；恢复1+1、末HI/ACK各12。共同逻辑SRAM/两态，非全输入形式或官方宏/时序 |
| 参考网表ECO | PASS：限定范围 | `045310…cap-eco-a2a7cf86/result.json`，46035标准单元/72宏，标准逻辑0.057015238mm²、相对原版+17.822μm²；SRAM面积未知。9 buffer及6处同函数强度替换，未改RTL/数值/SDC |
| 参考已知负载电气 | PASS：限定范围 | Make入口`045757…reference-electrical-a1c4d8a4/result.json`，48378输出/32类，已知cap/transition/clock无报告违例；182宏负载/1152宏输出驱动仍未知，完整电气BLOCKED |
| SRAM候选新SoC | PASS：开发12层 | `025544…356e16e2/result.json`，304128输出、608256写响应、soft abort和pending响应外部reset恢复；开发窗口21261300周期，非官方装载性能 |
| 官方平台/宏/正式PPA | BLOCKED | 缺正式E203/SDK身份、指定标准单元/PVT、宏功能/时序/面积/功耗数据，未知值不补零 |
| 官方材料预检 | PASS：工具，真实材料BLOCKED | `docs/runs/official-sram-intake-20261018.json`，9个CLI、22新增测试、全226主机检查；仿真/综合/时序/PPA分阶段文件计划。旧官方CLI仍待接通，文件核验不是模块/功能/PVT通过 |
| 官方原语/bank入口 | PASS：开发资格化 | 8场景/23,177数据检查、15预期拒绝；错误数据/缺模块/重复模块及夹具误用真实拒绝。`official-sram-contract…/final-v2/result.json`，全238主机检查；官方功能NOT_RUN、PPA BLOCKED |
| 覆写/复位门控补测 | PASS：开发功能 | 默认16/720，显式三后端24/1080分组检查，8组MATCH；3私有错误真实仿真exit1并准确检出。`docs/runs/sram-update-reset-20261018.json`，独立核签名/来源；非官方模型/PPA |
| Adapter核心/ICB入口 | PASS：开发资格化 | 14核心任务354816输出；12真实静音smoke为两态、2极值/ICB为四态。独立ICB25348输出/86保持/1reset丢弃；2实际故障拒绝，262主机检查。`docs/runs/sram-adapter-system-20261018.json`；官方宏/CPU/PPA未验收 |
| Adapter CPU入口 | PASS：开发资格化 | `060322…494a788d/result.json`12层304128输出/608256写响应/12 ACK及恢复；原平台/FW/RTL保留，相同形状/固件但不同输入的开发窗口均21261300周期，不是隔离后端A/B。独立索引`docs/runs/sram-adapter-soc-20261018.json`；非官方宏/平台/PPA |

当前运行和1073个唯一文件记录复核见`docs/runs/sram-implementation-20261018.json`，更早审计保留在`docs/runs/sram-current-audit-20261018.json`；完整日志在artifacts。宏切口标准逻辑证明NOT_PROVEN，目录`artifacts/diagnostics/sram-mapped-equivalence-20261018/`及purged子目录，两次均120秒超时；没有设计不等价的完整结论。

本轮框架审计：`docs/runs/sram-framework-audit-20261018.json`，1158个唯一证据文件SHA核验一致、原492文件无缺失、原RTL/模型/固件未变；`033333…sram-mapped-5c788634`的编译exit0但UNOPTFLAT被拒绝，未执行仿真。按位拓扑检查47332节点全部消除、无残余组合环，支持先诊断快照符号扩展表示；不是综合网表功能PASS。

后续A/B证据索引`docs/runs/sram-mapped-functional-20261018.json`：389唯一文件复核，12层回放原生exit0，合法格式兼容reader复用原binary，旧producer/失败保留。BUF_X8/X16宏切口视图removal -0.095160/-0.069030ns、data hold均-0.013133ns；仅有界电气诊断，不替换已接受映射或宣称完整时序。

最新来源索引`docs/runs/sram-reference-cap-closure-20261018.json`核验596个唯一文件，前一阶段`docs/runs/sram-reference-eco-20261018.json`保留。第三候选cap实查4驱动/8极性超限后，第四候选只作4处同函数强度替换，原图/72宏逐pin保持；实际重跑STA、全网已知电气、1层与12层。182宏输入负载/1152宏输出驱动未知继续BLOCKED；不把切口零外加负载当真实宏。方法见`docs/optimization/SRAM_REFERENCE_ECO.md`。

材料预检新索引`docs/runs/official-sram-intake-20261018.json`核验644个唯一文件，含旧596记录复核不变；实际入口`make -f scripts/official-sram.mk inspect-official-sram SRAM_STAGE=simulation`。当前缺包返回2/BLOCKED；私有非HDL夹具仅用于分类资格化、硬件任务0。未执行新的RTL/SoC/综合长回归，因为计算与冻结生产源未变。

独立BACKEND=3原语/bank入口说明见`docs/OFFICIAL_SRAM_CONTRACT_RUNNER.md`；它消费simulation源计划，不改旧核心/ICB/SoC CLI。默认缺包0条HDL命令；开发夹具绝非官方宏。final-v1父reader遇早期拒绝时缺identity字段而失败，保留原结果；修正初始/完整来源范围后final-v2的8 CLI/238主机检查通过。辅助include/外部数据/SDF/DPI尚无显式依赖清单，当前保守拒绝；不是完整HDL外部依赖证明。

当前契约入口索引`docs/runs/official-sram-contract-20261018.json`独立复核830个唯一文件，包含旧644记录全部不变；独立review核190文件/17来源ID/56原生命令。资格化限定为开发逻辑Adapter原语/bank及错误拒绝，官方功能NOT_RUN、PPA BLOCKED。

覆写/复位补测当前索引`docs/runs/sram-update-reset-20261018.json`复核1096个唯一文件，包含旧830不变。独立审查重算40正常case的全部签名，核6来源身份/307绑定文件/103原生命令；实际开发三后端结果一致，非真实官方宏或全序列证明。说明`docs/SRAM_UPDATE_RESET_VALIDATION.md`。

最新Adapter入口索引`docs/runs/sram-adapter-system-20261018.json`复核1346唯一文件，旧1096不变；默认缺包、缺前置及坏前置均0条HDL命令。新helper重验同包源SHA及33原生命令，不只信PASS/FILES_VERIFIED；旧核心/ICB CLI仍保持原源集。ICB未知响应/提前finish由新monitor实际拒绝，静态/功能接受不扩大为真实供应商或CPU/指定PPA。说明`docs/SRAM_ADAPTER_SYSTEM.md`。

最新CPU Adapter索引`docs/runs/sram-adapter-soc-20261018.json`复核1830唯一文件，旧1346不变；独立审查核完整前置33+9命令、731来源输入、143编译源、2私有替换、220运行输入/48向量与重算Golden。12层开发CPU原生exit0，官方宏/平台/PPA不继承；旧语音与新静音workload不同，周期相同不是隔离后端A/B。复现说明`docs/SRAM_ADAPTER_SOC.md`，历史两次前置失败及源码档案完整保留。

最新迁移入口索引`docs/runs/portable-cpu-20261018.json`复核2159唯一文件，旧1830不变；新行为基线和v2各12层/304128输出/608256写响应/12ACK与恢复通过。相同48向量/静音workload，开发窗口各21261300周期；显式新baseline/relocated平台，无隐式旧CPU报告。6CLI门槛、324主机检查、独立审查通过；说明`docs/SRAM_CPU_REBUILD.md`。当前仅证明同机换目录/同工具，未称另一OS/官方宏/PPA。

## 当前边界和阻塞

- 共享512KiB、平台TCM、AI内部20bank是不同对象。内部最多存4行Y；完整Y写共享区。72片/56.5KiB是容量模板，不是官方宏实装/面积结论。
- 一拍同步读、Q保持、reset不清payload、禁止同拍读写不变；不改X/W16、bias40、内部精确41、输出48和Golden。
- 新SoC必须按posedge真实响应统计，从CPU调度起包含配置/搬运/计算/等待/末写回与ACK；TB预装载共享区排除在开发窗口外，不能称官方完整装载性能。
- 根目录不是有效Git仓库，使用SHA checkpoint，不初始化或虚称commit；vendor和队友原仓库保留。官方材料缺失只阻塞正式宏/PPA，继续无依赖工作。

## 下一步（最多五项）

1. 官方文件到位后按`OFFICIAL_SRAM_INPUT_READINESS.md`填真实来源/SHA和用途清单；当前预检只收受控项目内文件，不自动复制/打包官方库。
2. 确认实际引脚/延迟/Q保持/碰撞，实施真实Adapter；先跑原语/bank和覆写/reset，再用已备核心/ICB入口重验同源Adapter；再用新增CPU入口复核同源12层，移植正式平台并补实际辅助依赖。开发夹具结果不继承为官方结果，不能只改旧READY。
3. 以指定标准单元/PVT/宏Liberty和真实IO负载重建映射/全部setup/hold/电气/覆盖；不能搬用当前精确buffer级数或典型角正值。
4. 正式150MHz/全部新增面积/功耗需指定角、宏Liberty/面积/功耗及正式装载窗口；未知值保持null，缺项BLOCKED。
5. 按`SRAM_CPU_REBUILD.md`生成接收方本机的原语/系统/行为CPU/Adapter证据；交接包不含工具/平台/原始run，历史harness不替代新机器验收。每里程碑保存实际源码字节checkpoint。

恢复：`source env/activate.sh && python3 scripts/harness.py resume`。阶段结束运行`python3 scripts/harness.py checkpoint --label <里程碑>`。参考候选接受仅限上述范围；正式PPA不能在缺材料时承诺完成时间。
