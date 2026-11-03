# xu：S2d / PE32 原综合网表等价与后续时序修复证据

本次服务器执行取得两份**有条件的原综合网表 Formality 通过结果**；后续 hold / gating 修复网表的已测试数据与门控检查没有违例，但仍有复位 removal、电气约束及未测试检查。**两项配置均未取得完整 150MHz 资格，也不能据此计算比赛能耗或总分。** 本目录只新增证据与离线检查，没有修改 Chisel、生成 RTL、固件或服务器输入。

| 实际执行 | S2d 双缓冲 | PE32 |
|---|---:|---:|
| 原网等价 campaign | `s2d-formality-campaign-20261103-16` | `pe32-formality-campaign-20261103-17` |
| 原网 passing compare points | 43,440 | 47,758 |
| 其中 BBPin / Port / DFF / LAT | 17,136 / 144 / 26,121 / 39 | 17,952 / 144 / 29,623 / 39 |
| 未比较 unread DFF | 511 | 511 |
| unmatched reference / implementation | 17 / 0 | 33 / 0 |
| FM 记录的 before / after 文件数 | 158 / 158 | 161 / 161 |
| 后修复 campaign | `s2d-hold-gating-repair-20261103-19` | `pe32-hold-gating-repair-20261103-21` |
| SRAM 宏数量 | 336 | 352 |
| 最终 PT setup / hold 违例 | 0 / 0 | 0 / 0 |
| 最终 PT gating setup / hold | 27 / 27 均 met | 27 / 27 均 met |
| 最终 PT removal 违例 / 全部 untested | 5 / 27,237 | 5 / 28,610 |
| 最终 PT max / min 最差 slack，ns | 0.000000 / −0.121483 | 0.000000 / −0.121483 |
| 最大 / 最小电容违例 pin block | 87 / 1,404 | 51 / 1,410 |
| DC 报告 HF GPIO 路径 slack，ns | −366.31 | −366.30 |
| 修复后完整 SoC cell area，µm² | 3,387,946.249303 | 3,615,601.175056 |
| 修复后加速器层级 cell area，µm² | 311,751.6765 | 539,763.4679 |

加速器层级面积分别约 **0.31175 / 0.53976mm²**，包括该层级物理 SRAM；全 SoC 数字包含固定 CPU、共享存储等，不能与加速器 2.25mm² 上限直接比较。本表是指定工艺库下的综合 cell area，没有布局布线与物理签核，也不替代比赛方对新增接口及面积归属的最终核查。PE32 的 32KiB 逻辑 W 存储映射为 32 个 1024×16 宏，物理容量 64KiB；固定 SoC 320 宏未缩减。

## 网表身份与等价范围

S2d 候选 main `3af4db98b893edd2103771fa132d69350b82ba96`，e203 child `dd692c190dadafd9baa6dffe8514a3f684e7fbf5`。PE32 候选 main `94ce6f0f54fffdd590ff9a3ebad0197ec0fd9114`，child `fc3977d0a6d5f85fbfd871fd9439c01c9acab5f5`。定义分别是 `SYNTHESIS DISABLE_SV_ASSERTION=1` 与额外 `XU_ACCEL_PE32=1`；`raw/context/` 保存先前已提交面积归档的 prepared / execution / implementation 与完整 `rtl.f` 原文。

| 配置 | FM16 / 17 实际验证的原综合网表 SHA-256 | PT19 / 21 实际分析的修复网表 SHA-256 |
|---|---|---|
| S2d | `025240541e4c58318c9fa44e816b54cbcc78f29cd8b5ea8672343a3840118137` | `7f1c1efaa27d9eb06a6e8a1979d43df3b7a0eaadb992c1096c4bf36f19477bab` |
| PE32 | `ca1d17a9adcd1a15e7b69758754e68d962c7535d8f2b31407c47d9bd136014c8` | `8aa1d86f72e4752e35a117ffa5359cd4cb76f1fc11130f3f178693ed584b8bbb` |

FM16 / 17 不包含 repair19 / 21 的 `repair.svf`，因此**原网的等价结果不能转移为后修复网等价通过**。本目录没有这两份修复网与 RTL 的新等价结果。

两份 FM 执行均退出 0，唯一实际 `XU_FULL_SOC_FORMALITY_PASS` 标记及 `Verification SUCCEEDED` 可在完整 `fm.log` 找到。FM 条件原文全部保留：

- `synopsys_auto_setup true`；`verification_set_undriven_signals synthesis`；`verification_verify_directly_undriven_output false`。日志还提示 RTL interpretation 与 logic simulator 可能存在差别。
- SRAM 在 reference / implementation 中均作为 black box。BBPin 等价没有证明 SRAM 存储体功能、PVT 或初始化行为。
- 17 / 33 个 unmatched reference DFF 分别是 16 / 32 个 W 适配器 `valid_read_reg`，加固定平台 PMU `count_reg[15]`。511 个 unread DFF 仍未比较。
- before / after 记录覆盖精确 `rtl.f` 的 155 / 158 个源文件，加 `rtl.f`、原 `mapped.v` 与原 `default.svf`，两次记录一致。**商业 DB 未列入这次 FM before / after freeze**；FM Tcl 中路径与 PPA / repair 中记录的 DB 路径一致，但不能补称 DB 在 FM 期间已做字节冻结。
- 大型 RTL、mapped / SVF 与商业 DB 字节仍在服务器，未随本目录提交。离线检查复核的是接收的原始日志、清单及 receipt 链，没有重新执行 EDA 或在本机重算这些未下载文件的 SHA。

## 时序结果的边界

repair19 / 21 从上表原网出发，使用同一 SS 工艺库、原分析 SDC SHA `404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98`，加有限 scope proposal SHA `45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e`。该 proposal 是 70 个结构明确的 first-D cuts 与 6 个 forwarded output clocks 的实验范围，没有放宽 reset、SRAM、gating、UART；它的适用性仍须审查。

综合只做 `compile -incremental_mapping -only_hold_time`，保护 SRAM 宏及层级边界；DC 以 0.12ns gating hold 作为保守优化目标，最终 PT 回到原 SDC 的 0.1ns，PT Tcl 未另设 gating check。最终分析为 pre-CTS ideal clocks；不是传播时钟或布局后签核。

已测试的 data setup / hold 与门控检查为零违例，并不覆盖未测试检查。两候选均有 5 个 removal 违例：两个 PMU ERST 异步控制和三个 AON reset catch 寄存器。`check-timing.rpt` 各报告 24 个 UART 数据锁存器 E 无 clock、31 个最大延迟 unconstrained endpoints，以及非展开时钟周期告警。不能通过删除这些检查宣布合格。

| untested 原报告 reason | S2d | PE32 |
|---|---:|---:|
| `constant_disabled` | 17,672 | 19,064 |
| `no_clock` | 9,239 | 9,220 |
| `false_paths` | 276 | 276 |
| `no_endpoint_clock` | 48 | 48 |
| `unknown` | 2 | 2 |

这些是原报告分类，不能直接等同于合法豁免。`no_clock` 含 RDN / SDN pulse width 与 24 个 E；`no_endpoint_clock` 为 48 个 D 检查，`unknown` 为两个 SDN recovery 检查。离线 checker 同时逐条核 27,237 / 28,610 个 detail 与汇总，不会把 untested 算作 met。

`dc-setup.rpt`、`qor.rpt` 和 `dc-violations.rpt` 明确保留 `io_pads_gpioA_o_oval[27]` 约 −366ns 的原始 DC HF setup 结果；最终 PT 在 ideal / forwarded-clock 实验范围报告 max 0ns。二者不能合并为“同范围全通过”：当前 forwarded output-clock / DC 处理与电气负载拓扑仍待诊断。`constraints.rpt` 的非空最大 / 最小电容违例同样保留，不因数据时序零违例被忽略。

## 原始字节与离线复核

来源导出 `terminal-results-export-22.tar.xz`：807,588 字节，SHA-256 `a6dd89390d2ba93c10f5d207e3111833d62bbab96772dee9787d6a7987401d7d`。接收时 `prepare_archive.py` 校验全部 142 个 unique regular payload；`source-export-manifest.json` 保留完整原导出清单，SHA `19968bd0ecc5fd25a3e9f2a698040f472bbb9d696bcba624ad4b03abc85d5ba7`。

本目录选取其中 60 个原始 payload，附 9 个先前提交的 context，解压总计 29,509,745 字节。大文件仅作无损 XZ 压缩，`selected-manifest.json` 同时记录原字节数 / SHA 与存储字节数 / SHA；没有修改日志空格、日期或换行。其余 82 个原导出 payload 不在本目录的复核范围内。原网与商业库身份的证据强度见上文。

在完整仓库执行：

```bash
xu_evidence=docs/validation/xu-score-s0-soc-20261102/s2d-pe32-formal-timing-server-20261103
python3 "$xu_evidence/check-evidence.py" > /tmp/xu-fm22-review.json
diff -u "$xu_evidence/evidence-review.json" /tmp/xu-fm22-review.json
python3 "$xu_evidence/test-check-evidence.py" > /tmp/xu-fm22-tests.json
diff -u "$xu_evidence/checker-tests.json" /tmp/xu-fm22-tests.json
```

实际正例与 110 次拒绝检查均已执行。负例覆盖全部 69 个 payload 的存储字节损坏、重复项、路径逃逸、符号链接、未列文件，以及重新签写 receipt 后的假终态、坏退出码、改变 frozen 输入、缺 pass 标记、隐藏 undriven / unread、换 repair 网、错 DB 身份、放宽最终 gating 约束、隐藏 untested / 电气 / DC 负时序等。`evidence-review.json` 是可重算审查输出，`checker-tests.json` 是实际测试输出；`review-receipt.json` 记录这些产物与脚本哈希。

## 同服务器复现 EDA

原输入位于 `/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102`。先核对 receipt 指定的 source、原网、SVF、SDC、scope 和两份商业 DB 的真实字节；不能仅凭本目录记录替代服务器核验。使用原服务器环境的 DC `T-2022.03-SP5-5`、PT `T-2022.03-SP5-1`、FM `R-2020.09-SP5`；完整命令与原绝对输入路径见原 `verify.tcl`、`repair.tcl`、`sta.tcl`。

例如，在新目录复跑，保留已有 campaign：

```bash
xu_base=/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102
xu_repro="$xu_base/xu-repro-fm16-repair19-$(date +%Y%m%d-%H%M%S)"
mkdir "$xu_repro"
mkdir "$xu_repro/fm" "$xu_repro/repair"
cd "$xu_repro/fm"
fm_shell -f "$xu_base/s2d-formality-campaign-20261103-16/s2d/verify.tcl" > fm.log 2>&1
cd "$xu_repro/repair"
dc_shell -f "$xu_base/s2d-hold-gating-repair-20261103-19/repair.tcl" > dc.log 2>&1
pt_shell -f "$xu_base/s2d-hold-gating-repair-20261103-19/sta.tcl" > pt.log 2>&1
```

PE32 使用 `pe32-formality-campaign-20261103-17/pe32/verify.tcl` 与 `pe32-hold-gating-repair-20261103-21/{repair,sta}.tcl`，仍在另一新目录执行。复现会重新综合并产生新 mapped / SVF；原来的网表 SHA 不应当作新运行必然重现的承诺，必须为新输出重新冻结、做修复后等价和完整 STA 复核。
