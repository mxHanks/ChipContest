# 2026-10-18 SRAM Adapter CPU 独立审查

审查结论：**PASS，限定开发功能范围**。未发现需要阻止本次 BACKEND=3 开放 E203 两态静音 12 层 smoke 接受的问题。官方 SRAM 功能仍为 NOT_RUN，正式平台及指定工艺 PPA 仍为 BLOCKED；不将该结果扩展到官方 600 样本、全数据集 RTL 精度、四态 CPU、正式 150MHz 时序、面积或功耗。

本审查仅新增本文件。未修改旧源码、报告、平台 checkout 或测试，未执行 HDL、EDA、完整回归或 SSH。按项目约定读取 AGENTS/PROGRESS/DECISION/需求及接口说明，`python3 scripts/harness.py resume` 返回 exit0/PASS（仅任务图和证据完整性）。最终 checkpoint 由主代理统一保存。

## 实际核验方法与结果

1. 阅读并审查 `scripts/verify/run_sram_adapter_soc.py`、`sram_adapter_system_evidence.py`、底层原生记录检查器、SoC 日志判定、测试台、固件及本批资格化/收集脚本。检查器拒绝非终止状态、非整数或错误退出码、超时、中断、重复/残缺结束族和错误诊断。
2. 在 `python3 -B` 中以真实 `collect.py` 路径作为 `__file__`，仅执行其 `review=ROOT/...` 之前的只读前半段；未调用其写来源索引部分。当前字节 SHA 见下表。**1,827 个唯一文件、6,644 次记录出现全部 SHA/尺寸匹配**，旧索引 1,346 个记录全部保持一致，旧索引本体与已保存 checkpoint 字节一致。此数字不包含本文件和收集器末尾随后加入的记录，不是整个文件系统或完整运行环境的镜像证明。
3. 额外只读调用 `PRIOR.verify_system_report(...)`，完整重验同 Adapter 计划、原语 **33** 条原生命令、核心/ICB **9** 条命令、实际二进制、向量、结束计数和来源身份；系统依赖集合为 **454** 文件。不是仅信任 PASS/FILES_VERIFIED 字段。系统 14 核心任务共 354,816 输出，独立 ICB 25,348 输出、86 次保持检查、1 次 reset 响应丢弃；静音核心为两态，极值与 ICB 为四态。
4. 额外调用 `baseline_inputs()`，原行为开发 SoC 的 4 条原生命令及 **392** 依赖通过；136 份平台源固定且与旧冻结记录相同。再独立重构新入口全部 7 条预期 argv/cwd/timeout/log/state 路径，与实际记录逐项比较。核验 native state 文件与报告字段全等、所有日志/状态文件 SHA、`EXITED/exit0/not timed_out/not interrupted`。
5. 新编译列表恰为 **143** 个不重复显式源：6 个新 SoC/核心/内存源、1 个显式开发 Adapter、136 个平台源（其中2个映射为私有副本）。两份副本逐字复算，唯一替换分别为 `kwt_icb_slave` → `kwt_icb_slave_sram #(.SRAM_BACKEND(3))`，`kwt_shared512_model` → `kwt_shared512_checked_model`。原136文件 SHA 均未变；没有递归编译 vendor 或向综合源集纳入仿真夹具。
6. 重新核算 runner/plan/source 三份 canonical source_id，并验证保存 JSON 与最终报告相等，731 项最终 identity 输入 SHA 全部有效。源码/工具/前置先冻结、生成物在消费前记录并复核的顺序来自已绑定 producer；这是项目记录完整性证据，不是外部可信时间戳或完整编译器/OS 镜像。
7. 使用当前数值模型只读调用 `validate_export`，重算全部 **304,128** 个 Golden 输出；核当前 KWT 来源、导出 provenance，并比较 CPU 实际 48 份 X/W/bias/Y `.mem` 与经验证图像逐字相同。CPU `runtime_inputs` 恰为预期 **220** 份记录。Golden 只进入 TB scoreboard，固件只从共享区装载 X/W/bias 并回写硬件结果。
8. 新固件编译与 objcopy 均原生 exit0；四份固件源码与已接受基线一致。实际716字节 BIN 与旧 BIN SHA/尺寸相同；逐字验证补零至65,536字节后编码的196,608字节 HEX，并验证其与旧 CPU HEX 相同。ELF保留自己的完整SHA；非装载字符串差异不作为程序负载差异。新 simulation binary 已独立核SHA。

## CPU 原生观测

`artifacts/runs/20261018T060322.777092Z-adapter-soc-494a788d/result.json` 为 PASS。7 条原生命令均 exit0；编译 **14.220s**，CPU执行 **647.757s**。CPU 原生日志具有唯一完整 suite、唯一原生 `$finish`，没有被接收器拒绝的失败诊断。

12层各25,344结果、22,976装载提交、50,688输出写响应和1 ACK；总计 **304,128结果、275,712装载提交、608,256写响应、12 ACK**。独立重新解析每层配置→首X→末写响应→ACK响应→最终邮箱响应的严格顺序和窗口算术，与保存的 per_task 完全相同。测试台在真实 posedge 握手处计响应，保存请求元数据，逐位比较全部 LO/HI，并拒绝未完成写回就 ACK/邮箱结束。

日志分别仅一次记录 soft abort、pending输出响应外部reset（丢弃8个输出字）、实际重启释放；测试台确认 reset 清事务态、保留 test phase、重新装载并完成所有12层。总开发窗口 **21,261,300周期**；第0层1,771,830，其余每层1,771,770，core各1,370,718。窗口包含本次CPU调度/配置/装载/计算/等待/全部写回/ACK/邮箱响应，排除 TB 共享区预装载及中断epoch，不能作为正式完整装载性能。

旧行为基线使用用户语音，新 Adapter 使用静音。逐层 W/bias 相同，X/Y 每层不同；两者 workload SHA 分别为：

- 旧语音：`383712c4985d78490ee580f8f0288947cc1f031e820c634a98ad1817661f12eb`。
- 新静音：`75f3d426fe696a7ced3c16e2a6c92e9e75ce962a701deb8a647988b2bd864986`。

两次21,261,300周期及core周期相同，仅支持相同形状/固件下的开发观测，**不支持同 workload 或隔离后端性能 A/B**。“同源/同输入前置链”在此仅指新原语→核心/ICB→CPU使用同一 Adapter计划，且核心real12与CPU使用相同静音导出；原语/ICB使用各自契约向量。不指旧行为CPU基线输入相同。

## 告警、资格化与历史失败

新编译计113 WIDTHEXPAND、7 WIDTHTRUNC、4 UNSIGNED、11 CASEINCOMPLETE、15 LATCH、2 UNOPTFLAT。独立核对全部 loop/latch 完整多行诊断（仅归一 run 目录）与旧平台相等：LATCH来自原 `e203_clkgate.v`，UNOPTFLAT来自 CPU BIU/LSU及QSPI仲裁路径。其余诊断检查来源与类别：宽度/unsigned来自现有内存/核心及平台，CASEINCOMPLETE来自平台。该门槛仅严格保持 loop/latch 不变，**不是全部告警严格等同、无环证明或 clean lint**；未修改原CPU来迎合告警。

外层 `final-v3/result.json` 为 PASS，6条原生命令退出码依次 **2/2/1/0/0/0**；缺官方包、缺完整前置、坏前置分别 BLOCKED/BLOCKED/FAIL，三个子报告均0条HDL/工具命令。281项主机检查与静态入口通过。另存 `post-doc-checks.json` 的 make test（281项）、make verify、harness validate 3条命令均原生exit0，只代表当前主机/静态/任务证据检查，未重跑HDL。

失败没有改写：final-v1 子报告 FAIL，5条工具命令后因ELF整体SHA过严拒绝，CPU未编译/执行；final-v2 子报告 FAIL，6条命令后因warning reader误将make输出纳入诊断而拒绝，CPU未执行。两者没有 run.log。两个父资格化仍为FAIL，producer/qualification/test源归档逐项匹配各自绑定SHA。旧测试字节在失败后按已绑定SHA恢复保存；**不追补旧运行的预冻结声明**。final-v3才是首次完整CPU长测。

## 关键身份

以下为审查时实际字节，未全文展开731项输入清单。

| 对象 | SHA256 / source_id |
|---|---|
| CPU result.json | `5b7c915ccf3f7cf90a900abae76f3dd5aff1542b0fa77946960a683e7472e3c6` |
| final-v3 qualification result.json | `8f833218ba4957b5f3cffd55b85b524dee9e6038a14be82b9858001b43eb0ace` |
| CPU source_id | `20bde79dd9d6bf0e82a5e620e9e98f662adfd871a74fb369f016772fbf5333a8` |
| 同源core/ICB source_id | `23e35a122aeb77caed4fbccf667221de96e9258a8215d514e1794596a6a55a56` |
| 同源primitive source_id | `44c33f110232b2eb1f2141bfa384f6a1d1da2f767852f4413c74167906d5ca68` |
| run_sram_adapter_soc.py | `d09c1624a8ac3dab5c88c0c932e04dd37547465e9cec668144be171fb5a6d091` |
| sram_adapter_system_evidence.py | `cac17fa542178621c3f28eeb8adc5fcc08aa83fb61c338f3810167ee28f400d5` |
| collect.py（已审查当前版） | `6eaddcb7164e34257be0c41bc2d57535b0b19787b01241ad8de5bb4aa0754db9` |
| docs/SRAM_ADAPTER_SOC.md | `54dbfca3912ccef8a812058164be61d184ac7c13a0d360da63231670dd46727a` |
| post-doc-checks.json | `bc6d6bf8b31d9d888b6bc1390e0a18828f89f986416b3cd47d9d14eb5cef8068` |
| CPU run.log | `a38a26dbffd2ed14049e268c9a35451e5e73cff51c2b5c13e9c7c1d88d5a4abe` |
| 实际firmware.bin | `7a8f2d44a5fe19c8f0216748667b0b1b0d4fbfaca4a3cb27412047584a6e842e` |
| 实际firmware.hex | `effeca1a9d4466c850063e8598516fdae1c9e30212e6c7562ea8fbd67ac6077a` |
| 新simulation binary | `f7c4bce359623f222e355df14631a9cc6c8c01098866ef480b9d4c39ac9c4889` |

收集器审查范围：递归复核历史及本批显式文件记录，重算canonical身份、核原生终止状态与保存记录、重新解析CPU计数/事件、比较两份私有补丁、固件负载、告警和不同workload，并按归档别名核旧失败字节。它是本次固定开发证据的收集索引工具；未执行其最终写入部分，未将其输出字段当成独立的官方认证。开发逻辑Adapter夹具、开放Fork、两态/SVA禁用和已知loop/latch限制均继续保留。
