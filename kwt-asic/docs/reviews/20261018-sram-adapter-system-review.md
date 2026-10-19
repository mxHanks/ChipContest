# SRAM Adapter 系统入口独立审查（2026-10-18）

结论：**PASS，限开发逻辑 Adapter 的源计划、原语前置再验和所测 core/ICB 功能**。未发现阻断本次有限结论的问题。官方材料仍缺失，官方功能验证为 NOT_RUN、官方 PPA 为 BLOCKED；本审查不接受 CPU SoC、指定宏、正式精度、时序、面积或功耗结论。

审查仅阅读源码、原生日志和持久记录，重新计算文件 SHA256/长度与 canonical source_id，并调用只读的前置报告/日志解析器；没有启动 HDL、EDA 或主机测试，没有修改生产源、旧记录或失败证据。唯一新增文件为本报告。执行终态由主代理确认后才审查，不以 RUNNING 文件或另一 PID namespace 的 PID 推定任务终止。

审查对象为 `scripts/verify/run_sram_adapter_system.py`、`scripts/verify/sram_adapter_plan.py`、`sim/tb_kwt_icb_backend3_checked.sv`、两个 `test_sram_adapter_*.py` 和 `tests/fixtures/sram-core-format.log`，并沿用实际被调用的原语、core 完成检查器和保留的 ICB TB。测试中的 inert 文件与格式日志明确仅验证 reader/规划器，不计入真实硬件结果。

| 证据 | 独立核对结果 |
|---|---|
| 父资格化 `artifacts/diagnostics/20261018-adapter-system/final-v1/result.json` | PASS；4 个 CLI，另 make test / make verify；父报告 SHA256 `fbed03daf0cfce3464ae0b40d0f446060943a53cf58ebf0add007c2884d57c79` |
| 完整子 `artifacts/runs/20261018T054213.004858Z-adapter-system-1b958078/result.json` | PASS；9 条真实 native 命令、3 个 binary、229 个 runtime 输入记录；SHA256 `48f15b175f4d969308fae1f0831b788015c38ad4e3ee1a521304a498386316e0` |
| 完整子 source_id | `23e35a122aeb77caed4fbccf667221de96e9258a8215d514e1794596a6a55a56`；saved identity 与报告一致，canonical digest 重算一致 |
| 原语前置 `20261018T051921.108279Z-official-contract-afdf0cfe/result.json` | SHA256 `9505814c6f68aaf4eecabeb88f83086cc56c4fd56d20be0a2039801d3d8aa3da`；8 正常、15 预期拒绝、33 native 命令、8 binary 均重新读取并验证 |
| 前置 source_id | `44c33f110232b2eb1f2141bfa384f6a1d1da2f767852f4413c74167906d5ca68`；与当前 producer、RTL/TB、Adapter 和工具身份一致 |
| 主机检查 | 原始 host.log 有 `Ran 262 tests` 和 `OK`，native exit0；verify.log 为静态 reference integrity PASS、exit0，不提升为官方功能结果 |

四条真实 CLI 的状态和完整结束标记分别对应：默认空官方清单 exit2/BLOCKED、显式开发 Adapter 缺原语前置 exit2/BLOCKED、前置报告 status 被改为 FAIL 后 exit1/FAIL、显式开发 Adapter 加完整前置 exit0/PASS。前三个子报告的 commands/cases 均为空；默认缺包没有执行 HDL，也没有启动工具版本探测。

前置门槛位于所有 build/simulation 之前。helper 重新生成并逐项比较当前 plan，核对 supplied/development scope、BACKEND=3、初始与完整 source identity、mandatory producer/RTL/TB/tool/Adapter SHA；逐一重建 33 条准确 argv/cwd、校验 log/state 路径与字节，并将 saved state 和报告命令逐字段比较。8 正常和 15 拒绝案例均重新解析，正常案例另要求唯一原生 TB `$finish`。因此缺报告、仅有 PASS 字符串、不同源计划或 BACKEND=0 命令不能满足当前入口。实际被选源是显式开发 fixture，未静默回退到 behavioral/FF 后端。

core 的两次运行保留原逐输出 Golden、顺序、last、读写守恒、随机装载气泡、背压稳定、buffer 耗尽、非法装载和三处中断复位检查。原始日志分别有准确数量的任务标记、唯一 suite 标记和原生 `$finish`；exit0、无 timeout/interruption，重新解析的 coverage 与报告逐项相同。

| 场景 | 实测结果与口径 |
|---|---|
| real12 | 12 任务、304128 输出；固定真实权重及对应层静音 smoke 输入，Verilator **两态**；3 个 reset_interrupts，115186 个 stall/stable 检查 |
| signed41-range | 2 任务、50688 输出；Icarus **四态**；3 个 reset_interrupts，19206 个 stall/stable 检查；原生运行 35.523 秒、exit0 |
| core 合计 | 14 任务、354816 输出；不是 14 个官方性能任务，也不是全数据集/官方600精度验证 |

48 份 real 运行输入/期望存储镜像与原 SHA 绑定 export 逐字节一致；8 份 range 镜像的 word 数和每个值按独立整数端点公式核对一致。所有 binary、复制向量、原 provenance、范围 manifest、源码和工具记录均重算 SHA/长度。编译命令固定 RESULT_BUFFERS=2、PIPE_MUL=1、SRAM_BACKEND=3；真实12层使用 Verilator，范围与 ICB 使用 Icarus。Verilator build 保留 84 条 WIDTHEXPAND/WIDTHTRUNC/UNSIGNED 警告，未报告 UNOPTFLAT 或阻断错误；ICB build 的7行 constant-select 提示说明 sensitivity 包含全部位，不是编译失败。该结果不宣称无警告。

ICB 原始日志同时具有保留 TB 的完成行与新 monitor 的完成行、唯一 `$finish`，原生运行 47.667 秒、exit0。独立 monitor 在真实 posedge 统计 `engine_y_valid && engine_y_ready`、command 和 response 握手，检查 X/Z 控制/有效载荷以及背压稳定；总账不被软件 abort 或外部 reset 清零。实际 25348 个 core 输出等于 abort 前4个加完整任务25344个，原 TB transactions=193938，新 monitor accepted_responses=193938、accepted_commands=193939、response_holds=86、reset_discarded_responses=1。86 精确对应19×2+4×(3+5)+9+7；最后额外接受的 ID 命令有 pending 响应被外部 reset 丢弃，解释 command-response 差1。最终 reset 后空状态、无 pending 响应和 output_count=0 也参与完成检查。

ICB 所测算术为零 X/W 加有符号 bias，CPU 与外部共享存储写回均 NOT_RUN；其局部窗口不能当比赛完整窗口。real12 两态结果不能推广为全网四态，范围/ICB 的四态结果也只是所测场景。源计划中的固定 fixture path/sentinel 检查与 external-consumption 词法拒绝仅为保守支持门槛，不证明官方来源真实性或完整 HDL 安全；当前源码与报告均保留这一边界。

补充实际 checker 敏感度探针 `artifacts/diagnostics/20261018-adapter-system/monitor-probes-v1/result.json` 为 PASS，SHA256 `ac919b0fa9b421a11c0a71aa8647264f3fc2f16e90da62b655e7f5b4d19f834f`、source_id `0aab32eb12ed3a82e79e2ed095de755b0bbc69493b4893a707b0ff86bf158224`。独立检查了该探针的57个唯一受记录文件、canonical identity、binary、compile/vvp argv 和全部 native state：Icarus compile exit0，两次 vvp 均真实 exit1，无 timeout/interruption，无正常完成标记。`tb_icb_backend3_monitor_fault` 实例化的是新的 checked top；它只在独立探针编译集合内，不在上述正例主入口的任何编译命令中。

探针1等到真实响应有效后 force `rsp_rdata` 为 X，在65ns首先触发 `tb_kwt_icb_backend3_checked.sv:71` 的 `ICB_BACKEND3_MONITOR_UNKNOWN_RESPONSE_PAYLOAD`，随后该新 monitor 的 final 总账再触发 INCOMPLETE；原始日志两条 FATAL 均来自新 monitor，没有保留 TB 的无关 FATAL。探针2在50ns主动提前 `$finish`，新 monitor 的 final 在自身116行触发 INCOMPLETE，accepted command/response/output 均为0。故这两次实际拒绝分别证明新监视器能拒绝未知有效响应和提前结束，并非借旧 TB 的其他失败冒充；它们只资格化这两条检测路径，不证明所有监视器错误路径。

父/四子/原语证据图内472个唯一受记录文件及48个唯一 native state 均复核一致；加入上述探针后为481个唯一受记录文件、51个唯一 native state。所有 state 均 EXITED、exit_code 为显式整数，timeout/interruption 均为 false。与旧 `docs/runs/sram-update-reset-20261018.json` 的1096个唯一 verified_records 合并后共1337个唯一文件，SHA/长度全部匹配，无冲突。旧索引文件自身 SHA256 为 `dbabc85b25c1ee0b463f62b7382beaa027f3e023edba0fd8b7e6bd0204bfa64a`、297389 bytes；与 `artifacts/checkpoints/20261018T053233Z-31d0cf-sram-update-reset-validated/` 中副本逐字节一致，并符合该 checkpoint manifest 中的 SHA/长度。本审查未修改该文件或其1096个记录文件。本次校验有界于这些已列证据，没有全库重新哈希。

当前可接受的是新增入口在显式开发 Adapter 下的有限功能闭环，以及缺材料/缺前置时拒绝执行的真实路径。真实 supplied 官方 Adapter 尚未测试；指定库/宏、电气边界、正式150MHz、面积、功耗和官方 E203 完整装载写回窗口仍待材料与对应验证。
