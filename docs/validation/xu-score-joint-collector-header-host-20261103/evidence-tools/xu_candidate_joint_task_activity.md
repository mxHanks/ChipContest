# xu S2c 同窗口 SAIF 与 SRAM 联合活动采集器

`xu_candidate_joint_task_activity.py` 是独立的新入口，schema 为
`xu-s2c-isolated-joint-task-activity-v1`。它组合冻结 `5e75581` 的 S2c
clear/internal-reset/REQUEST→final-Y-response-RETIRE 观测与只读 C/VPI
联合记录器，不修改或重标旧 collector、原 SAIF、旧 alias/common 工具。
工具必须从本独立分支的干净已提交 checkout 执行；不能用持续合入其他
PPA profile 的主优化树代替。新 context 重新校验整个工具主树的所有
tracked blob/mode/gitlink，固定旧派生来源的 SHA。DUT 来源仍严格限定为
主仓 `d276b55ffecbe8d620f9a361bf5d0859299ba7b5` 与子仓
`49a9436e01ea8ceeead94242e4a99c16e31a0865`，全部主树/批准子树的
tracked 字节、mode、gitlink、活跃 RTL 与 dirty 状态依旧检查。

本入口强制提供实际 PT mapped inventory，并在运行机器重新读取其中
网表、库和声明的文件 provenance。仅接受已测 S2c mapped 网表 SHA
`9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892`；
同名 336 宏的 baseline 网表也不接受。要求 336 个指定 RAMSP1024X16、
22,512 个准确 pin/direction，与冻结 RTL 宏逐一双射；实际 mapped
instance 中的字面点号保留。仅允许原 SMIC SS 标准单元 DB 与原
1024×16 SS SRAM DB，均对实际字节验证 SHA。这是身份绑定，不是等价
证明。121 弧 ledger 逐字节绑定既有实际 SRAM library report；不将
未知 Q、standby Q 或未覆盖 D 条件当作零功耗。

inventory 必须保留实际 PT 的 raw TSV、Tcl、工具/版本/log 与运行前后
输入哈希。采集入口逐字节重验这些原件，检查 TSV/JSON 的全部宏、
pin/direction 集合一致，Tcl 唯一网表输入和两个 link library 与声明
一致，并要求 before/after 覆盖相同网表、SDC 和库。SDC 在这里仅作为
输入身份冻结；该 inventory 导出脚本没有进行时序分析，不能据此称
150MHz 已合格。网表、SDC、库或原始导出原件在导出后发生变化都会拒绝。

每项任务新进程，原始 12 层 fixture 先全部通过整数校验，再将该任务
逐字节映射为 layer_00。CPU 执行原 33,697 个 legacy-MMIO 零写，实际
W/X/bias 提交及内部 reset、FIFO 所有权保持原成熟观测。首个源读取
REQUEST 处，在同一 procedural event 紧邻 `$toggle_start` 调用 VPI
begin；最终 Y 写响应 RETIRE 紧邻 `$toggle_stop` 调用 VPI end。最后
Y 请求地址/周期、最终共享响应退休及全部 50,688 写回数共同检查。
1 fs 绝对 HF/LF 相位与原 signed16/40/48 数值检查不变。

VPI 注册真实宏的 A/CEN/CLK/D/EMA/EMAW/GWEN/Q/RET1N/WEN 端口，且
在 C 中检查真实 scope/name/width。它没有 DUT driver 或 force。
`task-joint.stats.jsonl` 保存 67 bit 直接 dwell/16 类四态转换与 34
稀疏联合投影；`task-joint.simultaneous.jsonl` 保留同时间控制与功耗
pin 回调、begin/end 状态和回调顺序。展开 audit 检查 121 个条件弧的
三态条件占时及条件前后 edge 计数，全部使用整数。新集成复核还连接
begin/end 直接状态与全部 pin 转换守恒，并要求 sparse sidecar 的
转换属于独立直接计数、边界事件顺序/状态一致。sidecar 不包含每个
普通单端口时间戳，不能从它重建完整 trace，回调顺序也不自动等同
VCS delta-cycle 或 PT 条件弧语义。

同窗口 raw SAIF 保持不可变；原 S2c normalizer 生成独立 normalized
SAIF，并逐 bit 比较其 T0/T1/TX/TZ 与 VPI 直接 dwell，完整保留 TC、
TB、IG 与 VPI 四态转换，不转换、不拟合、不抹掉差异。所有输入的
字节/类型/mode、工具/来源/编译器/header/include 依赖、生成物和
原始向量都入 freeze，在编译和各任务前后重验。可选
`--calibration-receipt` 只固定一份原始证据身份，不因存在该文件声称
VCS、SAIF、PT 或能耗已合格。

实际服务器运行模板：

```sh
python3 /path/to/clean-joint-tool/tools/ppa/xu_candidate_joint_task_activity.py \
  --tool-root /path/to/clean-joint-tool \
  --source-root /path/to/frozen-s2c-source --profile s2c-autogroup \
  --out /path/to/new-joint-task00 \
  --vendor-model /path/to/original/RAMSP1024X16.v \
  --netlist /path/to/exact-s2c/mapped.v \
  --mapped-inventory /path/to/actual-s2c-pt/inventory.json \
  --constraints /path/to/exact-analysis.sdc \
  --vcs /path/to/same-vcs/bin/vcs \
  --vpi-include /path/to/same-vcs/include --cc gcc \
  --cross-prefix /path/to/same-server-toolchain/bin/riscv64-unknown-elf- \
  --task-ids 0
```

先在新输出目录加 `--prepare-only` 完整检查/编译生成物，明确未仿真；
随后 task00 再开新目录。默认任务列表才是全部 12 项，子集只产生
`PARTIAL_*`。真实运行的 VPI header 必须属于所选 VCS 同一安装。
host prepare 的 Icarus header 只是显式记录的编译接口检查，不允许
拿它进行实际 VCS run。默认不定义 INITIALIZE_MEMORY。

VPI include 目录使用 `-isystem`，因为实际 VCS 头文件的第三方旧式
函数指针声明会触发 `-Wstrict-prototypes`。自身 C 代码仍使用全部
`-Wall -Wextra -Wshadow -Wstrict-prototypes -Werror`；不修改 vendor
头文件，也不关闭自身警告。依赖输出使用 `-MD`，仍包含并冻结实际
system header 及递归 include 的字节。旧入口/旧 micro23 原件保持不变。

本地复现，必须保持工具树已提交且干净：

```sh
XU_S2C_SOURCE_ROOT=/home/mxhanks/Projects/ChipContest-xu-s2c-autogroup \
XU_JOINT_COLLECTOR_TEST_EVIDENCE="$PWD/build/xu-joint-collector-tests" \
python3 -m unittest discover -s tests/host -p test_xu_candidate_joint_task_activity.py -v

XU_S2C_SOURCE_ROOT=/home/mxhanks/Projects/ChipContest-xu-s2c-autogroup \
XU_CANDIDATE_ACTIVITY_TEST_EVIDENCE="$PWD/build/xu-joint-frozen-wrapper-tests" \
python3 -m unittest discover -s tests/host -p test_xu_candidate_task_activity.py -v
```

新测试实际编译 RISC-V 固件和 C/VPI、materialize 真实任务7、以真实
回调记录审查边界与篡改、elaborate 336 注册/22,512 路径，及通过
真实 CLI 拒绝占位 inventory。它不伪造真实工艺库的 positive prepare。
冻结测试运行真实 S2c wrapper 的 99 行全部结果和 9 个数据/协议故障，
实际内部复位链及故障、source 隐藏改动拒绝。只有服务器原始输入齐全
时才能完成真正的 positive `--prepare-only` 和实际 VCS 收集。

所有完成状态均仅为活动收集或整数不变量检查；完整同配置等价、
150MHz 时序、标准单元注入/传播活动、未知与联合条件、实际 PT SRAM
功耗语义及全 SoC 单任务能量仍需独立验证。本工具不输出比赛得分或
合格能量。
