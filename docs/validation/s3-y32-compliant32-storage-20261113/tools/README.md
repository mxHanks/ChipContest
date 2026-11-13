# 结果与 bias 存储宏化实验

此目录只生成隔离 overlay，不安装生产 RTL，不启动 EDA，不提交。三项 define 必须同时存在：`XU_MATRIX_DMA_SYSBUS32`、`XU_MATRIX_X_SRAM`、`XU_MATRIX_STORAGE_SRAM`。另外七种组合的 core 和 DMA 预处理 token 与原版本完全一致，包含旧 MMIO ABI、原回退和打包 X 功能。

已有 33 宏版本还包含 2×64×41bit 结果 FIFO、2×8×40bit 可复用 bias slot、64×41bit engine `resultReg`，以及 DMA 的 256bit Y 行快照。本实验选中分支消除这四类结果/参数存储副本；使用原 `MacPE_Acc41`（字节一致），保留 64 个算术 ACC。INT16 X/W、signed40 bias、signed41 ACC、有符号扩展到 raw48、RNE9 Y32 和 99 行尾行语义不变。

## 三宏候选的真实结构

- 原 W16、bias1、X16 不复制；新增 3 个指定接口的 RAMSP1024X16，拼成 48bit，41bit 有效，7bit 明确置零。两 packet slot 各有 64 个标量地址，只有实际有效行写入。全部 1024 个物理地址每次真实清零。
- 当前组计算结束后 ACC 停止累加，按 row/column 每拍将一个原始 41bit ACC 直接写入三宏。无 `resultReg`、行组装或寄存器结果数组。有效行全部写完后才发布 slot，ACC 才能初始化下一组。
- 一个 bias lane 从原 bias 宏的 `3*(group*8+lane)+{0,1,2}` 顺序同步读。低两片使用一个 32bit 操作数装配状态，第三片低 8bit 和它直接组成 MacPE 的 40bit 初始化输入，初始化八行中该 lane 的算术 ACC。下一 lane 覆盖临时片；没有 tag、epoch、hit 或可复用 slot。计算只能在八 lane 都初始化后开始。
- 标量结果外接原 32bit System Bus DMA。结果宏持续读取同一地址，Q 保持到对应 Y 写响应成功退休。总线背压期间结果宏不能写入其他地址；单端口冲突有互斥断言。每笔响应后才推进 column，末 column 后推进 row，最后一行后释放 slot。所有结果响应退休之后才可完成任务。
- 单个总线命令 `lock_data32` 保持 VALID/READY 反压所需 payload。没有把旧 `y_payload256` 改名藏在别处。DMA 的 W/bias 低 32bit 装配以及单笔 bias 主机接口 40bit payload 仍存在，按用途明确登记，不能称为“零寄存器数据状态”。

内部宏为 **36**，含既有 CPU64 与共享256 的全 SoC 为 **356**。物理内部容量 72KiB，逻辑结果队列仍为 656B。DMA 单元只实例化共享256+内部36，即 **292** 颗功能 generic 模型；这些不证明厂商宏时序/面积。

每任务清零实际写：W16,384 + bias768 + X16,384 + result3,072 = **36,608 个 16bit 字**。四组并行共用 1024 个地址步，不删除物理写。原 MMIO W/X 清零计数现在增加结果写，即 **35,840**，bias768 仍由物理观察器另列。未使用的 bias 768..1023 没有对外使用，也未计作已清零；结果宏所有 0..1023 全部清零。

## 可复现

```sh
python3 -B experiments/s3-y32-compliant32/storage-macro/prepare_candidate.py --out build/NEW/candidate
python3 -B experiments/s3-y32-compliant32/storage-macro/verify_overlay.py --candidate build/NEW/candidate --out build/NEW/overlay-review.json
python3 -B experiments/s3-y32-compliant32/storage-macro/run_dma.py --candidate build/NEW/candidate --vectors build/compliant32-20261113/numeric/dev-vectors-r1 --out build/NEW/dma --jobs 1
python3 -B experiments/s3-y32-compliant32/storage-macro/run_core.py --candidate build/NEW/candidate --vectors build/compliant32-20261113/numeric/dev-vectors-r1 --out build/NEW/core --tasks 12 --jobs 1
```

`run_dma.py` 复用既有 full12、读写故障、背压、单行模式、末 Y 响应保持97拍以及三种在途复位后完整新任务测试。观察器只读实际 36 宏 CEN/GWEN/WEN/A/D/RET1N，逐地址证明物理清零，并枚举所有 64 个 ACC 与真实临时状态归零。没有遇到不存在名字就跳过的分支。日志另记结果 store/read/hold 和实际生产者端口等待。

`run_core.py` 复用原 raw48 逐位比较、独立 C++ RNE、signed16/40 的正负边界、1/3/8 行、31/255 拍结果背压、abort/reset、公开非零写后清零及清零后零结果。驱动只将原 bundle 消费改为 scalar 消费。宏全地址证据由 DMA 原始端口观察器提供，core 驱动不冒充宏端口覆盖。

## 已完成的早期证据与限制

`build/compliant32-20261113/storage-macro/dma-r1` 已完成单任务，25,344 个 Y32 完全一致，实际 292 宏和 36,608 个物理零写均通过。其包尚未加强三 define 联合选择，后续 `candidate-r2` 保留同一有效实现并补全七种回退检查；r2 的完整实测应独立引用。

首轮单元 clear+DMA 是 **127,160 拍**；同条件原 33 宏是 **50,697 拍**。新方案的 scalar 握手与单端口保持明显增加周期，不能把三宏方案说成“吞吐不变”。这不是 CPU 整机计时，缺少加载和 CPU 调度，不能据此发布 task/s。完整 CPU12、PPA、全 SoC 活动/功耗、官方样本及面积价格仍需绑定最终候选重新验证。

最终三宏隔离包 `candidate-r2` 已通过 `dma-r2` 完整 campaign（304,128 常规 Y32、76,032 个复位后新任务 Y32），以及 `core-r2` 的 60 个 raw48 case。单元12任务总 1,525,920 拍，各任务127,160拍，未将慢的结果隐藏。结果宏读/写/保持的实际计数在 `SM_RESULT_PORT_MEASURE` 行，末Y响应实际保持97拍。

## 独立21宏候选

`prepare_wide.py` 从同一隔离实现生成另一份包，使用21颗1024×16，拼成336bit（328bit为8×41bit，8bit零）。两slot的地址变为`{slot,row}`。8个原始ACC通过组合连线直接一次写入一行，不增加行组装/结果快照寄存器。一packet入队需要实际有效行数的写周期（最多8），不能说成零周期。输出仍是标量接口，列选择直接在宏Q上进行；只有第7列Y写响应退休后才换行，读出的整行Q在这8笔事务期间持续保持。

内部宏 **54**，全SoC **374**；逻辑结果仍656B，新增物理结果存储42KiB。真实物理清零W16,384+bias768+X16,384+result21,504=**55,040**个16bit字，MMIO W+X+result=**54,272**，仍为1024个并行地址步。后续CPU/PPA/功耗必须按此包重做；既有33宏或3宏结果均不能冒充它的结果。

```sh
python3 -B experiments/s3-y32-compliant32/storage-macro/prepare_wide.py --out build/NEW/wide-candidate
```

其余结构和仿真命令相同，runner依据密封manifest选择实际宏数/清零字数，观察器不根据层次名是否存在来自动跳过检查。CPU复用生成器可调用 `generate(path, core='完整core层次', clock='shared_mem_clk', result_macros=21, dma='完整DMA层次', reset='复位表达式')`；生成指定include及同目录 `StorageMacroObserver.sv`。宏Q不是清零目标寄存器，证明的是每个要求地址的实际物理零写；ACC和所有相关单笔payload另逐一验证零值。

## 最终单元选型（2026-11-13）

两个 r2 候选均已完成完整单元 campaign，`summary-final-r2.json` 对各候选源码、输入、输出小日志和全部原始输出文件重新核对 SHA256。21 宏的 60 个 core case 已于 14:31 上海时间完成，终态 `PASS`；没有把未结束的任务当作通过。优先送交 CPU 整机验证的是 21 宏候选，3 宏候选保留为容量较小的回退。

| 项目 | 3 宏结果组织 | 21 宏结果组织 |
| --- | ---: | ---: |
| 内部宏／全 SoC 宏 | 36／356 | 54／374 |
| 结果宏物理容量 | 6 KiB | 42 KiB |
| 内部宏总物理容量 | 72 KiB | 108 KiB |
| 逻辑结果队列 | 656 B | 656 B |
| 每任务物理清零 16bit 字 | 36,608 | 55,040 |
| 每任务并行清零地址步 | 1,024 | 1,024 |
| 单元首任务 clear+DMA 拍 | 127,160 | 77,240 |
| 单元后续每任务 clear+DMA 拍 | 127,160 | 77,238 |
| 单元完整 12 任务拍 | 1,525,920 | 926,858 |
| 常规 Y32 逐位一致 | 304,128 | 304,128 |
| 在途复位后新任务 Y32 一致 | 76,032 | 76,032 |
| raw48／独立 C++ RNE case | 60 | 60 |

21 宏相对 3 宏减少 **39.26% 单元周期**，代价是多 18 颗宏、36 KiB 物理容量。相对同条件原 33 宏版本的首任务 50,697 拍，21 宏仍增加 **52.36% 单元周期**。这些都是实际 32bit 仲裁和共享 endpoint 下的模块实验，缺少 CPU、完整原 System Bus 路径以及 source 装载；不得换算为正式 task/s，也不得声称保持原版本吞吐。

21 宏 manifest SHA256 为 `9461237a61158e94544cd98d0db491db72cbed6530a98c48da9d78a8289a2f73`；3 宏为 `71929a93ccfbc328b495c11455716741b1356f4a4a9f5517c7e6ff287f2bb70c`。固定 manifest 本身保留生成时的 `PREPARED_NOT_VERIFIED`，通过状态在后续独立收据和 summary 中，未改写原密封身份。

每任务保持 15,040 次 32bit DMA 读取、25,344 次 32bit Y 写入和成功退休。实际 scalar POP 为 25,344；MMIO `pop_count` 在 column7 退休时累加，仍为 **3,168 个八列行组**。八行模式共 416 次 group 启动、26,624 次 MAC 步和权重数组取数。最后一组 tile 仅启用第 97–99 行这 3 行，8 行模式并未将尾组算作完整 8 行。

21 宏首任务端口观察器实际计数：3,168 个行存储边沿、59,696 个结果读边沿、56,528 个 hold 边沿、4,452 个 producer 因 held Q 停顿边沿，以及 25,344 个 scalar 退休 POP。3 宏对应 25,344／88,262／62,918／53／25,344。这里的 read 是反复保持地址的实际 SRAM 读使能边沿，不能当成互不相同的结果字数或外部总线访问次数。

两种方案均保留原 `MacPE_Acc41` 精确字节和另外七种 define 组合的预处理 token。64 次 signed16 乘积加 signed40 bias 的所有中间前缀均落在 signed41 范围；最终极值为 **−618,473,193,472 至 618,475,290,623**。每个 core case 还实际比较 2,048 个合法正负边界输出；RNE9 后截取低 32bit 沿用原语义，没有新增饱和或精度格式。打包脚本保存区间和模块字节证明。

早期三宏 r1 只有一次 smoke，通过后因缺少三 define 联合门控而未选用，r2 补齐七种原回退检查。早期 21 宏 r1 与 r2 只有更正注释的区别，但不混用身份；完整 campaign 引用 r2。未改变任何旧日志。

紧凑证据包由以下命令生成，保留两候选源码、测试驱动、所有小日志／JSON、完整原始输出 SHA、回退证明及失败／被替代版本身份。编译对象、大型输出数组和张量原件保留在原 build 目录，省略项明确列出。

```sh
python3 -B experiments/s3-y32-compliant32/storage-macro/package_evidence.py \
  --build build/compliant32-20261113/storage-macro \
  --out docs/validation/s3-y32-compliant32-storage-20261113
python3 -B experiments/s3-y32-compliant32/storage-macro/verify_evidence.py \
  --bundle docs/validation/s3-y32-compliant32-storage-20261113 --fallbacks
```

最终 CPU12、同库面积／有效 STA、映射后功能一致性和全 SoC 功耗仍需针对选中源码分别完成。**当前没有综合面积结果，不宣称符合 2.25 mm²**；宏化和功能通过也不能替代这项验收。
