# xu实际132：同一116映射的只读coverage、宏模式与reset结构终态

actual132终态为 `EXECUTED_SAME116_READ_ONLY_COVERAGE_RDC_NOT_QUALIFIED`，两次原生PT
均rc0、唯一marker各1、native errors0。135观察到原PID147832已退出。359项服务器
冻结身份before/after相等，无观察错误；83项输出及state共84份132原件完整导出。
**这确认只读采集完成，仍不构成reset、全SoC150MHz或比赛资格通过。**

|项目|实际原件结果|
|---|---|
|同一116 mapped / SVF|SHA `16d29dea…10292` / `2574d971…1d90a`|
|实际132 state|SHA `2f6b6147e384851f194c1f46cb21dfb8c574d1ea3abab136f80d32bd2a21a5b5`|
|实际worker|39436字节，SHA `d40a163a…52f91`|
|宏物理模式|336宏；RET1N=1、EMA=010、EMAW=00，均无新增user case|
|宏min-period|10832项：10416 inactive constant_disabled，416 active MET，0 violated|
|active clock|336个HF项＋80个PLL项；256宏1 clock、80宏2 clocks|
|macro clock arcs|12768项；每宏38项，其中32个mode period arcs有31 disabled、1 enabled|
|完整untested|116原始、132初始及最终27124条完整字段多重集一致|
|report DISPLAY|false→true→false；case/exception报告除Date字段外相同|
|真实首级Q消费者|PMU首级只到第二级D；AON真正首级reg_2只到reg_1 D|
|HF recovery|5项仍NO_PATH_UNKNOWN；开启显示选项后5份报告也仍无constrained path|
|PMU任意来源recovery|2项仍NO_PATH_UNKNOWN；AON任意来源及LF watchdog的recovery有路径|

宏active项原生slack按报告显示为+4.03ns；这是宏min-period的两位小数报告，不能当作
全SoC setup裕量。inactive常量不再依赖推测，原生数值MET按(pin、clock、condition)
与实际CLK.clocks集合核对，并与summary交叉验证。不能将一宏双clock的两项漏算。

5个精确reset输出为Q、QN、Q、Q、Q；第二PMU为DSNQNV，其输出确为QN。
两个真实首级的结构遍历使用all_connected，未因timing-disabled arc截断；原consumer
TSV只有两条，均是预期下一级D。3条正常级间D的完整max/min原报告均MET：

|正常级间路径|setup/max slack(ns)|hold/min slack(ns)|
|---|---:|---:|
|PMU第一级→第二级|30517.19531250|0.13130817|
|AON reg_2→reg_1|30517.18164062|0.13779064|
|AON reg_1→reg_0|30517.18164062|0.13779064|

以上为原LF时序场景结果，不能据此推导任意异步释放相位安全。26次R/R完整查询保留：
HF removal +0.13275149、+0.13641581、+0.22710226×3ns；LF watchdog→AON recovery
+30516.76953125ns、removal +0.56059015ns。5个HF recovery及2个PMU任意来源recovery
仍缺路径，未改成MET。conditional async checks在原design/lib arc、when/sdf_cond和
disable表中保留；PTE-052的同现不能证明缺路径只有一个原因。

132修复了126的SEL-005和错误Q端口查询，但原日志仍有以下限制，未隐藏：

- 10000条ATTR-1：新增集合观察scope对timing_arc调用get_object_name，原生full_name
  不适用。独立arc TSV的owner/index/from/to完整，泛化集合观察的arc scope不能当完整
  身份依据。没有为减少警告改写原日志或冻结工具。
- 68条PTE-079与8条显式ABSENT_NATIVE_ATTRIBUTE；首级D的arrival属性未保存。
  原pin slack中的INFINITY及空值保留，不能解读为有限安全裕量。
- PTE-052、18条PTE-060及原27124 untested保留。条件脉宽、跨级reset skew、异步
  pulse contract、模拟metastability、UART latch clock与完整150MHz资格仍未解决。

原包`xu-server-coverage-power-progress-20261105-135.tar.xz`为2730552字节，SHA256：

```text
7972967f569bdc76794e79fe8a112d43fb9ce0bd8d3c85aed8c589f9d5c1c19f
```

内部manifest165项载荷、181183292字节全部重新哈希。132没有omitted项，licensed
private-manuals正文不在导出中；installed-options保留其字节/哈希。原包还含128/130
伴随观察，本目录仅验证伴随原字节，其功能和功耗语义由各自归档处理。
359份冻结身份相等是服务器原回执；本地包没有全部359份源、历史链和工艺库正文，
checker不声称在本机重新读取所有服务器源/DB。

从任意目录只读独立复核原字节、原生日志/marker、全部报告和上述计数：

```sh
python3 /home/mxhanks/Projects/ChipContest-xu-score-opt/docs/validation/xu-score-coverage132-server135-20261105/check-evidence.py
```

从冻结worker及116原STA前缀重建两份实际132 Tcl，并按服务器原件再生成analysis，
输出目录必须不存在；此命令不运行EDA：

```sh
python3 /home/mxhanks/Projects/ChipContest-xu-score-opt/docs/validation/xu-score-coverage132-server135-20261105/reproduce-analysis.py \
  --out /tmp/xu132-new-analysis-reproduction
```

本次已在`/tmp/xu135-original132-reproduction-01`实际完成，生成的Tcl与analysis均与
服务器原件逐字节相同。analysis SHA
`1ea9ef63484f242adc8960a79797e5066be3648a1206219ca82a5e8f827c8a57`。
独立字段审查结果保存在`analysis132.json`；本地工具、原126失败及13+10红绿反馈见
相邻`../xu-score-timing132-local-20261105`。已有132输出不能重启，历史服务器命令是
`python3 -u "$HOME/Desktop/launch_timing_coverage132.py"`。

本次没有Chisel、RTL、ABI、向量、数值格式、SDC或时序例外改动。保持116原ideal-clock
场景；除临时恢复的report DISPLAY选项外无新clock/case/cut/propagation/horizon。
这是baseline116平台诊断，不能代替S2e自己的时序、面积、功耗、能量或评分资格。
