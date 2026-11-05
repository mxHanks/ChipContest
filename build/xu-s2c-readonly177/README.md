# xu：S2c原9c16只读连接及最短路径查询177

177是独立前台worker，仅用于原167未知值定位，不改变设计、约束、模型或TB。
所有状态均为`NOT_QUALIFIED`，不会把原生零路径、clock缺口或optional report缺失解释为通过。

冻结依据是`references177.json`中actual175已验包分析与原S2c57完整功耗输入回执：
same9c16映射、404c7d SDC、f69c08标准单元库、c2cce1 SRAM库、原PT启动程序afdcfa/原版本
T-2022.03-SP5-1。`frozen-ownS2c-power57.tcl`保留原c99c65字节，worker逐字节提取
`XU_CLOCK_MODE=envelope`、`XU_PLL_DIV=0`、原SDC/clock period guards及
`set_propagated_clock [all_clocks]`段，不使用baseline116或S2e155的clock方法。

原生查询枚举唯一DRNQV0_12TR40实例，再以`full_name`精确字符串相等确认。
`dp_gt0.vec_31_dfflr`是字面层级组件，`qout_r_reg[0]`是字面实例名，不转点为斜杠或glob匹配。
保存目标cell/库pin、D/CK/Q/RDN方向、实际net driver/load、CK与reset状态/来源、原native attributes、
最小延迟full_clock_expanded报告、coverage/check_timing及原警告。Q fanout仅至首个state/endpoint，
明确列STOP边界，不跨寄存器编造组合路径或unknown因果。
`units.rpt`与模型原timescale token分别保存两种时基；VCS模型hold与PT静态时序分别解释，
不假设SDF等价或据此证明notifier因果。可选空attribute明确记为ABSENT_OR_EMPTY，不能当物理逻辑值。

标准单元模型只在服务器进程内读取，冻结SHA；输出目标模块/UDP的hash与行号、少量timing check和
pin关系元数据，不输出模型、模块正文或UDP表。该结构摘要不证明notifier造成未知值。

部署runtime列表见`manifest177.json`的`runtime`；manifest本身也须冻结。新目录：

```
~/Desktop/xu-s2c-readonly177/
```

通过现有153总控登记`job177.py`生成的job；默认等待173归档终态及原167诊断成功，`native=true`占用原单槽，
`process_contains`使用唯一output_root。生成器不登记、不启动、无网络访问：

```
python3 -B build/xu-s2c-readonly177/job177.py --out /absolute/new/s2c_readonly177.json
```

实际复现命令（总控负责调用，不在同一输出根重复执行）：

```
python3 -B -u "$HOME/Desktop/xu-s2c-readonly177/readonly177.py" \
  --out "$HOME/Desktop/xu-score-optimization-20261102/s2c-own9c16-readonly-20261105-177"
```

只接受fresh绝对输出根。输出`state.json`、`query.tcl`、`own-clock-method.tcl`、`pt.log`、
`query-status.tsv`、各原生报告、`model-relations.json`及全部输入前后stat/SHA；
`output-manifest177.json`在成功/失败时均列出可取回原件（包括终态state）的逐文件SHA。
同一输入或runtime前后变化、任一必需报告缺失、原生失败/timeout均保留失败终态。
必需报告非空且不得含原生Error；`pt.log`必需或未归属报告的Error也阻断，optional report错误保留其归属。
`query-status.tsv`保留optional native报告不可用情况，`pt.log`保留所有原始警告和错误；不删日志。
成功仅表示只读查询完成：`EXECUTED_OWN_S2C_READONLY177_NOT_QUALIFIED`。
失败：`FAIL_OWN_S2C_READONLY177_NOT_QUALIFIED`。未执行前不声称新EDA结果。

Host检查仅冻结身份、Tcl模板语义、模型摘要边界、fresh-root/原生marker失败守卫及153 job合同：

```
python3 -B build/xu-s2c-readonly177/test177.py
python3 -B build/xu-s2c-readonly177/readonly177.py --describe
```

没有新增生产Chisel/RTL改动。
