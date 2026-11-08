# S3-Y32 postflow 便携仿真证据

原始测量与失败日志按字节保留；原绝对路径不重写。
`provenance.json` 给出每文件原路径、SHA256、大小与权限，`path-map.json`
把原campaign前缀映射到本包相对路径。`sha256.json` 核验其他每个文件。
各 campaign 保留 source、vectors、ELF、Verilog加载图像、soc_sim、原始日志、
plan/result、clear recipe、构建与版本信息；省略波形及Verilator/C++中间文件。
内容硬链接仅发生于已经复制完成的暂存文件之间，不连接原始证据。

`campaign-inventory.json` 逐项保留真实status。所有通过仅是
`DEVELOPMENT_PASS_POLICY_PENDING`，不代表官方验收；失败与fixture修复前的
NOTPASS输出见 `failure-log-index.json`。若初始失败fixture没有独立源快照，包内保存其原日志及最终修复后的fixture，不将其声称为可精确复现的成功运行。该索引按诊断字样列出，需结合原日志上下文，
不会把负例注入测试里的预期错误误写为新的成功仿真。

- `campaigns/`：8/16 PE基线、bias pipeline、batch16、组合、stream8、选中最终12层及旧固件兼容回归。
- `proofs/`：偏置流水化Chisel和真实wrapper、batch16及stream8错误/背压/复位、失败fixture及修复日志、回滚脚本。
- `proofs/source-review/`、`proofs/selected-first-stall7/`：逐项源码review与首请求额外等待7拍的新进程验证，后者保留原receipt/log，不代替主性能比较。
- `summaries/`：原始strict comparisons、完整reviewed SHA pairs/pins、路线评估JSON/脚本、测量摘要。
- `patches/`、`source-additions/`：NICE独立实验与偏置改动的源、源码差分及对应原文件摘要。
- `reports/`：最终选择及实测报告。整任务收益以payload+真实clear为准，phase重分类不能当作总周期收益。

在任意新目录解包并保留归档权限后校验，不需要原绝对路径存在（Python `data` 解包过滤器会主动删除组写权限，不能用它验证原模式精确相等）：

```
tar -xpzf s3-y32-postflow-evidence.tar.gz
python3 s3-y32-postflow-evidence/verify_evidence.py
python3 s3-y32-postflow-evidence/revalidate_comparisons.py
```

两个脚本仅只读证据，均不启动仿真或EDA。后者重新执行已有严格比较器，
核验source/ELF/load image/命令/时钟/复位/clear/数值与工作量约束，比较结果与封存报告一致。
失败campaign仅保存诊断，不能要求其成为通过。打印可重定位的原生执行命令：

```
python3 s3-y32-postflow-evidence/replay_saved_command.py campaigns/stream-bias8-task0/task-00/simulation.log
```

该脚本只打印，不执行；实际复现应另建输出目录并保持包内日志只读。
本包Linux x86-64原生soc_sim仍需要兼容系统库；从源码重建需要配套Git仓库。
精确命令保存在各campaign plan/result/原日志，不能混用不同实验源码。

所有本轮优化均未综合；150 MHz为测试台刺激，不是STA结论。
Verilator为二态开发仿真，vendor SVA关闭而Chisel断言保留；不替代VCS、门级、面积、
时序、能耗或官方资格证据。清空政策REVIEW_PENDING、FIFO payload物理清零UNPROVEN仍保留原义。
