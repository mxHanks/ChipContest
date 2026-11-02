# xu 独立 CPU-MMIO 任务前清空候选

本 helper 生成新的固件 wrapper 和只观察的 TB 声明，不修改既有 collector、固件、RTL、厂商模型或历史结果，也不默认改变 baseline。状态为 `GENERATED_NOT_FULL_SOC_SIMULATED`，正式缓存政策接受状态保持 `REVIEW_PENDING`。本地 Icarus probe 不是全 SoC、厂商 SRAM、12 任务、功耗、时序或比赛资格的通过证明。

指南印刷第11页要求每个任务从输入和参数开始装载计时，直到结果全部写回，任务开始前清空任务数据与参数缓存，参数装载、总线等待、E203 调度计入。指南未定义“清空”是否接受仅逻辑失效。当前 `cache_enable=0` 只切换 bias 输入，不失效 W/X；无上个任务的 fresh process 与首次计算前完整覆盖可以证明没有跨任务数据复用，但不能充当物理清空证明。原厂商 `INITIALIZE_MEMORY` 条件不是默认零初始化，也不清空 X/bias Reg。

本候选使用实际公共 MMIO 将全部加速器任务数据/参数内容写为零。共享 SRAM 中的输入 fixture 仍是任务装载的外部来源，预置 fixture 不是清空加速器缓存。清空过程中不读取任务 X/W/bias，不计算或预装本任务的任何参数；本任务完整装载继续位于原计时窗口中。为避免混淆，清空阶段的时间和活动应另外保留，不能把它改名为装载或丢弃其证据。是否接受该任务前清空配方仍需正式审查。

## 生成新的配方

在仓库根目录执行，显式给出已核实的 frozen main SHA256，输出目录必须不存在：

```bash
python3 tools/ppa/xu_task_clear_protocol.py \
  --main /absolute/repo/tests/e203/firmware/main.c \
  --main-sha256 <explicit-verified-main-sha256> \
  --out /absolute/new-candidate-clear-recipe
```

产物为 `xu_clear_main.c`、`xu_clear_observer.svh` 和 `clear-recipe.json`。默认 observer 路径为现有 TB 的 `` `ACCEL ``；独立 wrapper probe 可传 `--accel-hierarchy dut`。SHA 不符直接拒绝生成。wrapper 通过绝对路径 include 原 main，将其符号改名为 `xu_frozen_task_main`，先执行清空，再调用原 main；只支持 `TASKS=1`、每任务 fresh reset process。它不是对原 main 的源文件编辑。

构建候选时，沿用明确冻结的 gcc、架构、ABI、优化、实验宏、link.ld、start.S 和 accel.c 参数，仅以生成的 `xu_clear_main.c` 替代原编译命令中的 `main.c`。例如保持原 `bias-hw-window/-O2/both-unroll-no-masks` 配置时，应保留其全部 `-D` 选项。现有 `soc.compile_firmware()` 的源列表固定，不会自动选用本候选；不得直接运行旧 collector 后宣称已接入清空。编译前后重新核对原 main/header/start/accel/link 的 SHA，记录生成代码、observer、全部构建输入、ELF/image、RTL/宏模型、命令和配置 SHA。不得只复用旧固件身份。

清空前只读取 ID、capability 与 STATUS 进行 ABI/idle 检查。清空成功路径精确接受以下 33,697 个完整字 MMIO 写：

| 内容 | 公共寄存器偏移 | 写次数 |
| --- | --- | ---: |
| 禁用 bias cache | CACHE_CTRL `0x40` | 1 |
| 全 W | 8 次 W_BANK `0x1c`；16,384 次 W_ADDR `0x20` 与 W_DATA `0x24` | 32,776 |
| 全 signed40 bias cache | 每列 CACHE_ADDR `0x44`、LO `0x48`、HI `0x4c` | 768 |
| 8 个 legacy signed40 bias | 每 lane INDEX `0x28`、LO `0x2c`、HI `0x30` | 24 |
| 全 X row buffer | 64 次 X_ADDR `0x14` 与 X_DATA `0x18` | 128 |

末尾 `fence iorw, iorw` 保持 I/O 顺序。33,697 是写事务数量，不是 E203 实测周期；指令、仲裁与等待要由实际仿真计数。wrapper 在接受 W_DATA/X_DATA 后一拍才将 strobe 驱动到存储，因此“最后一写已接受”不足以证明已清空。新 observer 在首个任务 source accept 检查 strobe 已排空。

fresh reset 已将 MacPE.ACC、DotProductEngine.resultReg 和完成控制复位到零，故不增加 dummy MAC。指南未单独要求把 SRAM 输出 Q 或地址控制寄存器复位为零；本配方覆盖可寻址的 W、X、bias 数据/参数内容，不虚构额外要求。

## 显式接入候选 TB

将生成的 observer 声明插入 TB module 内。它只改变 TB 自身计数器，不驱动 DUT。每个复位释放后的观察边沿恰好调用一次：

```systemverilog
reg xu_payload_phase;
// Same task-source read predicate as the chosen task-window observer.
// The fixed original uses shared acceptance and the range [BASE, BASE+0x18800).
xu_observe_task_clear(shared_accept && cmd_read &&
                      cmd_addr>=BASE && cmd_addr<BASE+'h18800,
                      xu_payload_phase);
if (xu_payload_phase) xu_observe_upload();
```

上述是替换“调用位置”的示意，不是再额外增加一次 payload observer 调用。原 collector 目前会在窗口内/外分别调用 `xu_observe_upload()`；显式接入新配方时需两处分流，每边沿总共一次。原 payload observer 内部的所有完整性、fixture 数据、mask、重复项、group 顺序和窗口检查保持不变，也保留最终 16,384 W、256 bias、6,336 X、99 rows、3,168 START 的计数门槛。清零数据不进入 payload 计数器。

在首个 source accept 上，clear observer 要求所有地址和字节覆盖完整、恰好 33,697 次写、cache disabled、busy/core_start 为零、W/X pending strobes 为零，然后输出 `XU_TASK_CLEAR_OBSERVED`。缺清空项、重复或非零清空、partial mask、未知地址、非允许的清空前 MMIO 或过早 source accept 均为失败。它接受首个 source accept 后的写交给原 payload observer，不提供第二套弱化的 payload 校验。

现有 payload 窗口从首个 source **accept** 开始。本 helper 沿用该 predicate，未自行更改测量定义。另须审查首次请求若在 accept 前被阻塞，等待周期是否已计入；若采用首个 source **request** 作为正式起点，清空和排空证明也必须提前到该请求之前。不得因新清空配方将本任务装载或等待移出计时范围。

## 本地验证

```bash
python3 -m unittest discover -s tests/ppa -p test_xu_task_clear_protocol.py -v
```

测试用真实 `accel_icb_slave` 与 Chisel 计算模块、仓库原有行为 SRAM，通过公共 MMIO 发出全部零写，每个响应故意停顿一拍。无 DUT backdoor 写或 force；层级访问仅观察。开始时抽查 W/X/bias 实际未知态，清空后逐项检查全 W/X/bias/legacy bias 为零；随后写入带符号的小算例，经实际计算和结果 MMIO 检查 8 lanes。负例包括漏最后一个 W_DATA、bias HI 缺 mask、非零 W 清空、最后 X strobe 未排空。另对生成的 C wrapper 使用 RISC-V gcc 编译，SHA 不符必须拒绝生成。

这些 probe 不运行 E203，不模拟完整任务 payload 上传，也不使用私有厂商模型；不能替代实际新固件全 SoC 的清空/窗口/最终 Y 写回验证。完成该端到端验证并保存同一冻结配置的活动之前，仍保持 `REVIEW_PENDING`，不写 cache-policy、12-task、T/E/A 或 official qualification PASS。
