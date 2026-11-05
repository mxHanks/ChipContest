# xu actual123：真实连接切片及117因果范围复核

实际123终态为`EXTRACTED_FROZEN_MAPPED_CONNECTIVITY123_NOT_QUALIFIED`，五份所选输入前后完整identity相同，原state没有error，原返回结果589,099字节、SHA `174a38d8719b2b49237cf200072ec04fe80fcc8dbb3b2512150fe780acc65f73`。129导出时PID132032已不存在。**123补齐了目标FF Q与FIFO.o_vld的直接连接，但没有证明目标notifier导致最终shared握手X。其返回的全部最短潜在路径都经过另一FF，而该FF输出alias在117的记录区间无变化、Fatal终态仍为已知值。**

本目录实存完整129原包`payload.tar.xz`：57,416字节，SHA-256为：

```text
0ab784c48fed419fbd70d5862a9f2be6bd8a2d82b550b6ed9ad05bffaea3b82b
```

原包14项正文合计1,063,231字节，包含123全部原state/connectivity、launcher原件，以及124/128当时快照。原完整清单逐字存为`payload-manifest.json`。**128在本原包中仅为RUNNING快照**，其后继由独立证据负责；124原launch/错误日志也保留，不能以STARTED推导执行成功。这里的分析只授予123连接/117有限事件范围，不将其它快照晋升为功能、150MHz、功耗或能量通过。

## 来源与提取范围

123未运行EDA、未写输入、未写/force DUT，也未改变任何timing/notifier设置；没有导出工艺模型正文。它从原111冻结state选择并重新核对自己的工具、原111 state及以下三份同一输入，合计5份：

| 输入 | 字节数 | SHA-256 |
| --- | ---: | --- |
| S2c mapped.v | 14199670 | `9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892` |
| 标准单元Verilog model | 2198450 | `9ceaac7085f267c9a2da19d86aa9d88ddb25894df4b2485e32d13e04d0e46581` |
| SRAM Verilog model | 90818 | `81b55d87d5e6821d44037d6f0290ec89c9edb9582eb1932957f181aefc300d51` |

本目录`original111/state.json`和`original117/`是既有115/121归档原件的逐字副本。checker核对三份输入在123、111和117收据中具有完全相同的identity，并保留111真实失败与117的636项前后冻结记录。**123只重新读取了这5份所选输入，不能把它描述为又重读了111全部628项或117全部636项正文。** 本地归档没有14MB原网表和私有库正文，因此离线checker验证返回的路径/方向/事件/身份一致性，不能冒充在本机重新建图。

实际结构解析得到927个design module、927个层级scope、127,548个instance、126,622个叶cell、338,232个bit node及598,724条有向边；library声明schema为1,272项。escaped名称按原子保留，常量位选/concat及跨层port方向经过明确解析；未知语法/宽度/类型/pin会报错。工具原字节和19项synthetic机制/负例测试在`tools/`，不将这些fixture视作DUT运行结果。

## Q到FIFO的确切连接

目标是原117实际`DRNQV0_12TR40`：

```text
u_soc.u_e203_subsys_top.u_e203_subsys_main.u_e203_subsys_mems.
u_sirv_mem_fab.u_sirv_gnrl_icb_buffer.u_sirv_gnrl_rsp_fifo.
dp_gt0.vec_31_dfflr.qout_r_reg[0]
```

其真实声明pin为`CK←clk、D←n5、RDN←rst_n、Q→qout[0]`。`qout[0]`经该`dp_gt0.vec_31_dfflr`实例的`qout`输出pin直接连接父FIFO的`o_vld`，返回路径只有一条hierarchy_output边，中间没有标准组合单元或寄存器。117中目标Q和FIFO.o_vld也同时于`9359390060000fs`变X；这与直接连接一致。它仍不提供厂商cell内部`NOTIFIER→n0→Q`的UDP/行为语义证明。

## 到shared的返回路径均跨状态

从目标Q、FIFO.o_vld分别到shared四个握手信号，8个主搜索均在工具的保守stateful/behavioral分类下**未找到组合路径**，各自到达48个状态屏障且没有截断。这不等于物理电路不存在任何组合影响，也没有排除其它时序路径。组合cell采用“声明input到声明output可能有关”的保守关系，没有检查布尔可敏化或运行时控制值。

允许跨状态的第二搜索返回下表；edge数包括跨层port边和每个cell的input/hub、hub/output两条边，不是门数或周期数。全部列出的状态边都实际从D进入、由Q离开；一般算法也允许其它输入，但本次返回路径没有走CK/reset输入。

| shared终点 | FIFO.o_vld起点edge数 | 目标Q起点edge数 | 返回路径经过的状态单元 |
| --- | ---: | ---: | --- |
| cmd_valid | 42 | 43 | FIFO Q1；mem_fab split的rspid FIFO valid FF |
| cmd_ready | 30 | 31 | FIFO Q1 |
| rsp_valid | 32 | 33 | FIFO Q1；u_shared.rsp_valid_reg |
| rsp_ready | 26 | 27 | FIFO Q1 |

这里`FIFO Q1`是同一`dp_gt0.vec_31_dfflr.qout_r_reg[1]`，不是目标`qout_r_reg[0]`。4条从FIFO出发的返回路径共享以下前缀：

```text
FIFO.o_vld
→ U9(CLKINV0).I→ZN → n3
→ U10(NOR2CV0).A2→ZN → dp_gt0.vec_nxt[2]
→ dfflr.dnxt[1]
→ dfflr.U4(AO22V0).A2→Z → n4
→ qout_r_reg[1].D → [状态屏障] → .Q
→ dfflr.qout[1] → FIFO.dp_gt0.vec_r[2]
→ FIFO.U4(CLKINV0).I→ZN → FIFO.i_rdy
→ buffer.o_icb_rsp_ready → mem_fab.buf_icb_rsp_ready → split.i_icb_rsp_ready
```

之后rsp_ready经split组合cell和`o_bus_icb_rsp_ready[4]`向顶层shared.rsp_ready返回；cmd_ready再经过shared组合逻辑。cmd_valid的返回路径另经split的rspid valid FF，rsp_valid路径另经shared.rsp_valid_reg。完整原子scope、cell type、pin和每条边保存在原connectivity与派生`analysis.json`，无需把图路压成未经验证的CPU因果链。

## 与117事件的严格区分

117原生记录有453条事件（336条slice内value-change、117条终态snapshot），原25项hold告警与同一Fatal全部保留。`analysis.json`逐字选出相关原生事件；checker重新从原simulation.log解析全部453条，并与原passive-event-review逐字段一致比较。

共享rsp_ready于`9359383413333fs`（serial175）、cmd_ready于`9359383433333fs`（181）已短暂X，均在10ps后恢复，早于目标notifier。目标CK上升/D下降、NOTIFIER变化与n0失知同在`9359390050000fs`，随后10ps目标Q/FIFO.o_vld变X；同tick callback serial仍只是运行时通知次序。更晚shared cmd_valid/rsp_ready分别于`9359416766667fs`、`9359416776667fs`变X，最终于`9359423333333fs`因unknown_shared_handshake触发Fatal。

123返回路径中的`qout_r_reg[1].Q`经确切输出port绑定为`FIFO.dp_gt0.vec_r[2]`。但117完整453条中，该alias在slice内**没有value-change记录**，Fatal终态snapshot（352）是`aval=0,bval=0`，即已知0；其下游`FIFO.i_rdy`也无slice内value-change，终态snapshot（345）为已知1。所返回最短路径因此没有提供“目标X已沿Q1传到最终shared X”的运行时支持。这里不声称排除了其它路径或更早的瞬态影响，也不把rptr_vec_r的实际失知替代成Q1已失知。

下一步需要按运行时实际失知的状态/控制值继续追踪其它frontier及相邻采样边沿，结合gate语义和真实timing约束核查。不能仅凭静态最短图路修改RTL、关闭timing check，或宣布唯一故障原因。123和117都仍不是完整task00或比赛资格通过。

## 复核与复现

```sh
python3 docs/validation/xu-score-mapped-connectivity123-server129-20261105/check-evidence.py
python3 docs/validation/xu-score-mapped-connectivity123-server129-20261105/check-evidence.py \
  --extract /absolute/path/new-xu-original129
```

checker校验支持文件manifest、完整129所有14项原字节、123终态及五份输入前后身份、与111/117同源绑定、目标Q直连、8条路径连续性/方向/状态pin、全部117事件及known中间点限制，并重放原19项host机制/负例。PASS只授予这些范围；不重新读取服务器私有网表/模型或重跑VCS。

原服务器命令为：

```sh
python3 "$HOME/Desktop/launch_mapped_connectivity123.py"
```

原launcher拒绝已有123输出，不可删目录后重跑。若需要再次只读建图，应使用归档的原producer和新的未使用输出目录，保持原111和同一工艺输入：

```sh
python3 "$HOME/Desktop/xu_mapped_connectivity123.py" \
  --root "$HOME/Desktop/xu-score-optimization-20261102/mapped-task00-public-diagnostic-20261104-111" \
  --out "$HOME/Desktop/xu-score-optimization-20261102/mapped-connectivity-repro-UNUSED"
```

复现仍需实际服务器的固定网表和库正文；本地archive不提供它们。本目录未改历史收据、生产Chisel/RTL、向量或中心台账。
