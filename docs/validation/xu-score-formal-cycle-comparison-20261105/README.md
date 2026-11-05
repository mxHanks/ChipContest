# xu 正式任务窗口：S2c与S2e逐层比较

12个实际任务的elapsed总周期为 **11,887,872→10,420,116，减少12.3466673%**。同一150MHz名义时钟下，原RTL任务窗口算术吞吐为151.415→172.743任务/秒，增加14.0857933%。这仍是RTL测量：两个候选完整150MHz时序及正式能量资格未闭合，不能代入最终比赛得分。

本比较重新读取actual23与actual120的24份原生日志、24份输入身份收据及两份完整活动结果。逐层原始X/W/bias/Y身份相同，HF150MHz/LF32768Hz、1fs精度、signed16/40/48、33697次任务前清零及首个source REQUEST至最终Y RETIRE的`[begin,end)`政策相同。两份SDC路径不同但原SHA相同。两个候选的RTL、固件和网表不同；这里不是同一新RTL下仅切换固件的正式窗口实验。

| 每层实际计数 | S2c | S2e | 节省周期 |
|---|---:|---:|---:|
| elapsed总周期 | 990656 | 868343 | 122313 |
| W装载 | 183502 | 183502 | 0 |
| X装载 | 71133 | 71280 | -147 |
| bias装载 | 7775 | 7775 | 0 |
| 计算等待 | 48114 | 44946 | 3168 |
| 结果写回 | 666813 | 547766 | 119047 |
| 其它 | 13320 | 13075 | 245 |

各层上述计数相同，但每层日志、四tensor身份及对应原始层映射独立核对，没有把模拟进程内部`layer=0`当作复用了第0层向量。六阶段是原PERF_TASK inclusive诊断计数，各自合计为elapsed+1；两候选差值精确合计122313。节省主要来自结果写回。输入读取等待的相位变化仍计入，没有将增加的X装载周期隐藏。

[per-layer.csv](per-layer.csv)保存12对窗口、各阶段以及24份日志的完整SHA；[comparison.json](comparison.json)保存精确总数、算术和范围限制。此前开发窗口11,842,200→10,420,140（同新RTL旧/新固件对照减少12.0084106%）在[原S2e验收](../xu-score-s2e-server-20261104/README.md)保留，边界不同，不混入此表。

`payload.tar.xz`为44988B，SHA `e39310a9b4d66d1fc8d0af2cfac8488802142c642557f6dbb3d141317a826c9d`；53项2,884,729B全部是逐字选取的原结果、原日志、输入identity收据和来源manifest。上游完整53/125原包身份保存在`source-receipts.json`。这份小比较包没有tensor、SAIF、ELF或工艺库正文；checker核对的是已返回原件及其原始身份链，不声称本地重读未包含的正文。S2e全部SAIF逐bit重放另见[完整125归档](../xu-score-s2e-activity120-server125-20261105/README.md)。

从任意目录复核：

```sh
python3 /home/mxhanks/Projects/ChipContest-xu-score-opt/docs/validation/xu-score-formal-cycle-comparison-20261105/check-evidence.py
```

checker核对每成员SHA、原manifest关联、完整12任务、候选及配置身份、对应层tensor收据、唯一SOC_PASS、物理清零、窗口、原phase计数和派生CSV/JSON。它不运行EDA、不计算能量、不授予时序资格。本轮没有新增Chisel修改；S2e生产变更仍是paired-HI接口RTL和固件读回调度，见中心台账。
