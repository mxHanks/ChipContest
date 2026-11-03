# xu SRAM 连续联合活动观察

这是独立、只读的 VPI producer，状态始终为 `NOT_QUALIFIED`。它不修改旧 baseline/candidate collector，不驱动 DUT，不改 raw/normalized SAIF，不计算能耗。实际 VCS callback/调度区、SAIF 四态事件定义、PT `state_condition` 来源和正式任务源/边界身份仍须分别验证。

`xu_sram_joint_vpi.c` 直接注册每个实际宏的10个端口：`A[9:0] CEN CLK D[15:0] EMA[2:0] EMAW[1:0] GWEN Q[15:0] RET1N WEN[15:0]`，共67 bit。注册时检查所有参数的实际端口名、宽度及同一精确 VPI scope。每个 vector port 使用 `cbValueChange`，读取回调携带的真实事件值，保持 0/1/X/Z；没有周期采样、`#0` 当作 NBA 完成或 force。

新 API：

```verilog
$xu_sram_joint_register("actual.macro.scope",actual.macro.scope.A,
  actual.macro.scope.CEN,actual.macro.scope.CLK,actual.macro.scope.D,
  actual.macro.scope.EMA,actual.macro.scope.EMAW,actual.macro.scope.GWEN,
  actual.macro.scope.Q,actual.macro.scope.RET1N,actual.macro.scope.WEN);
$xu_sram_joint_begin(global_task_id,"unique-output-prefix","source REQUEST transaction identity");
$xu_sram_joint_end(global_task_id,"final Y response RETIRE transaction identity");
```

注册在窗口外、全局 time precision 必须为1fs。一个新进程只允许一个开始/结束；文件用 exclusive create，已有输出不能覆盖。必须把 API 加入**新的独立 collector**，沿用同次 SAIF 的首个 source/parameter REQUEST 和最后 Y response RETIRE 边界，在上下文中冻结所有宏/向量/模型/工具/RTL/库/网表/SDC 与实际 mapped inventory。当前交付仅提供 API 和微基准，尚未把该上下文的存在当作已证明。

输出为两个独立 JSONL。`*.stats.jsonl` 的 schema 是 `xu-sram-joint-projections-v1`，用整数 fs 和整数计数保存全部直接 pin 四态 dwell、16种 previous→next 转移，以及34组稀疏联合投影：

- projection 0：`RET1N,CEN,GWEN,EMA[2],EMA[1],EMA[0],EMAW[1],EMAW[0]`，按该顺序每位2bit，0/1/X/Z编码0/1/2/3。
- projection 1：同一控制向量，额外将 CLK 放在bit16..17。
- projection 2..17：对应 D[i] 的 `{WEN[i],GWEN,D[i]}`；projection 18..33：对应 Q[i] 的 `{RET1N,GWEN,Q[i]}`，每项依次占低位2bit。

dwell key 为 `(projection_id<<40)|state`；transition key 为 `(projection_id<<40)|(previous_state<<20)|current_state`。只写非零项。数据/条件中任一部分变化时，先累计旧状态到当前时间，再保留状态变化，因此相同 timestamp 的零 dwell 事件仍存在。RET1N/CEN 联合驻留与 RET 条件转移可从 projection 0 精确恢复。为每个 CLK 事件只更新一个稀疏投影，离线再展开42条实际时钟弧，避免运行时逐边沿展开42次。

`*.simultaneous.jsonl` 包含初始/最终真实67bit状态，以及同 timestamp 控制与条件切换 pin 都变化时的初始完整 tuple 和每个 callback 的 port、previous/current 值及单调 ordinal。边界 timestamp 的事件也保留。普通单独边沿只进入聚合统计，不写无限增长的逐边沿 trace。**callback ordinal 是 VPI 观察顺序，不声称是实际 simulator delta-cycle index**；在与 VCS/PT 语义核对前，这些同时变化的能量条件保持有歧义。

`xu_sram_joint_audit.py` 只使用实际 PT `sram-library.rpt` 提取并 SHA 冻结的121条弧 ledger（2 leakage、119 internal），逐弧以四值逻辑展开 condition false/true/unknown dwell、条件下 pin 四态 dwell 和条件 previous/current × pin previous/current 转移。每个直接 pin 的 dwell/transition 必须被全部相关联合投影精确还原；每个投影/弧的 dwell 必须等于窗口 duration。`default` leakage 保留 fallback 标记，不当作另一个可独立相加的泄漏条件。只适用于该1024×16库；128×16等其他宏必须另提取库弧。

本机复现：

```sh
mkdir -p build/xu-joint-new
cc -std=c99 -D_POSIX_C_SOURCE=200809L -fPIC -Wall -Wextra -Wshadow \
  -Wstrict-prototypes -Werror -O2 -I/usr/include/iverilog -shared \
  tools/ppa/xu_joint_activity/xu_sram_joint_vpi.c \
  -o build/xu-joint-new/xu_sram_joint_vpi.vpi \
  -L/usr/lib/x86_64-linux-gnu -lvpi -lveriuser
iverilog -g2012 -s tb_xu_sram_joint_micro \
  -o build/xu-joint-new/micro.vvp tests/ppa/tb_xu_sram_joint_micro.sv
vvp -Mbuild/xu-joint-new -mxu_sram_joint_vpi build/xu-joint-new/micro.vvp \
  +OUT=build/xu-joint-new/micro-00 +MODE=0
python3 tools/ppa/xu_joint_activity/xu_sram_joint_audit.py \
  --stats build/xu-joint-new/micro-00.stats.jsonl \
  --sidecar build/xu-joint-new/micro-00.simultaneous.jsonl \
  --out build/xu-joint-new/micro-00.audit.json
XU_JOINT_TEST_EVIDENCE="$PWD/build/xu-joint-tests-new" \
  python3 -m unittest discover -s tests/host -p test_xu_sram_joint_activity.py -v
```

本机 `/usr/bin/iverilog-vpi` 脚本的安装 CFLAGS 硬含非法 `0-3` 参数；首次直接调用失败后改用上述明确 cc 命令，未修改系统脚本。服务器必须用实际 VCS `vpi_user.h` 及同一平台 ABI 重新编译，不能复制本机 binary。导出的 VCS 可加载注册入口为 `xu_sram_joint_register_tasks`；`vlog_startup_routines` 同时支持 Icarus。请先用新的独立 VCS micro 输出验证同 timestamp active/inactive/NBA 行为、scope/port 可见性和编译选项，保留实际命令、版本、全部源/目标 SHA 与原始日志，再考虑正式全宏采集。这里没有把尚未执行的 VCS 命令标为可复现通过。

本地9项测试通过：256个 known mode 恰为完整互斥分区；false 遮蔽 X/Z 但不能把 unknown 当 false；相同 timestamp 的3次 CLK变化及2次 Q NBA变化保留；边际相同而相关性不同的序列产生不同 joint；CEN=1 时 Q仍在实际 `RET1N & GWEN` 条件下保留未知；13种重签语义篡改、错误 pin role/precision、未完成窗口均拒绝；352个独立实例的70,400个实际 CLK边沿及每位 Q 的整个 true-condition未知驻留全部精确复核。352实例使用明确 open micro 模块，既不是指定 vendor SRAM，也不是 SoC/功耗/STA 验收。
