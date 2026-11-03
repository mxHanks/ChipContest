# xu S2c 独立正式活动采集器

本工具只面向冻结 S2c 候选：主仓 `d276b55ffecbe8d620f9a361bf5d0859299ba7b5`，E203 子仓 `49a9436e01ea8ceeead94242e4a99c16e31a0865`，profile `s2c-autogroup`。它与 baseline 活动采集器独立，不能读取 baseline SAIF 充当 S2c 活动。工具仓可以在另一个干净工作树；`--source-root` 和 `--tool-root` 分别指定两者，后者必须是所执行脚本所在仓库。原 `xu_soc_task_activity.py`、`xu_soc_ppa_verify.py`、`xu_task_clear_protocol.py`、`xu_sram_activity_alias.py` 及共同固件/模型工具逐字节 SHA 固定，不修改它们的源码或模块对象，也不放宽其 f49 guard。

`xu_candidate_activity_context.py` 对主仓的完整 tracked blob/mode/gitlink、子仓批准 profile 的完整 tree/blob/mode 和活跃 RTL 目录做检查，拒绝 dirty、非忽略 untracked、隐藏的 assume-unchanged 字节修改、错误主/子提交及额外活跃 RTL。工具仓要求已提交且干净，并绑定 HEAD/tree。工具与源代码、输入向量、生成的 TB、observer/mapping、固件/编译器、外部模型、目标网表、SDC 在编译及每任务运行前后重验。网表/SDC 在此只是身份输入；此工具不证明该网表与候选的等价或时序。

每任务使用新仿真进程、`TASKS=1`，将全 12 任务的原始 fixture 校验后，把指定全局任务复制到该进程 `layer_00`，保留全局 ID 与文件哈希。默认 `--task-ids 0,1,2,3,4,5,6,7,8,9,10,11`，少于 12 项只能获得 `PARTIAL_*`。禁止任务间复用 W/X/bias。CPU 首先通过旧 MMIO 执行 33,697 个零写；被动 observer 检查全部 16,384 个 W、64 个 X、256 个 40 位 bias 的实际 core 输入提交及旧 8 路 bias 清零，确认 reset 后 FIFO head/tail、计数和逻辑所有权为空、没有流传输或响应未退休。FIFO payload 寄存器没有物理 reset，本工具明确保留这一限制；它检查空逻辑所有权及本任务全部结果重新产生/读出/退休。

首个任务源数据读取 **REQUEST** 前，除上述精确清空序列和允许的能力只读检查，不准额外目的设置写。S2c 的 W cursor、cache 模式等设置都在首源请求之后。首请求即打开 SAIF，阻塞直到 ACCEPT 的拍数也计入；结束是最后 Y 写响应 **RETIRE**。保留候选原 TASK/PERF/AUTO 计数作为旧 ACCEPT 窗口诊断，另外报告正式 elapsed/inclusive cycle 与整数 fs 时间。HF 150 MHz 和 LF 32,768 Hz 都按绝对目标相位生成，1 fs 精度，不逐拍累积小数周期舍入。LF 额外检查所有边沿的相位误差不超过 1 fs。

PACK32 不按 MMIO 写次数假定两份数据已生效。observer 在采样边沿检查 `u_linear_compute_core.io_wLoadWen/io_xLoadWen` 的实际 bank/address/data、第一/第二提交顺序及 fixture 值，精确覆盖 W16,384、X6,336（99×64）、256 个 signed40 bias。每行必须先上传完整 X，W/bias 完整且 FIFO drained 后才可 STARTROW；实际自主启动/完成为 3,168 组、所有 signed48 lane 值及 50,688 个返回字逐一检查，响应在阻塞至退休前保持正确。POP 只认实际响应退休的 `row_pop`，每组 16 字读取齐全后才释放。多余 cursor/cache 设置、重复/缺失/越窗提交、错误 FIFO 所有权或错误响应都会失败。

`xu_candidate_sram_activity_alias.py` 是冻结通用 alias 算法的显式 S2c 派生版本，使用新 schema、profile 与完整源/工具上下文，不修改或 monkeypatch 旧 normalizer。它检查真实新 core 层级的 336 个指定 1024×16 SRAM（共享256、ITCM32、DTCM32、权重16），每宏67 bit，共22,512 bit。VCS 的 `rtl_on` + cell debug 下，绑定普通 RTL observer 直接复制实际 vendor pin；不 force、不编辑模型、不将 X/Z/B 改为0。默认不设置 `INITIALIZE_MEMORY`。raw `task.saif` 永久保留，独立 normalized SAIF 按 bit 完整双射验证所有 dwell/TC/额外统计、native pin 一致性及非 alias 数据/时间基准，记录归一化回执。

这仍然只是 RTL 活动采集工具；必须另外审查实际 VCS 的 vendor/alias 相等性、mapped pin 映射与覆盖、未知活动、Liberty 模式、完整功能等价、全 SoC STA 和功率，才能产生合格能量。完成本地 Icarus/host 测试不代表服务器 VCS、SAIF 或比赛验收通过。

服务器命令模板（必须使用冻结候选对应的实际网表、SDC、工艺模型和同一工具链）：

```sh
python3 /path/to/clean-tool-root/tools/ppa/xu_candidate_task_activity.py \
  --tool-root /path/to/clean-tool-root \
  --source-root /path/to/frozen-s2c-source \
  --profile s2c-autogroup \
  --out /path/to/new-s2c-activity12 \
  --vendor-model /path/to/RAMSP1024X16.v \
  --netlist /path/to/s2c/mapped.v \
  --constraints /path/to/s2c/exact-analysis.sdc \
  --cross-prefix /path/to/same-server-toolchain/bin/riscv64-unknown-elf-
```

先加 `--task-ids 0 --prepare-only` 可核对完整生成物，状态明确为未仿真；首次单任务实际采集加 `--task-ids 0`。全部 12 项使用默认值。`--initialize-vendor-memory` 只用于明确标识的独立实验，不能混合到默认未知保留的结果。

本地复现：

```sh
XU_S2C_SOURCE_ROOT=/home/mxhanks/Projects/ChipContest-xu-s2c-autogroup \
XU_CANDIDATE_ACTIVITY_TEST_EVIDENCE=/path/to/clean-tool-root/build/xu-s2c-activity-tests \
python3 -m unittest discover -s tests/host -p test_xu_candidate_task_activity.py -v
```

测试包括真实 GCC 固件和 partial prepare、完整 336 宏/22,512 引用路径 elaboration（明确 open geometry stand-in、未仿真）、真实 S2c wrapper 的 99 行/全部组/返回字/退休及破坏性数据或协议注入、完整 pin SAIF 合成输入的未知保留/篡改拒绝、10000 LF 边沿绝对相位测试、实际 cloned repo 的 assume-unchanged 隐藏修改拒绝。探针以 Python 任意精度独立计算 signed16/40/48 golden；它不是 E203 全任务或 vendor SAIF 仿真。Python producer 使用3.6标准库兼容语法。
