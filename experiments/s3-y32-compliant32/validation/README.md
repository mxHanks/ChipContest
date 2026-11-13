# 原32位System Bus / 64PE CPU开发验证

本目录是针对2026-11-13答疑的整改验证，不继承旧DMA64吞吐或PPA。生产宏为 `XU_MATRIX_DMA`、`XU_MATRIX_DMA_SYSBUS32`；禁止同时启用 `XU_MATRIX_DMA64`。旧CPU/LSU/BIU、原mem_fab及其在途配置保持不变。新DMA和CPU在原mem_fab入口前仲裁，所有请求经原fabric到32位共享口。

本机CPU TB启用 `XU_SYSBUS_TEST_LOADER`，其32位刺激源接在同一原mem_fab上游，不是SRAM侧门、层次tensor写或64位并访。生产包不含测试端口。答疑2规定加载环境由参赛队自行实现、不另提供示例。该自建环境的原SystemBus行为在本机验收；所复用原SoC与组委会平台工程的来源一致性仍须核查。

## 软件协议

控制MMIO基址`0x10042300`。ID `+0x00=0x444d4131`；cap `+0x4c=0x00082001`（8行、外部32位、X单16/32槽）。`CTRL +0x04=1`真实清零；`2`一行模式；`0x802`八行/64PE模式。状态`+0x08`：bit0 BUSY、bit1 DONE、bit2 ERROR、bit3 CLEAR_DONE；错误码`+0x0c`。

任务顺序：确认前任务完成、所有结果可见 → 写clear → CPU等待`!BUSY && CLEAR_DONE` → fence → 本任务X/W/bias经原SystemBus完整装载并等所有写响应退休 → fence → 写四个描述符 → fence → start → 检查ERROR/DONE → fence → 读取共享矩阵。第一次错误中止整任务，可能已有部分Y写入，禁止无条件重试；需要显式清理并重新提交。

| 描述符 | 缺省共享地址 | 内容 |
|---|---|---|
| X `+0x10` | `0xa0000000` | 6336个32位槽，每槽低16位signed INT16，25344B |
| W `+0x14` | `0xa0008000` | 8192个32位词，每词两个连续signed INT16，32768B |
| bias `+0x18` | `0xa0018000` | 256个64位槽，每槽signed40；低32、高8并符号扩展，2048B |
| Y `+0x1c` | `0xa0020000` | 99×256行优先、25344个独立Y32，101376B；完整未压缩 |

INT16输入/权重、signed40 bias、41位内部有界累加、原RNE9/Y32数值规则不变。每任务DMA必须15040读（W8192/bias512/X6336）、25344写/响应、3168结果POP、八行模式26624 MAC步。shared接口永远32位/mask4，内部合并两次真实W读取不增加外部带宽。

## 复现

需要RISC-V RV32 GCC、Verilator、g++，最多2核编译。通用向量入口位于相邻`numeric/`，不锁定旧silence哈希。只有x/w/bias进入DUT；y/y32仅独立oracle。开发整数向量必须明确`--dev`，不能当音频精度证据。

```sh
python3 -B experiments/s3-y32-compliant32/validation/run_cpu.py \
  --out build/compliant32-20261113/cpu-task0-NEW \
  --vectors build/compliant32-20261113/numeric/dev-vectors-r1 \
  --tasks 1 --warmup --jobs 2
```

单层完整PASS后复用同一个已冻结二进制/固件/RTL，执行完整12任务以及首DMA读、首源装载各31拍强制等待：

```sh
python3 -B experiments/s3-y32-compliant32/validation/run_followups.py \
  --base build/compliant32-20261113/cpu-task0-NEW \
  --vectors build/compliant32-20261113/numeric/dev-vectors-r1 \
  --out build/compliant32-20261113/cpu-followups-NEW
```

所有输出目录必须新建，禁止覆盖。每个run冻结全部RTL/TB/firmware/checker，记录ELF/image/binary/模型/向量文件及工具身份并验证未漂移。CPU启动代码沿用已有ITCM boot初始化，张量与结果无TCM加载或层次写入。共享endpoint是原32位逻辑，实例类型仅等价重命名以单独使用256个真实功能宏接口；不将通用功能宏模型称为官方PPA/时序模型。

## 计时及覆盖

任务清零发生在首source加载之前：CPU收到clear许可，真实clear完成后fence写clear_ACK，TB等ACK经原SystemBus响应退休才开始装载；15040个source写响应全部退休才发ready，CPU再提交描述符。

`total`从clear请求接受至最后Y写响应在DMA退休，含真实clear、完整source装载、CPU轮询/调度、descriptor/fence开销及所有gap。`load_to_y`单列答疑首source VALID至最后Y响应窗口。`loading`首source VALID至最后source写响应，`dma_payload`首次DMA读VALID至末Y响应，仅分项，不作完整吞吐。poison输出和最终读回是验证动作，分别计数、在任务窗口外；不把poison当计算写回。

每任务source/Y端点计数单独核验；CPU邮箱轮询可以合法跨任务在途，全球endpoint请求/响应/owner账连续保留（最多1），不会在任意报告时强制总线空闲。DMA最后响应退休后才可DONE。只读物理观察器逐地址确认W16384/bias768/X1024个16bit实际清零、缓存/算术/FIFO及新增DMA w_low/bias_low归零。warmup先公开产生非零数据，之后每任务真实清零。

150MHz只用于仿真时钟及周期换算；没有STA通过即不能称实现频率。官方SDK接口、官方600音频与12性能样本、同候选面积/STA/综合后功能/全SoC功耗能耗必须单独验收。

## X SRAM候选

16颗指定RAMSP1024X16宏替换逻辑2KiB的X寄存器缓存。真实物理X32KiB、新增16宏全部计费，internal33/全SoC353；同W原1024清零步骤并行扫描每颗X宏1024地址。其余CPU/共享/W/bias与RNE数学不变，选择需同时定义`XU_MATRIX_DMA_SYSBUS32`和`XU_MATRIX_X_SRAM`。默认/只定义任一个宏保留旧B41预处理行为。

使用隔离candidate manifest的新CPU入口，不原地替换旧已测来源：

```sh
python3 -B experiments/s3-y32-compliant32/validation/run_cpu_xmacro.py \
  --x-candidate build/compliant32-20261113/x-macro/candidate-r2 \
  --out build/compliant32-20261113/cpu-xmacro-task0-NEW \
  --vectors build/compliant32-20261113/numeric/dev-vectors-r1 \
  --tasks 1 --warmup --jobs 2
```

`run_followups.py`按父PASS结果中的16宏配置选择相应runner，禁止与337宏版本混用，检查33536个物理clear词及全部输入/输出事务。
