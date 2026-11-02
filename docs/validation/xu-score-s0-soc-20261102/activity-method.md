# xu S0 全范围活动与任务能量流程准备

本文件是可执行流程准备，不是正式全SoC功耗结果。现有旧wrapper、单layer0的VCD/PT数据不能用于本科能耗8分。正式范围包含E203、互连、加速器以及ITCM、DTCM、512KiB共享和权重SRAM；固定平台RTL和原TB均未为本流程改动。

新增入口为`tools/scripts/xu_soc_activity.py`，仅需Python标准库。对应SV为`tools/ppa/xu_activity_probe.sv`，host验证为`tests/host/test_xu_soc_activity.py`。本文中的所有SERVER_OUT路径必须选新的空输出目录，保留原始日志、报告和哈希。

## 先实测服务器VCS的SAIF能力

服务器指定安装路径为`/eda/synopsys/vcs/vcs_2020.03-SP2-6/bin/vcs`。本地没有VCS，不能仅凭系统任务名字宣称安装支持SAIF。由持有服务器会话的root上传当前SV/Python后执行：

```bash
python3 tools/scripts/xu_soc_activity.py probe \
  --vcs /eda/synopsys/vcs/vcs_2020.03-SP2-6/bin/vcs \
  --out SERVER_OUT/xu-saif-capability
```

默认分别试`-debug_access+all`和另加`-cm tgl`的两种编译配方。每配方另试default、rtl_on、rtl_on+sv、on+sv、union五种监控策略；每策略在独立新进程运行三个123ns微实验，日志和所有SAIF均保留。union仅是试验：先rtl_on+sv注册区域，再on+sv重复注册，观察此安装能否保留两种对象，不能预设它有效。任务调用包括待实测的`$set_gate_level_monitoring`、`$set_toggle_region`、`$toggle_start`、`$toggle_stop`、`$toggle_report`。report timeUnit与precision均为1fs，避免nominal150下小数ns驻留时间丢失。`probe.json`只在实际SAIF的孤立窗口与以下已知电路精确吻合时给出`VERIFIED_SINGLE_WINDOW`：

- clk周期10ns，DUT每上升沿翻转q并增加4bit计数器，初值均零。
- 首窗口[22,62)ns与第二窗口[82,122)ns，时长各40ns，中间20ns不计。
- 各窗口clk的TC=8、T0=T1=20ns；q与count[0]的TC=4、T0=T1=20ns；count[1]的TC=2。
- count[2]首窗口T0/T1=13/27ns、第二窗口33/7ns，TC均1；count[3]首窗口40/0ns、第二窗口0/40ns、TC均0。
- 无中间report的多窗口若累积，DURATION必须80ns、计数与两窗口逐项求和一致；不把含20ns暂停间隔的100ns视作正确累计。
- `first_repeat.saif`与停表后再等1ns的`after_idle.saif`用于观察report是否清空、stop后时长是否继续增加。无法识别的多窗口/report语义原样记录，不推广到正式任务。

最稳妥的正式配方是**每个任务一个新仿真进程，只开启一次SAIF窗口，退休后停止并报告一次**，共12份SAIF。这样无需依赖`start/stop`多窗口累计或`report`是否清空。不能用两个累积SAIF逐项相减：那会混淆初始电平、持续时间和未知态。微探针通过只证明此安装与此配方的SAIF能力，不证明全SoC映射、SRAM功耗或比赛合格。

实际第一轮服务器结果已经取回并保留在`activity-server-probe-01/`：VCS Q-2020.03-SP2-6的debug/coverage均只报告clk，DURATION=40ns、TC=8、T0=T1=20ns正确；多窗口DURATION=80ns、TC=16且重复report保持数据。但q/count完全缺失，两个配方均正确判FAILED。原SAIF注释说明未指定监控策略而默认只监控nets，故不能把它改判完整活动成功。`manifest.json`保留原始源SHA `0185c85e251196c4e528372d91f1a431715482d8a37c840b0637d1143dabcac2`及每份原始日志/SAIF的SHA。新五策略需要第二轮实际服务器探针，尚未据手册宣布通过。

[厂商VCS MX User Guide（公开镜像）](https://www.francisz.cn/download/vcsmx_ug.pdf)区分on/rtl_on的net与reg监控并列出sv扩展；这些只是候选调用依据。本安装的对象覆盖与时长仍由实际probe判断，尤其不能接受clk-only文件。第二轮最小单编译命令可在上述probe命令后加`--recipe debug --monitor-policy all`并选新的02输出目录。

## 正式TB与边界契约

需由独立的全范围TB实例化`xu_soc_ppa_top`，内部`u_soc`保留完整E203/加速器/互连/TCM，`u_shared`包含512KiB真实宏。初始化器、测试向量与scoreboard在PPA顶层之外。活动选择整个PPA实例及全部后代，不能只选择该实例端口，也不能只选加速器。宏功能模型的所有输入端口须可观察；模型中未综合的存储数组无需当作标准单元门功耗叠加，但不得因此漏掉宏的端口活动与Liberty内部功耗。

每个新进程先做ITCM一次装载、平台复位和本任务输入/参数准备，再使任务缓存无上一任务数据；**本任务传输至共享SRAM之外加速器缓存的加载仍在正式窗口内**。实际正式任务数据身份与缓存重载事件需留证。开始事件为首次输入/参数共享读命令接受；结束事件为最后Y写响应退休。软件调度、总线等待、权重/X/bias加载、计算和Y写回均处于窗口。

新TB须明确物理时间契约。旧TB计数器`last-first+1`是包含两端采样沿的周期数，而其旧`ACTIVITY_BEGIN/END`时间差是`(cycles-1)*4ns`。本工具采用物理事件间隔`[begin_tick,end_tick)`，要求SAIF DURATION与此时间差精确相同，不偷偷多补或少扣一周期。若后续正式评测对周期采用其他约定，吞吐及能量报告须同时解释并对齐。结束沿后的HOST通信/下一任务初始化不计入。

在同一进程的边界日志中保留以下机器可读原始行；task为官方任务身份，不靠文件顺序猜测：

```text
XU_CACHE_RELOAD task=0 done_before_begin=1 scope=shared_fixture
XU_ACTIVITY_BEGIN task=0 tick=123456
XU_ACTIVITY_END task=0 tick=654321
```

该marker只证明共享fixture预加载完成，不证明加速器缓存物理清零。正式审计还需独立cache_review绑定实际任务/config/SAIF，证明任务前缓存失效、窗口内完整上传以及无跨任务复用。当前固定TB若只有每任务完整覆盖但缺任务前失效证据，应记录未完成；每任务新进程从reset开始是后续可验证方案。不能为了满足审计手工添加标记到旧日志。tick的时间单位另存manifest。仿真HF参考钟直接使用150MHz，SDC、库/PVT与功耗分析一致；1fs绝对目标累计调度可使每条边相对理想时刻误差小于1fs，避免每半周期独立舍入后随百万周期累积相位偏移。LF/JTAG等按固定平台实际情况驱动并披露。工具会比较SAIF中真实HF钟TC与记录周期，而非仅相信150MHz文字标签。旧4ns活动若需研究性缩放，应另存原始及变换证据；本版正式能量审计拒绝隐式5/3缩放。

## SAIF不支持时的无大VCD磁盘后备

`vcd-to-saif`逐行处理VCD，不保存事件列表，只为选定完整层级的每位保持当前电平、上次时间及T0/T1/TX/TZ/TC。因此主存随信号位数增长，磁盘输出随信号位数增长，均不随仿真周期数线性膨胀。SAIF仍可能包含较多宏模型信号；不能声称零开销。完整SoC数字活动不可裁成顶层端口来节省空间。

先对现有文件转换：

```bash
python3 tools/scripts/xu_soc_activity.py vcd-to-saif \
  --vcd full-soc-task0.vcd --scope tb_xu_soc_ppa/u_dut \
  --begin BEGIN_TICK --end END_TICK \
  --saif task0.saif --out task0-conversion.json
```

`--vcd -`从stdin消费；命名FIFO可避免全SoC VCD落盘。示例中的SIMV命令需换成已验证的专用全SoC TB命令，并由它将完整PPA层级写到指定FIFO：

```bash
mkfifo full-soc-task0.vcd
python3 tools/scripts/xu_soc_activity.py vcd-to-saif \
  --vcd full-soc-task0.vcd --scope tb_xu_soc_ppa/u_dut \
  --begin BEGIN_TICK --end END_TICK \
  --saif task0.saif --out task0-conversion.json &
converter_pid=$!
SIMV_WITH_FULL_SCOPE_FIFO_DUMP > task0-simulation.log 2>&1
wait "$converter_pid"
rm full-soc-task0.vcd
```

上述固定数值begin/end适用于先测窗口再复放的冻结、确定性仿真；两个回放的边界日志、配置及输入身份必须一致。首次边界未知时先做不记录波形的同配置功能/性能运行以取得时间，再做活动复放，仍保留并比较两次边界。FIFO生产者与消费者须同时管理超时和退出码；消费者失败时终止生产者，不能让VCS永久阻塞在FIFO。此示例不管理远端会话，工具本身也不调用SSH/FTP。

转换保留原TIMESCALE、层级、bus上下界及alias；所有bus逐bit写入SAIF，TC只统计窗口内已知0↔1转换，X/Z驻留时间保持为TX/TZ。`$dumpvars`/`$dumpon`快照不伪造TC；窗口内停dump或VCD未覆盖结束时间直接失败。begin处转换计入TC，end处转换不计。时间从原VCD读取，未做频率缩放；转换JSON记录完整输入流SHA、字节数、作用域、边界、位数和输出SAIF身份。非数字模型对象(real/string/event)逐项列出，不默默冒充已覆盖硬件。该转换器已与真实Icarus微探针及手算逐bit比对；生成SAIF仍需在服务器PT实测读入/映射，不能把host语法自检当成PT验收。

## 每任务PT与覆盖检查

每个任务启动干净PT会话，读取同一冻结网表、SDC、同库同PVT；以**averaged**模式读取本任务SAIF。`read_saif`的精确参数先保存服务器安装自带`help/man read_saif`并实测，不凭记忆生成未经验证的API。SAIF根路径与网表实例名不同，必须显式记录strip/map策略及其报告。PT网表中的`u_soc`/时钟分频与宏边界应保留，使SDC和活动映射可重放。

每任务至少保留：

1. SAIF读入日志、映射失败/未匹配对象报告、传播前后switching/static-probability coverage、power与hierarchy报告、单位报告。
2. CPU、加速器、互连的直接文件/传播/默认/未知活动来源；综合网表新节点允许传播，但须披露比例并检查顺序单元和时钟门控端。默认CPU=0不是省空间策略。
3. ITCM、DTCM、共享和权重SRAM各组的宏个数/实例，所有读写/使能/时钟/地址/掩码/数据输入的活动覆盖，宏输出映射，以及实际Liberty是否有可用内部功耗/漏电表。四组宏的internal+switching+leakage报告均须有身份。未注释或无功耗表的宏不得按零；必须补齐或明确未完成，不能标正式结果。
4. parasitic/wire-load状态。暂无SPEF或wire-load时明确为相应布局前估算，不借用了其他候选的寄生。

SAIF聚合可大幅降低磁盘成本，但不保留事件相位和逐瞬态功耗，因此本流程只做每任务averaged功耗和总能量，不声称波形级峰值或精确毛刺功耗。RTL活动映射到综合网表仍有映射/毛刺偏差；门级活动与门级/等价证明是更强的后续证据。

## 十二任务能量审计入口

```bash
python3 tools/scripts/xu_soc_activity.py energy frozen-task-energy.json \
  --out twelve-task-energy.json
```

输入schema为`xu-soc-activity-energy-v1`。本机host测试的`EnergyEvidenceTests.fixture`给出完整、可执行的结构示例，数据明确是host合成fixture，禁止作为正式结果。实际manifest包含：

- `configuration`：`nominal_hz=150000000`、`power_method=averaged`、`pvt`、`interconnect_model`；netlist/constraints/firmware/testbench的绝对路径与SHA；带`role=standard_cell/sram`的同角库身份；四组memories的name/logical_bits/macro_count；七个activity_scopes的name/完整prefix；`hf_clock_path`。
- 七作用域名称为cpu、accelerator、interconnect、shared、itcm、dtcm、accelerator_weights。prefix是SAIF中的精确`/`层级路径，各作用域须至少两信号并具有观测TC；SRAM端口恒定输入允许TC=0，宏组总体活动不能缺失。
- `tasks`严格为0..11各一次。每条绑定`configuration_sha256`（configuration规范JSON的SHA，函数`canonical_hash`），SAIF、输入清单、共享fixture预加载日志、边界日志和cache_review的身份；window保存begin/end tick、timescale_seconds、hf_period_seconds、明确start/end事件与`convention=edge_to_edge`。
- `power`保存正数`total_w`（显式瓦特，不能混mW）、原始report、activity_before/activity_after、人工annotation_review的身份，`unannotated_policy=propagate_and_review`，以及`sram_review`文件身份。工具校验原始文件SHA，但不把任意文字报告当成自动审查通过。
- cache_review JSON：schema `xu-task-cache-policy-review-v1`、status `REVIEWED`，绑定task_id/configuration_sha256/saif_sha256；task_cache_invalidated_before_begin、complete_parameter_upload_inside_window、no_cross_task_reuse均须为true，并有非空evidence原始文件身份。shared_fixture标记本身不能代替此审查。
- SRAM审查JSON：schema `xu-sram-power-coverage-v1`、status `REVIEWED`，绑定saif_sha256/netlist_sha256/library_sha256；四组groups均含name、expected_count、observed_count、library_power_modeled_count、missing_input_pin_count、unknown_input_pin_count、total_power_w。后三类计数须表明宏完整、输入无缺失/未知，四组不重叠宏功耗之和不得大于全SoC功耗。此审查由实际PT/SRAM库结果产生。

程序拒绝缺任务、混配置、窗口与SAIF时长不符、4ns源时钟、缺CPU/总线/任一SRAM作用域、宏无功耗模型以及把未注释活动按零处理。它同时报告各作用域的未知bit-time比例，保留原始coverage供人审查；普通组合节点依赖传播不能包装成100%直接文件注释。

对每任务使用`E_i=P_i*t_i`，最后输出`sum(E_i)/12`焦耳/任务及`sum(E_i)/sum(t_i)`的duration加权平均瓦特。不能对12个功耗先做无权平均后乘另一个时长，也不能用任务数相同推导任务时长相同。该入口输出固定状态`AUDITED_ESTIMATE_NOT_CONTEST_QUALIFIED`：身份和算术检查通过不替代数值、STA、SRAM功耗表、PT覆盖和综合前后功能证明。

## 已完成的本地验证

`activity-host-evidence-02/host-tests.log`保存最新版7项通过（第一版本地证据原样留在activity-host-evidence），覆盖真实Icarus SV→VCD→SAIF→手算每位比对，bus升/降序与aliases、Z驻留、边界TC、dump快照、dump空洞拒绝、SAIF驻留时间不符拒绝、12任务不同时长的正确加权，以及缺任务/混配置/错误频率/缺作用域/无SRAM模型拒绝。证据目录的两个SAIF均为微探针40ns，不是SoC或功耗测量。`manifest.json`保存源文件及证据SHA；VCS/PrimeTime能力和正式12任务未由这组host证据证明。
