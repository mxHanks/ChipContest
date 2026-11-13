# 1064.35 candidate: report data audit

状态：`RAW_LOG_AND_SOURCE_AUDIT_PASS_NOT_QUALIFICATION`。本目录是原候选 `5470c5650f2d11d16e7c52cc96626d21030a3973` 的原始日志复核、图表数据与证据索引，不是综合/时序验收报告。

| 原始日志重算项目 | 504 基线 | 原 1064 候选 |
|---|---:|---:|
| 完整 12 层周期 | 3,568,690 | 1,691,172 |
| 平均 clear | 1,028 | 1,028 |
| 平均源装载 | 126,331.0833 | 42,114 |
| 平均 DMA 取数/计算/Y 响应退休 | 169,964.9167 | 97,729 |
| 平均控制间隙 | 66.8333 | 60 |
| 150 MHz 假定下的 tasks/s | 504.3867638 | 1064.3506397 |
| 精确 Y32 比较数量 | 304,128 | 304,128 |

12 个主任务均为 `140931 = 1028 + 42114 + 97729 + 20 + 40` 拍。计时从实际接受 clear 请求到最后 Y 写响应退休，均含首尾拍；20 拍为 clear 完成与 source 开始之间的间隙，40 拍为最后 source 响应与首 DMA 请求之间的间隙。每层重新装载全部 X/W/bias，warmup 单独完成且排除；poison 和验证读回在窗外，与基线口径一致。

总共减少 1,877,518 拍，其中 source 少 1,010,605 拍，DMA 少 866,831 拍，控制间隙少 82 拍，clear 不变。串行 loader 对照只有 task0，189,061 拍 / 793.3947245 tasks/s；它说明连续装载调度本身有显著收益，不能把完整 2.1102 倍全部归因于 owner FIFO。

该 CPU 测试通过第三路 SystemBus test loader 真实发出源写；GPIO 输入接零。它运行原 CPU 与同一加载固件 image，使用 CPU 行为 RAM、shared256 + internal33 共289个功能 RAMSP 模型。当前 N3 开发 PPA 则保留第三路接口的106个新增顶层位，原生DC实际枚举353宏。它们均不能直接冒充 GPIO→CPU 生产加载边界或同一门级活动。

## 当前候选仍有的寄存器 payload

| 存储 | 实例/声明 | 组织 | payload bits |
|---|---|---|---:|
| 结果 FIFO | `u_xu_matrix_dma/u_core/results_{slot}_{row}_{lane}` | 2×8×8×signed41 | 5,248 |
| engine 结果寄存器 | `u_core/engines_{0..7}/resultReg_{0..7}` | 8×8×signed41 | 2,624 |
| bias 预取槽 | `u_core/bias/slotData_{slot}_{lane}` | 2×8×signed40 | 640 |
| DMA Y 行快照 | `u_xu_matrix_dma/y_payload` | 8×Y32 | 256 |

四类合计8,768个**逻辑声明 payload 位**，不是 mapped flop count；未含 accumulator、tag、valid、epoch、请求 metadata、装配寄存器和其他控制。原始 `.sv` 同时保留不活动的 register-X 分支，本次只数 `XU_MATRIX_DMA_SYSBUS32 + XU_MATRIX_X_SRAM` 实际分支，避免重复计数。源文件 SHA、声明行与计费 scope 见 `storage-inventory.json`；bias `currentHits/fillNeeded` 与 valid/tag/epoch 命中逻辑仍存在。

预计353宏 = CPU64 + shared256 + W16 + bias1 + X16，**没有 result 宏**。结果 FIFO/engine resultReg、bias slots 和 Y 快照仍按寄存器逻辑存在。结果 SRAM 与无缓存 bias 整改来自另一未合入候选；用户选原1064候选并不建立此版存储规则合规结论。

N3 综合的预期计费口径是完整 DMA/core、完整上游 ingress、保守完整 NICE interface scope 和 shared endpoint 标准单元，另计33个内部宏；复用的 CPU/shared 共320宏另列。还提供“全部 full-SoC 标准单元 +33内部宏”的保守上界。原始库面积、官方单位换算和宏定价必须分开；`native-dc-for-report.json`另绑定本轮实际数值面积，仍没有比赛面积 PASS。

## 文件与使用约束

- `audit-summary.json`：schema `s3-ingress-perf-report-data-audit-v1`；阶段、吞吐公式、比较、计时与适用边界。
- `per-layer-cycles.csv`：27行（baseline12 + optimized12 + 三个单任务对照），含每层原始日志行号和窗口时间戳。
- `run-aggregate.csv` / `phase-plot-data.csv`：直接供表格和堆叠图使用的数值；单任务对照不冒充完整12层。
- `source-identity.json`：168文件比对和 CPU 捕获源到冻结 child 的绑定。完整CPU测量时先修改后提交，捕获的`bde23ba + dirty diff`通过逐文件 SHA 对应最终5470，并非另一个候选。
- `ppa-input-identity.json` / `ppa-sealed-input-manifest.json`：`sysbus32-x-sram-353-dev-n3` 新包身份及159个编译源哈希复核；仅输入身份，无DC/PT/FM结论。
- `storage-inventory.*` / `macro-geometry.csv` / `area-expected-accounting.json`：payload、宏几何与预期面积口径。
- `cpu-functional-macro-scopes.csv` / `cpu-functional-model-scope.json`：本地生成模型的289个宏 scope 及来源文件 SHA；不构成门级活动/功耗证据。
- `evidence-index.json` / `SHA256SUMS`：引用旧冻结日志的 SHA 与本目录数据校验。

原始 `baseline/full12` log、result、checker负例和源码清单保持在 `../s3-y32-ingress-perf-20261113/`。重跑命令见 `experiments/s3-y32-ingress-perf/report/README.md`。本目录不引入公开600旧NRMSE、旧353 STA、merged374 PASS 或旧S2 FM结论；本轮同map DC/PT及106位loader路径观察已完成采集并逐原件核验，`native-{dc,pt,io}-for-report.json`绑定这些新证据。PT有467项时序违例、1973项电气违例和29335项未测检查，尚未闭合；GPIO生产资格、同map功能/等价与活动功耗仍缺本候选对应证据。

本轮完整map/DDC/SDC/SVF原始字节均已回传并与DC收据及同map PT核验，固定映射包、成功PT重收与IO原件分别保存在`../s3-y32-ingress-perf-native-20261113/native-map/`、`native-pt/`和`native-io/`。首次PT失败保留，没有以空required-report列表绕门禁；未实施ECO。原始数值和模型差异见主报告第6节。
