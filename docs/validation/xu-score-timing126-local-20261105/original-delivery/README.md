# 126：同一actual116映射的只读宏模式、coverage与reset/RDC采集

交付状态为 `READY_FOR_ONE_INDEPENDENT_SERVER_RUN_NOT_EXECUTED`；本目录没有服务器126结果。
116已经独立归档于 `docs/validation/xu-score-timing116-terminal122-20261105`，提交a1c2c06。

冻结上传到服务器Desktop的两份文件：

|文件|字节|SHA256|
|---|---:|---|
|xu_timing_coverage126.py|33770|64de7a24a25e03a6c132f844747fa059618c4a8c85c1b84da95838a7e1c2438a|
|launch_timing_coverage126.py|2339|8894234de27aeeb486b7e4b446f315d81c8b6d6c36c8f3e5158bde2a0c2eef7a|

服务器tcsh终端直接执行，不附加bash重定向：

```sh
python3 -u "$HOME/Desktop/launch_timing_coverage126.py"
```

输出在 `~/Desktop/xu-score-optimization-20261102/full-soc-coverage-rdc-20261105-126`，
启动回执在 `full-soc-coverage-rdc-launch-20261105-126`。任一目录已存在即拒绝重启；
网络或观察超时后查原state及PID，不删除目录规避。

输入guard固定116原终态SHA `7da5adb8…3c84f`、mapped `16d29dea…10292`、自己的SVF
`2574d971…1d90a`及实际执行sta.tcl `7f344a3c…b2aed3`。逐份重哈希274份原输入、
全部116报告/TSV/实际DC/PT/FM脚本和日志，并在结束/失败时保留自身before/after。
不是仅比较两份历史回执相等。仍要求原两SS DB、原SDC、原70 first-D/forwarded-clock
scope和116完整FM41,462点成功，不接受其它映射借用。

实际PT先读已安装文档及属性定义，再在116原STA preamble上采集。只把
`read_verilog mapped.v`的相对文件参数改为同一116 mapped绝对路径，保持原ideal-clock
分析场景；不新设propagated clock，不加clock、case、cut、exception、load或horizon。
原生文档支持后，临时开启 `timing_report_unconstrained_paths` **显示选项**来展示
5条HF recovery数据路径，随后恢复原值并再次收集coverage/exception/case。
这是report-only切换，不能把展示出来的到达时间当recovery slack。

采集范围：

- 336宏逐个读取6个实际RET1N/EMA/EMAW常量bit及CEN/CLK，保存原user_case_value、
  clocks与连接net；对照原完整coverage每宏31种inactive条件。读取CLK自检查全部
  design arcs和实际库自检查arc。若已安装命令支持，另报min-period全部met/violated/
  untested明细，单独检查唯一物理模式是否有native MET记录。
- 5个原精确reset端点的D/CK/Q/SDN或RDN属性、叶级连接、design/lib条件arc、disabled
  报告；5×HF、5×任意endpoint-source、3×LF watchdog的recovery/removal共26查询。
- PMU首级及AON真实首级reg_2的Q消费者，用all_connected结构遍历组合逻辑、直到
  sequential或输出port，绕过timing-disabled图的截断；异常分类和超4096输出拒绝。
  保存3条普通级间D的完整max/min报告，保留原条件与时序。
- 原始/初始/最终27,124条untested明细按完整字段及重复计数比较，不依赖未规定的
  相同slack排序顺序。原PTE-052、缺路径和不支持查询都保留。

所有状态保持NOT_QUALIFIED。inactive模式常量证明不等于active mode MET；缺失
GET属性或报告不能补0。两个PMU recovery、5个HF no-path的原因需结合原始新证据
审查，不把PTE-052同现升级为单一因果证明。这里没有实际reset脉宽/跨级skew/
模拟metastability资格；不修改固定UART。此baseline116不能代替S2e自己的资格或能量。

`private-manuals/`正文只留在服务器，后续导出须排除；`installed-options.json`保存
其字节/哈希。其它TSV、原报告、执行脚本/log、analysis和state应原样导出，不截断。

本地13项机制检查已在 `local-check-03/results.json` 实际通过，覆盖真实116的27,124
行/10,416标签、Tcl完整性、转义、绕过disabled图的结构遍历、unknown拒绝和模式/显示
恢复负例；输入pin表明确为 `ARTIFICIAL_TABLES_NOT_NATIVE`，不冒称原生PT常量证据。
没有调用PT/DC/FM。本机只验证Python3.6语法，不声称运行过服务器Python3.6。
01保存checker相对输出目录错误；02是修正后的前一版结果；最终交付绑定03。

本地复现须使用新目录：

```sh
python3 /home/mxhanks/Projects/ChipContest-xu-score-opt/build/xu-timing-coverage126/check_local126.py \
  --out /absolute/path/new-local126-check
```
