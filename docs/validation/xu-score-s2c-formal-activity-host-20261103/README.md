# xu S2c 正式活动采集器：本地交付验证

本轮直接对干净工具提交 `8d44c851fd0d181cbe4605915a9b31b43398f31a` 运行完整 9 项测试，92.042 秒全部通过，无跳过。源候选仍是主仓 `d276b55ffecbe8d620f9a361bf5d0859299ba7b5` / 子仓 `49a9436e01ea8ceeead94242e4a99c16e31a0865`。该提交之后本证据提交只新增本目录，不改变采集器实现。

`raw/unittest.log` 保留原始测试结果；其他 `raw` 文件保留每个编译/仿真/克隆/prepare 命令与日志原文，`evidence-tools` 是本轮源码副本。`summary.json` 给出覆盖与原工具/源上下文；`manifest.json` 对本目录其余全部文件记录 SHA256/字节数。临时目录路径原样保留，不能视为仍存在的服务器工件。

真实 S2c wrapper 的 99 行正例覆盖 33,697 次清零写、16,384 个实际 W 提交、6,336 个实际 X 提交、256 个 signed40 bias、3,168 个组、3,168 个 POP 响应退休及 50,688 个返回字，逐字与 Python 任意精度 signed16/40/48 golden 比较。9 个破坏例验证额外 pre-source 设置、实际 W/X 数据错误、源 REQUEST 阻塞期间地址/valid 变化、未读全便 POP、错误 capability read、重复 cursor 设置和阻塞响应数据错误会失败。

其他检查包括 336 宏全部 22,512 bit 的层级 elaboration（明确 open geometry stand-in、未仿真）、完整 pin SAIF 归一化的 X/Z/B/额外统计保留与篡改拒绝、完整源树假干净修改拒绝、真实 RISC-V GCC partial prepare、10,000 个 LF 绝对相位边沿，以及 REQUEST/RETIRE 整数 fs 边界核对。旧 baseline helpers、4 个共同 SoC/SRAM adapter 及其 guard 均未修改。

这里只证明本地开发测试通过。尚未证明实际 VCS 的 vendor/alias 一致、mapped pin 活动/未知值/Liberty 模式可用、候选完整 STA 或全 SoC 能量；不得代入比赛能耗评分。FIFO payload 没有物理 reset，采集器证明逻辑所有权为空且本任务结果全部重新产生/读取/退休。联合条件模式 observer 后续另 revision，不在本交付中混入。

本地复现（在干净、已提交的工具树）：

```sh
XU_S2C_SOURCE_ROOT=/home/mxhanks/Projects/ChipContest-xu-s2c-autogroup \
XU_CANDIDATE_ACTIVITY_TEST_EVIDENCE="$PWD/build/xu-s2c-activity-tests-new" \
python3 -m unittest discover -s tests/host -p test_xu_candidate_task_activity.py -v
```

服务器使用同一已确认的 VCS/RISC-V 工具链，在已有冻结 S2c 源树旁建立新的干净工具树。工具树必须包含本次 producer 的全部 4 个实现提交（`b35c422`、`ce0e361`、`f8140fe`、`8d44c85`，或其合并后的相同源码），原 baseline 树保持原状。下列路径是已知服务器布局；运行前对目标网表/SDC 的哈希与对应原始 PPA/等价回执核对。采集器记录这些身份，并不自行证明它们等价或时序合格。

```sh
xu_base="$HOME/Desktop/xu-score-optimization-20261102"
xu_tool="$xu_base/ChipContest-candidate-activity-tools-20261103-01"
xu_source="$xu_base/ChipContest-s2c-02"
xu_cross="$HOME/Desktop/xu-platform-eval-20261101-codex/sifive-rv32-c/bin/riscv64-unknown-elf-"

python3 "$xu_tool/tools/ppa/xu_candidate_task_activity.py" \
  --tool-root "$xu_tool" --source-root "$xu_source" --profile s2c-autogroup \
  --out "$xu_base/s2c-formal-activity-task00-20261103-01" \
  --vendor-model /storage1/admin_public_dir/SRAM_Lib_2025/RAMSP1024X16/verilog/RAMSP1024X16.v \
  --netlist "$xu_base/s2c-ppa-campaign-20261103-01/s2c/ppa/mapped.v" \
  --constraints "$xu_base/full-soc-pt-compatible-05/constraints.sdc" \
  --cross-prefix "$xu_cross" --task-ids 0
```

先作生成核对可加入 `--prepare-only` 并换一个新的 `--out`。实际任务 0 采集通过后，完整 12 层采用默认 task IDs 并使用另一个新输出目录；每层仍是独立新仿真进程。禁止加 `--initialize-vendor-memory` 与默认未知保留实验混用。
