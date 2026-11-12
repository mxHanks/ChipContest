# xu B41 收尾材料

三份固件为 `tight-O2`、`phased_64_fast4-O2` 和 `backoff_8_256_fast4-O2`。本目录提供它们在 64 PE、41 位 B 版上的冻结输入、已取回的验证原件、复算入口和后续物理验收材料。接续任务见 [队友交接说明](../../xu-b41-handoff-20261112.md)。

## 材料入口

| 内容 | 仓库内位置 |
|---|---|
| 三固件 ELF／映像、RTL、12 层向量与 SHA | [b41-strict-input-r1](reports/s3-y32-portable-software-design-20261110/hardware64-r1/b41-strict-input-r1/) |
| 背压与故障补测脚本、测试台与 SHA | [b41-followup-input-r1](reports/s3-y32-portable-software-design-20261110/hardware64-r1/b41-followup-input-r1/) |
| full12 原件 14 件 | [b41-full12-evidence-r1](reports/s3-y32-portable-software-design-20261110/hardware64-r1/b41-full12-evidence-r1/) |
| 背压／故障原件 21 件 | [b41-followup-evidence-r1](reports/s3-y32-portable-software-design-20261110/hardware64-r1/b41-followup-evidence-r1/) |
| 离线复算工具 | [tools](reports/s3-y32-portable-software-design-20261110/tools/) |
| 三固件的构建来源、驱动、配置及反汇编 | [candidates-r3](reports/s3-y32-portable-software-design-20261110/hardware64-r1/candidates-r3/) |
| 门级接入与宏位序 | [GATE-PREFLIGHT.md](reports/s3-y32-area-opt-synthesis-20261111/GATE-PREFLIGHT.md) |
| 门级核对所引用的 PPA 源码及 SRAM 检查台 | [gate-source](gate-source/) |
| 官方收尾脚本、固定哈希和现场观察 | [收尾目录](reports/s3-y32-area-opt-synthesis-20261111/) |
| 数值模型、参数转换与初赛材料 | [PRELIM-DELIVERY.md](reports/s3-y32-area-opt-synthesis-20261111/PRELIM-DELIVERY.md) |
| 赛题与已整理公式 | [reference](reference/) |

`b41-followup-input-r1` 复用 strict 目录的源码、三固件及完整回归结果。目录中的原生运行脚本绑定既有 t7920 宿主、资源守卫和原工作路径。下列离线复算直接在检出目录运行。

## 校验与离线复算

从仓库根目录执行以下命令。Python 3 标准库即可完成两项复算，Linux 可用 `sha256sum` 校验文件。

```sh
cd docs/validation/xu-b41-handoff-20261112
sha256sum -c SHA256SUMS
xu_review_root=$(mktemp -d "${TMPDIR:-/tmp}/xu-b41-review.XXXXXX")
python3 -B reports/s3-y32-portable-software-design-20261110/tools/compare_cpu64_runs.py \
  --b41 \
  --evidence reports/s3-y32-portable-software-design-20261110/hardware64-r1/b41-full12-evidence-r1 \
  --out "$xu_review_root/full12"
python3 -B reports/s3-y32-portable-software-design-20261110/tools/review_cpu64_b41_followup.py \
  --evidence reports/s3-y32-portable-software-design-20261110/hardware64-r1/b41-followup-evidence-r1 \
  --full12-review "$xu_review_root/full12/result.json" \
  --out "$xu_review_root/followup"
```

预期结果分别为 `PASS_RAW_CPU64_COMPARISON` 和 `PASS_RAW_B41_FOLLOWUP`。两个冻结输入清单的 SHA256 分别为 `1d8cd861b75c377ecd7282edd1fa1bdb7dae7a166078d43d6308e3010335a6c6`、`4ac437cd4ff2e480a4f33ae7c8c3b969949ebe151d195aa36b993ca9b47b5db4`。

每份完整回归覆盖 304,128 个正式输出、25,344 个 warmup 输出和 13 次物理清零。补测覆盖三份 31 拍背压与六项读写故障。原始展开包含六处 CPU SVA，冻结主测试台保留 52 条 fatal。逐项产物清单在两个 evidence 目录的 `artifact-manifest.json`。

## 版本与接手边界

实际父源码为 `96fffcb2a4b2492fd2cfdecb88e164d2c67881ae`，E203 为 `ccdac30d92ecf40f14d0b78879b8711fb0b1cdd1`。本次交接分支基于文档发布提交 `dafd56613e6cf084e3aa64d90e948008216da524`。完整 PPA 输入已在仓库的 [基线归档](../s3-y32-area-opt-20261111/candidate-b-ppa-inputs-r3.tar.xz) 中。本目录 `gate-source` 提供门级接入核对直接引用的文件。

`gate-preflight-r1.json` 的本地文件路径已改为相对本目录，文件 SHA 保留。原始运行回执与冻结输入中的路径保持原样，便于核对执行来源。发布范围和逐文件校验值见 `PUBLICATION-FILES.json` 与 `SHA256SUMS`。

官方工作区为 RDserver04 工作区 3，目录 `/tmp/xu-b41-close-20261111-r1`。RTL 等价 r2 和连接诊断的终态仍待队友现场读取。当前电气候选 `f73b4518…` 已有四工况采集，SS DRC 为 8/1449/0，FF 为 0/1449/1774。最终网表、DDC、SVF、SDC 和相应 PrimeTime／Formality 原件由队友在官方工作目录接续。厂商模型路径和已观察 SHA 位于门级接入记录中，使用官方已安装模型。

门级适配、同版本门级回归和三固件全 SoC 功耗测量仍待完成。原件与复算结果中的 `physical_energy`、`official_score` 均保持 `null`。后续按实际最终网表更新物理回执、逐窗能耗和初赛包。
