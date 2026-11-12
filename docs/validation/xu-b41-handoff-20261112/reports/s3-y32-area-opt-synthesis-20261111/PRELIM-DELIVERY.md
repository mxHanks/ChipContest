# 64 PE、41 位 B 版初赛材料索引

2026-11-11，接续目标的材料草稿。当前仍有直接 RTL 等价、电气检查、门级功能和同版本全 SoC 能量缺口，未生成最终提交包。

依据项目提供《赛题指南》PDF 第 8—9、14 页：本科初赛覆盖第 1—3 项，包含 RTL、驱动、验证工程和综合报告，以及数值格式、与 RTL 一致的软件数值模型及参数转换脚本。第 3 项另列综合网表、时序约束、面积和功耗估算、任务周期及吞吐记录。

## 固定身份

- 父源码：`96fffcb2a4b2492fd2cfdecb88e164d2c67881ae`。
- E203：`ccdac30d92ecf40f14d0b78879b8711fb0b1cdd1`。
- B tile：`710b8e180652f49751769e152a3b3a9e6a35ba622fb4c3e2385dc5ffab241fcb`。
- 已有网表间等价的候选：`9849303f264d97f2f6735353d89a35fbe143b0897f589e94352d23ae517aa87b`。电气 ECO 新候选为 `f73b4518be9e6670bc8ed3bcf38623e1411ba55b1256ac6aae5b5c636c60a7a3`，四工况理想时序非负但剩余 DRC 未闭合，新候选等价仍待；两者均尚未冻结为最终网表。
- 软件候选固定为紧轮询/O2、分阶段 64 NOP/O2、有限退避 8→256 NOP/O2，最终单一交付固件待同网表能量比较。

## 材料与验收位置

| 材料 | 已有位置及覆盖 | 尚待补齐 |
|---|---|---|
| B 版 RTL 与测试输入 | [269 项冻结输入](../s3-y32-portable-software-design-20261110/hardware64-r1/b41-strict-input-r1/INPUT.sha256)，176 项源码中仅按已核验 B tile 替换；源与三个固件由 prepared.json 绑定 | 将最终物理网表与这些源码的等价范围闭合 |
| 驱动及固件 | [通用 DMA64 驱动](../s3-y32-portable-software-design-20261110/software/dma64_driver.c)、[等待逻辑](../s3-y32-portable-software-design-20261110/software/ffn_wait.h)、candidates-r3 构建回执及三个冻结 ELF/映像 | 根据全 SoC 能量冻结一份提交固件 |
| SoC 功能验证 | [full12 原件](../s3-y32-portable-software-design-20261110/hardware64-r1/b41-full12-evidence-r1/fetch-receipt.json)及[逐任务复算](../s3-y32-portable-software-design-20261110/hardware64-r1/b41-full12-comparison-r1/result.json)；三份各 304,128＋25,344 输出、13 次物理清零，6 处 CPU SVA，原 52 条主 TB fatal 保留。[三份 31 拍背压与六项故障复算](../s3-y32-portable-software-design-20261110/hardware64-r1/b41-followup-review-r1/result.json)亦通过 | 最终网表对应的门级功能与活动；[接入核对](GATE-PREFLIGHT.md)已整理，尚未运行 |
| 点积、极值/RNE、背压、错误、复位与真实清零 | 绑定 B tile 的[原发布交接](https://github.com/mxHanks/ChipContest/blob/dafd56613e6cf084e3aa64d90e948008216da524/docs/s3-y32-area-opt-handoff.md)及其冻结归档 | 最终网表门级检查，保留原失败和断言，不以 RTL 通过替代门级 |
| 数值格式与范围 | 见下节；与固定源码的 s3_y32.py 和冻结向量 profile 对应 | 官方 600 样本和正式 loader 接入按官方评测单列 |
| 软件数值模型、参数转换 | [已提取原源码](prelim-materials-r1/source-receipt.json)，包含 model/fixed16_acc48.py、model/s3_y32.py、tools/model/export_kwt.py、tools/model/export_s3_vectors.py 及尺度/来源清单 | 外部模型/权重和遗留推理环境按原清单提供，不把整数文件转换称为重新推理 |
| 综合、网表与约束 | 原 B 综合、DDC、SVF 与报告已在官方桌面封存；当前候选见 [PROGRESS.md](PROGRESS.md) | 当前/最终版本的原件取回、四工况及完整电气/覆盖审阅；正式面积计价仍待官方口径 |
| 综合前后等价 | 当前候选对双角基线网表间等价原生退出 0；[现场观察](continuation-observation-r1.json)与原件位置分别记录。RTL 接续 r1 结束，57,016 通过、0 失败、1,316 未验证，新检查点保留，r2 已接续 | 读取 r2 实际终态并闭合未验证点；任何后续网表变更另行绑定等价 |
| 面积、时序及功耗估算 | 当前时序与面积只在各自已知范围保留 | 电气收敛、有效完整 150 MHz 资格、同版本全 SoC 功耗和单任务能耗；不拼接旧硬件功耗 |
| 周期与吞吐 | 三份实际周期、clear/gap、软件控制区间见 full12 复算的 tasks.csv | 有效频率及正式计时口径后再给正式吞吐；150 MHz 目标换算只能标为条件值 |

## B 版数值格式

每任务计算 `Y[r,c] = bias[c] + sum(X[r,k] * W[k,c], k=0..63)`，形状为 `99×64`、`64×256`、`99×256`。X/W 为 signed16，bias 为 signed40。B 的累加、引擎结果和 FIFO 均为 signed41；公开 raw48 通过符号扩展保持原语义。

任意长度不超过 64 的部分和连同偏置满足：

```text
-2^39 - 64*(2^30 - 2^15) <= S <= 2^39 - 1 + 64*2^30
-618473193472 <= S <= 618475290623
signed41 范围为 [-1099511627776, 1099511627775]
```

最终输出为 `Y32 = RNE(S/512)`，最近偶数舍入；可达端点为 `[-1207955456, 1207959552]`，在 signed32 范围内。不增加中间截断或饱和。固定尺度为 X `2^-11`、W `2^-16`、bias/raw48 `2^-27`，Y32 解码为 `code*2^-18`。

数值模型名称仍为 `fixed16_acc48_y32_rne9_v1`，模型中的精确整数运算覆盖上述 signed41 可达域，名称中的 acc48 对应原有公开数值契约。冻结 profile 不因内部存储位宽收窄而重写。已将提取的两个模型文件和 S3 exporter SHA 与本次 B41 冻结向量 profile 逐项核对，结果一致。

X 在 32 位槽中保留低 16 位；W 行优先，每 32 位打包两个 INT16；bias 在 64 位槽中符号扩展；Y 每 32 位一个结果。默认 X/W/bias/Y 地址为 `0xa0000000/0xa0008000/0xa0018000/0xa0020000`。这些传输布局保持原合同；每任务独立重载参数、真实清零和全部写响应退休后完成。

## 冻结顺序

1. B 版 full12、背压/故障均已终态、排空并取回复算。继续复用这些固定版本证据。
2. 读取直接 RTL 等价终态；电气修复按本次明确批准的上传和原单槽流程继续，修改网表后重新验证对应四工况与等价。
3. 封存最终网表、DDC/SVF/SDC、计费范围和完整报告 SHA，再完成门级功能及三份固件同窗全 SoC 功耗。
4. 按实际测量选择一份固件，生成带 SHA、复现命令和缺项说明的初赛提交包。当前不填写虚构功耗、正式吞吐或官方得分。
