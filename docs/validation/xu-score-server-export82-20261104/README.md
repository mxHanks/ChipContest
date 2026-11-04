# 实际82：保留reset80未知检查及完整诊断错误

53份原件共12,372,947字节；原始tar.xz为161848字节，SHA256为`636694128def9585a028290434b7081ed3851000209216d36d20ba8fc69eded5`。包内路径、大小、SHA逐项见[original-manifest.json](original-manifest.json)。原始日志、Tcl、TSV及状态保持字节不变。工具手册正文未返回；`installed-doc-identities.json`及执行状态保留其身份。

**实际80仍未取得时序资格。** 它只读链接reset61网表`502a29a0f990d2b1f9394b80da35639cfbb81b9021ad01355f96ab1465dc7597`，采用原SDC、原proposal和两份SS DB。实际61原FAIL状态及SVF身份在本包中再次确认，未改写。reset80终态是`EXECUTED_DIAGNOSTIC_NOT_QUALIFIED`，两条PMU recovery依旧`No constrained paths`、coverage `untested unknown`。不能把缺路径或无负slack记为通过。

|端点|recovery路径数/最差slack ns|removal路径数/最差slack ns|
|---|---:|---:|
|PMU erst_reset_r_reg/SDN|0 / UNKNOWN|1 / 0.132751|
|PMU erst_reset_r_r_reg/SDN|0 / UNKNOWN|1 / 0.136416|
|AON reg_0/q_reg/RDN|1 / 30516.769531|1 / 0.227102|
|AON reg_1/q_reg/RDN|1 / 30516.769531|1 / 0.227102|
|AON reg_2/q_reg/RDN|1 / 30516.769531|1 / 0.227102|

这8条有路径结果均只是诊断数据。原始coverage为17597 recovery中的17595 met、2 untested；removal为17597 met。

**实际80带有两条SEL-005，不能报告成无错。** 第一份`installed-docs.log` return0、唯一marker且`errors=[]`；第二份`diagnosis.log`同样return0及唯一marker，但原始state明确记录两次`Error: Nothing matched for -of_objects collection (SEL-005)`，位置为日志1171、1288行。终态脚本只要求returncode和marker，不以这两条Error判FAIL，因此该终态不等于无错误验收。[check-evidence.py](check-evidence.py)刻意要求两条原始错误仍在。

20个被查询pin的`nets`记录中恰有两条为空：常量0的PMU `erst_reset_r_reg/D`，以及常量1的AON `reg_2/q_reg/D`。**两条错误很可能由这两个无net常量D查询触发，但尚未逐调用证实。** 原脚本没有逐查询日志标签；其Tcl catch也未把空collection记录成`nets_QUERY_ERROR`。这条查询完整性问题与PMU recovery未知必须分别处理。日志还保留PTE-079：部分slack/constrained_launch_clocks属性没有保存，不能将空属性当作已知值。

**现有原件不支持“负recovery被默认禁用”结论。** 实际`printvar`输出为`timing_disable_recovery_removal_checks="false"`。两个CK→SDN recovery弧均未被user、DB或design禁用，条件为`!D`/`ENABLE_NOT_D===1'b1`，数值仍为−0.136499、−0.136345ns；两个SDN已有有限的max-rise arrival 0.892707、0.892943ns，却没有可报告的max约束路径。第一D由网表常量传播得到0，原`report_case_analysis`没有用户case设置。本次没有改任何库、SDC、clock、case或exception。

**下一条可证伪方向是HF→LF的边沿展开。** `diagnosis.log:1155`的PTE-052明确说明：最小周期最多展开1000次、最大周期最多101次；周期跨度过大时没有满足限制的公共基周期，可能使跨钟路径不受约束。紧接着HF被从6.667ns展开至6666.667ns，LF周期则为30517.578125ns。现有两PMU removal报告都从关联HF时钟的外部reset输入到LF捕获。三个AON的recovery报告选出的起点均为LF watchdog寄存器，而AON复位扇入还包含HF外部reset，因此这三条LF路径不能证明HF分量已被检查。该关联是诊断假设，尚非根因结论。

下一次只读probe已准备为[tools/launch_reset_clock_expansion86.py](tools/launch_reset_clock_expansion86.py)，本次82快照时未在服务器执行；后续实际86已另行[归档](../xu-score-server-export91-20261104/README.md)。它在同一冻结网表/库/SDC下，对HF reset→全部5端点各查max/min，以LF watchdog→3个RDN作正对照；给两个常量D和两个SDN的net查询加标签。它读取installed变量名、默认值和相应手册，寻找展开上限的准确设置与语义，**不改变展开上限或任何时序设置**。若后续单独实验需要增加工具分析展开范围，应新建输出、保存原分支，并保持物理时钟与SDC不变后重新验收。

本包还保留实际81模型目录盘点：103个目录、筛选结果为空。这次脚本同时限制文件后缀、大小、深度和路径名含`scc40/std/standard`，故空结果只说明该筛选没有找到模型，不能证明服务器不存在标准单元模型。

离线核验及原样提取（目标目录必须不存在）：

```bash
python3 docs/validation/xu-score-server-export82-20261104/check-evidence.py
python3 docs/validation/xu-score-server-export82-20261104/check-evidence.py \
  --extract /absolute/path/new-actual82-directory
```

实际服务器命令如下，复现时先为脚本更换全新的输出编号，禁止覆盖已有原件：

```bash
python3 "$HOME/Desktop/launch_reset_condition80.py"
python3 "$HOME/Desktop/xu-models81.py"
```

下一项只读probe的历史执行命令（现有86已完成；复现必须改全新输出编号）：

```bash
python3 "$HOME/Desktop/launch_reset_clock_expansion86.py"
```

本提交不修改Chisel、接口RTL或中央实验ledger，亦不把该诊断提升为完整150MHz、功耗或比赛评分资格。
