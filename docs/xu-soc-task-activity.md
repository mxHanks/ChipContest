# xu 十二任务独立全SoC SAIF采集器

`tools/ppa/xu_soc_task_activity.py`复用未修改的`xu_soc_ppa_verify.generate_tb(True, 'nominal150')`、固件构建、整数golden和性能契约。它准备同一份完整SoC、336个真实厂商SRAM宏、signed16/40/48配置，编译一次VCS，每个真实任务启动一个新进程，每进程只采集一个窗口。默认仍使用原固件与accept起点；显式`--clear-task-before-window`才选用新增CPU-MMIO清空wrapper与request起点。工具不调用远程服务，不修改固定平台、原TB、固件或厂商模型，也不把厂商模型复制进仓库。

默认任务集仍是仓库SHA验证过的真实checkpoint silence样本的12个独立FFN1层，**不是组委会正式12性能任务或600样本精度评估**。`--vectors`可以指定另一个完整`layer_00..layer_11`目录；每个任务的6336个X、16384个W、256个bias和25344个Y均先做现有独立整数golden核验。

## 服务器使用

输出目录必须不存在。`--netlist`和`--constraints`填写同一冻结全SoC DC/PT流程的实际网表、150MHz SDC；本工具绑定其SHA但不运行网表，也不把文件身份当作RTL/网表对应或等价证明。示例路径须替换为本次实际路径：

```sh
python3 tools/ppa/xu_soc_task_activity.py \
  --out /absolute/new/xu-soc-task-activity \
  --vendor-model /absolute/private/RAMSP1024X16.v \
  --netlist /absolute/frozen/full-soc-mapped.v \
  --constraints /absolute/frozen/full-soc-150mhz.sdc \
  --vcs /eda/synopsys/vcs/vcs_2020.03-SP2-6/bin/vcs \
  --cross-prefix riscv64-unknown-elf- \
  --firmware-schedule bias-hw-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks
```

默认固件配置就是上述`bias-hw-window/-O2/both-unroll-no-masks`。可选`bias-hw`保留完整bias缓存上传证明；其他已有schedule参数会明确拒绝，因为其首次START前不具有完整256项硬件bias上传，不能冒用同一证明。默认采集全部12项。开发探针可传`--task-ids 0`或`--task-ids 0,7,11`；ID须递增、唯一且处于0..11，保留真实global ID，不重新编号。子集状态只能为`PARTIAL_PREPARED_NOT_SIMULATED`或`PARTIAL_COLLECTED_REVIEW_PENDING`，不能成为12任务通过。`--prepare-only`执行完整12层fixture/golden、固件构建、TB生成和所选任务映射；完整任务集以`PREPARED_NOT_SIMULATED`退出，不运行VCS。

子仓必须为`f49a5fc914971426bd4530db39e270a84b41139f`、与主仓gitlink相同，且`rtl/e203`无修改或未跟踪文件。每次采集均使用同一ELF/固件镜像、TB、VCS二进制、RTL、厂商模型、目标网表和约束；SHA与编译/执行argv均写入结果。`configuration.analysis_sdc_sha256`是实际`--constraints`字节的SHA，不能当作DC生成的`mapped.sdc`身份；本采集器不生成正式功率manifest。工具在构建和每次仿真前后复核这些文件以及所有原始/映射tensor和任务manifest，拒绝中途改变。所有工具调用关闭stdin。Python使用3.6兼容语法和标准库，不使用`text=True`或`capture_output`。

## 实际任务映射

单任务固件/TB的`+TASKS=1`只访问`layer_00`。采集器为global task i新建`task_ii/vectors/layer_00`，将**真实`layer_ii`的x/w/bias/y四个原始文件逐字节复制过去**。`input-manifest.json`同时保存global ID、原始layer名称、模拟器local layer名称以及四个文件各自的原始路径/SHA和映射路径/SHA。运行参数另传`+XU_GLOBAL_TASK=i`；活动/缓存日志使用global ID，原scoreboard和性能记录保留local layer0，二者不混淆。12份SAIF由12个全新进程、各自复位和ITCM/共享fixture准备产生，不继承前一任务的加速器状态。

## 监控配方和物理窗口

使用普通RTL服务器微探针已经验证的配方：`-debug_access+all`，`$set_gate_level_monitoring("rtl_on")`，`$set_toggle_region(tb_xu_soc_ppa.dut)`，一次`$toggle_start()`、一次`$toggle_stop()`、一次`$toggle_report("task.saif",1.0e-15,"tb_xu_soc_ppa.dut")`。原始服务器探针见`docs/validation/xu-score-s0-soc-20261102/activity-server-probe-02/`；不使用失败的默认nets-only或不支持的sv扩展策略。该微探针只证明普通RTL寄存器记录完整，并未证明带`celldefine`的厂商宏引脚也被记录。首次真实全SoC活动在DTCM范围检查处停止验证；宏引脚范围须用真实服务器专门探针核实，不能因RTL范围存在就放宽336宏与引脚检查。

默认配方start直接插入原性能观察器首次输入/参数共享读命令接受的分支；stop直接插入最后Y写响应退休的分支。两者在与`XU_ACTIVITY_BEGIN/END`相同的原采样沿执行，没有添加`#delay`、额外等待沿或额外包含周期。日志/SAIF统一按1fs时间戳的物理`[begin,end)`核对；原性能周期数仍是含首尾的`last-first+1`，两种口径分别保存。HF使用原生成器nominal150绝对目标排程、LF为标称32.768kHz，原静态PLL/bypass断言和端点模7背压断言保留。

监控范围是完整`dut`及后代，包含CPU、互连、加速器、ITCM/DTCM/512KiB共享/权重SRAM。采集器严格解析SAIF驻留时间、核对窗口时长和真实HF钟TC，并检查作用域存在/活动及四组宏实例数32/32/256/16，共336个。DTCM在当前寄存器热循环中可全程时钟关闭：它只有在配置明确声明静态范围、32个宏齐全且每个宏的CEN=1、CLK=0、RET1N=1在完整窗口内均为已知稳定值时，才记为`OBSERVED_KNOWN_STATIC_DISABLED`。未声明、缺宏、缺控制引脚或控制X/Z均拒绝。其他范围仍必须有真实TC；DTCM内部未知驻留时间另行保留，不能据此按零功耗计。**这些存在性检查不是PT映射覆盖或宏功耗表审查**；SRAM输入端口未知态、活动传播、Liberty内部功耗和网表对应仍需原始PT报告及独立审查。

## 缓存证据和待审项

新增观察器只读取已接受的ICB命令及原fixture，不驱动SoC。它在窗口开始检查`cache_enable=0`、idle、无先前上传和START；拒绝窗口外W/bias/X数据写入。窗口内逐地址检查并比对实际fixture：16384个W地址均完整上传一次；256个bias的5个字节均完整上传；每个X行的64个地址均完整上传；每次START前W和bias已完整、当前X行完整、cache已启用且group按0..31顺序；最终要求99行、6336个X和3168次START。缺地址、重复、字节mask不全或数值不符均fatal。原完整SoC逐字Y scoreboard、HOST顺序和CPU完成检查仍运行。

这证明本进程无上一任务、reset后cache关闭以及窗口内完整数据覆盖。`XU_CACHE_RELOAD scope=shared_fixture`只表示共享fixture准备，**不等于清空加速器缓存**。XRowBuffer和BiasBankCache的数据Reg没有复位清零；原厂商模型的mem零初始化受`INITIALIZE_MEMORY`条件控制，默认配方没有该define。因此结果始终将初始物理清空和正式缓存失效政策标为`REVIEW_PENDING`，不生成伪造的`REVIEWED` cache review。

`--initialize-vendor-memory`显式加入厂商支持的`+define+INITIALIZE_MEMORY`，保留原厂商文件字节，并写入单独的冻结配置SHA。这是另一个采集配方；只涉及该厂商模型支持的SRAM初始化，不能据此宣布X/bias Reg已清空或正式缓存政策通过。它与CPU-MMIO清空是独立选项；不使用force。是否满足指南中的缓存失效语义需后续独立审查。

## 显式CPU-MMIO清空与request窗口

新配方仅在传入`--clear-task-before-window`时启用。它调用`xu_task_clear_protocol.py`生成wrapper，以绝对路径include已冻结的原`main.c`，先清空，再调用原main；不编辑原固件、基线TB、RTL或厂商模型。构建沿用同一架构、ABI、优化、实验宏、link.ld、start.S和accel.c，仅将编译源main替换为`xu_clear_main.c`。结果保存真正参与编译的源列表、原main/所有固件输入、helper、生成observer、gcc/objcopy/objdump身份、gcc版本、精确argv、ELF/image及完整配置SHA。

清空通过公共MMIO执行33,697次完整字写：禁用cache一次、8个W bank选择、16,384个W地址和零数据、256项signed40 bias地址及低/高零数据、8项legacy bias地址及低/高零数据、64个X地址及零数据。地址/选择寄存器自然含非零值；33,697不是“每个wdata均为零”，也不是周期数。原accel.c在第一笔W源读之前还有`W_BANK=0`、`W_ADDR=0`两次目的地址设置；只允许这两次按原顺序、完整字的零值控制写，单独计数，不能作为清空写或提前payload装载。禁止此间任何W/X/bias数据写。

只观察的clear monitor每个复位释放边沿调用一次。它在首个有效任务X/W/bias共享读**request**上要求全地址/字节零写覆盖、恰好33,697次清空写、两次原目的地址设置、cache=0、busy/core_start=0、W/X strobe与MMIO响应排空，之后才打开SAIF。首次request被背压时也立即开始采集，检查请求地址/valid保持到accept，并记录`XU_SOURCE_REQUEST/ACCEPT`的cycle与1fs tick及实际等待周期。原payload observer随后每边沿一次，完整保留所有fixture、mask、重复、顺序与窗口检查；最终仍要求16,384 W、256 bias、6,336 X、99 rows和3,168 START。

`TASK_PASS`、`PERF_TASK`与`PPA_WINDOW_BEGIN/END`保留原accept起点和原始inclusive cycles，作为legacy诊断，不改写任何历史日志。新`XU_TASK_WINDOW`单独保存request/accept/end、initial_wait、formal inclusive/elapsed cycles，并要求formal inclusive等于原legacy inclusive加首次等待；实际SAIF按request至最后Y响应退休的物理`[begin,end)`验证。JSON的`activity_window.legacy_accept_window`保留旧窗口，`initial_source_wait_cycles`与`formal_*_cycles`明确区分口径。

`XU_TASK_CLEAR_BEGIN/LAST_WRITE`另存清空首/末实际写的cycle/tick；`pretask_clear`报告这段写跨度及末写到首request的间隔。该跨度不冒充整个清空函数的CPU运行时间；任务SAIF不含清空阶段，当前没有另行测量清空SAIF。正式缓存政策、能量和比赛资格仍为`REVIEW_PENDING`。

先在新的服务器副本上执行真实首任务探针，确认完整清空、request/accept、逐字Y、最终CPU完成和SAIF时长/范围后，再创建另一个新目录运行12任务；不覆盖旧结果。例：

```sh
python3 tools/ppa/xu_soc_task_activity.py \
  --out /absolute/new/xu-clear-task00-probe \
  --vendor-model /absolute/private/RAMSP1024X16.v \
  --netlist /absolute/frozen/full-soc-mapped.v \
  --constraints /absolute/frozen/actual-analysis.sdc \
  --vcs /absolute/vcs --clear-task-before-window --task-ids 0 \
  --max-cycles 4000000
```

该命令成功也只能产生`PARTIAL_COLLECTED_REVIEW_PENDING`。完成首任务运行后，去掉`--task-ids 0`并使用新的输出目录才是12任务采集。清空增加CPU指令和总线等待，必要时显式提高startup在内的`--max-cycles`/`--run-timeout`，不得据此更改测量频率或重标旧周期。

成功采集状态为`COLLECTED_12_TASKS_REVIEW_PENDING`；每任务为`COLLECTED_REVIEW_PENDING`。它们不是能量、PPA、STA、门级一致性或比赛资格PASS。后续应按同一配置分别执行每任务PT averaged功耗、映射/四组SRAM功耗和cache review，形成`xu_soc_activity.py energy`所需的独立能量manifest；采集器JSON不是该能量manifest。

## 本地证据

新增host测试入口：

```sh
python3 -m unittest discover -s tests/host -p test_xu_soc_task_activity.py -v
```

原5项测试覆盖全部真实12层文件映射/原始SHA、global/local ID混淆拒绝、精确插桩锚点、合成SAIF的336宏/时长拒绝，以及实际Icarus运行被采集器使用的同一个SV观察器。Icarus正例上传16384W/256bias/6336X并启动3168次；缺W、缺bias、缺X、错误W数值、窗口前上传五个负例均fatal。另以原始私有厂商模型对完整生成的336宏SoC TB做Icarus elaboration（仅以`XU_TASK_ACTIVITY_HOST_CHECK`去除Icarus不支持的SAIF系统任务），并执行12层整数golden和真实RISC-V固件编译。证据保存在`docs/validation/xu-score-s0-soc-20261102/task-activity-host-01/`。这些不是VCS完整SoC执行或全SoC SAIF/PT测量；Python3.6做了语法兼容检查，未在真实Python3.6解释器运行。


新增request/clear测试入口（厂商路径只读，内容不复制到证据目录）：

```sh
XU_TASK_ACTIVITY_VENDOR_MODEL=/absolute/private/RAMSP1024X16.v \
  python3 -m unittest discover -s tests/host -p 'test_xu_soc_task*activity.py' -v
```

新增检查包括真实公共MMIO全量清空及四个破坏负例，使用collector实际observer逐项检查W/X/bias物理内容与8-lane signed小算例；实际RISC-V wrapper链接/内存审计；首次request阻塞3周期后完成全部payload、禁止撤回/改址/窗口前数据写及缺失目的设置；真实layer7的prepare-only映射/明确PARTIAL状态；完整生成336宏TB的Icarus elaboration；静态DTCM的声明、已知idle控制与缺失/未知负例。13项测试的原始日志、实际构建命令、生成TB及源码/证据SHA保存在`docs/validation/xu-score-s0-soc-20261102/task-clear-activity-host-01/`。厂商模型只保留路径/SHA，不复制内容；二进制留在本地build目录。无本地VCS运行或全SoC SAIF/PT测量结论；实际服务器首任务及12任务结果须另存后再审查。


## 显式SRAM宏引脚观测

`--sram-pin-alias`使用[宏引脚观测工具](xu-sram-activity-alias.md)在DUT内绑定只读仿真observer，保留原DUT-only活动范围；只在该选项下添加VCS `-debug_region+cell`及生成的observer源。功能RTL、SRAM模型、时钟和内容均不改写。默认构建不添加observer。

每个任务原始`task.saif`保留字节及SHA，新生成`task-normalized.saif`和`task-normalization.json`。归一化要求336宏全部22512位的实测统计一一对应，保留全部X/Z/B停留时间、TC与其他原始活动；缺失、重名、源身份变化及native pin不一致均拒绝。VCS的精确`macro_0000.PIN`拼写只作有限命名兼容，不能用于任意推测层级。严格范围/时长/静态DTCM检查作用于新文件，原始文件不覆盖。

配置与每任务结果分别绑定observer、mapping、normalizer、原始及归一化SAIF身份。完整SoC实际VCS采集、PT映射覆盖、SRAM内部功耗、能量及资格仍须实测审查；合成host handoff测试不替代这些证据。先用`--task-ids 0 --clear-task-before-window --sram-pin-alias --max-cycles 4000000`在新目录验证首任务，通过后另开目录执行12任务。
