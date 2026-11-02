# xu S0 工艺映射 wrapper 验证补充（2026-11-02）

本包保存服务器真实 VCS/DC/PT/Formality 原始证据。**范围为完整 accelerator wrapper/core，尚未获得竞赛资格或完整 SoC 物理签核。** CPU、系统互连和共享系统 RAM 不在本次综合与门级验证范围内。

## 实际结果

| 运行 | 原始证据支持的结论 |
| --- | --- |
| `gate-dc-01` | VCS RTL 与 SMIC40 映射门级各接受、退休 **17,151** 笔事务；各有 **17,149** 条 trace，两个 trace 原始字节完全一致。命令返回码均为 0。 |
| `wrapper-qualification-02/hold-fixed` | DC 真实执行 `set_fix_hold` 与 `compile -incremental_mapping -only_hold_time`；DC/PT 均返回 0。PT 最差 setup **+0.00292103 ns**、hold **+0.06229059 ns**，属性输出分别为 +0.002921 / +0.062291 ns。 |
| 修复后综合面积 | **294,418.797328 µm² = 0.294418797328 mm²**，包含 **16** 个 `RAMSP1024X16` 宏，为综合单元与宏占地总和。低于当前用户指定 2.25 mm² 综合面积上限。 |
| 修复后覆盖 | 53,772 项检查中 51,056 项 met、0 项 violated、**2,716 项 untested**。setup/hold 各有 416 项未测；recovery/removal 等仍未完整覆盖。 |
| `wrapper-qualification-03` | 两次 Formality 干净重跑均 `Verification SUCCEEDED`、13,362 点通过、返回 0，分别绑定修复前后 netlist；修复后 VCS 回放也返回 0，RTL/门级各接受、退休 17,151 笔，结果记录相同 trace SHA。 |
| `wrapper-qualification-02/fm-original` | Formality 显示 `Verification SUCCEEDED`，13,362 个 compare points 全部通过；随后 `report_verification` 不被该版本支持，产生 `CMD-005`，脚本**返回 1**。这是“证明成功、脚本失败”的历史 attempt，不能记为干净 PASS。 |

`gate-dc-01` 验证的是**修复前** netlist `6f90b1ce…`，其旧 hold 属性为 **−0.118136 ns**（原详细报告为 −0.11813561 ns），面积 293,988.515714 µm²。修复后 netlist 为 `75d732b4…`；03 已对修复后 netlist 独立回放通过；不同 netlist 的门级结果不得互相替代。[机器可读结果](result.json)明确区分这些身份。

VCS 回放为零延迟功能验证，无 SDF，命令含 `+nospecify` 和 `+notimingcheck`。Formality 使用 `synopsys_auto_setup`，SRAM 为技术库 black-box 边界；通过点含 816 个 black-box pins。证明以原日志列出的 setup 语义为条件，包括 undriven 信号按 synthesis 处理、直接 undriven 输出不验证；`unmatched.rpt` 保留 16 个 reference `valid_read_reg` DFF 未匹配记录。有限事务回放与该 SRAM 边界均不能证明完整 SoC 或 SRAM 内部行为。

DC/PT 使用相同 SMIC40 RVT SS/0.99 V/125°C 标准单元和 SRAM 库、6.666666667 ns 时钟。未读入提取 RC/SPEF；DC 明示 `No wire load specified`。实验 SRAM adapter 的 EMA/EMAW 与 PVT 资格尚未建立。本包不新增 Chisel 生成、能耗、600 样本准确率、官方分数或竞赛合格结论。

## 不改写历史字节的证据包

- [原始服务器清单](raw/server-qualification-01/manifest.json)：导入归档 SHA256 `1ab627fbf7e7ac442ff5763875d253497bf275bcb258f2359fab17b2e3fe2d26`，125,480 字节；36 份 `included: true` 文件全部按原 SHA/大小核对后复制。日志、报告、Tcl、SDC、命令及结果 JSON、事务 trace 保留原字节，包括历史空白及失败信息。
- [gate 原始结果](raw/server-qualification-01/gate-dc-01/replay/result.json)记录实际 VCS 命令、各步返回码、工具/输入/日志 SHA；[原始 state](raw/server-qualification-01/gate-dc-01/state.json)记录部署提交与厂商模型目录身份。
- [03 原始 state](raw/server-qualification-03/state.json)及两个 clean FM 目录、[修复后 gate 结果](raw/server-qualification-03/gate-fixed/result.json)来自 9,960 字节小归档，SHA256 `639463d4dd2014a568136241d4a6f4d8a437ca34d0e70c2b515a50f7eed863f3`；19 个归档成员全部按原字节核对。03 的两份 trace 未重复下载：原始结果报告的 trace SHA 均与已保存的 01 两份 trace 相同；本包独立核验的是 03 结果/日志与 01 trace 字节，不宣称另行下载比较了 03 trace。
- [02 原始 state](raw/server-qualification-01/wrapper-qualification-02/state.json)、[repair Tcl](raw/server-qualification-01/wrapper-qualification-02/hold-fixed/repair.tcl)、[PT Tcl](raw/server-qualification-01/wrapper-qualification-02/hold-fixed/audit.tcl)、[FM Tcl](raw/server-qualification-01/wrapper-qualification-02/fm-original/verify.tcl)及对应命令日志保持原样。
- `raw/prior-candidate-ss-02/` 保存同一修复前候选的原始 Tcl、约束、adapter、面积/hold 报告与历史清单；旧历史清单的面积单位 caveat 原样保留。
- `raw/prior-area-unit-proof/` 保存随后完成的 LEF 单位证明、独立核验及当前 2.25 mm² 限额记录。四种 mapped 标准单元的 LEF `SIZE` 乘积与库面积一致；SRAM LEF 82.46×110.945 µm 与相同 SHA 的 Liberty 面积一致，因此可按 µm² 换算。原单位证明收据中的历史 2.5 mm² 限额保持原字节，当前判断使用 `area-requirement.json` 的 2.25 mm²。
- [源身份](source-identities.json)记录所有导入来源与 SHA。被冻结硬件源为主仓 `97b35421dfbbfa8f4d495b6927a7c66610ff8206` + E203 `f49a5fc914971426bd4530db39e270a84b41139f`；门级 runner/TB 实际部署主仓为 `bd484edb3a1b21844bef5366091781357fc7d472`。15 份门级源文件均独立核对了精确 Git 对象。

Git 不包含工艺库/厂商模型、mapped Verilog/DDC/SVF 或仿真二进制；原始清单保留其 SHA 和服务器路径。这里的 `mapped.sdc` 为约束文本，并非 netlist。目录中唯一额外 `.sv` 是原实验的自有宏 adapter。

## 严格校验与服务器复现

包根目录执行以下命令。校验器检查文件集合完全相同、每份文件大小/SHA256、原始 included/omitted 清单、实际结果与关键限制；额外、缺失、篡改或符号链接均失败。`--git` 再核验上述 15 份源的精确 Git 对象。该校验仅审计已存在证据，不启动 EDA。[本地核验记录](local-verification.json)保留五种失败反例，以及明确标注为桩输入检查的命令生成/Bash 语法检查；这些不作为新增服务器实跑。

```bash
python3 xu_verify_evidence.py --git
```

[逐文件严格 SHA256 清单](evidence-sha256.json)覆盖包内除清单自身外的全部文件；清单自身由 Git 提交身份绑定。后续证据须作为新的原始运行目录加入，不能覆盖本次历史日志或清单。

在原服务器上保留以下 hash-bound 输入：

```text
/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/
/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/candidate-ss-02/mapped.{v,ddc}
/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/ChipContest/
```

冻结 RTL 的 13 个 SHA、原始 mapped/DDC、两份 DB 与 SRAM Liberty、VCS 工具和模型 SHA 都在 `source-identities.json`。使用相同有许可的 EDA 环境，`dc_shell`/`pt_shell`/`fm_shell` 必须分别为原日志版本 T-2022.03-SP5-5 / T-2022.03-SP5-1 / R-2020.09-SP5；VCS 为 Q-2020.03-SP2-6。需准备同一哈希的工艺库与模型，不能以开发用通用单元库替代。

```bash
xu_report=/绝对路径/docs/validation/xu-score-s0-mapped-20261102
xu_replay=/storage2/2026contest/server4/s4_23usr/Desktop/xu-s0-wrapper-replay-new
python3 "$xu_report/xu_prepare_replay.py" --out "$xu_replay"
bash "$xu_replay/run.sh"
```

准备器先验证上述输入 SHA，要求输出目录不存在；生成新 gate 输出与独立 DC/PT/FM 工作目录。原始 repair Tcl 原样复制，PT Tcl 仅将被分析的修复后 netlist/SDC 路径改向**本次新输出**，原输入与历史输出均不被覆盖。生成的 `commands.json` 和 `run.sh` 可直接审查；准备器本身不运行 EDA。此回放先保留 02 的 FM 脚本返回 1，再执行 03 两份 clean FM Tcl 与修复后 gate 回放；各步保留单独返回码，不将历史失败改成成功。修复后 gate 的输入 SHA 在运行时从本次新 `mapped.v` 计算，并传给 runner；两个 clean FM Tcl 同样仅将修复后读入路径改向本次新输出。准备器仅核输入与生成命令，是否获得原结果仍须检查新工具日志和报告。若冻结目录缺失，可使用前一份 [PPA 源恢复流程](../xu-hw-optimization-20261102/ppa-reproduction.md)从固定 E203 Git 对象和原 adapter 恢复，每份源仍必须匹配清单 SHA。
