# xu 首个正式清空/请求窗口与 SRAM 引脚活动证据

实际服务器 VCS `Q-2020.03-SP2-6_Full64` 首个独立 task 0 完成：25,344 个输出、50,688 个 Y 写回字逐项正确，使用 nominal150 HF、32.768kHz LF、1fs 精度。源码主仓 `854164105f1ab7a9aac79ceaadddad41a1bb6c5f`，子仓 `f49a5fc914971426bd4530db39e270a84b41139f`，SiFive GCC10.2，`bias-hw-window/-O2/both-unroll-no-masks`。没有改 Chisel、功能 RTL、厂商模型或数值格式；生成绑定的普通 RTL observer 只观测宏引脚，不驱动 DUT。

此运行是 **`PARTIAL_COLLECTED_REVIEW_PENDING`**，只有 task 0；不是十二任务验收、映射后功耗覆盖合格、SRAM internal_power 审查、正式能量或评分。正式窗口要求“任务前物理清空”；清空不等于把 SRAM 模型内部未知值强置零。

## 实际窗口与清空

| 事件 | HF cycle | tick（1fs） |
| --- | ---: | ---: |
| 清空开始 | 1,201,701 | 8,011,343,333,333 |
| 最后清空写接受 | 1,403,894 | 9,359,296,666,667 |
| 第一笔输入/参数读请求 | 1,403,981 | 9,359,876,666,667 |
| 最后 Y 响应退休 | 2,774,837 | 18,498,916,666,667 |

实际执行并观测 **33,697 次清空 MMIO 写**：16,384 个 W 数据字、256 个 bias、8 个 legacy bias、64 个 X 等数据清空及控制事务，随后 drain 至 idle/cache-enable=0。清空数据写内容被 TB 逐项检查为零。另保留原固件第一笔输入前两次 W 目标设置零写；它们不是数据装载，单列而未隐去。第一请求无等待，所有该任务 W/bias/X 上传均在窗口内且与原向量逐项匹配。清空前/中活动在此任务 SAIF 之外；本证据没有清空阶段功耗。

物理半开区间 `[first valid source request, final Y response retired)` 为 **9,139,040,000,000fs = 9.13904ms = 1,370,856 个经过周期**。保留原 inclusive TASK_PASS 诊断为 **1,370,857**，firmware mcycle 为 1,370,927；不得混为同一个计时定义。这个单任务独立、物理清空的窗口不能直接与此前连续十二任务的旧接受窗口作优化对照。

## 真实宏引脚与未知值

336 个实际 RAMSP1024X16：共享 256、ITCM 32、DTCM 32、加速器 W 16。每宏 67 个信号位，共 **22,512 个测量位**。VCS 将生成 observer 的 net 标记为 literal `macro_0000.CLK` 形式；归一化只对清单中的确切名字做双射，保留每一位全部 T0/T1/TX/TZ/TB/TC/IG，原 SAIF 不变。其余 113,642 条原活动信号同样保留。生成 observer、mapping 和归一化 receipt 原字节已带回。

DTCM 在该 hot loop 中确实禁用：32 个宏的 **96 条 CEN/CLK/RET1N** 全窗口分别为 1/0/1，且已知、零翻转；内部未知 dwell **5,437,728,800,000,000 bit·tick** 仍保留，不解释为零功耗。CPU、加速器、互连、ITCM、共享存储均存在实测活动。信号存在与归一化完成，不能替代 PT 映射后 file/default/propagated 覆盖审查或 SRAM Liberty 工作模式审查。

完整 task SAIF 留在原服务器，不在本次紧凑归档中；这里核对其服务器记录身份，不声称对本地缺失字节重算哈希：

- 原始 25,301,213 字节，SHA `1f545129409db7c546d5c3a1446cc54612de7bb122d2b694ded25961144b1b0e`。
- 归一化 12,707,556 字节，SHA `3799d77185447a680d4444f5d9568ca66370e5c456fe72b19e9eb751c13e0f06`。
- 每位比较摘要 `659ab9c24a395563a6353e4c7ef705a3c3a726d9fda3f7532a8b392f5b2e7d05`。

## 单宏独立校验及失败历史

另外保存实际 VCS 单宏 22–62ns 的 raw 与 normalized SAIF、端口 VCD、源码及日志。独立逐位核对全部 67 引脚：CLK 8 次已知翻转，T0/T1 各20ns；数据、地址和控制为源码指定值。Q 从 22ns 到 **25.01ns 仍未知**，所以每个 Q 位 TX=3.01ns，余下36.99ns为55AA对应值；X→已知不计为0↔1 TC。raw alias 与 normalized PORT 全部状态完全相同。VCS 模型最终 Q=55AA，仿真结束于62ns。

原直接 VCD 转换检查拒绝末尾最大 timestamp=60ns而未达到62ns；原手算首次又误以为 Q 整窗已知而失败。这些 FAIL 原文与错误原因保留，没有改写成 PASS。第二份独立手算明确依据源码、VCD 的25.01ns转变和原仿真62ns结束日志，得到 `VERIFIED_67_PIN_HAND_EXPECTATIONS_REVIEW_PENDING`。它支持该 observer 在实际 VCS 的精确状态采集；不能推论 SRAM 内部功耗模型已合格。

## 本地复核与服务器复现

原取回包 45,104 字节，SHA `e8cf2c1ef7cc84a2efb6782668b3c3c4d87ad7a0a139388dba466e2d499191e7`，24 个唯一 payload 全部大小/哈希相同。`raw/manifest.json` 与 `server-export.tar.xz` 保留；`evidence-tools/` 是本次使用的外部 launcher/手算/导出脚本，脚本不含访问凭据。归档 checker 还独立核对 **152 个已带回/可验证源文件**、正式窗口日志、DTCM控制记录与实际单宏SAIF；没有重放完整缺失 task SAIF。

```bash
python3 docs/validation/xu-score-s0-soc-20261102/clear-alias-server-20261103/check-evidence.py
```

服务器使用实际厂商模型，检出同一主仓/子仓后，必须取新的输出目录：

```bash
python3 tools/ppa/xu_soc_task_activity.py \
  --out "$xu_new_activity_out" \
  --vendor-model /storage1/admin_public_dir/SRAM_Lib_2025/RAMSP1024X16/verilog/RAMSP1024X16.v \
  --netlist /storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/full-soc-campaign-03-ppa/ppa-ss-01/mapped.v \
  --constraints /storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/full-soc-pt-compatible-05/constraints.sdc \
  --cross-prefix /storage2/2026contest/server4/s4_23usr/Desktop/xu-platform-eval-20261101-codex/sifive-rv32-c/bin/riscv64-unknown-elf- \
  --clear-task-before-window --sram-pin-alias --task-ids 0 --max-cycles 4000000
```

映射网表 SHA `0f4898ba5ab6571c2125978cdce0a9984a87d4df9901757cb1c00662e4ef3616`，分析 SDC SHA `404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98`。绑定源码、向量、固件、工具命令的完整原记录在 `raw/task-activity-clear-alias-20261103-01/task00/result.json`，首个全量十二任务采集及 PT 功耗注释需另行归档。
