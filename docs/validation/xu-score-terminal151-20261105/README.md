# xu：服务器终态151独立核验（2026-11-05）

151原包完整返回130十二任务功耗终态、134时序流程失败终态、142只读恢复检查展示实验和150总控当时的状态。独立审查直接读取原生报告、日志及原始JSON，不运行EDA、不修改RTL/Chisel，也不解除任何资格门。

原包为`xu-server-control-terminal-20261105-151.tar.xz`，672360B，SHA256：

```
84ad6475f61d14f68f51c52a4f2ecac4ae26aa43fe4c48227e579b435c1235ff
```

安全检查确认191个payload、50892386B；每个成员均为安全相对路径的普通文件，无重复、链接、厂商RTL/Liberty/DB正文或私有manual目录。全部payload长度和SHA与原包内manifest一致。`check-evidence.py`还将107个返回输出原件与服务器执行回执逐项匹配。

## 130：十二层全SoC诊断功耗完成，仍不能用于评分

十二任务均实际PT rc0，逐层唯一完成标记，日志无原生Error/Fatal。原`power.rpt`确为`xu_soc_ppa_top`全SoC Averaged Power，动态与漏电单位均W；版本为T-2022.03-SP5-1。逐层原power报告、PT日志、版本、单位和生成Tcl的长度/SHA均核对。

| 内容 | 独立核对结果 |
|---|---|
| 物理测量窗口 | 每层5788953333333fs（0.005788953333333s） |
| 正式elapsed周期 | 每层868343，十二层10420116 |
| 原inclusive计数 | 每层868344；与elapsed分开保留 |
| 原生报告功耗 | task0、3、10、11为0.0354W，其余0.0353W |
| 十二层算术平均报告功耗 | 约0.0353333333W |
| 报告功耗×物理duration之和 | 0.0024545162133331920J，仅诊断算术 |
| 冻结输入回执 | 554项before/after及prepared输入表完全相同 |
| 映射身份 | S2e own89：`0cfac0b5e99ec05301ec8c0efde38ef2c96790dd1243e84727687b15b25c09d0` |

逐层结果见`s2e-power130-layers.csv`，含原power及PT日志SHA、返回码、完成标记和输入表哈希。每层能量从原生**舍入后的报告值**计算；小数位不代表额外测量精度。

prepared和execution两份回执一致报告每层5376个Q pin中5280个存在TX、4256个整窗TX。这些统计对应原始活动的回执；151未携带原SAIF或24份约20GB native pin报告，不能称为在本地重新读取pin正文后的结论。报告getter的`x_probability=0`不证明物理Q已知。初始化清零阶段在任务SAIF之外，完整150MHz和SRAM模型/轨迹资格仍未补齐。因此0.0024545162133331920J不能作为比赛能耗或评分输入。

## 134：五个原生步骤完成，Python解析失败

原终态为`FAILED_NOT_QUALIFIED`，精确错误为`Error: field larger than field limit (131072)`。traceback显示在`posthold-inventory`之后读取`native-cells.tsv`、生成repair-plan时触发Python CSV字段上限。

独立核对五项原生执行：original inventory DC/PT、hold DC、posthold inventory DC/PT均rc0、各有唯一完成标记且无native error；204项原冻结输入before/after相同。失败发生在repair-plan、final DC/PT及完整FM之前，不能将五项原生成功描述为时序收敛或流程完成。

以下正文因大小未回传；151只保留服务器身份回执，原文件仍在服务器：

| 文件 | 大小B | SHA256 |
|---|---:|---|
| `original-inventory/native-cells.tsv` | 98866265 | `7c7f86330c889c21f9c6229a99067d424e0d9305759ff7ff419eff68ee429a8d` |
| `posthold-inventory/native-cells.tsv` | 99406716 | `2d7e3518ee0db58b25e71f97e2eb6688b410b85328014929561b96dd9e29946c` |

这些哈希保留了原件定位与后续服务器复核入口，不构成本地逐字节验证这两个正文。

## 142：解释了七处展示差异，没有得到恢复时序证明

实际终态为`EXECUTED_SAME116_READ_ONLY_RECOVERY_VISIBILITY_NOT_QUALIFIED`。唯一原生PT进程rc0、有唯一标记且无native error。36项输出原件与回执一致；463项冻结输入before/after相同。目标仍为baseline116映射`16d29dea71ed2668b33c893e1a38be01a6eea02ca190ba8aabcb4658fe610292`，与S2e own89/134分别记录。

直接核对七个源/端点组合的21份报告与执行命令：原filtered及matched filtered均显示`No constrained paths.`；去掉slack阈值的对应unfiltered报告各显示一个`(Path is unconstrained)`，均无有限recovery slack。每份报告的端点、原始观察JSON与分析结果逐一相符。命令记录里的unfiltered查询不显式传`-slack_lesser_than`、`-max_paths`或`-nworst`；报告header出现默认`-max_paths 1`不改变这个命令事实。

独立读取已归档的原116/132报告进行比较：116、132 final、142 initial/final完整27124项untested的**逐pin/完整字段多重集**相同；case、exceptions、clocks去除Date后与132一致。十条真实CK→async arc保持原owner/from/to、两个sense及enabled属性。DISPLAY为false→true→false。七处“能展示路径”仅解释过滤行为，全部仍为`NOT_PROVEN`，完整150MHz资格继续开放。

## 复现

在此工作树运行，无需服务器或EDA工具：

```sh
python3 -B /home/mxhanks/Projects/ChipContest-xu-score-opt/docs/validation/xu-score-terminal151-20261105/check-evidence.py
```

脚本重验本目录input-manifest、151原包及每个payload，并直接从下列两个原归档提取历史证据；不会复用旧工具计算出的结论来替代原报告：

- `docs/validation/xu-score-coverage132-server135-20261105/xu-server-coverage-power-progress-20261105-135.tar.xz`，SHA256 `7972967f569bdc76794e79fe8a112d43fb9ce0bd8d3c85aed8c589f9d5c1c19f`。
- `docs/validation/xu-score-timing116-terminal122-20261105/xu-server-terminal-20261105-122.tar.xz`，SHA256 `654e1c7b3a4d22f41810b0d3a7c1a73de9707f79e879b254e558374cf5dd6c50`。

重新计算的`analysis151.json`及逐层CSV必须与交付字节完全一致。原包中的进程观察只证明151取样当时130/134/142已退出、150 PID159584仍live，不是当前时刻存活证明。所有交付均为`NOT_QUALIFIED`。
