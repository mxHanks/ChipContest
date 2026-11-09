# 两行 × 八列真实 RTL 单层筛选

本原型回答“两个输入行共享八路权重能否精确工作，以及消费背压会吞掉多少计算收益”。它没有接入正式 CPU/MMIO，不将模块周期当作 SoC 周期。正式最优已测总周期 5,874,840 不因本实验改变。

生产源码是 `../rowpair-repo/src/main/scala/linear/LinearRowPairPrototype.scala`，生成 RTL 在 `../rowpair-repo/generated/LinearRowPairPrototype/`。固定 `DotProductEngine` 的 signed48 算术、同步 SRAM 时序和 bias-demand 预取方式。两个引擎共享唯一八 bank 的 WeightBankArray、唯一 BiasSramPrefetch；各有64个INT16的X缓冲。第二行增加128 B X存储。两个pair槽共192 B raw48结果容量，输出顺序是group0/row0、group0/row1、group1/row0、group1/row1；没有缓存整行1 KiB的Y32。99行最后一行禁用第二引擎且只输出row0。每个8lane结果在消费者POP提交前保持稳定。

对照的“单行”是**同一原型**将secondRow设为0，第二引擎不启动。它不是正式8PE SoC基线。原型具有16个MacPE，但没有面积、关键路径或功耗资格结论。

## 已冻结证据

`final-numeric/receipt.json`锁定所有生成SV、所有生产Scala、driver、只读observer及其生成器、runner、五个实际task0向量的SHA256；整个测量source_drift为空。核心Scala SHA256为`2f4688fdf7768b1ea96120ec5fe433d6680dcc1183e555f39d944ed4aaa8c002`，顶层SV为`a6abaf295e8ccbbef77106f3cca3dd5a960c21f0a50e2aed1a36a9a983767b9f`。

十种场景是单/双行乘以每8lane束额外消费停顿0、31、60、80、255拍。每种都从公开load口真实加载原task0 W/X/bias，逐个比较25,344个真实RTL raw48结果与原y.mem，保存实际采样文件`*.actual-raw48.mem`。C++分别按独立整数公式重算golden，并把采样raw48执行RNE比较y32.mem；`*.cpp-rne-y32.mem`的Y32转换在C++，**不是RTL转换证明**。真实NICE和RTL转换由相邻DMA组合实验独立验证。

每场景另验证512个合法端点结果（包含618,475,290,623与−618,473,193,472）、三个复位边界（MAC期间、row0束停顿、row1束停顿）、复位恢复512结果、dirty清零前512个非零结果、clear后512个零结果。所有POP由公开口驱动，没有force、deposit、层次写或FIFO预置。

`generate_observer.py`生成test-only bind，直接只读17个真实`mem_ext.RW0_*`端口，逐个物理地址检查每次clear的16,384个W零写、768个bias零写和两个X真实写口的128个零写，无漏址或重写。第二次clear前通过公开口把每一个W/X/bias物理字实际写成非零，并确认这些地址覆盖；同时只读确认X128、ACC16、engine result16、FIFO32个寄存器全部非零，clearDone后全部为零。它也对每个row/pair结束检查实际W宏读16,384次、bias宏读768次。此证据限定当前行为SRAM与两态Verilator，不升级正式clear政策或vendor宏资格。

## 测量结果

这里每束消费停顿是C++ sink的控制变量，**不是测得的NICE平均服务时间**。每束还有一个POP边沿；不存在假想并行总线写。

| 每束额外停顿 | 单行active+Xload | 双行active+Xload | 降低 | 单行FIFO满等待 | 双行FIFO满等待 |
|---:|---:|---:|---:|---:|---:|
| 0 | 224,631 | 116,635 | 48.077% | 0 | 0 |
| 31 | 227,700 | 119,704 | 47.429% | 0 | 0 |
| 60 | 230,571 | 204,601 | 11.263% | 0 | 79,380 |
| 80 | 272,448 | 267,744 | 1.727% | 38,610 | 138,570 |
| 255 | 826,848 | 822,144 | 0.569% | 558,360 | 658,320 |

X load两种均6,336拍。单层真实宏W读从1,622,016降至819,200（49.495%），bias宏读从76,032降至38,400；总MAC工作仍为25,344×64。计算launch从3,168次变为1,600次。宏读减少不等于任务加速：80拍消费时模块收益已不足2%。

每case启动前完整物理clear观察窗口16,387拍，W/bias参数load18,432拍；JSON的`clear_parameter_x_compute_consume_window_cycles`另包含这34,819拍。这是模块公开口按一拍写一个权重的驱动窗口，不能与正式packed MMIO清零的66,802拍比较。`active_cycles`含内部bias等待、计算及消费背压；FIFO满等待和MAC边沿是实际监测，消费停顿与计算重叠，不能重复相加。

## 复验

从rowpair-repo生成：

```bash
scala-cli run . --server=false --jvm system -M GenerateRTL -- LinearRowPairPrototype
```

从任意目录调用runner；`--out`必须是新目录，避免覆盖旧证据：

```bash
python3 /home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest/build/last-two-20261109/rowpair-checks/run_rowpair.py \
  --repo /home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest/build/last-two-20261109/rowpair-repo \
  --vectors /home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest/build/bias-demand-20261109/pilot-task0/task-00/vectors/layer_00 \
  --out /tmp/rowpair-new-campaign
python3 /home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest/build/last-two-20261109/rowpair-checks/verify_rowpair.py /tmp/rowpair-new-campaign
```

`final-verification.json`是独立重读证据；`negative-verification.json`保留三个拒绝案例：实际raw48翻一bit、源SHA篡改、第二次physical-clear marker删除。`negative-*/rejection.log`保存失败原因。先导证据在本目录顶层及`final/`，最终只引用`final-numeric/`。先导runner在执行前因错误预期生成SV数量12（实际11）退出，随后修正；没有从该失败产生测量结果。未综合、未修改CPU/LSU/BIU/仲裁/在途配置、未改已封存旧证据。
