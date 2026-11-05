# xu：S2e final155 与 S2c own9c16 完整12层原件

两个服务器原件包已取回，安全路径、全部成员集、长度和SHA逐字节核验。原171包412payload/353192073B，原191包392payload/367456367B。
所有大pin报告正文仍保留服务器，本包依据导出snapshot中的bounded stream hash；不称本机重读约40GB原报告。

S2e完整12层原件于17:48:31 CST终态，冻结179独立审计通过AUDITED_FULL12_DIAGNOSTIC_NOT_QUALIFIED。
12层总周期10420116；同155 map3440182e面积0.3003096339mm²；原生四舍五入功耗按各层实际5788953333333fs独立重算，总诊断能量2.3659452273331971mJ。
每层5280Q有未知、4256Q整窗未知，不能用于最终比赛能耗/评分。task0与完整12层单独原生运行、同捕获/目标，成功先验及before/after身份已核。

S2c原190服务器18:55:05 CST完成12层，205独立核验sum energy2.6384471466669330mJ/11887872cycles，task0先验/native336宏22512pin/624与678份服务器输入回执均核对。
新190与166采用同404c7d SDC+45037c forward scope。29c3923独立205已完成，root再次实际重跑四输出逐字节一致；12对Tcl时钟contract均一致、各自own-map面积和原生P×窗口重算完成。
这两图仍有功能、150MHz覆盖和未知活动资格缺口，诊断测量完成不解除资格。

177与186实际诊断失败原件均在191：177 mandatory target-clock-reset.rpt因get_clocks -of_objects非法失败，186在同API原生rc1退出。
另外report_annotated_check两list参数互斥；失败不证明网表不等价，现有coverage缺口仍未解除。原失败报告不改写，后续修复查询使用新namespace。

复现安全验包（替换绝对fresh目录）：

```sh
python3 -B docs/validation/xu-score-two-candidate-final-20261105/check_unpack171.py unpack --archive docs/validation/xu-score-two-candidate-final-20261105/original171.tar.xz --sha256 2f46075e337a21608faf8dc4f4308e90a31c610e6dd5d1dec4a4fb7bb17ae515 --out /absolute/fresh171
python3 -B docs/validation/xu-score-two-candidate-final-20261105/check_unpack171.py unpack --archive docs/validation/xu-score-two-candidate-final-20261105/original191.tar.xz --sha256 44770417f09a4244cbeea5690b4f21923e5d641de365094010ca7eeaf7c998b3 --out /absolute/fresh191
python3 -B build/xu-s2e-result-audit179/audit179.py --evidence-root /absolute/fresh171 --archive docs/validation/xu-score-two-candidate-final-20261105/original171.tar.xz --sha256 2f46075e337a21608faf8dc4f4308e90a31c610e6dd5d1dec4a4fb7bb17ae515 --out /absolute/fresh179
```

本轮无新生产Chisel/RTL改动。S2c既有Chisel是GenerateRTL.scala与linear/LinearAutoGroupCore.scala；S2e paired-HI改动位于接口accel_icb_slave.v与accel.c。
其它候选不追加评测。原153 PID27671单槽继续管理两候选，既定本机01:00关机未改变。


两组当前共同方法的最终诊断对照（逐层见s2c-comparison.csv）：

|指标|S2c own9c16|S2e final155|S2e变化|
|---|---:|---:|---:|
|12层总周期|11887872|10420116|−12.3466673%|
|全SoC任务诊断能量mJ|2.6384471466669330|2.3659452273331971|−10.3281174%|
|加速器面积mm²|0.2948018380|0.3003096339|+1.8683045%|

两组相同任务吞吐的相对增益为14.0857933%；S2e面积占2.25mm²预算13.3471%。这些数字仅支持当前主方案取舍，不计算比赛最终分。
原179中关于旧57/allprop的方法差异警告保持历史原文，新205另外以190共同方法完成join，不改写旧结果。
190完整12每层21报告正文重扫+6服务器hash-only，12份未包SAIF仅校原receipt/连贯性。未知活动和clear phase窗外的边界不因数值对齐而消失。

补充205复现：

```sh
python3 -B build/xu-s2c-result-audit205/audit205.py --evidence-root /absolute/fresh191 --archive docs/validation/xu-score-two-candidate-final-20261105/original191.tar.xz --sha256 44770417f09a4244cbeea5690b4f21923e5d641de365094010ca7eeaf7c998b3 --s2e-audit /absolute/fresh179/audit179.json --s2e-evidence-root /absolute/fresh171 --s2e-archive docs/validation/xu-score-two-candidate-final-20261105/original171.tar.xz --s2e-sha256 2f46075e337a21608faf8dc4f4308e90a31c610e6dd5d1dec4a4fb7bb17ae515 --out /absolute/fresh205
```
