# xu：S2d / PE32 修复网及 PE64 原 PPA 网 Formality 终态

三组真实 `fm_shell` 执行均退出 0，完整日志各有一次实际 `Verification SUCCEEDED` 和 `XU_FULL_SOC_FORMALITY_PASS`。**S2d repair19、PE32 repair21 与 PE64 原 PPA02 网表取得指定条件下的 RTL 等价通过。** 本批补齐此前 S2d / PE32 修复网和 PE64 原网的 FM 终态；不改变任何候选的完整 150MHz、SRAM 内部功能、功耗或比赛资格状态。

| 实际记录 | S2d 双缓冲修复网 | PE32 修复网 | PE64 原 PPA 网 |
| --- | ---: | ---: | ---: |
| FM campaign | `candidate-repaired-formality-20261103-27/s2d` | `candidate-repaired-formality-20261103-27/pe32` | `pe64-formality-campaign-20261103-37/pe64` |
| implementation 来源 | `s2d-hold-gating-repair-20261103-19` | `pe32-hold-gating-repair-20261103-21` | `s3-pe64-ppa-campaign-20261103-02/ppa` |
| passing compare points | 43,440 | 47,758 | 55,537 |
| BBPin / Port / DFF / LAT | 17,136 / 144 / 26,121 / 39 | 17,952 / 144 / 29,623 / 39 | 19,584 / 144 / 35,770 / 39 |
| failing compare points | 0 | 0 | 0 |
| 最终未比较 unread DFF | 511 | 511 | 511 |
| unmatched reference / implementation compare points | 17 / 0 | 33 / 0 | 65 / 0 |
| 匹配阶段 unmatched unread，reference / implementation | 144 / 0 | 144 / 0 | 144 / 0 |
| 原日志 black-box references，reference / implementation | 321 / 336 | 321 / 352 | 321 / 384 |
| 原日志 undriven nets，reference / implementation | 24 / 5,166 | 24 / 5,166 | 24 / 5,166 |
| SVF guidance accepted / rejected / unsupported / unprocessed | 11,772 / 0 / 0 / 0 | 11,042 / 0 / 0 / 0 | 11,431 / 0 / 0 / 0 |
| reference RTL 源文件数 | 155 | 158 | 163 |
| `frozen_before` / `frozen_after` 条目数 | 162 / 162 | 165 / 165 | 169 / 169 |

三份日志的 passing 表中 Loop、BBNet、Cut 均为 0；没有用其余排除项补齐 passing 数。`unmatched.rpt` 逐点保留：16 / 32 / 64 个 W 宏适配器 `valid_read_reg` 加一个固定 PMU `count_reg[15]`，均为 reference DFF。匹配阶段的 144 个 unmatched unread 与最终表中的 511 个 unread DFF 是两个原始统计，不能互相替换。

## 网表与输入绑定

| 配置 | FM 实际 implementation `mapped.v` SHA-256 |
| --- | --- |
| S2d repair19 | `7f1c1efaa27d9eb06a6e8a1979d43df3b7a0eaadb992c1096c4bf36f19477bab` |
| PE32 repair21 | `8aa1d86f72e4752e35a117ffa5359cd4cb76f1fc11130f3f178693ed584b8bbb` |
| PE64 PPA02 | `3e503963574a49d1111facf23b04877ccffed1eb317912871cbd7796593009ce` |

S2d / PE32 按顺序读取各自原 PPA `default.svf` 和 repair19 / repair21 `repair.svf`；PE64 只读取 PPA02 `default.svf`。Tcl、FM 的 `SVF files read` 和完整 before / after 回执交叉相符。三份输出 `formality_svf/svf.txt` 完整保存，没有截断 guidance 内容。`verification.json` 列出每个输入 SVF 的路径、字节数和 SHA。

三组 before / after 字典逐项完全相同，覆盖全部清单 RTL、`rtl.f`、上述实际 mapped、全部输入 SVF 和两份商业 DB。标准单元 DB 为 48,432,887 bytes、SHA `f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723`；SRAM DB 为 52,224 bytes、SHA `c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f`。与旧 FM16 / 17 的收据相比，这批确实包含 DB before / after 记录。

每组 freeze 还保留一份旧 Tcl：S2d 为 FM16 `verify.tcl`，PE32 与 PE64 均为 FM17 `verify.tcl`。它们属于冻结清单中的历史上下文，不是本次执行脚本。本次 Tcl 由 `script` 收据、FM 日志中完整脚本回显及 `fm_shell_command.log` 三者绑定；不把当前 Tcl 说成已包含在 before / after 字典中。

`context/` 仅复用已有归档的 9 份原件：三组 prepared 与 `rtl.f`、两份 repair state、PE64 PPA execution。离线检查逐一对比 155 / 158 / 163 个 RTL SHA 与 prepared 源清单，检查 defines、两份库，以及 actual mapped 与原 repair / PPA 收据。S2d 候选 main / child 为 `3af4db98b893edd2103771fa132d69350b82ba96` / `dd692c190dadafd9baa6dffe8514a3f684e7fbf5`；PE32 为 `94ce6f0f54fffdd590ff9a3ebad0197ec0fd9114` / `fc3977d0a6d5f85fbfd871fd9439c01c9acab5f5`；PE64 为 `3443fad8945577626d226b1cd53eadec89331a20` / `7aae96776e116d5e95d6ebb49d29a5fccce04ab9`。

大网表、输入二进制 SVF、完整 RTL 树与商业 DB 本体没有随本批导出。本机重算的是返回原件与 context 字节的 SHA；上述未返回输入的真实字节 SHA 由服务器 before / after 回执支持，不能称作本机重哈希。

## 等价条件与资格边界

完整原件保留 `synopsys_auto_setup true`、`hdlin_unresolved_modules black_box`；Auto Setup Summary 逐项记录 `hdlin_ignore_parallel_case false`、`hdlin_ignore_full_case false`、`hdlin_error_on_mismatch_message false`、`hdlin_ignore_embedded_configuration true`、`verification_set_undriven_signals synthesis`、`verification_verify_directly_undriven_output false`。日志还明确提示 RTL interpretation 结果可能与 logic simulator 不同。本归档不消除这些假设、警告或未比较点。

SRAM 在两侧均为 black box。`formality.log` 的 FM-158 明细与 `fm.log` 的 FM-182 统计逐条相符：reference 库设计内列出 321 个引用（含共用 `mem_1024x16/macro` 定义），implementation 为展开网中的 336 / 352 / 384 个引用。不能把 reference 的设计定义计数改写成完整 SoC 宏实例数。BBPin 数分别等于 implementation 宏数 × 51，但这些是宏边界比较点，不能证明 SRAM 存储体、读延迟、mask、初始化、PVT 或内部时序。

FM27 不重新执行 STA；它将 repair19 / repair21 网表的条件等价结果与此前时序归档绑定。两网仍有各 5 项 removal 违例、27,237 / 28,610 项 untested 及电容违例；原结论见 [S2d / PE32 formal / timing 归档](../s2d-pe32-formal-timing-server-20261103/README.md)。既有修复方法与 ideal-clock 实验范围另见 [hold / gating 归档](../hold-gating-repair-server-20261103/README.md)。FM37 验证 PE64 原 PPA02 网，不是其他修复网；其原负时序与 31,185 项 untested 仍见 [PE64 PPA 归档](../s3-pe64-ppa-server-20261103/README.md)。这些条件等价终态均不等于完整 150MHz 或比赛资格通过。

## 原件与复核

来源为 `next-results-export-53.tar.xz`，1,128,868 bytes，SHA `13ee20401b85fd3d7d241e77fa8dca908e73b02d08c90687265ec953e6af9f05`。归档时独立复核整包 169 个唯一 regular entry：原 manifest 加其全部 168 个 payload，逐份字节数 / SHA 与解包内容相符。`source-export-manifest.json` 是原 manifest 原文，SHA `dd5f1135a7a593e0027f991bea82ddfbfabfc4e557c0b732543755fa1258c20f`。

本目录完整选择 FM27 的 14 份及 FM37 的 8 份原件，共 12,910,152 展开字节；另附 9 份 context 后共 13,478,228 展开字节。超过 64KiB 的原件仅无损 XZ 压缩。`selected-manifest.json` 记录每份原件的存储 / 展开字节数与 SHA、导出路径或 prior archive 路径。没有加入商业工具手册，也没有改写原始日志的空白、日期或终态。

仓库根目录执行以下有限检查；本机不运行 EDA：

```bash
xu_evidence=docs/validation/xu-score-s0-soc-20261102/candidate-formal-completion-20261104
python3 -B "$xu_evidence/check-evidence.py" > /tmp/xu-formal-completion-review.json
diff -u "$xu_evidence/verification.json" /tmp/xu-formal-completion-review.json
```

若本地仍有原包，追加 `--source-export build/xu-score-resume-20261103/next-results-export-53.tar.xz` 可再次验证全部 168 份 payload；省略时只验证已提交的 22 份 actual raw 与 9 份 context。此参数不改变审查 JSON。

服务器上先复核所有冻结输入及三份实际 Tcl 的真实 SHA，再在新目录重放。先在本机导出 SHA 清单并传回原服务器：

```bash
python3 -B "$xu_evidence/check-evidence.py" --server-sha256 > /tmp/xu-formal-server-inputs.sha256
```

原服务器使用 FM `R-2020.09-SP5`，保留原绝对输入路径和同一库：

```bash
set -e
sha256sum -c /tmp/xu-formal-server-inputs.sha256
xu_base=/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102
xu_repro=$(mktemp -d "$xu_base/xu-fm-repro-20261104.XXXXXX")
mkdir "$xu_repro/s2d" "$xu_repro/pe32" "$xu_repro/pe64"
(cd "$xu_repro/s2d" && fm_shell -f "$xu_base/candidate-repaired-formality-20261103-27/s2d/verify.tcl" > fm.log 2>&1)
(cd "$xu_repro/pe32" && fm_shell -f "$xu_base/candidate-repaired-formality-20261103-27/pe32/verify.tcl" > fm.log 2>&1)
(cd "$xu_repro/pe64" && fm_shell -f "$xu_base/pe64-formality-campaign-20261103-37/pe64/verify.tcl" > fm.log 2>&1)
```

重新执行须另记 before / after、退出码、完整输出与各项假设；新运行的结果独立验收，不覆盖历史 campaign。
