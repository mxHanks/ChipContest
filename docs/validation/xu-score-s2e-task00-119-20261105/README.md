# S2e actual104 task00：请求至退休窗口与原始活动归档

本目录保存actual119中`s2e-formal-activity-task00-20261104-104/`的**完整19项原字节，共40,514,461字节**，包括顶层/task结果、原始与normalized SAIF、原VCS日志、observer与mapping、固件构建收据。派生包`payload.tar.xz`为731,452字节，SHA：

```text
fd084168155c5f4bc7ce43a87958e34e61eab73ad1b9c8001b482fb477ee8d2d
```

每个文件与[完整119原包](../xu-score-native-audit118-20261105/supplement119.tar.xz)逐字一致；原包为872,692字节，SHA `ec9657776616f72bc98bb7c876acf71a77bdc9614ab31b9581f4c780c3acb934`。`selection.json`、原完整119清单及子树清单保留选择范围，不改写原收据或日志。

**本次只采集task00。原顶层状态为`PARTIAL_COLLECTED_REVIEW_PENDING`、taskset_complete=false；不代表全12层完成，不代表mapped活动注入、完整150MHz或全SoC能量合格。**

## 实际窗口、清零和结果

冻结main为`5bf123bfead8f2a37f97f3234d4e40ce8201aae9`，child为`a0767db69628ef30e53de2d1e93dd0360c0ccf76`。同服务器GCC10.2/VCS2020；HF名义150MHz、LF32768Hz，仿真精度1fs。配置SHA `0e839b465577bf313345ddba8f02d4f860c5fa3a02f4f753e6acd327ef2df029`。

| 边界 | 周期号 | 原始tick（fs） |
| --- | ---: | ---: |
| 首次输入/参数source REQUEST（同周期ACCEPT） | 1,403,992 | 9,359,950,000,000 |
| 最后Y响应退休 | 2,272,335 | 15,148,903,333,333 |

物理区间为`[begin,end)`：**868,343 elapsed周期，868,344 inclusive周期**，持续5,788,953,333,333fs（约5.788953ms）。日志`TASK_PASS cycles=868344`是inclusive诊断值，不能再多加一个周期。固件读数868,419是另一测量边界，不拿来替代活动区间。

活动开始之前，CPU实际接受33,697次legacy零写；内部零提交观测为W16,384、X64、bias256，FIFO逻辑所有权复位且空。最后零写在source请求之前98周期；SAIF不包含清零阶段，未把其能量算入任务。原始源请求前没有候选任务数据/目标设置写。

窗口内重新提交W16,384（8,192次pack32）、X6,336（3,168次pack32）、bias256；99行、3,168次start/done/POP退休，结果FIFO最终为空。结果读取为25,344 legacy字＋12,672 paired-HI字，共38,016次物理读，对应50,688逻辑字；输出25,344、共享写50,688。原日志唯一`SOC_PASS tasks=1 outputs=25344 writes=50688`，原始数值/上传/结果/时钟检查通过。

## 同一候选映射证明绑定

本活动收据绑定S2e自己的mapped SHA `0cfac0b5e99ec05301ec8c0efde38ef2c96790dd1243e84727687b15b25c09d0`，以及独立109原件审计收据SHA `79c011fc965b620cd39954405ade0b9759e4a409a90b33ad6c683eea3f18594f`。109的完整顶层原生Formality为42,338 passing点，原89误报失败状态保持原样；具体范围和SRAM黑盒限制见[109归档](../xu-score-server-progress114-20261105/README.md)。

这是RTL活动及其同源mapped证明身份，不是门级任务仿真或PT注入通过的证据。没有借用S2c映射、SVF或活动结果。

## 原始SAIF与逐bit normalization复核

| 文件 | 原字节数 | SHA-256 |
| --- | ---: | --- |
| raw `task.saif` | 25,568,880 | `5390a5698d41d4734ae218e93c410076e0dd55f9c2e68dfc5cee764e2f7969c7` |
| `task-normalized.saif` | 12,854,048 | `7d91fc3e15f3abe42c6f3e7572e46f41ad34f3afb6cd4db91be41827f32294d2` |

本地从原始两份SAIF重新解析全部信号，独立构建mapping的336宏×67bit双射，并逐22,512bit比较所有dwell/TC/IG等统计；114,927条非alias原信号逐项保留，normalized共137,439条。alias名称和per-bit比较摘要均匹配原收据，timebase与持续时间不变，TX/TZ/TB没有置零或推断补值。alias未知bit-ticks合计26,076,600,970,238,528，原样保留。

这重放的是已返回原始活动的测量双射与保真转换，不绕过或冒充重新执行服务器源码绝对路径guard。工艺模型、固件ELF及完整源码等未进入此子树；它们身份保留于原收据，不能仅凭本地归档声称已经重新哈希这些未返回正文。后续仍需检查实际mapped注入覆盖、原生未知态解释、Liberty功耗以及完整任务能量；本目录不增加新能耗数字。

## 复核与复现

```bash
python3 docs/validation/xu-score-s2e-task00-119-20261105/check-evidence.py
python3 docs/validation/xu-score-s2e-task00-119-20261105/check-evidence.py \
  --extract /absolute/path/new-xu-s2e-task00
```

第二条要求目录不存在。校验器逐字核对完整119原包与子树原件、配置及109绑定、实际日志边界/计数，并重读raw/normalized SAIF比较完整alias双射；PASS只授予以上范围。

`tools/ppa/xu_s2e*`保存本次相关公开producer工具，`tools/scripts/xu_soc_activity.py`是本地逐项重放所用的原SAIF读取器，完整身份见`tools-manifest.json`。task结果保存真实VCS执行命令和固件构建命令。服务器生产命令参数见实际collector的`--help`及原driver；使用`xu_s2e_activity_server.py task00`时必须提供同一冻结source、自己的mapped与109 proof上下文，并使用新输出目录。原104、原119均不可覆盖；本归档不会把后续full12进程已启动当作终态证明。
