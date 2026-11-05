# xu132：以actual131原件修复126只读采集器

两份上传文件已冻结；这是 `READY_FOR_ONE_INDEPENDENT_SERVER_RUN_NOT_EXECUTED`，
不是原生132或资格通过。保持actual116相同mapped/SVF、两SS DB、SDC/scope及ideal-clock
场景，没有新增clock、case、cut、exception、propagation或horizon。冻结126不修改。

|上传文件|字节|SHA256|
|---|---:|---|
|xu_timing_coverage132.py|39436|d40a163adf3fe13cbce0a9ecee9258929a07eb53068781a7ce9054694c152f91|
|launch_timing_coverage132.py|2339|aa7fae3cf83b0892cf4c542572e87c91bd7c1ea6c51b6438ee4304bdc2eade2d|

根任务负责上传到服务器Desktop并仅启动一次：

```sh
python3 -u "$HOME/Desktop/launch_timing_coverage132.py"
```

输出 `~/Desktop/xu-score-optimization-20261102/full-soc-coverage-rdc-20261105-132`，
launcher回执 `full-soc-coverage-rdc-launch-20261105-132`。任一目录已存在则拒绝重启；
观察超时后查询原PID/state，不删除原输出。tcsh不附加bash重定向。

失败原件来自export131：`coverage131/full-soc-coverage-rdc-20261105-126`。
actual126原state SHA `e6b6bd0e…237fa`为FAILED_NOT_QUALIFIED，before/after全部一致；
文档run rc0/marker1，diagnosis rc1/marker0、2017个SEL-005及1个准确fatal。
实际fatal为第二级PMU `erst_reset_r_r_reg/Q` 缺失；同一116 mapped明确DSNQNV仅QN。
5项输出按原映射为Q、QN、Q、Q、Q，132又要求native输出集合数量1且完整名称相同。

宏实际6个literal mode pin每宏均无net对象，共2016；首级PMU D也是literal，共2017，
与原SEL-005数量一致。原调用点的Tcl主机重放能同时复现错误，132使用已安装属性定义
中的native `pin.net` collection查询，显式保存空集合，命名空集合前先判断数量；
不把无net对象判成不连接，也不把空clocks判成有时钟。集合观察新增完整TSV。
实际arrival/slack缺省不可用保持ABSENT_NATIVE_ATTRIBUTE，不打开保存/传播选项。
行写入立即flush，减少fatal时TSV尾行截断；126原有截断原件保持不动。

另修复实际period-all-status解析：原生MET是数值slack行，没有“met”文字。
131完整原报告10832项=10416 inactive +416 positive numeric MET，0 violated；
336宏均HF clock，80宏另有PLL clock，所以256宏各32项、80宏各33项。
132按完整(pin、clock、condition)验证active与实际CLK.clocks集合并核对native summary。
数值必须有限；正值MET、负值violated；报告舍入0保留UNKNOWN并拒绝晋升。
这仅证明该macro min-period原报告项，不建立reset、全SoC150MHz或评分资格。

`check_local132.py`原13项机制检查通过；`check_regression132.py`新增10项通过，包含
原126实际调用点红→绿、actual131真实模式/416 MET逐clock及missing/zero/negative/
overflow/summary/clock负例。末轮结果在 `/tmp/xu132-regression-03/results.json`。
回归里的reset/display表明确是人工表，不属于服务器采集；无本机EDA执行。

本地复现，输出目录必须不存在：

```sh
python3 /home/mxhanks/Projects/ChipContest-xu-score-opt/build/xu-timing-coverage132/check_regression132.py \
  --out /tmp/xu132-new-regression
```

`diagnosing-bugs`技能用于构造先红后绿的原调用点重放。独立agent已只读复核原macro
计数和5输出集合，以及native pin.net属性类型；仍需一次132实际PT运行决定采集是否完成。
132启动前/结束时重新哈希原116完整输入及原失败126state、producer与36项输出，保留
所有失败回执。完整运行后唯一成功状态仍为
`EXECUTED_SAME116_READ_ONLY_COVERAGE_RDC_NOT_QUALIFIED`。

服务器`private-manuals/`正文不导出；保留installed-options.json字节/哈希、其它所有
Tcl/log/rpt/TSV/state/analysis全文。reset缺路径不改MET、PTE-052不据同现推定单因果。
UART固定RTL、实际异步释放相位、条件脉宽/skew、模拟metastability未获得资格。
该116实验不能替代S2e自己的映射、面积、功耗或能量验证。
