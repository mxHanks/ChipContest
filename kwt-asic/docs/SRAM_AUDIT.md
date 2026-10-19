# KWT-1 / E203 存储子系统审计

初次审计日期：2026-10-17；当前复核：2026-10-18（执行后的现况见第13节；第12节保留此前审计时点）。审计对象是本仓库实际源码及既有运行报告；这是本轮 SRAM 重构**之前的基线**，新候选及新测试结果须另行绑定，不能由本文继承 PASS。

核心结论：当前开发 SoC 使用 `kwt_linear_engine_rowpair(PIPE_MUL=1, RESULT_BUFFERS=2)`，其加速器内部有 **20 个逻辑 payload bank，415,744 bit，50.75 KiB**。它们仍是直接在引擎中声明的同步数组，没有实际官方 SRAM 宏。现有本项目结构综合特意保留 `$mem_v2`，并没有把这些 bank 全部展开为 FF；队友的**历史** Nangate45 综合确实把另一版存储展开成大量 DFF/MUX。这两种事实不能混为一谈。

## 1. 正式要求与统计范围

依据根目录 `赛题要求.pdf` 的既有逐页文本 `docs/requirements/competition-extracted.txt`，印刷第3页规定：512 KB 系统共享 SRAM；加速器内部由 16-bit×128、×1024、×4096 的单/双端口 SRAM 组合；150 MHz；本科负责第一前馈线性层、SoC 和综合。印刷第12页的增量面积统计范围与追溯见 `docs/requirements/UNDERGRAD_REQUIREMENTS.md` U09、U12、U13、U27。项目采用用户要求的严格 `<2.25 mm²` 门槛。

- **512 KiB 共享存储**属于系统，用来装载当前任务的 X/W/B 和接收 Y；它不等于加速器内部 bank，也不是 E203 的 ITCM/DTCM。
- **内部 bank**是加速器自行组织的副本/缓冲，其物理宏和外围译码/拼接/流水均进入新增面积。
- X/W/B/Y 的逻辑地址是张量元素编号或软件 byte 地址，不能直接当作物理宏地址。
- 本文统计 memory bank，不把每个 MAC 寄存器、队列标志、总线临时信号数组称为 SRAM 实例。平台 GPR、debug RAM、FIFO 另列，不与 payload 总量混加。

原始 PDF 的上限表述为面积预算；本文未发现与用户列出的矩阵尺寸和频率冲突。正式端口名、CE/WE 极性、延迟、碰撞规则和 PPA 数据**不在现有 PDF 概括中**，仍必须等官方器件文件，不能猜测。

## 2. 当前架构和依赖

```text
开放 E203 Fork 的 CPU / LSU
   ├─ ITCM / DTCM（已有平台，不是新增 accelerator SRAM）
   ├─ 开发共享512KiB ICB行为模型 ← TB装载当前层X/W/B
   └─ o15 / 0x10042000
          kwt_icb_slave：staging / COMMIT / START / Y_LO+HI / WRITEBACK_ACK
               kwt_linear_engine_rowpair
                  ├─ X偶/奇bank：每拍2个X
                  ├─ 8个W bank：每拍8个W，广播给2行
                  ├─ 8个bias bank：每tile首项读取
                  ├─ 16 MAC + 可选乘积寄存级 + 41位精确累加
                  └─ 16项快照 → 后台串行写 → 1/2结果buffer → 2项队列 → 48位输出
CPU读取全部结果后写回共享存储，最后提交WRITEBACK_ACK
```

主要代码：`src/rtl/kwt_linear_engine_rowpair.sv`、`soc/kwt_icb_slave.sv`、`sim/kwt_shared512_model.sv`、`soc/firmware/kwt_smoke.c`。ICB 当前是开发 System Bus 接入，不使用 NICE 代算；Fork 自带 NICE 示例硬件保留而不作为当前 AI 数据通路。正式组委会平台尚缺，不把此 Fork 等同正式验收环境。

根目录执行 `git status --short` 返回 “not a git repository”；不能在根目录声称存在干净 Git 工作树或已提交基线。`ChipContest/` 是独立仓库，当前工程的 `integration/ChipContest/` 是开发融合副本；二者与 `vendor/` 不应被重构脚本原地覆盖。可回滚基线依靠原源码保留、既有 SHA 报告和 harness checkpoint；本轮新设计应另立候选。

## 3. 当前 rowpair 的精确 bank 清单

所有下表内部 bank 都是**一个时钟沿采样读地址、同步更新读数据，未使能时读输出寄存器保持**；写也发生在上升沿。RTL 有独立读写条件，但算法不需要同一 bank 同拍读写，不能据此要求物理双端口。

| 实例（相对引擎） | 个数 | 每个深度×位宽 | 合计bit | 用途与地址 |
|---|---:|---:|---:|---|
| `g_x_row[0].x_mem` | 1 | 3200×16 | 51,200 | 偶数行50×64；计算地址 `{pair_index,k_issue}` |
| `g_x_row[1].x_mem` | 1 | 3136×16 | 50,176 | 奇数行49×64；最后row98禁止第二行读 |
| `g_lane[0..7].w_mem` | 8 | 2048×16 | 262,144 | `W[k,c]`：lane=`c%8`，word=`k*32+c/8` |
| `g_lane[0..7].b_mem` | 8 | 32×40 | 10,240 | `B[c]`：lane=`c%8`，word=`c/8`；数据不截断 |
| `g_result_buffer[0..1].result_mem` | 2 | 512×41 | 41,984 | 每buffer容纳2×256结果；序列化写，按原row-major输出 |
| **双buffer合计** | **20** | — | **415,744** | **51,968 B = 50.75 KiB** |

`RESULT_BUFFERS=1` 时是19个 bank、394,752 bit、48.1875 KiB，不能把两种配置一起累计。`PIPE_MUL`不改变 payload 容量，只改变乘积寄存器和标签。

关键位宽边界：X/W signed16，Bias signed40，累加/结果 signed41，向外符号扩展至 signed48。41位由全部合法输入范围的证明决定，不是样本截断。快照 `result_snapshot[2][8]` 共656 bit、累加器共656 bit、流水乘积（启用时）512 bit，都是标准单元寄存器；两个41位输出队列项、读保持和标签也须计入逻辑面积。`product`是组合乘法输出，不是额外存储副本。

现有结构证据 `docs/runs/optimization-v2/structure-04.json`：20个`$mem_v2`、415,744 bit、16个 signed16×16→32 乘法器、无 multiport/asynchronous mapping warning。该报告还有2,086个**不含 memory read flops 的寄存器bit**，及161个 RTLIL `$mux`、9个`$pmux`；这些宽字RTLIL单元不是门级MUX个数，更不是映射面积。

## 4. 保留基线和互斥候选

下面各行是可选择的不同顶层，**不得把它们的存储相加**。

| 顶层/参数 | 逻辑组织 | Yosys保留对象数 | payload bit |
|---|---|---:|---:|
| `kwt_linear_engine`, LANES=8/16 | X 6336×16，W按lane分配总16384×16，B总256×40 | 3 | 373,760 |
| `kwt_linear_engine_opt`, LANES=8/16 | 同上；bias只在首k读取，乘积可流水 | 3 | 373,760 |
| `kwt_linear_engine_banked`, LANES=8 | X 6336×16，8×W2048×16，8×B32×40 | 17 | 373,760 |
| `kwt_linear_engine_banked`, LANES=16 | X 6336×16，16×W1024×16，16×B16×40 | 33 | 373,760 |
| `kwt_linear_engine_rowpair`, RESULT_BUFFERS=1 | 上节X/W/B + 1结果buffer | 19 | 394,752 |
| `kwt_linear_engine_rowpair`, RESULT_BUFFERS=2 | 上节X/W/B + 2结果buffer | 20 | 415,744 |

前两版二维 W/B 数组被 Yosys 合并为大对象：LANES=8时 W、B各是8R/8W，LANES=16时各是16R/16W。算法上的lane分区并不使通用存储映射自动理解物理单端口分bank。`banked`和`rowpair`已通过 generate 内的一维独立数组解决这个结构问题，值得保留。

上述各版共同的X/W/B有效容量是46,720 B（45.625 KiB）。原版/opt/banked没有完整输出矩阵RAM，输出在lane累加器中保持至被消费。rowpair只额外存最多4行结果，不在内部复制完整99×256矩阵。

## 5. 平台和队友存储的边界

| 对象 | 当前容量/端口 | 与本轮改动的关系 |
|---|---|---|
| `kwt_shared512_model.memory` | 131072×32 = 512 KiB；32位ICB命令、byte mask、单outstanding、可变等待 | 开发仿真；不在加速器综合清单，不是官方macro |
| E203 `u_e203_itcm_ram` | 8192×64 = 64 KiB；1RW、8个byte write enables；当前config地址宽16 | 已有平台；`e203_srams → e203_itcm_ram → sirv_gnrl_ram → sirv_sim_ram` |
| E203 `u_e203_dtcm_ram` | 16384×32 = 64 KiB；1RW、4个byte write enables；当前config地址宽16 | 已有平台；不能代替512KiB共享区，不能装下完整Y |
| E203 GPR `e203_exu_regfile.rf_r` | 32×32逻辑寄存器，x0恒0，实际31×32 payload FF；2异步读/1同步写 | 已有CPU关键结构；当前非latch配置，本轮不改 |
| E203 debug RAM / ROM | 7×32 debug寄存器，异步读；29×32 debug ROM；mask ROM逻辑1024×32 | 已有平台功能，不替换为AI内部宏 |
| Fork示例 NICE row buffer | 4×32寄存器 | 平台示例，未进入本任务的计算；不将其结果当AI验证 |
| 已有总线/外设FIFO | 通用`fifo_rf_r`，QSPI TX/RX各8×8，AON队列等 | 小容量平台寄存器；完整SoC功耗不能漏记，本轮不重写 |
| 队友 `WeightBankArray` | 8个WeightBank，每个由2×1024×16 `Sram1024x16`组成，共16个行为SRAM | 独立Chisel候选，不同时实例于当前rowpair |
| 队友 `XRowBuffer` | 64×16寄存器，同步写、**异步读** | 独立Chisel候选；不可直接替换为同步读宏 |

按可替换的大块 payload 边界，当前开发SoC中已定位20个accelerator bank + 1共享model + 2 TCM = **23个**；这个数不包含上表平台GPR/ROM/FIFO/小寄存器，不代表“全芯片只有23个有状态对象”。平台小存储保持原实现，正式平台到位后须按其实际elaboration重新生成完整层级面积清单。

E203 `sirv_sim_ram` 在读请求边沿锁存**地址**，由锁存地址组合选择数据；随后对同址写入可能让Q变化。它与rowpair“读数据本身被寄存器锁存并保持”的语义并不完全相同；`FORCE_X2ZERO`还会把DTCM未知值强制为0。该平台仿真特性不能移植为AI SRAM未初始化规则。

## 6. 张量地址空间和重复存储

一层逻辑数据量：X=12,672 B、W=32,768 B、B=1,280 B、Y=152,064 B（48位紧密表示）。软件开发布局在共享区 `0xa0000000`：

| 对象 | byte偏移 | 开发存储大小 | 说明 |
|---|---:|---:|---|
| X | `0x00000` | 12,672 B | 两个int16合一个32位字 |
| W | `0x04000` | 32,768 B | 同上；外部row-major |
| B | `0x0c000` | 2,048 B | 每40位bias放两个32位字，存在对齐padding |
| Y | `0x10000` | 202,752 B | 每48位结果放两个32位字，高字只用低16位 |
| 任务邮箱 | `0x7ff00` | 两个32位字 | host flag/fail，远离Y范围 |

这些区域无重叠，均在512KiB内。内部加载每任务6336 X + 16384 W + 256 B，共22,976次元素提交；12层是逐任务替换，不在内部同时缓存12层。共享存储与内部计算bank的副本用于CPU分层装载和并行读口，不能在没有DMA/仲裁和新性能证据时简单删掉。Y没有内部全矩阵副本，结果buffer是为保持顺序和计算/写回重叠。

队友W bank地址为`group*64+k`，本项目为`k*32+group`。二者必须通过`W[k,c]`统一，不允许直接复制bank镜像。官方宏的深度级联片选还必须与1拍读返回对齐。

## 7. 读取时序、使能和冲突审查

### 7.1 当前rowpair

- 请求使能全部高有效：`x0_rd_en`、`x1_rd_en`、`w_rd_en`、`b_rd_en`、`result_wr_en`、`result_rd_en`。它们是**逻辑接口**，不说明官方宏引脚极性。
- C_RUN每拍发X/W请求，地址在边沿采样；`read_valid/read_first/read_last`与同步读结果同拍到达。`PIPE_MUL=1`再将乘积和metadata一起延迟一拍。Bias只在k=0读，`b_read`随后保持到该tile首MAC使用。
- C_DRAIN/C_STORE/C_FLUSH排空依赖，不能因为替换内存而删掉。若宏读延迟大于1拍、内部pipeline不可停顿或Q不保持，须由Adapter和等长标签/读保持处理，旧回归不能继承。
- 结果写先捕获16项快照，后台每拍1项。`result_full`只在整个pair写完后置位；输出只从full buffer发读。buffer最后一项真正`out_fire`才释放；2项队列与`rd_pending`共同计credit，避免回压丢首尾字。
- 装载只在`!active`且非错误时允许；START要求X/W/B顺序计数完整。计算期间X/W/B不写，避免1RW端口冲突。结果读写由buffer所有权隔离；不同buffer并发不意味着同一宏组要双端口。
- 不对payload RAM批量清零，复位清valid/count/ownership；读数据寄存器复位值未定义，只能在相应valid时消费。任务结束后fresh计数清零，下一任务不能隐式复用旧参数。

### 7.2 风险与已有检查的证明范围

| 检查项 | 基线事实/风险 | 本轮应建立的检查 |
|---|---|---|
| 多驱动 | 既有Yosys `check -assert`通过；静态源码每bank单写always_ff | 新wrapper候选重新跑结构check，不能沿用旧报告 |
| 同bank读写/双端口同址 | 当前任务调度不需要；数组RTL的同拍读写会呈NBA旧数据语义，但没有官方碰撞保证 | 将非法冲突显式检测，不能把仿真old-data当官方保证 |
| 未初始化读 | SRAM无reset，基线以完整加载/ownership阻止消费；原数组本身没有逐地址written检查 | 行为模型保留X并可fatal，测试有意触发；不可自动填零冒充加载 |
| 非2次幂地址 | X3200/3136在12位空间中有洞；现有外部load_legal及row1_active限制 | wrapper验证`addr<DEPTH`；最后row98禁止奇bank读 |
| 首尾/有效标签 | 现有全矩阵、回压、奇尾行和重任务证据有效，但仅对原源SHA | 新模型需逐位、cycle/valid、reset/repeat回归 |
| 使能低时保持 | 当前AI读数据寄存器保持；Chisel SyncReadMem不保证无效周期Q | 明确wrapper对上层保持契约，可由外围寄存器实现，面积不得漏计 |
| shared模型非对齐访问 | 现有实现只在addr[1:0]==0时真正读写；部分mask检查仅限制addr[0]，例如addr+2/mask3可能无错无写 | 当前固件只用aligned32，未触发；通用halfword支持需修复或统一拒绝并测试 |
| shared模型未初始化/错误读 | 当前TB显式装载X/W/B，Y预置哨兵，检查全部write和mask | 不能把2态Verilator的默认0当初始化证明；新增严格4态单元测试 |
| 外部共享写回完成 | 核心DONE不等于CPU写回完成 | 保留HI响应消费及WRITEBACK_ACK，SoC TB核对全部写事务 |

## 8. FF/MUX与现有综合证据

本项目 `scripts/synth/run_structural.py`、`run_rowpair_structural.py` 使用`proc; opt; memory_dff; memory_collect`并核对bank形状，**没有运行 memory_map**。因此415,744 bit是保留memory容量，不能说已用了415,744个DFF，也不能说真实宏已经映射完成。FF回退模式若完整展开会需要相应payload状态bit外加读保持、译码和大量选择逻辑；具体门数必须以实际mapping报告为准。

队友历史`ChipContest/reports/baseline/LinearComputeCore_nangate45.log`由Yosys0.52记录：

| 历史映射结果 | 原始报告值 |
|---|---:|
| memory / memory bit | 0 / 0 |
| 总cells | 951,271 |
| DFF_X1 | 263,958 |
| MUX2_X1 | 295,146 |
| Nangate45 chip area | 2,159,601.598019 library area units（该公开库按µm²解释为约2.159602mm²） |
| sequential area | 1,193,618.076003（55.27%） |

它证明旧设计确实发生FF/MUX展开。该263,958包含全部历史顶层的寄存器，并非“SRAM专用DFF”精确分拆；295,146也包含计算/控制MUX。历史top不是当前rowpair，没有新ICB接口，不含官方宏，脚本无150MHz有效SDC或功耗，不能以2.1596mm²声称满足比赛总面积。

本机现有重跑 `artifacts/integration/20261017-teammate/area-DotProductEngine.log`在Yosys0.33 ABC阶段超时；其状态TIMEOUT，不继承历史报告PASS。Nangate45仅是公开参考标准单元库，不是组委会指定工艺，无任何官方SRAM Liberty/Verilog/面积表。

## 9. 可保留、待改造与迁移次序

**保留：** fixed16_acc48软件真值、精确41位内部证明、外部load/start/out契约、rowpair数据流、乘积pipeline标签、odd-row gating、结果双buffer/credit、ICB输出原子性、旧版所有源码及历史报告。新memory候选另取顶层，避免让115项主机测试和既有RTL证据的源码绑定失效。

**必须改造：** 引擎直接持有数组、仿真与综合文件集不区分backend、行为模型缺少非法访问/初始化检测、标准宏拼接边界不存在、Blackbox不存在或统计不完整。Blackbox需要保留地址/数据/使能与上层计算，不让优化把计算切掉，也必须列出所有未建模时序弧。FF模式必须由显式开关选择，正式全容量综合默认拒绝。

建议增量顺序：固定此基线 → 单独memory wrapper及单元测试 → 新`kwt_linear_engine_rowpair_sram`候选保持1拍契约 → 与原rowpair对照 → 完整矩阵/12层/回压/重复任务 → ICB/E203开发SoC → Blackbox逻辑综合和可覆盖局部STA → 官方文件到位后Adapter、宏拼接、全部回归和正式PPA。

当前72宏/56.5KiB是按128/1024深度的**候选容量组合**（X8、W16、B24、结果24），不是实装宏数或物理面积。`docs/optimization/SRAM_AREA_BUDGET.md`早期“proposed结果48位、逻辑51.625KiB”描述先于当前41位rowpair；本轮以415,744bit/50.75KiB为当前payload，48位宽padding后的配置容量仍可能56.5KiB。宏的宽度/深度padding、输出保持寄存器和片选mux都应在正式Adapter中明列。

最值得后续测量的是bias bank浅深度浪费：8×32×40映射最浅128×16可能需要24片。集中bias预取可减少宏填充，却增加预取周期、缓存和控制；在当前子系统重构中先保持算法，不把未实现方案当收益。

## 10. 证据与验收边界

本次审计的输入摘要/SHA见 `docs/runs/sram-audit-20261017.json`，只记录静态审计来源，不伪造新仿真。已有基线证据入口：

- `docs/runs/optimization-v1/*structure*.json`：baseline/opt/banked组织与373,760bit核对。
- `docs/runs/optimization-v2/structure-01..04.json`：rowpair19/20bank与394,752/415,744bit；对应原源SHA。
- `docs/runs/optimization-v2/summary.json`：既有18组、116任务、2,939,904输出功能回归摘要。
- `artifacts/integration/20261017-teammate/integration-report.json`、`soc-build/fusion-result.json`：开发E203 1任务、25,344输出、完整写回、1,670,319周期证据。
- `docs/integration/LIBRARY_AUDIT.md`、`ICB_CONTRACT.md`、`FUSION_RUN.md`：公开参考库、接口/版本、可复现步骤。

静态存储组织审计：**PASS**；本轮新wrapper/RTL/SoC回归：以各新运行报告为准；官方SRAM仿真/时序/面积/功耗和正式150MHz/增量面积/能耗：**BLOCKED**。官方缺项不阻止功能重构，但不能被Blackbox零面积、无时序弧的正slack或行为模型PASS替代。

本轮实施入口为独立`kwt_linear_engine_rowpair_sram`及`kwt_sram_bank`：保留原FSM和外部协议，将bank拆成16位×128/1024/4096的逻辑原语边界，双buffer配置预期72个原语、56.5KiB配置容量。这是可替换的组织边界，仍不是官方宏实装。原`kwt_shared512_model`也保留；独立`kwt_shared512_checked_model`将对全部非32位对齐地址返回错误、保证无存储副作用，并使读请求不依赖无语义的wmask。本段记录实施方向和修复边界，**不提前声称新候选已经通过测试**。

## 11. 计划模式复核：当前已落盘与未验收项

2026-10-17后续只读审计，机读记录为 `docs/runs/sram-plan-audit-20261017.json`。本节补充前述重构前基线，不替换原始失败/运行记录；本轮没有启动新仿真或综合。

| 对象 | 当前真实状态 | 依据/限制 |
|---|---|---|
| 原源码保护 | PASS：原checkpoint492文件均在 | 本轮状态文档更新前，仅Makefile/README/harness既有文件有变更；原RTL/Golden/固件/平台字节未改，存储候选为新文件 |
| SRAM原语/拼接/checked共享模型 | PASS：已执行51案例、7组行为/FF匹配 | `142618…sram-unit-6d94fd06/result.json`；25正例原生exit0、26预期拒绝负例非零exit，均无timeout；全位0/1覆盖、所有绑定SHA复核一致 |
| 新核心双后端 | PASS：12个已完成子运行、76任务、1,926,144输出 | 四种PIPE/BUFFER组合、每组6合成任务×两后端；双后端12层单波形真实参数；双后端四态signed41极值；含回压/在途复位/非法load/连续任务 |
| 原版对照 | PASS：另1个原rowpair运行、12任务 | 5份比较报告重算一致，组内周期完全相同；不能将子项通过改写为整套含SoC通过 |
| Blackbox core-only | 历史结构/映射PASS | 20逻辑bank/72opaque/16MAC；41,683标准单元，参考逻辑面积0.05184473mm²；不含ICB或SRAM；mapping脚本已更新，当前脚本需重跑 |
| Blackbox含ICB | FAIL | `142838…sram-blackbox-9f144c6d/prepare.log:2377`：`check -assert`组合环，exit1；候选adapter尚未修复 |
| 全FF结构 | PASS：已完成，无需继续等待 | `143003…sram-ff-reference-aa213bf0`；exit0，71.279s，429,231 register bits，0残留memory，约1893MB峰值；非门级映射，未给全FF面积/STA |
| 参考局部STA | 工具流程历史PASS；setup/hold FAIL | `142935…sram-partial-sta-a094c9c2`：WNS=-22.923624ns，TNS=-22525.019531ns；原hold报告最差-0.004303ns；当前STA脚本已更新需重新绑定新mapping |
| 新12任务E203与整体regression | 未完成验收 | `142439…sram-soc-2ef93db7`、`142223…sram-regression-53976e7f`缺最终result；SoC run.log为0字节，无原生运行退出码/完成marker；旧session无法恢复。不判功能FAIL，也不再声称仍在运行或PASS |
| 官方宏/正式工艺PPA | BLOCKED | 正式模型/Liberty/面积功耗/平台条件未提供 |

含ICB的组合环为 `request_ok → engine_start_valid → core.load_ready(!start_valid) → staging/COMMIT request_ok`。虽然地址解码在功能上互斥，综合后的结构检查仍有真实反馈，不能豁免。计划仅在候选adapter里将装载合法性检查与START授权解耦，再以协议与结构回归证明等价，不改E203核。

局部STA的最差路径是 `read_valid FF → INV → NOR2 → MUX → accumulate_product FF`；真实网表对应INV/NOR有499/472个sink pin，NOR延迟23.657425ns。应先诊断控制广播扇出与映射缓冲，再考虑局部RTL，不预设MAC计算是瓶颈。72个宏被切成432个端口组，1153输入/2436输出缺delay、2436未约束端点为显式未建模宏/reset边界；不能把该局部分析称150MHz全路径验收。

SoC还需补三项：①现有首个X读取起点漏了CPU初始调度和KIND/ADDR配置，共享区由TB backdoor预装载，不能代表正式完整窗口；②TB在negedge观察最终响应valid/ready就结束，而实际响应在posedge消费，须改成真实接受事件；③新runner缺simulation/BIN产物SHA及可恢复中断记录。旧独立审查对“等待最终响应”的措辞以本节更精确的边沿审计为准，原审查文件保留。

当前仅功能层面可接受原语/核心证据；新SoC在途reset/错误恢复尚未运行，不能从核心复位证据继承。后续修改与验收顺序见 [项目设计](superpowers/specs/2026-10-17-sram-subsystem-design.md) 和 [增量计划](superpowers/plans/2026-10-17-sram-subsystem-plan.md)。


## 12. 2026-10-18当前状态复核（优先于第11节历史状态）

本次重新核对正式PDF、当前文件和已结束运行；没有新建RTL或启动新的EDA实验。完整带SHA索引为 `docs/runs/sram-current-audit-20261018.json`。PDF SHA仍为b73a5414…927c，矩阵、12层、512KB、指定宏、150MHz和面积口径与原追溯一致；PDF上限≤2.25mm²，工程使用更严格的<2.25mm²目标。

### 十项审计问题的当前答案

| 问题 | 当前答案 |
|---|---|
| 共有多少存储实例？ | 在选定rowpair双buffer配置中，AI内部20个逻辑payload bank；平台另有共享区1、ITCM1、DTCM1，即23个主要payload存储对象。新容量拼接后AI内部72个原语，加平台3个为75个开发存储对象；这些不是75个官方物理宏。CPU寄存器文件/debug/ROM在第5节另列，不能把源码中互斥候选累计成总实例数 |
| 容量/位宽/端口/用途？ | 内部2X、8W、8bias、2result详见第3节，总415744bit；均按1RW使用。候选50个128×16+22个1024×16，共462848bit。共享512KiB、ITCM64KiB、DTCM64KiB独立于AI内部容量 |
| 共享与内部怎样区分？ | 共享存当前任务X/W/B与完整Y，由CPU搬运；内部是计算访问副本/最多4行结果。共享/TCM模型不进入AI综合源集 |
| FF与选择逻辑用了多少？ | 历史全容量候选FF展开：429231寄存位、26801个RTLIL宽字mux、21个pmux、0残留memory；不是26801个门级MUX。当前完整FF门级面积/STA未跑。队友263958 DFF/295146 MUX为另一历史设计，不能混用 |
| 延迟、极性和保持？ | 逻辑请求高有效，上升沿采样；同步一拍读、Q保持；reset清valid/control而不清payload。真实官方CE/WE极性和宏延迟仍未知 |
| 核心依赖异步读吗？ | 当前AI payload数据通路原本就是同步读，现有标签/流水时序不需新增READ_WAIT；E203 GPR/debug的异步读属于平台，不能一起改 |
| 哪些有Wrapper？ | 原rowpair直接数组保留；候选已改成core→bank→1rw后端。平台TCM保持原wrapper，官方adapter只有明确接口边界且缺文件时拒绝 |
| 多驱动/冲突/未初始化/越界？ | 当前含接口结构检查无逻辑环/多驱动；单元67案例覆盖禁止冲突、未写读、hole和X/Z使能。bank译码屏蔽未知使能的漏检已修。该结论只覆盖当前检查范围，CPU恢复/末响应仍待新SoC验证 |
| Yosys是否展开了SRAM？ | 正式早期入口BLACKBOX保留72 opaque，无剩余数组或意外大FF展开；显式FF对照才memory_map。不能说整个工程所有memory都已FF化 |
| 哪些阻碍官方接入？ | 官方引脚/时序/库/面积功耗未知；后端JSON尚未成为所有runner统一源集入口；新SoC验收组件未接通；参考局部时序失败；综合前后功能等价尚未验收 |

### 本次核验的已完成证据

- **原实现保护：** 相对`sram-pre-refactor`492文件无缺失；只有状态/入口文件变化，原RTL、Golden、原固件与平台文件未改。根目录Git不可用；队友原仓库及E203子仓库状态无修改输出。
- **单元PASS：** `20261018T020757.224881Z-sram-unit-a0557578/result.json`，25正常+42预期拒绝=67案例，7组行为/FF匹配；146个带SHA文件记录核验一致。
- **ICB协议PASS：** `20261018T020523.486625Z-sram-icb-e6432c66/result.json`，两后端各193938事务、86次响应保持检查、1完整+1abort任务；25348输出含中断任务的4项，不能当成两个完整矩阵。20个带SHA文件记录一致。
- **核心汇总PASS：** `20261018T020827.090979Z-sram-regression-8423d1c1/result.json`，18子阶段全部完成；新核心76任务/1926144输出、另原版12任务、5份对照；697个带SHA文件记录一致。`include_soc=false`，不包含SoC。
- **含ICB映射PASS：** `20261018T020610.045677Z-sram-blackbox-173fe72f/result.json`，72 opaque、16MAC、44120标准单元、参考逻辑面积0.055476428mm²；26个带SHA记录一致。不含宏/复用平台面积。
- **局部STA工具PASS、Timing FAIL：** `20261018T020713.509216Z-sram-partial-sta-2fe2e15f/result.json`，setup WNS=-22.790979ns、TNS=-22493.648438ns，hold=-0.004303ns；19个带SHA记录一致。1153输入/2436输出缺delay、2436未约束端点为显式未建模宏/reset边界，非全路径150MHz通过。
- **当前主机测试PASS：** `artifacts/runs/20261018-sram-plan-refresh/host.json`，`make test`原生exit0、144项测试通过；其中SoC validator测试通过不等于SoC仿真通过。

### 剩余问题及保留失败

1. 原ICB组合环已修，原反馈失败记录保留；不能继续将它列为当前阻塞。Yosys0.33私有名字冲突采用映射前私有重命名规避，接口/算法不变。
2. `run_sram_soc.py`的新validator尚未被main调用；main仍编译旧TB/旧固件、解析旧marker。新恢复固件已落盘但未接入，`tb_e203_kwt_sram.sv`尚不存在，新SoC仍未验收。
3. SoC需核对posedge实际响应、完整配置窗口、在途soft abort/外部reset及恢复；manifest合法但非默认路径的向量须按已验证字节暂存，避免TB硬编码路径错绑。
4. 缓冲profile `20261018T020758.384301Z-sram-blackbox-8eb64395`失败并保留。真实ABC在buffer遇到无fanout节点，可能exit0但无输出/标记。最小复现仅增加cleanup通过；实际全网修复验证NOT_RUN。诊断见 `artifacts/diagnostics/20261018T020921Z-abc-constr/`。
5. 持久证据helper已有，但真实runner还需统一使用其终态检查；总回归还需核验子report本身状态/哈希，不能只相信stdout的PASS摘要。
6. 当前harness自动源树没有`reports/`和`tech/`，因此不能把checkpoint称为这些文件的完整镜像。将显式归档/覆盖测试列入入口收口；本次另存当前报告和技术目录说明的带SHA快照。

可保留：核心算术/调度、已验收同步读契约、20bank布局、旧固件/原接口、固定Golden和向量。待改部分集中在新SoC TB/runner、参考映射脚本、源集/验收入口；先不做更小cache、集中bias或位宽优化。

下一步与验收命令以 [10月18日剩余计划](superpowers/plans/2026-10-18-sram-remaining-plan.md) 为准。官方宏实装、正式平台、完整150MHz/面积/功耗仍BLOCKED。


## 13. 2026-10-18实施后的当前验收

本节优先于前述历史状态。当前完整运行入口`make regress SRAM_VECTORS=artifacts/runs/20261015T091234Z-speech-smoke/export`已完成：原生exit0，20子阶段均PASS；核心76新任务/1926144输出、另12原版任务，存储67案例/7组匹配，ICB双后端完整任务/abort/回压。E203开发SoC完成12层、304128输出、275712 load commit、608256个输出写响应，包含CPU soft abort及在途外部reset恢复。原始输入、源、二进制、向量及日志共1073个唯一文件记录重新核验一致。

SoC新TB/固件/validator已实际接通；基于posedge响应接受完成和准确开发窗口，不再使用旧parser。运行前记录ELF/BIN/HEX/simulation SHA并在结束复核。首个中断的12层目录不覆盖，`recovery-observation.json`明确其没有最终终态。统一后端选择器已被核心、ICB、SoC、黑盒和FF综合入口消费；原语单测保留显式最小源集。原RTL、Golden、原固件和E203原仓库仍保留。

最新主机测试175项通过；当前源码包的544文件异目录恢复和当时174项主机测试通过，不把它称完整平台/工具链迁移。checkpoint现保存白名单源码实际字节，明确包含PPA报告及技术目录README，官方包/外部平台仍需独立管理。

含接口有缓冲参考映射通过，46026标准单元、0.056997416mm²（不含SRAM和复用平台）。局部setup最差+4.652084ns，data hold=-0.013133ns，内部soft_reset removal=-0.255385ns，Timing FAIL。后续电气复核纠正历史“pin-only/无wire parasitics”元数据：OpenSTA实际采用库默认统计模型5K_hvratio_1_1，现显式绑定相同模型，重跑数值不变。没有改变SDC目标/uncertainty或新增例外。

综合前后标准逻辑证明已做两次120秒有界尝试（含共同SRAM切口及clock-sampled reset假设）；均未得到全量结论，状态NOT_PROVEN，不把部分等价点或RTL PASS说成综合网表功能通过。下一步切换到有效信号感知的模型/门级功能回放，不继续盲目扩展同一证明。官方模型缺失也不等于这些未证明点已经被豁免。

执行/证据索引：`docs/runs/sram-implementation-20261018.json`；参考时序与真实路径：`docs/optimization/SRAM_TIMING_ANALYSIS.md`；负责人摘要：`docs/USER_CHANGELOG.md`。正式E203/官方宏实装/完整150MHz/总增量面积/功耗保持BLOCKED，S3仍有综合后功能和参考min违例待收口。

## 14. 本轮计划复核：当前框架及下一批改动

用户要求先审计并明确修改计划；本轮只读核查源码/赛题/原始报告、运行主机检查和按位结构诊断，未修改RTL、Golden、固件或工艺文件，未启动新的EDA。当前唯一计划入口为`docs/SRAM_CURRENT_PLAN.md`，含十项审计回答、实例/容量表、模块框架、A–D执行顺序、文件范围、验收和耗时假设；较早计划保留为历史。

最新主机178项通过。已存在的`20261018T033333.146159Z-sram-mapped-5c788634`结束：编译原生exit0，但runner发现UNOPTFLAT主动FAIL，仿真NOT_RUN。报警为48位`y_snapshot`的高7位符号扩展别名；按实际端口方向切开2343个DFF与72同步宏后，43683个组合cell的47332个bit节点全部拓扑消除、残余0，41个独立快照bit均由DFFR驱动。它支持先排查向量表示/仿真调度，**不能**升级为综合后功能等价PASS，也不应据此重写核心。

补清共享模型检查范围：`kwt_shared512_checked_model`有地址/对齐/mask/响应保持检查，但没有逐地址known bitmap或完整X/Z命令拒绝；内部1RW的未初始化读检查不能迁移成共享模型结论。共享写在命令接受沿生效，reset只撤销pending/response，不回滚已经完成的写入。现有SoC通过显式装载和预装载提供有效数据；增强共享模型诊断是后续可选小任务，不作为重做存储布局的理由。

下一批优先修复门级回放的表示/采样/未知值/边界场景，再1层→12层；后处理真实data hold/removal，不放宽SDC。20bank/72容量原语、一拍1RW、16/16/40/41/48数值与System Bus协议保持。官方文件缺失继续只阻塞正式Adapter/PPA。可复现诊断及源/证据SHA在`docs/runs/sram-framework-audit-20261018.json`。

## 15. 计划A执行结果：12层门级功能及有界电气诊断

本节更新第13/14节的“尚未运行门级回放”状态。先以实际工具小例资格化split_var，再以Icarus四态21例资格化检查器；真实门级1层和12层均完整结束。12层共304128个输出逐位一致、1873549个实际响应、9756次保持检查、12个末HI和12个ACK背压；含一次busy abort和一次pending HI响应外部reset，未完成epoch不计入完整矩阵。私有Golden只翻转第0输出的一位时准确失败，记录EXPECTED_REJECTION。

参考mapped.v仅更改一次仿真top名称，外部.vlt定点拆分符号扩展向量，无关闭结构告警；源/模型/Liberty/实际binary/native退出/完整标记均核验。综合网表旧engine_y_ready名字无实际驱动，改观测真实保留状态、外部握手及output_count，七个mapped状态均核唯一驱动。普通数组/FF/Golden/MAC/生产RTL没有因此修改。12层通过是Verilator两态零延迟及共同逻辑1RW模型范围；全网四态、所有输入形式等价、官方宏功能/时序不由此证明。

12层复用初次因bytes与size_bytes同身份记录被旧reader拒绝，保留旧生产脚本与失败。独立reader仅兼容两种等值长度表示及验证相对路径别名，原mandatory source/工具/模型recipe/原生命令/binary验收全部继续执行；不重复综合或编译。当前轻量索引`docs/runs/sram-mapped-functional-20261018.json`。

另在独立宏切口STA视图只改变reset BUF_X1强度：BUF_X8/X16使removal分别变为-0.095160/-0.069030ns，data hold均仍-0.013133ns，覆盖setup最差仍+4.652084ns。两次均导出后在新OpenSTA进程重读、使用原SDC/统计wire-load；实际143负载、约369.244fF未删除。它们是电气诊断，不是已接受全网映射候选；未做候选功能回归且宏边界仍未知。既有设计Timing仍FAIL，不覆盖原映射。进一步选择见`docs/optimization/SRAM_MIN_DELAY_OPTIONS.md`。

## 16. 计划B执行结果：独立参考网表ECO及新网表回放

本节更新第15节之后的状态，不覆盖原版失败。原完整保宏网表复制到独立目录，在真实D支路/内部reset输入插入9个BUF_X1，reset驱动BUF_X1→X16；仅再将一个10负载NOR4_X1改为同函数NOR4_X2。保留20bank/72宏、16MAC、原RTL/Golden/固件及外部端口。原始图至第二候选通过buffer折叠投影；第三步由同Liberty函数及逐pin图核验独立证明，不能冒用只允许buffer的投影证明。

最终`20261018T042058.542924Z-slew-eco-1836b7fb`：46035标准单元、57011.514μm²标准逻辑面积，相对原版+14.098μm²，不含任何SRAM面积/功耗。原SDC逐字节保持，同参考wireload/ideal clock，setup最差+4.652084ns、data hold+0.001379ns、removal+0.055262ns；reference transition及clock pulse/period报告0违例。hold仅1.379ps，未知宏边界和正式工艺条件不因此补全。

最终网表重新跑1层及12层真实语音回放，12层304128输出、1873549响应、9756保持检查、恢复1+1、末HI/ACK各12通过，不能继承前候选PASS。202项主机检查及静态入口通过；索引`docs/runs/sram-reference-eco-20261018.json`。两态零延迟/共同逻辑1RW模型范围不扩大为全网四态、全输入形式、官方宏或完整150MHz。官方PPA继续BLOCKED，后续需以官方文件重建模型、源身份和全部依赖验证。

## 17. 交接电容审查与第四候选

第三候选的完整参考cap采集实际遍历48378个标准输出，4个驱动/8个极性超出库上限。保留失败后，在独立第四候选仅把2个NOR3_X1和2个NOR4_X1改为同函数X2；旧版网表、RTL/Golden/数值/SDC保留。实际bit/连接签名核对匿名报告到完整实例，targets绑定原完整cell和报告SHA；全图逐pin独立检查仅这四处type变化，72宏不变。

第四候选`a2a7cf86`标准逻辑57015.238μm²，累计相对原版+17.822μm²；参考setup/hold/removal保持+4.652084/+0.001379/+0.055262ns。实际新网表1层、12层回放通过，12层304128输出/1873549响应、9756保持检查、恢复1+1、末HI/ACK各12完整。204主机测试及静态入口通过。

电气正式入口`make check-reference-electrical STA_REPORT=...`实跑，48378标准输出/32类上限全部扫描，已知cap0违例/0舍入边界、transition/clock零报告违例，包含X2引入的上游负载。182条标准驱动连接宏输入的真实负载、1152宏输出驱动位仍未知，完整宏/官方电气BLOCKED。索引`docs/runs/sram-reference-cap-closure-20261018.json`；仅参考macro-cut已知负载与所测两态零延迟场景接受，不能扩大到正式150MHz/PPA、全网四态或全输入形式。
