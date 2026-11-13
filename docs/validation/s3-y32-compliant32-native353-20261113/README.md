# 353 宏版本原生综合／STA 证据（2026-11-13）

**综合和 PrimeTime 报告已实际完成；时序未闭合，也未证明符合 2.25 mm²。** 这是原 353 宏配置的历史测量，不能用于宣称后续 374 宏 storage 候选的面积、频率、功耗或比赛资格。

归档保留全部已回传的原生报告、未改写的 DC/PT receipt、mapped.v/ddc、default.svf、完整 leaf inventory 和本次183个密封输入＋其package清单。没有携带厂商 `.db`／`.lib`、`alib` 派生库缓存、`WORK` 中间文件或凭据。

## 实测结果

| 项目 | 实际数字 | 判定 |
| --- | ---: | --- |
| 全 SoC SRAM 宏 | 353 | CPU64＋共享256＋W16＋bias1＋X16 |
| 最差 setup slack | −5.16538525 ns | 不通过；GFCM 时钟高扇出到 debug 输出 |
| 最差 hold slack | −0.13472039 ns | 不通过；bias SRAM D 短路径 |
| 覆盖报告 violated check | 595 | hold562＋gate hold27＋removal5＋out_setup1 |
| 覆盖报告 untested check | 29,269 | 原因原样保留，仍需独立审查 |
| max capacitance 违规 | 68 | 未修复 |
| min capacitance 违规 | 1,416 | 未修复，部分默认打印精度不足 |
| max transition 违规 | 483 | 未修复 |

`coverage.rpt` 的595条是 clock/check 上下文计数；`all_violators.rpt` 中583条 timing path 是另一种报告行数，不能用后者替代前者。两份原件都在归档内。`violation-catalog.json` 另列所有595条的分类与原报告位置。

面积全部为**原生库面积单位**，没有假定其为 µm²，也没有用旧宏价冒充官方宏价：

| 口径 | 原生库面积单位 |
| --- | ---: |
| 加速器及命名接口范围内的标准单元 | 221,331.045600 |
| 同范围33颗内部 SRAM | 301,901.305662 |
| 上述命名范围合计 | **523,232.351262** |
| 保守独立上界：全 SoC 标准单元＋33颗内部 SRAM | **657,808.986462** |

命名范围合计包含 DMA/core、System Bus 入口、保守计入的整个 NICE 接口和共享 endpoint 逻辑。保守上界另外把 CPU／复用外设的全部标准单元也计入；两者是替代口径，**不能相加**。官方面积单位和 SRAM 计价表仍未核实，因此没有 mm² 数值或“低于2.25”的结论。完整分模块原始数字在归档 `native/candidate/area-components.tsv`，原生面积总表与147,239个标准单元的逐叶清单同时保留。

## 可复查内容与身份

- `native353-evidence.tar.xz`：18,608,488字节，SHA256 `f1caba15dc2e72c754206f842a22e26d47f1c17b0b40f4c2d19cc0ab3010e503`。
- `package-manifest.json`：归档身份和309个 payload 文件的逐项大小／SHA256；解压总量约140MB。
- `summary.json`：从原生文件重新计算的数字；`verification.json`：独立解包后的实际重放收据。
- `negative-replay-checks.json`：四个实际拒绝反例，证明库缓存例外不能掩盖缺少的报告／网表。
- `verify_native353.py`：只用 Python 安全解包并执行归档内只读 reviewer，不访问服务器、EDA 或库。
- `package_native353.py`：交付包生成器；`check_omission_guards.py`：可重跑的反例验证器。
- `SHA256SUMS`：本目录交付文件的 SHA 清单。

对应 mapped.v SHA256 为 `a7ec03579236948ea73fb72351490625e99661a87fe61e8af8aca05922d072dd`；密封输入清单 SHA256 为 `f697416ea83570b25ad9aa9ecfb37c915f7b93547cd8aa6297297e9092313555`。工具和两库的原生身份、原 SDC、各次完成状态都在原 receipt 和纯源码包中。没有修改旧报告或将红项改成通过。

## 安全遗漏策略

原 DC receipt 列有531个 `WORK` 编译中间文件，这些没有作为回传证据发布。另有一份厂商派生缓存 `alib-52/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db.alib`，4,905,088字节，原 SHA256 `43a1bf7b362bc9d33bc56c6c0f35dc074056a19298594cf4add8fc86606b5c81`；本归档明确剔除它。两类原 SHA／大小仍在**未修改的原 DC receipt**，不是把不存在的文件写成已核验。

归档内 reviewer 必须显式带 `--allow-omitted-alib-cache` 才接受上述 DC-only、固定两层 `alib-52/*.db.alib` 遗漏。它不能遗漏 `mapped.v`、`mapped.ddc`、任何原始报告或原生 receipt，也不能以 `alib-52/` 前缀隐藏 `.rpt`。独立重放核验了99个实际原生输出和183个密封输入。全部已回传原生文件中，只有上述一份缓存被排除。

安全解包逐文件检查 SHA／大小、成员全集和禁止文件规则，拒绝绝对路径、`..`、反斜杠、符号／硬链接、设备、重复成员、未登记成员和库／凭据文件。输出目录必须是全新目录，避免覆盖既有证据。

## 本机独立重放

在仓库根目录运行（可将输出位置换成任何新的空路径）：

```sh
python3 -B docs/validation/s3-y32-compliant32-native353-20261113/verify_native353.py \
  --extract-to build/NEW-native353-replay
```

期望终态：`PASS_SAFE_EXTRACTION_AND_NATIVE_REPORT_REPLAY_NOT_QUALIFIED`，`violated_checks=595`，`timing_verdict=NOT_CLOSED`，两个面积数字分别为 `523232.351262` 和 `657808.986462`。这仅表示证据身份和原始数字重放成功，不表示一次新的仿真、综合、STA、功耗或资格验收。

反例验证只对该**可丢弃的独立解包目录**操作，并在 finally 中恢复逐字节原内容：

```sh
python3 -B docs/validation/s3-y32-compliant32-native353-20261113/check_omission_guards.py \
  --extracted build/NEW-native353-replay --out build/NEW-native353-negative-checks.json
```

该交付没有启动任何新 EDA／服务器作业。下一步仍是实际修复违规，并对最终374宏配置重新绑定源码、CPU12、同库面积与完整 STA、映射后一致性和全 SoC 功耗。
