# xu 独立全SoC SRAM验证边界

`xu_soc_ppa_top.sv`保留原`e203_soc_top`的37个真实pad端口，通过`u_soc`实例化未修改的固定SoC，并将`EXTERNAL_SYSMEM=1`的ICB端口连接到`u_shared`的512KiB SRAM。共享端点使用`hfextclk`和外部复位，保持参考TB的周期和复位口径。综合时pad是顶层真实输入/输出，不能将仿真TB里的常量pad驱动用于综合。

`xu_soc_ppa_verify.py`直接读取固定RTL源码，输出到独立目录；不执行`make clean/install`、不修改固定RTL/TB/固件、也不读写`build/e203`的仿真缓存。固件构建、fixture SHA核验、独立整数golden检查及性能契约检查复用`e203_soc.py`，在新输出目录执行。

参考配置运行原`tests/e203/tb_accel_soc.sv`。`harness`配置仅把其共享端点移入top。`macro`配置进一步以`xu_sirv_sram_adapter.sv`替换TCM/共享RAM的`sirv_sim_ram`定义，以`xu_weight_sram_adapter.sv`替换16个权重RAM。小debug RAM仍使用adapter中保留的原行为数组，综合将计入标准单元。权重adapter逐字复制历史已测源，SHA256为`86b49e6279e9e9ac2c91467028608be8e3ca1caadb811ddd09d379311730d707`；EMA/EMAW的指定PVT取值仍须单独核实。

变体TB由受保护锚点生成，原TB漂移会报错。性能观察器、计数边界、输出逐字比对、最后Y写响应退休、HOST ACK先后关系以及CPU gp完成检查全部保留。端点`cmd_ready`在每个复位后时钟沿与原`cycles%7`表达式逐拍比对，不能隐藏新增等待或模7相位变化。比较结果要求每层总周期、固件周期和全部PERF计数相等；如果不同，保留各配置日志并返回FAIL。

预加载只发生在非综合TB：ITCM从原`program_bytes`构造64位字，共享SRAM从原`ram`影子数组加载；未初始化位的X状态按原数组保留。DTCM不预加载，权重仍完全由CPU正常上传。指定厂商`ARM_UD_MODEL`模型的物理数组为`mem[0:255]`、每行64位，逻辑16位字地址`A`的数据位`b`映射为：

```
mem[A >> 2][4*b + (A & 3)]
```

生成器按此映射将4个逻辑16位字转置成一行，并通过常量bank/lane层级写`macro_storage.depth_bank[b].width_lane[l].macro.mem[row]`。没有将内部物理数组误当作1024×16，也没有运行中强制信号。每次运行记录vendor模型绝对路径、SHA、fast functional选择和全部实际RTL源SHA；vendor文件不复制到仓库或输出源码树。

`tb_xu_vendor_preload.sv`通过厂商模型真实Q口回读全部1024个逻辑字，并用4个含X的字检查四态位转置。可用`iverilog -g2012 -DARM_UD_MODEL -s tb_xu_vendor_preload -o preload.vvp tools/ppa/tb_xu_vendor_preload.sv /absolute/private/RAMSP1024X16.v`及`vvp preload.vvp`独立执行；这只验证preload路径，不代替四态完整SoC回归。

真实厂商宏的四态筛选示例（输出目录必须不存在，默认模拟器为VCS）：

```sh
python3 tools/ppa/xu_soc_ppa_verify.py \
  --out build/xu-score-s0/soc-macro-real1-new \
  --variants reference harness macro --sim vcs --tasks 1 \
  --firmware-schedule bias-hw-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks \
  --vendor-model /absolute/private/RAMSP1024X16.v
```

单任务通过后改为`--tasks 12`执行完整12层回归。VCS进程使用关闭的stdin，不依赖交互终端。`--sim verilator --variants reference harness`只用于二态开发筛选；本工具拒绝Verilator与`macro`组合，因为真实`ARM_UD_MODEL`的X/Z时钟检查需要四态语义。先前停止的Verilator宏实验及其原始日志保留为未完成或失败，不能解释为完整宏SoC PASS。

默认`--clock-mode reference4ns`保持原4ns HF、66ns LF和绝对120ns释放复位的功能比较口径。TB在1ns后预加载以避开厂商time-zero初始化，复位使用绝对目标时间，避免把该1ns加入原有复位延迟。正式时钟开发检查另用`--clock-mode nominal150`：HF半周期按`index*(10/3 ns)`绝对目标排程，精度1fs，无固定舍入半周期的累计漂移；LF半周期15258.7890625ns（标称32.768kHz），绝对200ns释放复位且断言30个HF复位上升沿，保持端点模7相位2。任务期间逐拍检查静态PLL bypass/divby1及寄存器复位配置；该检查不代表动态PLL模式或STA通过。

`nominal150`记录每任务`PPA_WINDOW_BEGIN/END`和`XU_ACTIVITY_BEGIN/END`，边界仍为首个输入/参数读请求接收至最后Y写响应退休。功能计数为含首尾周期数，物理时间差为`(cycles-1)*20/3 ns`并容许1fs量化；结果分别保留这两种口径。`XU_CACHE_RELOAD scope=shared_fixture`仅表示TB任务fixture已重装，未证明加速器缓存物理清空。

`--waves`对新top开启任务窗口内完整SoC VCD；参考配置仍遵从原TB的加速器窗口导出。活动标记不等于SAIF、门级映射覆盖或功耗报告。完整四态、mapped GLS/等价、150MHz STA、全范围活动覆盖/功耗仍需独立证据，不能由本工具PASS推定完成。`tb_xu_nominal_clock_probe.sv`只检查长时间HF相位与复位边沿，不是完整SoC证据。
