# xu142：同一116原生recovery报告展示的最小差分诊断

状态为 `READY_FOR_ONE_INDEPENDENT_SERVER_RUN_NOT_EXECUTED`。本目录只准备工具，
没有运行服务器142，没有恢复资格。actual132已完成两次原生PT（均rc0、marker1、
native errors0），但5个HF recovery及2个PMU任意来源recovery仍为
`NO_PATH_UNKNOWN`；完整27124项untested保持未解决。

本次只读核对了新132归档及其tar原件、progress135实际132、terminal122实际116、coverage131实际126失败收据，
复用了冻结132的116输入守卫与原STA前缀。独立132 checker重哈希tar的165项载荷并通过。
本地检查只核验已导出的原件；服务器上的全部源、DB和private-manuals在本地没有正文，
只有未来worker会在服务器按原收据逐文件重新哈希。未修改任何历史工具或证据。

待检验的候选按顺序为：

1. slack过滤隐藏unconstrained路径。预测：相同DISPLAY=true的matched filtered报告为空，
   而只去slack阈值的unfiltered报告出现`(Path is unconstrained)`。这仅说明展示缺口，
   不能证明recovery MET、任意异步释放安全或150MHz资格。
2. 原查询的其它展示参数影响输出。预测：原132命令与matched filtered输出发生差异，
   而matched/unfiltered差分不支持slack单因果。三联对照保留这种情况，不强推第一候选。
3. 当前native上下文即使没有展示阈值也不给出这7个路径。预测：三份报告均为空；
   这会证伪“仅去阈值即可看到路径”，但不能区分条件敏化、边沿关系或PTE-052等剩余原因。
   不为检验此项改clock、case、cut、exception、propagation、edge/horizon或scope。

每个未知端点有3份report_timing，总计21份：

|变体|命令差异|用途|
|---|---|---|
|original132_filtered|原132命令，含slack阈值、max_paths10、significant_digits8、full_clock_expanded|保存历史命令对照|
|matched_filtered|`-delay_type max -exceptions all -slack_lesser_than 1000000`|仅用于与下一行做单变量差分|
|unfiltered|`-delay_type max -exceptions all`|没有slack/nworst/max_paths显式过滤|

5项HF都保留`-from`精确HF reset port、`-to`精确SDN/RDN；另2项为PMU任意来源，
保留原查询无`-from`。三联都在DISPLAY=true期间运行并恢复原值。PMU原132任意来源
查询在DISPLAY=false；这里“original132”指命令选项一致，实际132原报告仍作为独立
冻结历史对照。仅matched filtered与unfiltered之间是单变量差分。

116图约束保持完整，冻结身份包括：

|输入|SHA256|
|---|---|
|mapped.v|`16d29dea71ed2668b33c893e1a38be01a6eea02ca190ba8aabcb4658fe610292`|
|repair.svf|`2574d971c759fc2650ed660b52b6219928c54117be156cdf616ccbea10f1d90a`|
|原sta.tcl|`7f344a3c017b6de915b522aef798be5fcae06119592391008f16e75841b2aed3`|
|原SDC|`404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98`|
|原scope|`45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e`|
|actual116 state|`7da5adb892fcaa33b5876e4f8dcbd9467a09dd8b40687476de529d1f7bf3c84f`|
|actual132 state|`2f6b6147e384851f194c1f46cb21dfb8c574d1ea3abab136f80d32bd2a21a5b5`|

worker首先验证116的274份原冻结输入、自己DC/PT/FM原收据、两个精确SS DB及原SDC/scope，
随后验证132的359份before/after收据、83份输出、producer、两次PT原收据和已安装文档
哈希。所有引用及worker/PT身份加入142的before/after清单。licensed手册仅在原132
private-manuals中读取，142不复制或导出其正文；不借用旧94的不同61网结论。

额外仅采5个精确CK→async的10条setup_rise/hold_rise arc，并与实际132逐字段对照。
它们实际均`is_disabled=false`，不能用CK→D常量disabled解释async缺口。新scope由
owner/index/from/to组成，不对timing_arc调用get_object_name或读取full_name。
5个单元的ref与唯一输出Q、QN、Q、Q、Q继续校验。run后完整27124字段多重集必须与
116及142前后一致；case、exception和clock报告除Date外必须与132及142前后一致。

本地可从任意目录复核，输出目录必须不存在：

```sh
python3 /home/mxhanks/Projects/ChipContest-xu-score-opt/build/xu-rdc-next142/check_local142.py \
  --out /tmp/xu142-new-local-check
```

`local-check142.json`记录13项通过；`diagnosis-preview142.tcl`由实际116原前缀生成。
检查覆盖132真实调用点红→绿、原tar/导出字节、完整coverage多重集、Tcl语法、真实10条
async arc、opaque collection日志、DISPLAY成功/异常恢复、full_name负例、人工报告分析
及launcher既有目录拒绝、preflight失败不误记空freeze已验证。审查修复了重复生成native collection handle造成日志与执行句柄不一致，以及preflight失败时空freeze误记true；递增句柄与失败注入检查均通过。所有MOCK/ARTIFICIAL表只存在本地检查输出，不是native142证据。
`diagnosing-bugs`技能用于构建这些原调用点差分及红绿反馈。

交接时只上传下列两个文件到服务器Desktop，不覆盖132文件：

- `xu_rdc_next142.py`
- `launch_rdc_next142.py`

启动命令只提供给后续获准的独立运行；本次没有执行：

```sh
python3 -u "$HOME/Desktop/launch_rdc_next142.py"
```

输出为`~/Desktop/xu-score-optimization-20261102/full-soc-rdc-next-20261105-142`，
launcher回执为`full-soc-rdc-next-launch-20261105-142`。任一目录存在即拒绝重启，
不要删除后再跑。超时只观察原PID/state。worker和launcher精确SHA见`handoff142.json`。
最终成功状态也仅能是`EXECUTED_SAME116_READ_ONLY_RECOVERY_VISIBILITY_NOT_QUALIFIED`。

macro的416 active min-period MET、10416 constant-disabled属于actual132原证据，
142不重复采集或扩展其含义。条件reset脉宽/skew、任意释放相位、模拟metastability、
UART latch clock和全SoC150MHz/比赛资格仍开放；baseline116也不能替代S2e自身资格。
