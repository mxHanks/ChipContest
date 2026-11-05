# xu S2e130：身份修复、Tcl绑定及实际准备中快照

本目录保存独立130功耗工具、43项聚焦host检查及actual131返回的真实进度原件。**131时PID135097仍活着，driver.log仅完成task0、1、2的活动重放；这不是全12重放、PT inventory、完整功耗执行或能量合格终态。** 后续结果需使用新原件归档，不能改写这里的历史快照。

`payload.tar.xz`为24,016字节，SHA `86bd9a31a747d5b77a301816cbda48e695aa7448dd02b515d5ad18124b49ff1b`；14项载荷共156,141字节，逐项身份见`payload-manifest.json`。原131包为305,944字节，SHA `64f1b81c1615bfe0708c902342ebb5551baa5eb67358307c9ebdf4d6816398b3`。本目录只选130的worker副本、launch/log及原manifest/进程快照；不审查131伴随的其他实验。

## 130相对124修复内容

原124实际在首任务报`normalization raw/output identity differs`：task.raw身份省略bytes，normalization.raw身份有bytes，整dict比较误拒合法同文件。原代码和失败均保存在[124归档](../xu-score-s2e-power124-tools-20261105/README.md)，未覆盖。

130要求两种收据的原path、SHA一致，并分别重读正文，核对实际SHA以及任何声明的整数bytes。它接受合法的省略字段，同时拒绝错误大小、SHA、path和bool大小。run还强制原own89 implementation、实际inventory及120窗口/路径一致，再按冻结common为每份任务重新生成Tcl并逐字比较。即使同时更新保存的脚本SHA，换netlist、缩到wrapper或注入零活动仍被拒绝。

driver为49,042字节，SHA `95caa5fab255c5126e5b51f6f0b06c9bf63283f9bbf89dd310202abc87515d46`；launcher SHA `82ed8f7db2bf88643d320ea9016b0435c2c6dc11363825d5a024efb4c2f2a3b2`。服务器冻结worker副本与交付driver逐字相同。`review/124-to-130.diff`保存完整差异；校验器另外比较两份代码的冻结main/child映射上下文、NETLIST、SDC、两库及common资产SHA常量，确认未改这些固定输入。

没有修改Chisel、RTL、MMIO、数值格式、向量、工艺DB、网表或SDC。候选仍是S2e main `5bf123b`、child `a0767db`、自己的mapped SHA `0cfac0b…c09d0`和109原生证明。actual120完整12任务活动的[独立归档](../xu-score-s2e-activity120-server125-20261105/README.md)已保留全部raw/normalized正文和逐层SHA；这里不重复复制465MB展开数据。

## 已验证范围与运行限制

43项host检查原收据/log完整保留并可重跑，其中新增actual120全部12任务raw/normalized收据形状正例；每项都读取真实原始/normalized本地正文核对bytes与SHA。新增负例覆盖错误大小、SHA、path、bool大小及三个协调修改Tcl+stored SHA的情况。其它检查沿用原native PT57的parser、actual120输入pin unknown保持、冻结common报告及语法检查。合成DB/TSV仅用于host生成器/parser测试，没有执行EDA，也未冒充工艺库或实际S2e inventory。

131真实driver.log三行均为868,343 elapsed周期、unknown bit-ticks `26076600970238528`，对应task0、1、2。原进程快照同时保存匹配的完整130命令和`pid_alive_now=true`。launch的`STARTED_NOT_QUALIFIED`只说明启动，不能代替完整执行状态。

准备流程在12任务raw/normalized校验结束后才创建output/preparation-state。此之前必须观察同一PID实际`/proc`及driver.log；输出目录尚不存在不能证明已停止。后续inventory/state、last_prepared_task、execution/current_task_id分别标识不同阶段。不要因观察超时重新启动130。

原计划的PT测量保留full-DUT scope、原始pin/source/coverage/Liberty报告和TX/TZ/TB；原生getter的X概率不等于物理Q已知，file/default/propagated来源与toggle coverage也不能混称。own89完整150MHz、SRAM条件功耗以及正式全SoC任务能量仍未由本快照证明。所有结果保持`NOT_QUALIFIED`，不能计分。

## 复核和复现

```bash
python3 docs/validation/xu-score-s2e-power130-tools-20261105/check-evidence.py
python3 docs/validation/xu-score-s2e-power130-tools-20261105/check-evidence.py \
  --extract /absolute/path/new-xu-power130
```

默认校验全部14项原字节、原handoff、43项host收据/log、source131身份链、匹配PID与三任务准备进度，并重新核对124→130差异和冻结输入常量。它不运行PT，不将RUNNING快照提升为终态。

以下完整归档重跑43项host检查已实际通过；需要同一工作树的actual125正文、actual57报告和clean原109工具checkout：

```bash
python3 docs/validation/xu-score-s2e-power130-tools-20261105/check-evidence.py \
  --rerun-host --workspace-root /home/mxhanks/Projects/ChipContest-xu-score-opt \
  --frozen-tools /home/mxhanks/Projects/ChipContest-xu-score-opt/build/xu-s2e-power124/frozen-tools109
```

原启动命令是`python3 "$HOME/Desktop/launch_s2e_power130.py"`，实际完整参数保存在launch原件。其新输出为`~/Desktop/xu-score-optimization-20261102/s2e-full-soc-power12-20261105-130`，新launch为同父目录`s2e-full-soc-power-launch-20261105-130`；已存在会拒绝覆盖。原130已启动，不应再次执行；新环境复现须保存同SHA输入并使用新的实验编号。
