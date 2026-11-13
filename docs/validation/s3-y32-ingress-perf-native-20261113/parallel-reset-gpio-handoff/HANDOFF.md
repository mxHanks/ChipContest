# 并行 reset/AON/GPIO 交接 — 2026-11-13

**交付状态：根因诊断、独立补丁、原生运行入口及本地预检已完成；新原生ECO尚未执行，没有可宣称通过的修复网表。** 原种子的HF/LF waveform expansion尚未解决，候选会在第一个buffer前拒绝这一状态。主会话先读取 `ANALYSIS.md` 的边沿见证和下面的阻塞，不要直接把新增delay当作剩余7项已解决。

工作区边界：本轮所有写入只在 `/home/mxhanks/Projects/ChipContest/build/parallel-reset-gpio-20261113/`。原候选工作树、子模块、已有脚本/证据、进程和共享VNC均未修改；未发消息给其他聊天。对主工作树执行过只读 `git apply --check`，没有实际apply/checkout/reset/stash/commit。

## 最需要主会话处理的三点

1. **AON两D、PMU两SDN的max仍unknown，增加展开可能暴露新的失败。** 原SDC精确周期下，第11个LF沿只晚于前一HF沿0.026024882ns。仅外部max0.5ns和uncertainty0.1ns，已给出传播/setup均为0时−0.573975118ns的算术见证。见 `edge-witness.json`；它不是新PT slack，必须由原生period量化、展开及真实库check核实。原生discover入口不猜控制变量，也不改SDC。
2. **三条reset-catch RDN可独立准备局部缓冲，但也须检查精确ERST→RDN的外部HF上下文。** LF看门狗来源的数值recovery不能代替它。候选同时查询全clock上下文和exact source port→leaf pin；无数值或margin不足就拒绝。
3. **GPIO A27属于当前时钟树工作。** 已核对主会话clock-tree-targets的 `g0012` 正好选择 `u_soc/u_e203_subsys_top/u_e203_subsys_main/U64/A2`，新cell `XU_ECO_clock_g0012`。A27是inspect_core_clk的可观察输出，原U8延迟6.09815788ns、U64延迟1.48118687ns；维持原0.5ns IO要求，在该树持久化后重测。未另改该分支。

## 原始失败与候选对象

W=`u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper`。`baseline-replay.json`保留8条原始完整路径和输入SHA；`target-bindings.json`逐级追踪了7个实际叶端点/单元/本地网。

|精确对象（除A27外相对W）|原生slack ns|根因/候选|
|---|---:|---|
|bootrom_deglitch/T_8_reg/D|−0.06666514|外部反相后直接进LF首级；本地D缓冲候选，setup unknown|
|dwakeup_deglitch/T_8_reg/D|−0.06666514|同上|
|u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/SDN|−0.12148283|ERST双级异步置位捕获器；局部SDN缓冲候选，recovery unknown|
|u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/SDN|−0.11847966|同上；保留第二级异步捕获行为|
|aonrst_catch/reset_n_catch_reg/reg_0/q_reg/RDN|−0.04010564|ERST/WDOG/POR复位catch；局部RDN缓冲候选|
|aonrst_catch/reset_n_catch_reg/reg_1/q_reg/RDN|−0.04010564|同上|
|aonrst_catch/reset_n_catch_reg/reg_2/q_reg/RDN|−0.04010564|同上|
|io_pads_gpioA_o_oval[27]|−5.26054335|inspect_core_clk经U8、U64到pad；与主会话g0012整合验证|

17条已有reset电气分布网已按原有分析提取到 `reset-electrical-summary.json`，均在加速器或CPU CSR，不是上述AON本地网。未重复51条普通信号工作，也未重做全死锥/吞吐基线。原17网尚未在最新seed重测。

## 可用产物与验证事实

- `reset-gpio-candidate.patch`：仅新增4个独立命名文件，`git apply --check`已通过；不覆盖主会话同期新增的通用reset只读诊断工具。
- `src/`：12文件密封包，包含原生PT edit→write_changes dctcl→DC回放/新SVF→fresh PT reload；原SDC/工艺库/353宏口径不改，没有RTL行为补丁。
- `run-native.sh`：无传输或VNC代码的新目录运行器，先discover/diagnose，再有条件pipeline。完整命令和最新seed覆盖方式见 `README-native.md`。
- `local-preflight.json`：Python编译、Tcl完整性、bash语法、helper冻结字节、返回receipt/SHA、7端点绑定通过；字段明确为 `native_executed:false`。
- `guard-results.json`：6个明确标注合成PT primitives的控制流用例通过：未展开时钟、缺max、外部上下文缺max、最后端点max负值、插入后max丢失均拒绝；只有模拟合格情形导出。它们不是原生API/STA证明。
- `report-review-results.json`：真实329284 coverage检查和1973电气违例完整解析；新增时序违例、未测原因或电气检查的负例被拒绝。
- `patch-preflight.json`：只读补丁检查rc0；封包器独立重建所得manifest逐字节一致。

真实基线复现命令（实际exit1，预期失败）：

```bash
python3 -B replay_remaining.py --out baseline-replay.json
```

结果始终按原证据口径保留：329284 total / 299941 met / 8 violated / 29335 untested。尚无新的setup/hold/recovery/removal数值结果。

## 原生执行入口与接受条件

本机没有pt_shell/dc_shell；现有远端配置仅有FTP及共享VNC，没有独立命令通道。共享VNC正在主会话使用，本轮没有连接或控制它。原生seed的mapped.ddc及mapped.sdc也未在本地返回子集中；不得伪造补齐。主会话在其可用原生通道将包放到一个新的reset-gpio目录后执行：

```bash
bash run-native.sh discover
bash run-native.sh diagnose
```

默认seed为远端 `/tmp/codex-ingress1064-eco-hold-20261113-r5/{apply,reload}`。在最新已完成clock/electrical/prune seed上使用时，按 `README-native.md` 同时指定 `RG_SEED_APPLY`、`RG_SEED_RELOAD`、`RG_SEED_MAPPED_SHA256`。runner核对原基线、同库apply→fresh reload链及精确SHA，不自动替换失败作业。原始hold种子之外的目录不能被当成已经通过的时钟树。

原生发现并解决展开限制后，可用 `bash run-native.sh pipeline` 串行验证；默认只选择reset_catch三个RDN。每端点最多8颗BUFV2、全轮最多56颗、原库面积预算100，目标min/max余量各+0.03ns。全量检查计数必须逐类型保持，任何新增时序/untested、电气新增或恶化超过1e-5都会拒绝。只在原生数值验证后才产生可回放候选；已知旧种子未展开，预期拒绝，不是待通过乐观结果。

原生通过后还须返回新mapped.v及function-proof/receipt/TSV，在本地对**实际最新seed→新map**运行 `README-native.md` 给出的buffer-contraction命令。保留原综合和历次seed的SVF顺序，再追加本轮eco.svf。主会话最终在整合候选上串行运行全量STA、RTL→mapped FM及所需复位/物理验证。原1064.350640 task/s仍只是1691172 cycles按150MHz换算的条件结果。

## 身份

- 持久化hold种子 mapped.v SHA256：`1e0ca5d1281ff3e296204c75abbf07fa7732628523feab8b1be6289cb7cfc048`。
- 原始DC map SHA256：`882b160f2dfde6a9593f63212ae173fc96bb00b6212c56d304a6e6e80ae4e56e`。
- 原SDC SHA256：`c15ede0fc2c65771f87e2d6aee763b4ea0d53934868ca807b4785c36182fce7c`。
- 密封脚本、补丁及归档最终SHA见 `DELIVERY.json`，其中不含任何新的原生通过声明。
