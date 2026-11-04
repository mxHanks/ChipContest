# S2c 全SoC 12任务实际PT审查

实际服务器目录为 `~/Desktop/xu-score-optimization-20261102/s2c-full-soc-power12-20261104-57`。12次独立 PrimeTime `T-2022.03-SP5-1` 均返回0，每份原始日志有且只有一行独立完成标记，无原生 error/fatal；367项冻结输入的服务器 before/after SHA一致。这里的PASS只表示原件、配置和报告算术一致；**能量状态仍是 `NOT_QUALIFIED`，不能代入比赛评分**。

同一S2c源主提交 `d276b55ffecbe8d620f9a361bf5d0859299ba7b5`、E203子提交 `49a9436e01ea8ceeead94242e4a99c16e31a0865`，原始采集工具 `5e75581319f926642ee7dc214ad825f3564a8e39`，本次独立功耗工具 `ad866b9185b0ee505e720cad51effa5853191a50`。真实原始完整SoC网表SHA为 `9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892`，配置SHA为 `5b5cf619e8b0e5c2fc050abe8b589d5f7544a98eed174f4fc979bffe60fa6018`。STD/RAM两库和SDC逐项绑定在原始prepared/execution中；未混入基线网表或时序修复网表。

正式窗口为首次输入/参数源读请求至最后Y响应退休，时间区间 `[begin,end)`；33,697次任务前清零写在窗口外。每任务990,656个elapsed周期、990,657个inclusive周期、6,604,373,333,334fs，即0.006604373333334s。12任务elapsed合计11,887,872。此前开发验收的986,850周期/层、11,842,200周期/12层不是此正式窗口，不能混合作为同一配置的能量比较。

原始 `report_power` 明确采用W：8份总功耗报告为0.0348W，task01/04/07/08为0.0347W；报告均值0.03476666666666666666666666667W。以报告舍入数值乘实际窗口的**诊断**能量合计0.0027553445546669448J。长小数是Decimal算术重现，不表示工具功耗具有这些有效位数。逐层周期、功耗分项、诊断能量、覆盖及原始日志/功耗报告SHA见 [per-task-diagnostic.csv](per-task-diagnostic.csv)。

所有任务的活动来源统计相同：145,347个net中file为49,763（34.24%）、default为1,132（0.78%）、implied为8,435（5.80%）。`update_power`前86,017未注释，之后86,017被propagated（59.18%），未注释变0。这不等于全部来自真实轨迹。Sequential输出file为22,578/25,569（88.30%）；memory输出file为5,376/5,376，但file来源不保证状态已知。`coverage-*.rpt`定义为“至少出现一次toggle的net比例”，逐任务32.67%等数值不能称为注释率。

每任务保留336宏、22,512个映射SAIF测得输入pin记录，完整67-pin双射与整数dwell守恒通过；其中5,280个Q有TX、4,256个Q全窗TX，未知总dwell为29,636,086,623,576,352 bit·fs。`measured-sram-pins.json`是prepare保留的映射SAIF输入统计，**不是PT引擎原生pin属性报告的本地重放**。未知绝对Q、条件edge/internal_power/when语义、活动转换、file/default/propagated覆盖及同网表完整时序/电气资格尚需闭合；此次 `check_timing`仍明确有28个最大延迟未约束端点。此实验的PT使用propagated pre-CTS时钟及envelope分频场景，不能据此称完整150MHz通过。

本次不更改Chisel或RTL，只归档服务器实际证据及独立审查程序。生产S2c Chisel改动仍是 `GenerateRTL.scala` 与 `LinearAutoGroupCore.scala`（自动分组和两槽结果FIFO），见候选代码提交及中央实验账本。

原始数据在共享不可变包 [payload.tar.xz](../xu-score-server-export69-20261104/payload.tar.xz) 中保留，包SHA `a02b3c1e156c90e03dec98d07c855a479f7da34d383e5f57106dd43267cb0f47`，没有再次复制1.35GB展开正文。本实验362份返回原件/1,350,032,481B的路径、大小、SHA见 [selected-native-index.json](selected-native-index.json)。原始execution共记录397个artifact，其中36个未导出，详见 [unreturned-server-artifacts.json](unreturned-server-artifacts.json)：24份约805MB的 `sram-pins-before/after.rpt` 被64MB导出阈值排除，12份mapped SAIF正文未导出。它们的服务器SHA回执不能冒充本地重新读取其正文；本审查也不声称重放了这些缺失正文、全部冻结输入正文或工艺DB正文。

在仓库根运行以下命令会流式重核共享包全部435原件的字节/SHA，再审查本实验并核对CSV/索引/复核结果。9个有意义的篡改负例覆盖W→mW、冻结输入删除、只有Tcl回显的假完成、返回0但有原生错误、非0返回、1fs窗口改变、pin dwell不守恒、未知dwell改写和报告功耗改写。

```bash
python3 docs/validation/xu-score-s2c-full-soc-power-server-20261104/check-evidence.py
```

服务器复现必须使用新的输出目录，并保持两库、原网表、原始12任务活动及inventory不变：

```bash
B="$HOME/Desktop/xu-score-optimization-20261102"
R="$B/ChipContest-s2c-power-tools-20261104-60"
O="$B/s2c-full-soc-power12-replay-new"
python3 "$R/tools/ppa/xu_s2c_full_soc_power.py" prepare \
  --activity "$B/s2c-formal-activity12-20261103-23/result.json" \
  --source-root "$B/ChipContest-s2c-02" \
  --mapped-sram-inventory "$B/s2c-pt-macro-pin-inventory-20261103-20/inventory.json" \
  --out "$O"
python3 "$R/tools/ppa/xu_s2c_full_soc_power.py" run \
  --out "$O" --pt /eda/synopsys/prime/prime_2022.03-SP5-1/bin/pt_shell \
  --lc-root /eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5 --timeout 21600
```

须先核对工具checkout确为上述ad866b9、候选源码确为上述d276b55/49a9436；prepare/run执行真实依赖校验，拒绝已存在输出，12个PT进程的命令也逐项在execution中保存。归档校验结果见 [review.json](review.json) 和 [replay.log](replay.log)。
