# 64 PE 候选：RTL 原始存储位清单

此清单只读检查现有 elaborated.xml 和冻结 Git 源码，未启动仿真、综合或新的 elaboration。
计数为每个实例中由时钟沿非阻塞赋值更新的独立变量的完整声明位宽。它包括可被综合优化掉的状态，**不是映射触发器数量或面积**。
RAMSP 宏内部阵列及输出状态单独计容量；不把功能模型中的行为数组计作寄存器。

- 最终 E203 子提交：`a80dd184536e0f2312c62768d5acf4ba1b01c34e`。
- 回退子提交：`45e61b6101ad6f0aaa7583098294ffb1550f1f2d`。
- 回退平台/PPA adapter 父提交：`655713b304597ca5b2810a0940ac3f1850072d63`。
- 最终 XML：`build/parallel4k-20261110/ppa-final-prepared-r2/preflight/elaborated.xml`。
- 权威机器清单：`build/parallel4k-20261110/storage-inventory-r1/final-result-r2.json`，逐实例、逐变量列出名称和位数。

| 状态类别 | 回退16 PE（bit） | 最终64 PE（bit） | 新增（bit） |
|---|---:|---:|---:|
| X双缓冲 | 4,096 | 16,384 | +12,288 |
| 结果FIFO原始48位数据 | 1,536 | 6,144 | +4,608 |
| PE累加寄存器 | 768 | 3,072 | +2,304 |
| 计算引擎结果寄存器 | 768 | 3,072 | +2,304 |
| bias缓存数据 | 640 | 640 | +0 |
| 其余控制/缓存元数据/地址/计数器 | 1,605 | 1,681 | +76 |
| **合计** | **9,413** | **30,993** | **+21,580** |

X 缓冲从512 B增至2,048 B；结果FIFO原始数据从192 B增至768 B。PE ACC和引擎结果寄存器各从96 B增至384 B。DMA中的256-bit写回快照两版都存在，不重复计入FIFO。

总数包括 DMA＋核心＋仲裁器以及共享存储端点控制；不包含CPU、原SoC控制或SRAM内部。
最终 DMA＋核心＋仲裁器为30,979 bit（回退9,351 bit，新增21,628 bit）；端点及其非宏adapter控制14 bit（回退62 bit，减少48 bit）。
除了处理循环的整数索引 `lane`，这些范围内无被遗漏的时钟沿阻塞赋值目标。`lane`仅用于展开八个结果的256-bit快照，不是需保持的硬件状态。

| SRAM用途 | 最终物理宏数 | 最终容量 | 相对回退 |
|---|---:|---:|---|
| 权重 | 16 ×1024×16 | 32 KiB | 不变 |
| bias | 1 ×1024×16 | 2 KiB | 不变；使用768个16-bit地址 |
| 共享存储 | 256 ×1024×16 | 512 KiB | 不变；从128深度bank×2 lanes改为64×4 |

最终每种模块的原始时序状态：

| 模块 | 实例数 | 每实例bit | 总bit |
|---|---:|---:|---:|
| `xu_matrix_dma64` | 1 | 1,247 | 1,247 |
| `LinearTileDmaCore` | 1 | 6,196 | 6,196 |
| `DmaBiasSramPrefetch` | 1 | 888 | 888 |
| `Sram1024x16` | 17 | 1 | 17 |
| `mem_1024x16` | 17 | 1 | 17 |
| `DotProductEngine` | 8 | 384 | 3,072 |
| `MacController` | 8 | 9 | 72 |
| `MacPEArray` | 8 | 0 | 0 |
| `MacPE` | 64 | 48 | 3,072 |
| `TileXRowBuffer` | 16 | 1,024 | 16,384 |
| `TileWeightBankArray` | 1 | 0 | 0 |
| `TileWeightBank` | 8 | 1 | 8 |
| `xu_dma64_shared_arb` | 1 | 6 | 6 |
| `xu_shared_icb_sram64` | 1 | 14 | 14 |

回退侧从固定 Git 源码逐层遍历实例，并识别时钟沿赋值目标；六种两版共有模块与最终 XML 的变量名称和位宽逐项交叉核验一致。17个物理 SRAM adapter 的 `valid_read` 位由两版完全相同的冻结 adapter 字节和最终 XML 共同证明。回退共享端点还包括 `sirv_sim_ram storage` 的PPA adapter：DP=131072、DW=32、AW=17，选择macro_storage分支，read_bank7＋read_addr17＋forward_valid1＋forward_data32=57 bit，加端点wrapper5 bit合计62 bit。只排除RAMSP宏内部，保留这些路由和写后读转发元数据。回退侧未新做 elaboration；这些原始计数不能替代综合网表比较。

`result.json` 和 `final-result.json` 都已废弃。第一次遗漏回退17个权重/bias adapter有效位，随后根审查进一步指出回退共享端点的物理adapter57位被排除；分别见 `initial-result-disposition.json` 和 `final-result-r1-disposition.json`。应使用 `final-result-r2.json`，对应脚本 `inventory_r2.py`。旧脚本 `inventory.py` 仅保留说明旧结果的来源，不作为权威清单。

复核命令（仅只读现有证据，并写入新输出）：

```sh
python3 -B experiments/s3-y32-4k/inventory/inventory_r2.py \
  --xml build/parallel4k-20261110/ppa-final-prepared-r2/preflight/elaborated.xml \
  --out build/parallel4k-20261110/storage-inventory-NEW.json
```
