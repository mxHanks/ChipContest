# 最终候选原件索引

官方原件保留在 RDserver04、s4_23usr、工作区 3，不下载至本机。本文为界面审阅后整理的索引，不是原件副本或最终提交冻结声明。根目录为 `/tmp/xu-b41-close-20261111-r1`。

## 物理综合导出

目录 `xu-closure-20261112-r4/dc`。当前 run.tcl/native.log 的 SHA 与 complete=true、native_exit=0 的原生回执一致。回执记录实际执行在 `xu-closure-20261112-r3/dc-clean/run.tcl`；该目录成果随后封存在 r4，不能把封存路径误写为另一轮新综合。

脚本从 r2 mapped.ddc 读入，启用 eco.svf，执行 r3 clean.tcl，前后 link 均有失败退出，核对 337/17 宏和时钟缓冲后依次导出 Verilog、DDC、SDC。网表、DDC 和导出 SDC 之间没有新的网表变换。

| 文件 | 字节 | SHA256 |
|---|---:|---|
| mapped.v | 20,816,052 | `2d5adc613980dc21dc1f0aaa398045252911a5c67594349630ff35d78688a220` |
| mapped.ddc | 17,391,616 | `a030a8b2fdd5f54e6ccb2c9cfe5be1cbce9fe08e7decf9b6d156236d388f81b0` |
| mapped.sdc | 59,460 | `7f075aedba00cd1a8c1b9ddcf0bdb312ea8d0b0bad014cbd38c167fc0a739a1d` |
| eco.svf | 9,984 | `af3e8a42eba3402c85616008ef28ec2c171c1fedf8f94624be949b37ae2138f9` |
| run.tcl | 2,156 | `6576346c5e29af7ae2fa069ae3b6aaa30f78ef93b307539d216a76e333709ac5` |
| native.log | 57,096 | `9e14975ff3c6aeee1ba0b91d172aaed3d310f1d17bf8add89a0e712b7ffa893b` |

`dc/mapped.sdc` 是 DC 导出快照。四工况 STA 和全 SoC 功耗实际使用的是保留的 `pt-clock-root-r1/constraints-pt-add.sdc`，SHA256 `404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98`。两份约束的角色分别保存，不把导出快照当作实际 STA 输入。

## 门级与独立复算

功能副本 `xu-gate-reset-20261112-r2/mapped-functional-reset-r2.v` SHA256 `d8e1c611016b0baa943115078ad49f6e0a147980a7e9fe13df5d3e5827da95ac`；同一可执行件 `xu-gate-reset-20261112-r1/simv-row-r1` SHA256 `1845483bafd5c8fdd6e16111a5a03eefdb275c8817306978e87851f6f9da64fa`。

tight-O2 原件在 `xu-gate-20261112-r1/tight-O2-full12-r15`。扩展独立复算 r2 包含 13 组软件计时、全部 clear 脏前态与清零末态、物理夹具交易字段、逐批有效行数和时钟身份。每任务 13 批为 12 批 8 行加尾批 3 行，合计 99 行；169 组宏读对应 warmup 加 12 正式任务。

独立脚本 `xu-review-gate-full12-r2.py` 为 8,416 字节，SHA256 `acb23e938adab68ebb194abe5fba9884456bd6ab6248e0cd3e2e327d65914a13`。tight 回执 `xu-gate-independent-20261113-r2/tight-O2.json` SHA256 `f75f69aea0c3e9959ea92aa07e8d7e6cc5f0faad42f7ddebdd0f6407d5ee4a4e`。

| tight-O2 正式任务合计 | 周期 |
|---|---:|
| payload | 416,580 |
| 主 TB clear | 12,336 |
| principal = payload + clear | 428,916 |
| gap | 528 |
| TB 中固件报告字段 firmware_cycles | 429,744 |
| 软件完整控制窗口 | 429,864 |

最后一项按 `report_retire - clear_request + 1` 复算，与冻结 RTL 对照值一致。r1 独立回执中的 `software_control_cycles` 字段实际只累加 TB firmware_cycles；原 r1 回执保留，使用 r2 正确区分后的两个字段。

phased_64_fast4-O2 原件在 `xu-gate-20261112-r1/phased_64_fast4-O2-full12-r15`。原生 2,323.528 秒、exit=0，12 正式任务、1 warmup、304,128 正式输出、25,344 warmup 输出、13 次清零与 169 组宏读通过。实际周期为 payload=416,580、clear=12,336、principal=428,916、gap=756、固件报告 firmware_cycles=429,984、外部软件控制=430,104。

| phased 原件 | SHA256 |
|---|---|
| native.log | `331e7d25b1843376b6a00687884924900e5809e032cee42649f3f7d47dcf0d86` |
| result.json | `ce42996183ad3be34661704b27ddf403825d022c3f0ef0a1250a3b033b1f06ba` |
| verified-binding.json | `df94133f1a396df1404c8f7c0dbb415e45124abc98475c43a37f659cc75911f7` |
| 94,355,730,661 字节 VCD | `7797a235563c964901210617b19ceb88822866b2e8b3538447a934d9d277c7cb` |
| 独立 R3 回执 | `8a95f116ae1a42d55a38400c85f1425f22e54b55c1cda137e477638086fd251f` |

phased 的实际门级周期与冻结 RTL 有小幅差异。R3 保留全部原生/冻结检查及预算，记录跨模型差值；原 R2 的额外常量比较失败保留。R3 程序 SHA256 `500221eb850b894f1d6ed5d58c51ebbd780bb8c2418c6e3b6dda709bcf8e79e8`，原件在 `xu-gate-independent-20261113-r3/phased_64_fast4-O2.json`。旧 R2 campaign 路径为有来源记录的符号链接，不代表旧程序重新通过；见 [复算合同修正](REVIEW-CONTRACT-CORRECTION.md)。

目前 backoff 固件完整门级、三份同窗功耗、能量、最终选型和资格补充检查仍待完成。
