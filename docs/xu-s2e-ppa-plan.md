# xu S2e 独立面积、映射一致性与时序实验

S2e服务器同工具完整VCS终态已经归档：main `5bf123bfead8f2a37f97f3234d4e40ce8201aae9`、child `a0767db69628ef30e53de2d1e93dd0360c0ccf76`，paired12层10,420,140周期，同一物理RTL旧调度11,842,200周期。开发窗口下降12.0084106%；该周期不替代任务前清空的nominal150MHz全SoC能耗窗口。

本工具树 `codex/xu-s2e-ppa` 从root `eb5963761c0efb7fa5eb86b9de5f87248e6d9a5b` 独立创建，不改上述硬件/固件源码。新增明确的 `s2e-paired-hi` profile，旧 `s2c-autogroup` pin保留。相对固定f49 child基线，S2e仅允许 `LinearAutoGroupCore.sv`、`accel_icb_slave.v` 两个文件delta；同时核对全部child原始Git blob/mode、实际SHA、固定平台文件、未跟踪RTL，及S2e main全部1331个tracked条目/mode/gitlink/实际SHA。原来的source guards不放松。

本阶段仍没有Chisel改动。S2e生产硬件变更是手写wrapper的paired-HI传输，既有8PE、FIFO、SRAM及计算SV保持，因此不能沿用S2c旧面积或旧Formality结论。

执行顺序：

1. 核对服务器原始终态和raw_files全部SHA，要求64项host中的mandatory direct VCS、五个旧平台VCS配置、synthetic1/2、paired与control各完整real12及192旧配置load image gate。两次必须同main/child、RTL、VCS binary、GCC10.2、向量和固件优化参数。
2. 用独立profile生成真实全数字SoC映射：原S2c top、SRAM adapters、原标准单元及RAM1024库、原6.666666667ns HF约束。固定ITCM64KiB、DTCM64KiB、shared512KiB、accelerator W32KiB，四组共336个RAMSP1024X16；无SRAM128、无额外PE宏、无vendor模型进入综合。
3. 运行同DC2022.03-SP5-5 `compile_ultra -no_autoungroup`，保留真实hierarchical area/references/units/qor、mapped.v/mapped.sdc及该次自己的default.svf。加速器面积按原库单位换算mm²，比较2.25mm²上限；全SoC面积另列。
4. 在PT之前，用本次prepared全部RTL、两份实际库、本次default.svf及mapped.v，运行同Formality2020.09-SP5全SoC `match`、`verify`，收取完整匹配点/blackbox/unread/unmatched报告。冻结上述每个输入前后SHA，不以旧S2c证明替代。
5. 独立运行同PT2022.03-SP5-1原始完整时序收集，保持原propagated/pre-CTS分析以及setup/hold、recovery/removal、gating、pulse-width、untested/no_clock和原工具命令失败。错误或未测试范围原样保留，不自动添加false path或豁免。完整150MHz资格仍需要逐项审查，EDA调用成功不等于时序收敛。
6. 独立测S2e正式任务前清空/第一源请求至最后Y响应退休的全SoC活动，再测该次own mapped网表功耗与能量；此前wrapper或S2c能量不登记成S2e评分。保留Pareto候选，资格不足时不宣布最终保留。

固定库：

| 输入 | SHA256 |
|---|---|
| standard cell SS0.99V125℃ | `f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723` |
| RAMSP1024X16 SS0.99V125℃ | `c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f` |
| 原S2c完整SDC | `404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98` |

`xu_s2e_ppa_server.py` 还逐字节固定top/shared/SRAM adapters，记录真实DC/PT/FM executable SHA，核对原版本；LC_ROOT固定2022.03-SP5，避免实际库读取PT-063。FM独立先执行，PT失败仍保留已经得到的DC面积和FM原件，状态仍是NOT_QUALIFIED。

服务器复现（工具树与输出必须独立；默认命令后台启动并打印真实PID）：

```bash
B="$HOME/Desktop/xu-score-optimization-20261102"
python3 "$B/ChipContest-s2e-ppa-tools-89/tools/ppa/xu_s2e_ppa_server.py" \
  --source "$B/ChipContest-s2e-74" \
  --acceptance "$B/s2e-full-vcs-accept-20261104-74" \
  --out "$B/s2e-ppa-campaign-20261104-89"
```

程序只运行本地服务器EDA，不包含FTP/VNC、凭据读取、网络下载或自动修改候选源码。全SoCFM的SRAM blackbox边界以及原始时序unknown/violations必须在收取原始报告后解释，不能由本工具的单测或生成的脚本宣称通过。
