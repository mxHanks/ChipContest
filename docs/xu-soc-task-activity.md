# xu 十二任务独立全SoC SAIF采集器

`tools/ppa/xu_soc_task_activity.py`复用未修改的`xu_soc_ppa_verify.generate_tb(True, 'nominal150')`、固件构建、整数golden和性能契约。它准备同一份完整SoC、336个真实厂商SRAM宏、signed16/40/48配置，编译一次VCS，每个真实任务启动一个新进程，每进程只采集一个窗口。工具不调用远程服务，不修改固定平台、原TB、固件或厂商模型，也不把厂商模型复制进仓库。

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

默认固件配置就是上述`bias-hw-window/-O2/both-unroll-no-masks`。可选`bias-hw`保留完整bias缓存上传证明；其他已有schedule参数会明确拒绝，因为其首次START前不具有完整256项硬件bias上传，不能冒用同一证明。工具固定采集全部12项，没有静默只采layer0的`--tasks`选项。`--prepare-only`执行完整fixture/golden、固件构建、TB生成和12任务映射，随后以`PREPARED_NOT_SIMULATED`退出；不会运行VCS。

子仓必须为`f49a5fc914971426bd4530db39e270a84b41139f`、与主仓gitlink相同，且`rtl/e203`无修改或未跟踪文件。每次采集均使用同一ELF/固件镜像、TB、VCS二进制、RTL、厂商模型、目标网表和约束；SHA与编译/执行argv均写入结果。工具在构建和每次仿真前后复核这些文件以及所有原始/映射tensor和任务manifest，拒绝中途改变。所有工具调用关闭stdin。Python使用3.6兼容语法和标准库，不使用`text=True`或`capture_output`。

## 实际任务映射

单任务固件/TB的`+TASKS=1`只访问`layer_00`。采集器为global task i新建`task_ii/vectors/layer_00`，将**真实`layer_ii`的x/w/bias/y四个原始文件逐字节复制过去**。`input-manifest.json`同时保存global ID、原始layer名称、模拟器local layer名称以及四个文件各自的原始路径/SHA和映射路径/SHA。运行参数另传`+XU_GLOBAL_TASK=i`；活动/缓存日志使用global ID，原scoreboard和性能记录保留local layer0，二者不混淆。12份SAIF由12个全新进程、各自复位和ITCM/共享fixture准备产生，不继承前一任务的加速器状态。

## 监控配方和物理窗口

使用实际服务器微探针已经验证的唯一完整配方：`-debug_access+all`，`$set_gate_level_monitoring("rtl_on")`，`$set_toggle_region(tb_xu_soc_ppa.dut)`，一次`$toggle_start()`、一次`$toggle_stop()`、一次`$toggle_report("task.saif",1.0e-15,"tb_xu_soc_ppa.dut")`。原始服务器探针见`docs/validation/xu-score-s0-soc-20261102/activity-server-probe-02/`；不使用失败的默认nets-only或不支持的sv扩展策略。

start直接插入原性能观察器首次输入/参数共享读命令接受的分支；stop直接插入最后Y写响应退休的分支。两者在与`XU_ACTIVITY_BEGIN/END`相同的原采样沿执行，没有添加`#delay`、额外等待沿或额外包含周期。日志/SAIF统一按1fs时间戳的物理`[begin,end)`核对；原性能周期数仍是含首尾的`last-first+1`，两种口径分别保存。HF使用原生成器nominal150绝对目标排程、LF为标称32.768kHz，原静态PLL/bypass断言和端点模7背压断言保留。

监控范围是完整`dut`及后代，包含CPU、互连、加速器、ITCM/DTCM/512KiB共享/权重SRAM。采集器严格解析SAIF驻留时间、核对窗口时长和真实HF钟TC，并检查作用域存在/活动及四组宏实例数32/32/256/16，共336个。**这些存在性检查不是PT映射覆盖或宏功耗表审查**；SRAM输入端口未知态、活动传播、Liberty内部功耗和网表对应仍需原始PT报告及独立审查。

## 缓存证据和待审项

新增观察器只读取已接受的ICB命令及原fixture，不驱动SoC。它在窗口开始检查`cache_enable=0`、idle、无先前上传和START；拒绝窗口外W/bias/X数据写入。窗口内逐地址检查并比对实际fixture：16384个W地址均完整上传一次；256个bias的5个字节均完整上传；每个X行的64个地址均完整上传；每次START前W和bias已完整、当前X行完整、cache已启用且group按0..31顺序；最终要求99行、6336个X和3168次START。缺地址、重复、字节mask不全或数值不符均fatal。原完整SoC逐字Y scoreboard、HOST顺序和CPU完成检查仍运行。

这证明本进程无上一任务、reset后cache关闭以及窗口内完整数据覆盖。`XU_CACHE_RELOAD scope=shared_fixture`只表示共享fixture准备，**不等于清空加速器缓存**。XRowBuffer和BiasBankCache的数据Reg没有复位清零；原厂商模型的mem零初始化受`INITIALIZE_MEMORY`条件控制，默认配方没有该define。因此结果始终将初始物理清空和正式缓存失效政策标为`REVIEW_PENDING`，不生成伪造的`REVIEWED` cache review。

`--initialize-vendor-memory`显式加入厂商支持的`+define+INITIALIZE_MEMORY`，保留原厂商文件字节，并写入单独的冻结配置SHA。这是另一个采集配方；只涉及该厂商模型支持的SRAM初始化，不能据此宣布X/bias Reg已清空或正式缓存政策通过。当前工具不增加窗口前的MMIO清零固件、不使用force、不更改任务窗口。是否满足指南中的缓存失效语义需后续独立审查。

成功采集状态为`COLLECTED_12_TASKS_REVIEW_PENDING`；每任务为`COLLECTED_REVIEW_PENDING`。它们不是能量、PPA、STA、门级一致性或比赛资格PASS。后续应按同一配置分别执行每任务PT averaged功耗、映射/四组SRAM功耗和cache review，形成`xu_soc_activity.py energy`所需的独立能量manifest；采集器JSON不是该能量manifest。

## 本地证据

新增host测试入口：

```sh
python3 -m unittest discover -s tests/host -p test_xu_soc_task_activity.py -v
```

5项测试覆盖全部真实12层文件映射/原始SHA、global/local ID混淆拒绝、精确插桩锚点、合成SAIF的336宏/时长拒绝，以及实际Icarus运行被采集器使用的同一个SV观察器。Icarus正例上传16384W/256bias/6336X并启动3168次；缺W、缺bias、缺X、错误W数值、窗口前上传五个负例均fatal。另以原始私有厂商模型对完整生成的336宏SoC TB做Icarus elaboration（仅以`XU_TASK_ACTIVITY_HOST_CHECK`去除Icarus不支持的SAIF系统任务），并执行12层整数golden和真实RISC-V固件编译。证据保存在`docs/validation/xu-score-s0-soc-20261102/task-activity-host-01/`。这些不是VCS完整SoC执行或全SoC SAIF/PT测量；Python3.6做了语法兼容检查，未在真实Python3.6解释器运行。
