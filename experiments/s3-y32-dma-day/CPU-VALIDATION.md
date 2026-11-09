# CPU 与共享存储端到端验证

发布联调 v1 的共同 clock/reset 与独立命名 bias 使用专门冻结测试台，
请优先按[发布交接说明](../../docs/s3-y32-hw-sw-handoff.md)中的源码身份和重建命令复核。
下文保留原单日 R2 测量入口，不将旧测试台替代新版共享时钟/复位验证。

`tests/e203/dma_day_main.c` 是实际 RV32 固件，`tests/e203/tb_dma_day_soc.sv` 实例化完整 E203 SoC。候选通过 `XU_MATRIX_DMA` 选择，CPU 经 MMIO 提交描述符，独立外围 master 经真实仲裁访问共享 ICB SRAM。原 `tb_accel_soc.sv`、旧固件和其观察器未修改。

共享端点为 512 KiB、32 位、单注册响应，默认每 7 拍阻塞 1 拍，与基线开发端点一致。X 每个 INT16 占一个 32 位源字；W 每个 32 位源字携带两个 INT16；bias 每个 signed40 占两个源字。每任务完整读取 8,192 个 W 字、512 个 bias 字和 6,336 个 X 字，写回 25,344 个 Y32。Y 按目标地址逐项检查，支持两行交错写回；每个地址只能写一次，任务结束时再检查内存全部结果及覆盖。

CPU 在 CLEAR、START 和完成后执行 `fence iorw, iorw`，遇首个硬件错误即终止，不重试。任务完成必须晚于末 Y 写响应退休，所有 DMA 请求响应必须配对；NICE 请求必须为零。每次 ACK 后，端点才装入下一任务的独立冻结输入，并毒化全部输出。端点装载公共输入和固件 ITCM 初始化是测试激励；测试台不层次写入加速器内部存储或预置计算结果。

`--warmup` 额外完整计算并核对一份 task0，在其正常退休后再开始计量 task0。该预处理单独打印 `DMA_WARMUP_*`，25,344 个输出同样检查，计量的 12 任务仍为 304,128 个输出。这样第一个计量任务清零前已有由正常 DMA 端口产生的非零物理前态；所有计量任务都包含完整物理清零和重新装载，不保留参数。

物理清零观察器由 `core/soc_observer.py` 生成，只读真实 17 个 SRAM 宏写端口、4 个 X 缓冲写端口及寄存器。每次清零要求所有 16,384 个 W 地址、768 个 bias 地址、256 个 X 地址各写零一次，并检查 X、ACC、引擎结果、FIFO、bias cache 和 DMA 快照的载荷为零。计量任务要求上一次公共写入确实产生非零 W、bias 和 X 前态。详细非零地址数量、真实写入数和覆盖均保存在日志中。

`run_soc.py` 在编译前复制 RTL 和测试源码，生成逐文件 SHA-256 清单。生成核心按文件名替换快照中的同名依赖，避免重复模块定义；不操作共享 `vsim/install` 缓存。固件 ELF/image、仿真器二进制、输入向量、工具版本和所有命令都保存。编译开启 Verilator `--assert`。复用二进制时，`--replay-from` 要求原记录 PASS，并重新检查源码、ELF/image、仿真器 SHA-256；每次运行仍独立导出、验证向量并保存原始日志。

HF/LF 时钟使用 `1ns/1fs` 精度，实际测量周期分别为 6,666,666 fs 和 30,517,578,126 fs。150 MHz 仅用于吞吐换算，不表示已通过 STA。启动采用明确的外部引脚二次复位，不层次初始化 CPU 或外围状态。

计时主口径为：

- payload：独立 DMA 首个源请求 VALID 到末 Y 写响应退休，首请求等待包含在内。
- clear：CPU CLEAR 命令被接受到 `clear_done` 可见，包含全部真实清零工作。
- principal：payload + clear。
- gap：clear 完成后到首源 VALID 之前的间隔，继续另列；同时给出包含 gap 的总值。
- START 到 DONE、CPU 固件周期、W/bias 装载、X/Y 窗口、请求间隔、响应延迟、端点停顿、DMA 停顿和在途峰值另列。

通道观察器逐事务确认独立 DMA 接受的命令与真实共享端点命令的地址、方向、数据和 mask 完全一致，响应退休和读数据也必须属于同一 DMA。以单层强制首请求等待 31 拍的运行验证 VALID 起点不能被接受起点替代。

## 可复现命令

以下命令均从仓库根目录执行，输出目录必须不存在。日期截止保护默认为 2026-11-09 23:59 上海时间；后续复核须由操作者明确给新的 `--deadline`。

```sh
python3 experiments/s3-y32-dma-day/core/soc_observer.py build/dma-day-20261109/soc-physical-observer.svh
python3 experiments/s3-y32-dma-day/run_soc.py --out build/dma-day-20261109/cpu-dual-task0-final-r2 --tasks 1 --dual 1 --warmup --generated-dir generated/LinearRowPairDmaCore --observer build/dma-day-20261109/soc-physical-observer.svh --jobs 2
python3 experiments/s3-y32-dma-day/run_soc.py --out build/dma-day-20261109/cpu-dual-full12-r2 --tasks 12 --dual 1 --warmup --replay-from build/dma-day-20261109/cpu-dual-task0-final-r2
python3 experiments/s3-y32-dma-day/run_soc.py --out build/dma-day-20261109/cpu-single-full12-r2 --tasks 12 --dual 0 --warmup --replay-from build/dma-day-20261109/cpu-dual-task0-final-r2
python3 experiments/s3-y32-dma-day/run_soc.py --out build/dma-day-20261109/cpu-dual-stall31-r2 --tasks 1 --dual 1 --warmup --first-source-stall 31 --replay-from build/dma-day-20261109/cpu-dual-task0-final-r2
```

单层、原型和预算不能代替完整 12 任务性能证明。面积、时序、正式资格由独立报告判定；本验证不会据此宣称正式成绩。

## R2 已测结果

`build/dma-day-20261109/cpu-summary-r2.json` 汇总四份最终运行，并核验它们的 163 项源码身份、ELF、image 和仿真器 SHA-256 全部相同；12 层各输入和参考结果的哈希也与原 8 PE 基线逐层一致。

| 完整 12 任务 | payload | 真实 clear | 主口径 | gap | 含 gap | 150 MHz 主口径 task/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 原 8 PE | 5,073,216 | 801,624 | 5,874,840 | 1,224 | 5,876,064 | 306.39 |
| 新 DMA 单行 | 2,785,249 | 24,624 | 2,809,873 | 492 | 2,810,365 | 640.60 |
| 新 DMA 双行 | 1,489,612 | 24,624 | 1,514,236 | 492 | 1,514,728 | 1,188.72 |

双行每层主口径为 126,185–126,188 拍，各层分别低于 150,000；含 gap 吞吐为 1,188.33 task/s。两种新路径各核对完整 304,128 个计量输出，另各核对一份预处理 task0 的 25,344 个输出。每次 clear 完整写零 17,408 个 16 位物理地址，计量任务前均观察到公共端口产生的非零前态。

最终原件为 `cpu-dual-task0-final-r2`、`cpu-dual-full12-r2`、`cpu-single-full12-r2` 和 `cpu-dual-stall31-r2`，位于上述 build 目录。31 拍首请求等待测试中，计量任务首 VALID 为 1,332,399、首接受为 1,332,430，完整等待包含于 payload。R1 原件保留；R2 增强了逐事务仲裁身份和实测时钟证明，并修正了 R1 停顿计数漏掉上部 Y 地址的观察器范围，周期及数值结果未改变。

这些结果证明完整开发仿真的周期目标达到；面积、STA 和正式资格不由此验证。
