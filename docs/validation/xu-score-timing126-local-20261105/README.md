# xu126：冻结只读采集工具与13项本地主机机制检查

本目录保存服务器126所用worker/launcher的原字节、本地主机checker及最终03原始结果。
这是本地工具交付归档，**不包含服务器126执行或资格结论**，所有结果为 `NOT_QUALIFIED`。
不修改Chisel、RTL、mapped、MMIO ABI、数值格式、向量或时序约束；没有本机EDA执行。

随后根任务已观察到actual126终态 `FAILED_NOT_QUALIFIED`：文档采集rc0/marker1，
diagnosis rc1/marker0；原生错误与pin身份查询仍待131完整导出独立核验。
这里记录该观察来源，尚未纳入服务器原字节，不把本地主机检查通过当作原生执行通过。
冻结126工具不会为覆盖失败而改写；后续修复需新实验编号及原始日志依据。

|冻结工具|字节|SHA256|
|---|---:|---|
|`tools/xu_timing_coverage126.py`|33770|`64de7a24a25e03a6c132f844747fa059618c4a8c85c1b84da95838a7e1c2438a`|
|`tools/launch_timing_coverage126.py`|2339|`8894234de27aeeb486b7e4b446f315d81c8b6d6c36c8f3e5158bde2a0c2eef7a`|
|`tools/check_local126.py`|10268|`8e359ca34c40dd4ff532d5744d1a0fc76480fa32967c1ee66e25e015fc1907c3`|

worker要求actual116的state `7da5adb8…3c84f`、mapped `16d29dea…10292`、自己的SVF
`2574d971…1d90a`和实际sta.tcl `7f344a3c…b2aed3`，重新读取并哈希其274份原输入及
脚本、日志和报告。只在116相同ideal-clock场景收集336宏实际mode/clock/pin/arc、
完整coverage及5个reset端点的条件R/R和首级Q消费者。26次R/R与3条级间D查询保留
缺路径和unknown；all_connected结构遍历不依赖timing-disabled图。

工具先读取服务器已安装文档，再临时切换文档支持的
`timing_report_unconstrained_paths`显示选项，结束时恢复并核对coverage完整字段多重集。
不新建clock、case、cut、exception或propagated-clock。inactive模式常量与active-mode
原生MET分别审查；0个报告路径不当作MET，报告到达时间不当作recovery slack。
宏脉宽、UART、实际异步释放相位/脉宽、跨级skew及模拟metastability资格仍需原生证据。

`local-check-03.tar.xz`原样保存17项最终主机检查载荷，包括生成的Tcl、mock图、明确标成
`ARTIFICIAL_TABLES_NOT_NATIVE`的输入表及正/负例结果；`hostcheck03-members.json`
逐份绑定字节/哈希。`hostcheck03-results.json`为原包同字节副本，SHA256为
`d22c75827cef16c3eb37fa4bb49bf9987645f88fbcab22b0790d6280d84ce17b`。

13项检查实际通过：Python3.6语法、真实116的27,124条untested/10,416条mode标签、
Tcl parser完整性、没有新增约束、TSV转义、结构遍历及unknown拒绝、人工常量表与真实
coverage交叉分析，以及flip/case/missing/duplicate、未恢复显示选项和无主coverage
reason的拒绝。人工表不证明服务器实际常量，语法检查不证明服务器Python3.6运行。
原checker的结构负例复用输出文件，故最终`structural.tsv`为空；正例消费者断言在同一
运行中先执行，原件保持该行为，不能把此mock输出描述为原生reset消费者证据。

`original-delivery/`保留最初README/handoff原字节，其中“未执行”的状态属于当时本地
交付回执。实际126远程运行状态及日志应在独立服务器证据归档核验，不能由这里推断。
`attributes80-fixtures.tar.xz`的4份实际旧属性列表仅供本地生成Tcl，原字节及空格保留，
`attributes80-members.json`逐份绑定哈希；旧导出中port/clock列表
不存在，复现继续按原checker使用空列表，不能冒充126服务器属性发现结果。

只读核验全部本地交付、原03成员和真实116输入来源：

```sh
python3 /home/mxhanks/Projects/ChipContest-xu-score-opt/docs/validation/xu-score-timing126-local-20261105/check-evidence.py
```

从已提交原件独立重跑全部13项检查，输出目录必须不存在：

```sh
python3 /home/mxhanks/Projects/ChipContest-xu-score-opt/docs/validation/xu-score-timing126-local-20261105/run-hostchecks.py \
  --out /tmp/xu126-new-hostchecks
```

本次实际复现已在 `/tmp/xu126-archive-hostchecks-20261105-02` 完成，rc0；最终结果与
原03的 `d22c7582…ce17b` 逐字节一致，见 `reproduction-receipt.json`。

适配器不修改原checker，只将其输入根指向新输出目录中的fixture副本。三份实际116
state/coverage/STA从相邻已提交的
`../xu-score-timing116-terminal122-20261105/xu-server-terminal-20261105-122.tar.xz`
提取，并先核对整个原包SHA `654e1c7b…d6c50`及三份内容哈希；不依赖ignored build。
生成Tcl里的mapped路径仅接受Tcl语法检查，不读取mapped、不运行PT。

历史服务器复现命令（已有输出目录时不得重启）：

```sh
python3 -u "$HOME/Desktop/launch_timing_coverage126.py"
```

两份冻结工具应位于服务器Desktop。输出为
`~/Desktop/xu-score-optimization-20261102/full-soc-coverage-rdc-20261105-126`，launch回执为
`full-soc-coverage-rdc-launch-20261105-126`。观察超时后只读查询原PID/state，不删除目录。
`private-manuals/`正文只留服务器；后续导出保留`installed-options.json`的字节/哈希回执，
导出其它原报告/TSV/Tcl/log/state/analysis全文。本目录不执行此命令。
