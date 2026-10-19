# 可迁移开发 CPU v2 固定范围审查

审查日期：2026-10-19（Asia/Shanghai）；被审运行日期：2026-10-18。结论：**PASS，限本次开发功能与来源完整性范围；无待修阻断项。**

本审查读取当前 AGENTS、PROGRESS、DECISION、需求基线及 `docs/SRAM_CPU_REBUILD.md`，实际执行 `python3 scripts/harness.py resume`（exit 0），检查新增入口、基线 reader、相对路径平台清单及对应测试，并只读复核已完成运行。审查过程没有重新启动 HDL/EDA，没有改 RTL、固件、Golden、旧入口或历史报告；仅新增本文。主代理负责随后生成来源索引与 checkpoint。

## 固定代码与说明

以下 SHA256 对应本次实际读取的当前字节，完整文件记录另由 collector 登记。

| 文件 | 字节数 | SHA256 |
|---|---:|---|
| `scripts/verify/run_sram_adapter_soc_v2.py` | 12085 | `f4eb72a81ec81f8ffc2ab71f24249e2f5bfd07d6e4d079dbb9491c49c58f5587` |
| `scripts/verify/sram_soc_baseline.py` | 23749 | `d88ef48ac160caefd1b8cd264553c3b3190681af3da7c1bf9ec7e1255de801df` |
| `configs/e203-development-platform.json` | 24475 | `5a352e228a40198196b3e50c13db403198723d2a6cfd2c96d3b9172f60794ae6` |
| `tests/test_sram_soc_baseline.py` | 28968 | `77130c38dc852d709d5e85ebcf2eadd55798c817a28eea61759c492b40dcd299` |
| `tests/test_sram_adapter_soc_v2.py` | 4466 | `d24e24ff1556daf38ced3e8a7b8c1b61a2990e0763b0f95ad7d01374378e640d` |
| `docs/SRAM_CPU_REBUILD.md` | 7052 | `73973854f7af89a9bfbbcc2f85360d053dee2bd71788d804e1849cc26adb72ae` |
| `artifacts/diagnostics/20261018-portable-cpu/collect.py` | 8889 | `ed266134fd96e38b512c903056de2d42a4ebd01f61d6af9245bb4895347502e8` |

## 实际复核及门槛

只读执行 collector 中 `review=ROOT/` 之前的完整部分，使用 `python3 -B`、设置原始 `__file__` 后 `exec(compile(...))`；exit 0，得到 **2156 个唯一文件、9023 次记录核验 PASS**。此数不含 collector 随后追加的本文等记录，不充当最终索引文件数。旧 `docs/runs/sram-adapter-soc-20261018.json` 的 1830 个文件记录当前 SHA/尺寸均复核一致，索引本体与 `20261018T084747Z-2993ce-progress-explained-20261018` checkpoint 相同。审查时发现过 collector 单行缩进错误，已由主代理修复；上述 SHA 和通过结果均来自修复后的完整只读执行。

另行执行只读断言（exit 0）：独立从平台原件重算两份 BACKEND3 私有补丁；重建 143 项编译源的精确有序集合并核编译 argv；核固件编译、objcopy 和 CPU 仿真 argv；复核 runner/plan/source 三份 canonical source_id、所有当前输入字节及保存的 identity。三个 identity 都未包含旧 `025544…356e16e2/result.json` 作为输入，v2 未调用旧 `baseline_inputs()`，未重绑 `S.BASELINE`、`S.PLATFORM` 等模块全局变量。

实际重新调用只读 `PRIOR.verify_system_report`，结果与 v2 保存的完整前置相同：系统前置 9 条原生命令、454 份依赖，并递归复核同源原语前置 33 条原生命令；未执行这些 HDL 命令。系统报告 SHA 为 `48f15b175f4d969308fae1f0831b788015c38ad4e3ee1a521304a498386316e0`，原语报告 SHA 为 `9505814c6f68aaf4eecabeb88f83086cc56c4fd56d20be0a2039801d3d8aa3da`。前置不是仅凭 PASS/FILES_VERIFIED 字符串接受。

基线 reader 检查指定平台下精确的 136 个相对 `.v` 路径、SHA256 和尺寸，拒绝同数改名、增删、重复、遍历及链接成员；同时核绑定 include。清单中的旧历史报告仅作来源说明，当前运行不读取该旧文件来继承 CPU 通过。reader 重新核 mandatory identity 集合、当前源字节、两份行为后端补丁、四条准确原生命令及完整保存状态、日志、工具、固件 ELF/BIN/HEX、仿真 binary、48 份实际向量和导出来源；调用数值模型重验 Golden，再从完整逐层日志重新计算结果。非法退出、超时、中断、缺少/重复完成族、错误最终 `$finish` 或报告汇总不符都会拒绝。

6 个真实 CLI 门槛覆盖缺包、缺系统前置、缺显式基线、坏基线、错误平台、有效预检，观察到退出码分别为 **2/2/2/1/1/0**；各自无工具/HDL命令、无 binary、无输出计数。有效预检只接受 `acceptance=PREFLIGHT_ONLY` 和 `development_cpu_functional=NOT_RUN`。`gates-v1` 另含 `make test`、`make verify` 两条 exit 0；完整 8 条原生命令及保存状态均复核。其有效预检使用显式旧报告作工具资格化，本次新的换目录基线/预检/完整运行由 `full-v1` 独立覆盖。

新增 38 项 reader 主机测试和 5 项入口控制测试使用惰性临时文件/模拟计划，不能代表 CPU 功能；保存的全套 **324 项主机检查 PASS**。`post-checks` 中 `make test`、`make verify`、`harness validate` 三条原生命令均 exit 0，测试日志确有 `Ran 324 tests`。本审查读取和校验这些实际状态及日志，没有再次运行完整测试集。

## 新基线及新 CPU 运行

| 证据 | 实际结果 | result.json SHA256 |
|---|---|---|
| `artifacts/runs/20261018T085210.474235Z-sram-soc-8f007ab7/result.json` | 新行为后端，4 条原生命令均 exit 0，CPU 665.177 秒 | `3d123a4f6960b74c43d3996962a5776e56e15298265eabb332480e18fb683350` |
| `artifacts/runs/20261018T090411.563908Z-adapter-soc-v2-6c7a24d6/result.json` | 新 BACKEND3，7 条原生命令均 exit 0，CPU 652.876 秒 | `a9a21a96c620f5129dc6fe097b94f2c52fed02bd7c72aa39fd89df93a4daa9bc` |
| `artifacts/diagnostics/20261018-portable-cpu/gates-v1/result.json` | 6 CLI 门槛及主机/静态检查 PASS | `3cd78724c83dd23525de0e1df488f06c05790c43392d3ce9c2704177be6cd098` |
| `artifacts/diagnostics/20261018-portable-cpu/full-v1/result.json` | 显式新基线及 relocated-platform；预检与完整运行各 exit 0 | `b820ca6fb4f3505c082e9ab2314e2e8a1fb5f37ea5aff045d0f712e9ca9b7eeb` |
| `artifacts/diagnostics/20261018-portable-cpu/post-checks/result.json` | 3 条收尾命令 exit 0 | `412547814227bd19b7dfd37c956c098537d2e809ccf6cd80703e58ebe5a22c27` |

两次真实运行均使用独立 `artifacts/diagnostics/20261018-portable-cpu/relocated-platform`，v2 的配置和 `platform_baseline` 精确绑定上述新行为报告。行为报告 source_id 为 `1f3df06b75665586b93c036e5c0994122771bee5733bf280e3460697b11d5ade`；v2 最终 source_id 为 `39833006bae8d66731ed08698f21ee02a9448a12fcf7b427299809d2cea19739`。

两后端的 12 层 X/W/Bias/Y 共 48 份文件已逐文件直接比较，全部相同；reader 也重新核了真实静音 smoke 导出的数值来源和 Golden。workload SHA256 同为 `75f3d426fe696a7ced3c16e2a6c92e9e75ce962a701deb8a647988b2bd864986`。此处对照的是新行为基线与新 Adapter 的同输入运行，未把先前不同语音输入的旧结果用于同输入比较。

两后端各有 12 个顺序任务、304128 个逐位结果、275712 次装载提交、608256 个输出写响应及 12 个 ACK。按 posedge 实际响应统计并检查末写回响应早于 ACK、ACK 早于完成；每层输出及响应守恒、12 层总和与日志 suite 一致，均正常结束于实际 TB 的唯一 `$finish`。soft abort、外部 reset 和中断 pending response 后恢复均为 1。TB 原有逐项 LO/HI 值及输出地址/掩码比较保留，CPU只调度/搬运。

新固件 ELF 各自独立绑定，不要求非装载内容相同；实际 BIN（716 字节）与填充 CPU HEX（196608 字节）逐哈希/尺寸一致，并核 BIN 到 HEX 的关系。共同 BIN SHA256 为 `7a8f2d44a5fe19c8f0216748667b0b1b0d4fbfaca4a3cb27412047584a6e842e`，HEX 为 `effeca1a9d4466c850063e8598516fdae1c9e30212e6c7562ea8fbd67ac6077a`。

v2 两份私有补丁的 SHA256 分别为 `2ace10e052238f1d95c3160625b350f55fd3e63cf2edb9a05f9cc7947de61e5b`（外设 BACKEND3）和 `91452e4fb14a8f81079713149837461ac65fde78d9e0ab01ddd2c3c2b9df6024`（checked 共享模型），均为唯一准确替换，平台原件未改。143 项编译集合是固定 136 项平台替换两私有副本后，加 6 项固定项目源及 1 项开发 Adapter；未递归编译 vendor。

UNOPTFLAT 2 条和 LATCH 15 条按完整诊断及缩进续行与新基线比较，归一化仅替换对应运行目录；块 SHA256 分别为 `7a8513fb88323b6cd81ce9bd350415393e6615534e6246fae86b07dc225a76ca`、`cfb08b87c60120ef10fe199279895f9a733e13a87f37ee2e10e7212bc6536d89`。两类保持 `UNCHANGED_DEVELOPMENT_LIMITATION`，没有因本次 PASS 消除。其余告警分类也保留。

## 接受边界

**PASS**：显式选择当前基线和精确平台清单的入口资格化；同机同工具、换平台目录后实际新生成的行为 CPU12 与开发逻辑 Adapter CPU12 功能证据；当前来源完整性。

两者开发窗口均为 **21261300 周期**，逐层核心周期也相同。窗口从 CPU 任务释放到最终接受 mailbox 响应，含配置、搬运、计算、等待、末写回及 ACK；排除 TB 预装载和中断 epoch。这些周期和主机仿真秒数不能充当正式比赛装载性能、芯片频率或能耗结论。

**NOT_RUN/BLOCKED**：真实官方 SRAM 功能 `official_validation=NOT_RUN`；正式平台和指定工艺 PPA 均 `BLOCKED`。本次使用同一 OS/机器和已核工具，未验证另一机器/OS或完整工具镜像。CPU 仿真仍为 Verilator 两态、Fork SVA 禁用；开发 Adapter 是逻辑夹具。测试输入为 `synthetic_zero_silence_smoke` 的真实 12 层权重导出，范围未扩展到官方 600 样本或全数据集 RTL 回放。指定宏引脚/时序/面积/功耗、指定 PVT/标准单元及 150MHz 全路径闭合仍须真实材料和独立运行验收。
