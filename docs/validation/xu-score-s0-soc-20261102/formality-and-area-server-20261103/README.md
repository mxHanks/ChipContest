# xu 完整 SoC Formality 与 S1 工艺库面积证据

服务器 RDserver04 使用比赛方服务器工艺库完成实际综合与 Formality。原始日志执行于 2026-11-02，本目录于 2026-11-03 收取归档；保留原文与字节哈希。这是开发结果，完整 SoC 150MHz 时序与全 SoC 单任务能耗尚未合格，不能计算正式评分或据此保留候选。

| 候选 | 加速器面积 mm² | 全 SoC 单元面积 mm² | 2.25 mm² 加速器面积限制 |
| --- | ---: | ---: | --- |
| frozen combined | 0.2857860337 | 3.356776688916 | 满足 |
| S1 H2-only | 0.1785626035 | 3.249519742708 | 满足 |
| S1 SRAM bias | 0.2469499369 | 3.317884732166 | 满足 |

加速器面积取 DC `report_area -hierarchy` 中完整 `u_accel_icb_slave` 子树，包含其内部存储宏；全 SoC 包括 CPU、TCM、512KiB 共享 SRAM 与外设，不能拿全 SoC 面积与加速器面积上限直接比较。标准单元为 SMIC SCC40NLL VHSC40 RVT SS 0.99V/125℃，RAM 为实际 RAMSP1024X16；SRAM bias 候选另外使用 RAMSP128X16。库文件 SHA、Liberty 与 LC 编译记录见 `raw/s1-ppa-campaign-01/libraries.json` 和 `lc.log`。没有布局布线与线网面积。

S1 源码、改动 Chisel 清单、同服务器工具链十二层周期、完整八步 VCS 验收和复现命令见[独立 S1 记录](../../xu-score-s1-server-20261103/README.md)。H2-only 改 `GenerateRTL.scala`、`LinearCachedCore.scala`，移除 elaboration 中的完整 bias cache；SRAM 候选改 `GenerateRTL.scala`，增加 `BiasSramCache.scala`、`LinearSramCachedCore.scala`，以同步读 RAM 和 tile 预取替代寄存器 bias cache。两者均保留 8 PE、数值格式和固定向量。

## 完整 SoC 等价检查的范围

Formality `R-2020.09-SP5` 第二次运行实际返回 `Verification SUCCEEDED`：41,462 个 passing compare points，其中 17,136 个 SRAM 黑盒引脚、144 个端口、24,143 个 DFF、39 个 latch；511 个 unread 点未比较。17 个 unmatched reference 点为 16 个 weight SRAM adapter 的 `valid_read_reg` 和固定平台 PMU `count_reg[15]`。原 `unmatched.rpt` 完整保留。

该检查绑定 frozen child `f49a5fc914971426bd4530db39e270a84b41139f`，是 baseline 完整 SoC RTL→映射网表，不能沿用为 S1 或 S2 等价结果。映射网表 SHA 为 `0f4898ba5ab6571c2125978cdce0a9984a87d4df9901757cb1c00662e4ef3616`；SVF SHA 为 `84e1db4df8586c660e52e15149a624e8fe6c7f4d824ca002a71a1d817c3a1e67`。本地没有重新下载映射网表、SVF 或工艺库，以上身份来自服务器原 state，不声称对缺失字节重新计算哈希。

`set synopsys_auto_setup true` 采用 `verification_set_undriven_signals synthesis` 和 `verification_verify_directly_undriven_output false`，SRAM 内部黑盒未证明；日志还记录 RTL interpretation、undriven 和 black-box 警告。因此本证据是这些明确假设下的比较成功，不能单独替代 SRAM 模型功能测试、全部 unread/unmatched 审查或全 SoC 门级运行。先前第一次运行因 `read_sverilog -vcs` 与独立 `-f` 参数不兼容失败；失败日志及原脚本同样保留，第二次将参数置于 `-vcs` 列表中后成功。

## 时序与功耗边界

两份 S1 原 `execution.json` 都是 `EXECUTED_NOT_QUALIFIED`，并列出各自尚未完成的 mapping proof。它们使用所有时钟传播的未 CTS 网表，H2 的 max/min slack 为 −18.028177/−14.807570ns，SRAM 为 −18.132763/−15.292112ns；不能把这两份报告解释为 150MHz 闭合。`clock-reports/review_status.txt` 保留未覆盖时钟端点及不支持 `report_exceptions -verbose` 的报告失败。RAM 的 CEN/RET1N 等控制引脚在该 clock collector 中也被枚举，故 NO_CLOCK 数字不能直接称为相同数量的真实寄存器时钟缺失；仍须逐项审查。原始约束、STA Tcl、工具单位、QOR、执行状态和报告 SHA 完整保留。

这里没有平均功耗、单任务能量或评分结果；此前 wrapper 功耗不能用于比赛全 SoC 能耗项。正式 REQUEST→最后 Y 响应退休窗口的清空和 SRAM 引脚采集正在独立验证。

## 哈希与复现

原收取包为 54,088 字节，SHA-256 `3ccdf038cbb4ff5172c2d4e622280a7152b9e678e0591d2d35e91c34914f5d70`；其中 37 个 payload 路径全部唯一，逐项大小和 SHA 核对一致。本目录只选取完整 FM 与 S1 PPA 原文，并加入既有 baseline 原面积；所选文件逐字复制，清单为 `raw-manifest.json`。未采用此前有路径冲突的 compact export 中的 area head。

在服务器原目录复现 FM（输出必须放入新目录，所引用网表、SVF、库和源路径保持不变）：

```bash
mkdir "$xu_new_fm_out"
cd "$xu_new_fm_out"
fm_shell -f /storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/full-soc-formality-02/verify.tcl
```

PPA 使用工具主仓 `8dcc84d4430ecf28d619559f5a3243b294e960c3`，从固定候选检出源码：H2 main `23992eb77f2c42eaeefbe7dcbdb682aba1ef2b78` / child `434628c1525931c15dfaf06b5586118eb530ccba`；SRAM main `b6f5075e79eff9c14267e1ef97d90b9f8e82f23a` / child `eee41507965d562066af3335192e3ef93ef36d31`。生成命令如下，库参数分别取原 `libraries.json` 中的 path、sha256（`xu_tool_root` 是上述工具提交的独立检出目录）：

```bash
python3 "$xu_tool_root/tools/ppa/xu_soc_implementation.py" \
  --root "$xu_candidate_root" --profile h2-only --out "$xu_new_impl_out" \
  --standard-cell-db "$xu_standard_db" --standard-cell-sha256 "$xu_standard_sha" \
  --sram-db "$xu_weight_db" --sram-sha256 "$xu_weight_sha"
python3 "$xu_tool_root/tools/scripts/xu_soc_ppa.py" prepare \
  --root "$xu_candidate_root" --implementation "$xu_new_impl_out/implementation.json" \
  --out "$xu_new_ppa_out" --allow-unqualified-mapping
python3 "$xu_tool_root/tools/scripts/xu_soc_ppa.py" run \
  --root "$xu_candidate_root" --out "$xu_new_ppa_out"
```

SRAM 改为 `--profile sram-bias`，并在第一条命令增加 `--bias-sram-db "$xu_bias_db" --bias-sram-sha256 "$xu_bias_sha"`。原分析约束 SHA 为 `404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98`，不得用 DC 写出的 rounded `mapped.sdc` 替代该分析约束身份。`prepared.json` 逐项绑定源、工具、库和生成脚本，原实际 STA/DC Tcl 由该准备流程生成。

本地独立复核：

```bash
python3 docs/validation/xu-score-s0-soc-20261102/formality-and-area-server-20261103/check-evidence.py
```
