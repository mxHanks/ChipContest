# xu：候选失败159及S2e时序155终态独立核验（2026-11-05）

本归档保留真实失败，解释活动采集的共同阻塞，并核对S2e时序接续155完整FM终态。原件不修改，核验不运行EDA、不修runtime、不解除资格门；所有结果仍为`NOT_QUALIFIED`。

原包`xu-server-failed-campaign-20261105-159.tar.xz`：867328B，SHA256：

```
676da6baf9142f6e7f234a0c6e870e9229102dcab73bf083ff3c20316fd128d1
```

安全核验确认232个payload、46315396B，所有成员为普通文件、安全相对路径、无重复或链接；逐成员长度与SHA均等于原manifest。发布注册与157原始快照24项逐字节一致，事件历史保持追加。`analysis159.json`保存独立重算结果、逐层日志SHA及具体未通过门。

## 159取样时队列

| 状态 | 数量与内容 |
|---|---|
| 诊断完成 | 4：130、138、142、155 |
| 失败待审查 | 9：原134、147、156和六个activity候选 |
| 依赖阻断 | 6：对应失败activity的power146 |
| 正在运行 | 1：pe64活动采集 |
| 等待依赖 | 4：compact32/128活动、其功耗、pe64功耗、汇总 |

原`/proc`观察确认取样时controller153 PID228660及pe64 worker PID317009身份与spawn/队列一致，其余被观察原进程均已退出。这只是159的历史取样，不代表当前进程状态，也不影响后续用户排除32/64PE的调度决定。

## 活动采集：固件路径重复后缀，未执行到测量任务

baseline_h1_h2、s1_h2_only、s1_sram_bias、s2b、s2d、pe32均在task00失败，零个完整任务。原日志均显示`+TESTCASE=.../firmware/accel_soc.verilog`，而原TB再拼接`.verilog`，实际尝试打开`accel_soc.verilog.verilog`并报告`Cannot open file`。4,000,000周期超时，`layer=0 writes=0 completed=0`；clear begin/last和source request/accept标记均未出现。这支持固件未正确装载的共同问题，不能将失败解释成候选计算架构不正确，也不能导出周期/能量。

五个非PE候选均有相同原证据；pe32原失败也完整保留。pe64在159快照中尚未终态，但已经报告相同无法打开文件问题，不能提前写成失败完成。32/64PE被用户排除后，其历史实验仍保留，不在本归档修复或重启。

## 155：完整原生FM成功，完整150MHz资格仍未完成

155终态为`EXECUTED_OWN_S2E_SAME_MAPPED_DC_PT_FULL_FM_NOT_QUALIFIED`。八项原生执行回执均rc0、有唯一完成标记、日志无原生Error/Fatal。前五项明确采用134原生原件；final DC、PT、FM是155的新执行。204项冻结输入before/after回执相同、无输入错误，且接续器重核了采用的原件。

原生FM明确`Verification SUCCEEDED`，42338 passing、0 failing；核验器检查同一S2e own89→hold→final三份SVF链和final mapped输入，没有借用baseline图。final FM log SHA256：

```
d88c3a5e3e8842d501efb13d70a1eb33aa9547d35eb1cecca9434dce68a2b0e4
```

final mapped服务器身份回执为14152273B、SHA256 `3440182eca862290a874bedc4eb3f94168681a7028d584d15217a13dbeafa794`。正文未回传，本地不能声称重新读取网表或SVF正文。两份约99MB native-cells表也仅保留服务器原身份回执。

final PT原报告298878项检查中仍有27217项untested，包含2项recovery；仍有31个最大延迟未约束端点，以及3个无负载PLIC输出的min_capacitance门。max/min最差已报告slack为0.000000/0.006015ns，但这些有限路径结果与FM成功都不足以证明完整150MHz时序资格。

## 147和156真实失败

147的VPI build、VCS build、simulation进程返回码均0，但simulation在原生hold时序警告后触发`XU_CANDIDATE_REJECT unknown commit/FIFO ownership state`。强制终态资格标记未到达，driver据此失败。632项输入before/after回执相同、解除门数0。不能以VCS返回0将此记为功能验收通过。simulation log SHA256 `3a231022be64a2a8a2e341f9f1c86023c16bd53d9c029d2c60b5c0b41f86c6b3`。

156在task00/before阶段失败：`ValueError: complete source-report streaming identity differs`，完成任务为空。完整traceback和原state保留。这不是24份报告独立审计完成，也不能提升既有130功耗的资格。

## 复现

在本工作树直接执行，无需EDA或服务器：

```sh
python3 -B /home/mxhanks/Projects/ChipContest-xu-score-opt/docs/validation/xu-score-failed159-20261105/check-evidence.py
python3 -B /home/mxhanks/Projects/ChipContest-xu-score-opt/docs/validation/xu-score-campaign157-20261105/check-evidence.py
```

159核验器直接读取相邻157原包比较不可变注册、采用的134原步骤及历史事件前缀；157核验器另直接读取151原包。保存的分析JSON必须逐字节复现。冻结输入身份来自服务器原回执，未回传的外部库、RTL和大报告正文不冒充本地全文复核。
