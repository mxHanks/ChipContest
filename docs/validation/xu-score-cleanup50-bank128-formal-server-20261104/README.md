# 清理50和紧凑32PE的完整实际Formality终态

17份原件共8,662,432字节，无损保存在[共享原包69](../xu-score-server-export69-20261104/README.md)；本目录的[selected-manifest.json](selected-manifest.json)列出逐份原始SHA。没有用已有候选证明替代新网表，也没有把SRAM黑盒验证说成内部仿真。

| 目标 | 实际网表SHA | native passing | unread | 冻结before/after输入 |
|---|---|---:|---:|---:|
| 清理50 | `9b7265e703ea62487c5b5c39c66adf245e720ac02f1066063cfd0eb4753f460c` | 41462 | 508 | 176 |
| 紧凑32PE原综合网表 | `7a69a1219561ca7a2e162ac84007f9fb32f34264132d1e6999e34c990cabe628` | 52334 | 511 | 346 |

两次均真实return0、唯一`Verification SUCCEEDED`及专属完成marker、native failing table为0、全冻结输入before/after相同。原日志没有独立aborted统计行，不凭空补0。

清理50保留default→08→09→49→50完整SVF链，17136 BBPin、144 Port、24143 DFF、39 LAT通过。删除3个有RTL未使用证明的PLIC状态寄存器后，unread从511变508；该PASS并不等于所有原RTL状态都比较过。50仍有187项min-cap、5项removal和27124项untested，详见[实际清理报告](../xu-score-electrical-cleanup-server-20261104/README.md)。

紧凑32PE证明读取164份冻结参考RTL，四个define明确包含`XU_ACCEL_PE32_BANK128=1`，仅使用自身原始default.svf，不借用原32PE修复SVF。22464 BBPin、144 Port、29687 DFF、39 LAT通过；三份SS DB分别为标准单元、RAMSP1024X16、RAMSP128X16，包含所有448个混合宏边界。vendor128仿真model仅冻结provenance，没有读入FM改变黑盒语义；指定宏真实VCS另有[独立证据](../xu-score-s3-pe32-bank128-server-20261103/README.md)。source own SVF首次在本次服务器before/after冻结，不伪称本地已有历史正文。

auto-setup、undriven、unmatched和全部原始日志保留。**证明只覆盖各自数字逻辑映射一致性，不代表宏内部、完整150MHz、电气、功耗/能量或比赛资格。** 两目标也不是同一个候选，不能混用最优指标。

```bash
# 默认流式核验完整435份共享原件，再审查此17份实际证明：
python3 docs/validation/xu-score-cleanup50-bank128-formal-server-20261104/check-evidence.py
# 若已有严格解包目录，可只重放此17份原件：
python3 docs/validation/xu-score-cleanup50-bank128-formal-server-20261104/check-evidence.py \
  --source-export build/xu-score-resume-20261103/next-results-export-69
```

服务器实际命令（现有输出禁止覆盖；复现时修改helper输出名）：

```bash
python3 "$HOME/Desktop/launch_electrical_formality54.py" 50
python3 "$HOME/Desktop/xu-bank-fm57.py" start --fm fm_shell
```

第二个helper SHA256 `b891040f2bf4aa8d9e60ddfe85a76c96db0c09637156d0359eb6cb4ecd4df7b3`，已被346项输入freeze覆盖；完整实际Tcl在共享原包内，可直接用于新目录重放同一证明。
