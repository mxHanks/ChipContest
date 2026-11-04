# xu 115 — mapped task00 的私有观察补齐与真实111失败

本说明只读分析现有源码和原始日志。没有操作服务器、修改111、重综合或将任何pending改成已完成。`reference-candidates115.json`列出72个原始引用、每项在原TB的行号、候选接口、宽度、来源SHA及实际mapped未观察状态。

## 先处理实际111的失败

实际114回传的111 `simulation.log` SHA为`c7d9933f20be539b11534ce9318f22dd9166747b0b096f169ff0c426514b3832`。唯一原生Fatal位于冻结生成TB第216行：`unknown_shared_handshake`，原生时间及finish时间均为`9359423333333 fs`。这早于原始first REQUEST `9359903333333 fs`，相差480ns；没有SOURCE_REQUEST、FINAL_Y_RETIRE、PUBLIC_COMPLETE或REQUIRED_GATE_PENDING marker。实际VCS退出码为0。原builder首先因`returncode!=0`假设抛错，遮住了原生失败原因；不能据此把111改判成功。

日志含25项真实库`$hold`违反：24项启动UART相关、1项`...u_sirv_gnrl_rsp_fifo.\dp_gt0.vec_31_dfflr .\qout_r_reg[0]`。最后一项CK和D都在`9359390050000 fs`变化，原生limit为10000fs；随后约33.283ns发生共享握手未知态拒绝。两者时间相近是调查线索，尚不是已证明的唯一因果。

115只读审计工具绑定8份原111正文SHA、生成TB SHA/具体216行/精确scope/原生Fatal及finish时间，实际重新哈希全部628个冻结输入与56项runtime树成员，审计前后再次核验。它记录失败、全部25项hold块的原字节offset/hash及60pending，不重跑VCS、不更改111。原件解析和21种语义/身份mutant检查在`local-audit115-v1`保存。

## 60项的确切含义

72是原始TB中三种层级宏后的唯一路径字符串数；其中12项ACCEL公开接口已有111的实际VPI观察，余60项为48 ACCEL、3 EXU、9 clock。它们不是60个相互独立的物理寄存器组。

| 来源类别 | 原引用数 | 最小候选观察方式 |
|---|---:|---|
| wrapper信号到现有LinearAutoGroupCore命名端口的直接别名 | 16 | 直接读取子模块真实端口；`bias_regs`展开8×40bit，`row_result`展开8×48bit |
| 已经是nested module端口 | 13 | 11项W/X/bias提交输入，加`core.io_group`及`peArray.io_enable` |
| hclkgen输入 | 9 | 原模块输入`test_mode/pllbypass/plloutdivby1/plloutdiv/pll_RESET/pll_ASLEEP/pll_OD/pll_M/pll_N` |
| EXU commit输入 | 2 | `u_e203_exu_commit.alu_cmt_i_valid/alu_cmt_i_pc` |
| gp候选现有DFF子模块输出 | 1 | 只需原`rf_r[3]`：尝试`u_e203_exu_regfile.regfile[3].rfno0.rf_dffl.qout`32bit |
| wrapper/core内部state | 17 | 真实mapped local net或对应库FF Q/未改变的现有子模块输出；需实际身份/极性/位序核对 |
| wrapper组合表达式 | 2 | 首选真实mapped `busy`/`row_start_accept`；若消除，可从真实底层信号执行逐字同义组合表达式并证明连接 |

16项别名具体是`bias_regs/cache_addr_reg/cache_enable/compute_start/core_done/core_start/row_active/row_count/row_group/row_pop/row_produced/row_result/row_retired/row_running/row_start/row_valid`。例如`row_active`就是`u_linear_compute_core.io_rowActive`，`core_start`是`io_start`，`core_done`是`io_done`。不要通过预测MMIO事务创建“影子DUT状态”。

17项内部state为`bias_index_reg/manual_busy/stream_cursor/stream_error/stream_is_w/stream_pair/stream_pending/stream_second/w_addr_reg/w_bank_reg/w_cursor/w_load_wen/x_addr_reg/x_cursor/x_load_wen`和`u_linear_compute_core.head/tail`。原FIFO head与retired最低位、tail与produced最低位在这份源FSM中有同复位及同脉冲递推关系，可作为候选等价端点；需以实际mapped连接或一个独立的、绑定原源码的状态等价证明确认，不能直接按本说明替换。

原始cfg未打开`E203_CFG_REGFILE_LATCH_BASED`，所以gp有DFF输出候选。仍需核对真实mapped hierarchy。若该子模块已消除，可读取实际RF写回端口形成只读gp scoreboard，但必须从最后一次确实写入x3=1及其后无x3改写、真实commit-PC终止事件证明；该方案替代原直接rf_r[3]读取时要单独登记证明，不可把HOST ACK直接当gp成功。

重要范围澄清：原始clear检查采样的是11项`io_wLoad* / io_xLoad* / io_cacheWrite*`在真实采样边沿的提交输入、legacy bias的8×40bit现有core输入、以及FIFO/stream ownership状态。它没有遍历读取全部X/bias缓存FF或全部SRAM存储单元。因此恢复原验证语义不要求新增debug端口，也不要求逆向所有缓存FF。接口提交、实体RTL连接、own-netlist FM及实际vendor宏行为是不同证据，仍应全部绑定。

源码分析使用S2c main `d276b55ffecbe8d620f9a361bf5d0859299ba7b5` / child `49a9436e01ea8ceeead94242e4a99c16e31a0865`。本机wrapper SHA `1a088c873c5e5de84ca92fdc74d693a326e430cc6191128979f573fe4e64ad45`、LinearAutoGroupCore SHA `fd853fc7be0949eabf9aa56885850115ab4b68b9a654f5a7abcd436e1baa613c`与实际S2c prepared清单对应项一致。这里没有mapped正文，不能据源码端口列表宣称它们在mapped VPI已可见。

## 最小可实施补齐顺序

1. 先运行115只读失败审计，保持111原始失败。117对同binary及VCS执行原生`-help`，保存完整原始help及timing相关相邻行；不从记忆猜测或自动启用任何timing选项。
2. 117在独立目录用相同网表、原模型、原生成TB、原adapter和原编译选项，仅追加一个只读VPI库及改变输出路径。观测原报错FF的所有native local net/reg（含notifier如可见）、其FIFO父层local net/reg、共享端口及ACCEL clock/reset，记录`9359300000000..9359500000000 fs`的四态aval/bval、通知serial和原生时间。查是否存在notifier→FF Q→FIFO occupancy/ready→共享握手X的实际链；如果没找到则明确未证实，不删checker。
3. 在一个新编号的、无时钟/无写入的metadata探测中同时盘点上表60项候选。使用VPI真实module/port/net/bit句柄和canonical escaped名称，要求恰好对应模块与位宽、所有数组lane齐全。不同原引用可能合法指向同一实际端口（如cache_addr_reg与io_cacheWriteAddr），须登记已证明别名组，不能用通用“所有句柄必须不同”误拒。
4. 端点可用后，将原TB的clear、physical commit、stream顺序、FIFO conservation/owned result、EXU终止和clock静态约束逐项移植到独立adapter。采样相位须与原posedge pre-NBA语义对应；不能悄悄改成post-NBA。保留原72引用到实际端点逐项manifest、原反例拒绝能力、原完整计数/边界/golden。新task00运行全部通过之前，60pending的总gate保持失败。
5. 如果117证明是库原生same-edge timing/notifier引入X，先保持真实失败证据与STA缺口。可以在原生帮助确认具体功能模式选项后做**另一个独立功能诊断**（或原库单FF微探针），但禁用timing/notifier后的仿真只能补充数字功能排查，绝不代表150MHz闭合。实际timing检查仍需同库同网表STA及既有完整约束覆盖，必要时修真实网表后重新own-FM/面积/能量。
6. 只有完整task00可运行并恢复原观察，才扩至同配置12任务、真实任务窗口mapped活动与全SoC能量。门级零SDF仿真不替代完整150MHz STA；SRAM黑盒FM不替代宏行为/PVT；file/default/propagated活动来源、未知Q及下游标准单元功耗仍须分别核验。不要添加赛题未要求的无依据签核门槛，也不要把现有明确未解决项隐藏。

## 交付及运行

115上传：`xu_audit_mapped111_failure115.py`和`launch_mapped_audit115.py`，命令`python3 "$HOME/Desktop/launch_mapped_audit115.py"`。输出为新`mapped-task00-readonly-audit-20261105-115`。

117上传：`xu_mapped_causal117.py`、`xu_mapped_causal117.c`和`launch_mapped_causal117.py`，命令`python3 "$HOME/Desktop/launch_mapped_causal117.py"`。输出为新`mapped-causal-native-20261105-117`。两个launcher均detached；观测超时不允许重启现有任务。117 C没有put/force/control调用。`local-callback117-v1`只证明真实Icarus回调机制能保留synthetic notifier/Q/handshake X，以及缺失目标明确失败，不是mapped/vendor因果证明。
