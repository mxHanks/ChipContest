# 剩余8项的路径、RTL与修复边界

本报告基于已返回的原生PT路径及当前持久化hold映射，不是一次新PT运行。复现脚本 `replay_remaining.py` 实际返回1：329284 total、299941 met、8 violated、29335 untested。8条完整路径及报告SHA保存在 `baseline-replay.json`；7个叶端点由映射层次实际追踪到相应库单元与本地网，见 `target-bindings.json`。

## AON两项hold

共同前缀 `u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper`，端点为 `bootrom_deglitch/T_8_reg/D` 与 `dwakeup_deglitch/T_8_reg/D`，均为DQV0。

`sirv_aon_wrapper.v` 将两个低有效外部输入反相后直接接到 `sirv_DeglitchShiftRegister`；该模块 T_8→T_9→sync→last 每个LF上升沿移位，输出sync & last。reset端口在该always中不使用，wrapper将其系为1。这是实际异步输入的第一级采样，不能因后续已有移位同步链而忽略T_8自身的时序。

原生min输入延迟0，单级CLKINV0延迟0.06306268ns。含0.1ns uncertainty及0.02972782ns library hold后，要求0.12972783ns，slack −0.06666514ns。欲达到候选+0.03ns min余量，至少须增加0.09666514ns min路径延迟；这不是已表征的buffer数量。两条setup在原完整coverage中均为unknown。

本地非反相I→Z缓冲在结构上不改变移位级数；但它增加max路径延迟。没有完整、数值化的HF→LF max检查时，不能接受此延迟ECO。给第一级再加同步寄存器仍会留下新的首级外部采样检查，不能据此证明原SDC闭合。

## PMU两项removal

端点 `u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/SDN`（DSNQV0）及 `erst_reset_r_r_reg/SDN`（DSNQNV0）。`sirv_pmu.v:330` 的两个寄存器同时由ERST异步置1；LF沿到来后第一级清0、第二级取前一级。第二级的异步置位是可观察复位原因捕获行为的一部分。

外部低有效ERST经wrapper/U4和PMU/U3两次反相，SDN释放到达0.12784207ns。两种库单元removal要求分别为0.24932489、0.24632174ns，slack −0.12148283、−0.11847966ns。到+0.03余量分别需至少增加0.15148283、0.14847966ns min路径延迟。两项recovery在原coverage仍为unknown。候选只允许分别缓冲精确SDN叶负载，不改置位极性或级间D逻辑。

## AON reset-catch三项removal

端点 `aonrst_catch/reset_n_catch_reg/reg_{0,1,2}/q_reg/RDN`，均DRNQV0。`sirv_ResetCatchAndSync.v` 使用三位AsyncResetRegVec，复位异步断言，随后串移1以同步释放；test_mode仍直接旁路reset。ERST、看门狗与POR合并后经NAND2BV0与各级CLKINV0到RDN，释放到达0.12101069ns，要求0.16111633ns，三项均 −0.04010564ns。目标+0.03余量需至少增加0.07010564ns min路径延迟。

三项是默认优先候选；这表示对象范围优先，不表示已经安全或通过。它们可能具有LF看门狗来源的数值recovery路径；该路径不能代替精确外部ERST→RDN的HF→LF max上下文。新脚本额外查询精确source port→leaf pin，任何缺失都以UNKNOWN或失败保留。全局HF/LF仍未展开时，edit直接拒绝。

## GPIO A27

`e203_subsys_main.v:359`：`inspect_mode ? inspect_core_clk : gpioA_o_oval[27]`。映射是AO22V12 U64，`.A1(inspect_mode), .A2(inspect_core_clk), .B1(n281), .B2(gpioA_o_oval[27])`。

原完整路径从GFCM `u_clk1_clkgate/enb_reg` 启动，经过已存在的两颗hold buffer、U2、U3、U5、U4、U8、U64再到输出。U8增量6.09815788ns，U64增量1.48118687ns；arrival11.32698250，对比required6.06643915，slack −5.26054335ns。IO max仍为0.5ns。

主会话现有静态时钟树计划已经包括 `g0012`：owner `u_soc/u_e203_subsys_top/u_e203_subsys_main`，唯一load `U64/A2`，local网inspect_core_clk，alias hfclk/inspect_core_clk/shared_mem_clk，新cell名 `XU_ECO_clock_g0012`。因此本任务没有再准备相互覆盖的时钟分支修改。`rg_gpio` 保留原IO约束，并输出整合前后min/max的真实slew/cap/full-clock-expanded路径。

## HF/LF展开的精确算术证据及限制

原PT的PTE-052日志明确说最小周期最多展开1000次、最大周期最多101次；原check_timing列出HF、LF、JTAG及PLL envelope为同一failed set。原4个max-unconstrained叶端点正是上文两D及两SDN。

`edge_witness.py` 用原SDC SHA `c15ede0fc2c65771f87e2d6aee763b4ea0d53934868ca807b4785c36182fce7c` 的精确十进制有理数计算，不改约束：HF6.666666667、LF30517.578125ns。第11个LF沿为335693.359375ns；其前一个HF沿编号50354，时刻335693.333350118ns；间隔只有0.026024882ns。仅减去外部max0.5ns与uncertainty0.1ns，传播延迟与library setup均暂设0，算术上界为−0.573975118ns。

这是需要原生核实的具体边沿见证，不是实际setup slack，也没有假设库setup一定为正。PT内部period量化、展开、所选边沿及真实库check须在原生报告核对。增加展开量可能把原unknown变成新的真实失败，不能将“LF周期很长”作为余量证明。原SDC精确十进制比值也不保证小范围内存在完整共同基周期；候选不会通过猜测变量、忽略PTE-052、修改频率/相位/IO或加例外绕过这一点。

## 17条复位电气分布网

复用已有electrical-topology.json，只提取17条已标识异步复位网，未重做完整网表/死锥普查。16条属于加速器复位分布：U27=195个直接sink（194个经单输入单元可达异步sink），U25及U201/U213…U224共14条各68sink，U212=56sink；另CPU CSR U47=275个RDN sink，原transition1.35672736ns对比1.35000002ns。

这些原始高扇出网均不在AON wrapper之下，与7个目标叶端点不是同一局部网。`reset-electrical-summary.json`保留源SHA和原映射SHA，并显式标记未在post-hold/最新整合种子重测。主工作树同期已有针对128组reset分布的只读诊断工具，本补丁使用独立名称并不改它们。

## 验证边界

本机没有pt_shell/dc_shell。已配置访问只暴露FTP和共享VNC，不提供独立远程命令通道。没有连接、接管、粘贴或发送按键到共享VNC，没有发送其他聊天消息，没有运行或停止远端作业。

本地真实证据：8项失败重放、7端点映射层次/单元/引脚绑定、已返回原生receipt及文件SHA核对、Python编译/Tcl完整性/bash语法、独立封包字节一致、git apply --check。6个Tcl控制流测试使用明确标注的合成PT primitives；它们验证拒绝条件及导出门禁，不验证原生API、库延迟、物理reset pulse或ECO等价性。真实报告审查验证329284检查及1973电气项能完整解析，并拒绝新增时序/电气违例或新增未测原因。

没有新的native execution receipt、没有新mapped.v、没有新setup/hold/recovery/removal通过值，也没有新的吞吐结果。最终全量STA、SVF链上的RTL→mapped等价性、reset pulse/CDC/物理验证均由主会话在最新整合候选上完成。
