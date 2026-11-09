# 软硬件联调冻结候选 v1（2026-11-09）

统一联调 **16 PE（两行×八列）＋共享 W/bias＋独立外围 DMA＋共享端点共同 clock/reset 修复 A**。软件可见接口按本文冻结，父/子仓库发布分支均为 `codex/s3-y32-hw-sw-v1`。它是完整 CPU 功能验证通过的联调候选；尚未完成最终时序、新面积或正式平台资格验收。

## 已实现的硬件优化

| 改动 | 实际行为与收益 |
| --- | --- |
| 两行×八列 16 PE | 两个 8 PE 引擎同时处理两行；第 99 行只启用第一路。相同搬运路径下，完整任务吞吐由约 640.60 提高到 1,188.72 task/s。 |
| 共享权重与 bias | 两路使用同一套 16 个 W SRAM 宏和 1 个 bias 宏；没有复制第二套权重存储。每个任务重新装载自己的参数。 |
| 独立外围 DMA | CPU 提交四个地址并启动；硬件经实际仲裁和共享存储接口装载、计算和写回。每任务 40,384 笔请求/响应；不经 NICE 串行 LSU。CPU 每任务 6 次 MMIO 写。 |
| packed W 与计算搬运重叠 | 一个 32 位 W 源字同拍装入两个 INT16 bank；512 B X 双缓冲装载下一对行，224 B 结果缓冲承接写回。 |
| 硬件并行物理清零 | 每任务从 66,802 拍降到 2,052 拍；实际清零 17,408 个物理地址，并清空累加器、缓存和控制状态。 |
| 共同 clock/reset 修复 A | 共享端点接已有 fabric clock/reset，修复分频或单独复位导致的事务丢失；CPU、LSU、BIU 及原在途配置的 42 个文件不变。 |

所有吞吐数字按 150 MHz 换算；目前不代表已通过该频率的时序验收。当前联调候选仍使用已验证的 48 位累加路径；41 位累加、更多 PE、通用多在途 DMA 及失败的时钟树试验不在本候选内。

## 当前已核实结果

修复 A 和发布版独立命名 DMA bias 的 CPU 完整 12 层均实际执行通过：304,128 个计量 Y32 输出逐位一致，另一个预热任务的 25,344 个输出也检查。每层独立输入/参数身份、事务计数、payload、真实 clear 和 gap 均与原 full12 基线逐层相同。

| 方案 | 完整 12 任务主周期（含真实 clear） | 150 MHz 换算吞吐 |
| --- | ---: | ---: |
| 原 8 PE | 5,874,840 | 306.39 task/s |
| 新 DMA 单行 | 2,809,873 | 640.60 task/s |
| 新 DMA 双行＋修复 A | 1,514,236 | 1,188.72 task/s |

新候选 payload 1,489,612 拍、真实 clear 24,624 拍；clear 后 gap 492 拍另列。包含 gap 合计 1,514,728 拍，约 1,188.33 task/s。源码漂移为零，42 份 CPU 文件逐字节不变；固件装载 image 与原 full12 相同。ELF 非装载 `.strtab` 中的临时对象名差异已有独立记录。

发布原件：[冻结源码与完整证据](validation/s3-y32-hw-sw-v1-20261109/README.md)，包含完整 12 层结果、逐层表、原始日志、固件、向量、源码身份和可重建包。原修复 A 的本地证据仍保留在 `build/timing-opt-20261109/boundary-repair-A/`，没有覆盖。

发布前回退验证发现，直接覆盖同名 `BiasSramPrefetch` 会使旧接口缺失五个端口。现将 DMA 专用模块命名为 `DmaBiasSramPrefetch`，通用模块恢复为原字节；DMA 仅改模块/实例类型名称，逆命名归一与原测量源码逐字节相同。实际 CPU 回退重新通过：25,344 输出、payload 422,768 拍、clear 66,802 拍、gap 102 拍。Chisel 生成器也采用独立名称，防止重新生成时再次覆盖旧接口。

## 软件侧冻结接口

- 编译打开 `XU_MATRIX_DMA`；不打开时保留旧加速器/NICE 回退构建。
- MMIO 基址 `0x10042300`，ID 寄存器返回 `0x444d4131`。采用 32 位对齐整字访问。
- `+0x04`：写 `1` 真实清零，写 `0x102` 启动双行模式；`2` 为同硬件单行对照模式。
- `+0x08`：busy bit0、done bit1、error bit2、clear_done bit3；`+0x0c` 读取首个错误码。
- `+0x10/+0x14/+0x18/+0x1c`：X/W/bias/Y 起始地址。START 时冻结四个地址；busy 时配置写入报错。
- 共享地址范围 `0xa0000000..0xa0080000`，Y 不得与输入或参数重叠。当前验证布局 X=`0xa0000000`、W=`0xa0008000`、bias=`0xa0018000`、Y=`0xa0020000`。
- 固定任务为 99×64 的 X 乘 64×256 的 W；输入/权重 INT16，bias signed40，内部累加 48 位，按既有 RNE 除以 512 得到 Y32。W 每个源 32 位字打包两个相邻 INT16；bias 每项两个 32 位字；X 每个源 32 位字放一个 INT16。
- 顺序：准备输入/参数 → fence → CLEAR → 检查 clear_done/error → 写四个地址 → fence → START → 优先检查 error、等待 done 且 busy=0 → fence → 读取 Y。首次错误中止，不直接重试已部分写回的任务；新任务必须重新 clear。
- DONE 仅在全部 Y 写响应退休且内部在途请求排空后可见。保留原错误处理、fence 和输出数值检查。

可复用驱动示例为 `tests/e203/dma_day_main.c`；其中 HOST 握手为验证环境使用，软件集成到实际应用时应保留 DMA 提交和完成语义，替换测试台任务管理部分。完整寄存器表见 `experiments/s3-y32-dma-day/README.md`。

## 精确版本与交付口径

父仓库从基准 `1800a0767f1df5f0af483d546b24edcf84a7b857` 发布，使用本分支当前提交的 gitlink；E203 发布提交固定为 `45e61b6101ad6f0aaa7583098294ffb1550f1f2d`。这包含原 `79c8af1` 的 DMA 实现、三份生成 RTL、共同 clock/reset 导出及保持旧接口的命名隔离修复。

生产 RTL 直接来自 `third-party/e203_hbirdv2/rtl/e203/`，生产 PPA 包装来自 `tools/ppa/xu_soc_ppa_top.sv`。发布版冻结验证快照共 170 项文件，其中以下三份生成文件必须齐备：

| 文件 | SHA256 |
| --- | --- |
| `rtl/e203/perips/LinearRowPairDmaCore.sv` | `7299a95d127f9bb33141baf4d8872c9070662b94e8299e4d47da38d6dda81da1` |
| `rtl/e203/perips/DmaWeightBankArray.sv` | `3fcd0cd40b24d71e2de38560ad23e1b0fc750f174fa0444ad4fdb7306070a003` |
| `rtl/e203/perips/DmaBiasSramPrefetch.sv` | `6ebec7d73d8dc038bfba66f2249299c0aefda399a6ad34926120d72a38f829ed` |

共同 clock/reset 接线已经进入子仓三个 SoC/子系统模块和父仓 PPA 包装。测试专用 `boundary_tb_shared_endpoint.sv` 仅保留在冻结验证快照中，不是生产 SRAM 或正式宏替代品。旧测试入口 `tests/e203/tb_dma_day_soc.sv` 为历史测量口径；复核当前修复应按发布证据 README 重建带 fabric clock/reset 的冻结测试台。

发布固件 ELF SHA256=`b256b70b8ec5bad899a84dfb560909e68434b24ac7ef5c2a03515b251d4bfdf1`；image SHA256=`7f20af91d64efad7267b1badd5aad3473d070e3f151dff9268242c8d89840370`。发布包、清单及校验凭据位于 `docs/validation/s3-y32-hw-sw-v1-20261109/`。先前 168 文件本地包作为历史证据保留，不作为本次 Git 发布的新源码身份。

## GitHub 与剩余工作

本次按用户新指令发布父/子仓库 `codex/s3-y32-hw-sw-v1` 分支；没有合并 main 或创建 PR。原始本地包中“尚未推送”的字段记录的是打包当时状态，新发布身份以发布证据 README、publication.json 及分支 gitlink 为准。较早的 `s3-y32-development` 快照（父仓库 `680be46`）不包含本次完整修复。

当前可冻结软件 ABI 并开展联调；最终参赛版本仍需同一个冻结候选的完整时序、新面积、SRAM 模式/复位电气合同及正式接口资格验证。旧综合基准存在 setup/hold/DRC 违例，修复 A 不能借用旧面积或旧 STA 作为通过证据。面积硬上限保持 328,309.34679750 同库面积单位（当前基准的 1.25 倍）；本文件不宣称目标已完成。
