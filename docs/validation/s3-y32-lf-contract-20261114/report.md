# 团队 LF 合同 v1：1064 候选验证报告

**修正后的 r2 原生结果为 0 项数值违例、0 项电气违例、0 项 unknown；新 CPU12 实测为 1,691,172 cycles、304,128 个 Y32 逐位通过，按假定 150 MHz 换算 1064.350640 task/s。**全量检查身份的独立审阅及导出 SDC 的全新 PT 进程重载均已通过。本报告采用团队定义并实际验证的外部接口条件，不表示官方认证或原通用输入条件下的未知项已经得到证明。

合同正文见 [README](README.md)。原冻结报告、原 SDC 及原 4 项 unknown 证据保持不变。

## 同源结果与计时

| 项目 | 原冻结条件 | 团队 LF 合同 v1，r2 |
|---|---:|---:|
| 全部检查 | 328,981 | **328,981** |
| met / violated | 299,649 / 0 | **299,653 / 0** |
| unknown / 全部 untested | 4 / 29,332 | **0 / 29,328** |
| 电气违例 | 0 | **0** |
| 12 task 总周期 | 1,691,172 | **1,691,172，新执行** |
| 精确 Y32 输出 | 304,128 | **304,128 PASS** |
| 条件吞吐，task/s@150MHz | 1064.350640 | **1064.350640** |

这不是将全部 328,981 项检查都称为已测通过；仍有 29,328 项 untested，其身份及原因必须完整保留。独立对比了全部检查身份：仅原四项 unknown 变为明确 met，其余状态及原因不变。

新 [CPU收据](cpu-full12/result.json)、[原始日志](cpu-full12/simulation.log)及[源码身份对照](cpu-full12/identity-comparison.json)已发布。北京时间 2026-11-14 11:13:41 完成，每任务 140,931 cycles，`source_drift=[]`。比较确认全部 **172 份实际编译 RTL 快照文件（含适配与观察模块）**及执行的固件 image 与原测量逐字节一致；本轮重新编译了模拟器和 ELF，未声称沿用旧 ELF 字节。

启动阶段两次 ERST 释放分别满足 8／9 次 LF 上升采样、LF 下降沿后 1.5 ns 撤销。两次复位 prelude 在任务窗外；每任务仍真实 clear、完整装载输入和参数、CPU调度、DMA读取/计算/完整Y写回，主计时窗保持从 clear 请求至最后 Y 响应退休。暖机、poison、验证读回与原版一致。吞吐仍是 SystemBus 测试 loader 环境下的 RTL 周期测量，不等于 GPIO生产吞吐或硅上实测频率。

## 原生时序结果

r2 对同一最终映射与同一双库，重新收集原条件及新条件的完整 coverage，包括 met、untested、violated 全部明细；未改 RTL、未改映射、未重综合。原生 rc0、Error/Fatal均0，最多8核，执行收据墙钟约33.27秒。

14份限定 min/max路径报告具有明确原生 arrival、required 和 `slack (MET)`，不是仅查询负裕量后返回“无路径”：

| 精确外部源 → 端点 | max 检查 | 最小 slack，ns |
|---|---|---:|
| BOOTROM pad → `bootrom_deglitch/T_8_reg/D` | setup | **15256.49316406** |
| DWAKEUP pad → `dwakeup_deglitch/T_8_reg/D` | setup | **15256.49316406** |
| ERST pad 上升释放边 → PMU `erst_reset_r_reg/SDN` | recovery | **15256.48828125** |
| ERST pad 上升释放边 → PMU `erst_reset_r_r_reg/SDN` | recovery | **15256.48828125** |
| ERST pad 上升释放边 → 三个 `aonrst_catch/.../q_reg/RDN` | recovery | **15256.47363281** |

上述大裕量来自合同约定的 LF 下降沿后变化至下一 LF 上升沿的半周期关系，不能外推为任意异步相位的裕量。限定报告同时保留 min路径，七个目标均显示 MET；PMU使用实际外部 ERST上升边上下文，没有拿内部 LF watchdog路径替代。

`check_timing` 仍保留 ERST 的 `partial_input_delay` 警告。r2 的 port 原件显示两极性均有预算：上升释放边绑定 LF下降沿后 min1/max2ns，下降断言边保留原 HF min0/max0.5ns模型。每个 related clock 只定义其对应一极，触发分时钟检查警告；这与 r1 丢失整条下降边不同。警告及逐极port证据一起保留，不能只删警告或将其称为全无告警。

ERST下降断言边的旧HF envelope仅为遗留分析模型，不能证明真实任意相位断言的物理安全。本轮数字脉宽、复位恢复用例与实际 STA 分别限定结论。

## 合同与身份

- RTL 子提交：`5470c5650f2d11d16e7c52cc96626d21030a3973`。
- 最终 mapped SHA256：`d83acb49caec51aabc66d8ad61b8784294bebe26c5458aa0b095f9d12a2ae0d1`。
- 原 SDC SHA256：`c15ede0fc2c65771f87e2d6aee763b4ea0d53934868ca807b4785c36182fce7c`；PT兼容版：`404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98`。
- r2 overlay SHA256：`59d242f407f46f979db386a1e875bb7f735769ea0c27ffc690a16d2674334da7`；r2 原生导出SDC（回放对照）：`53edb620a4b09eff2fd6d48b8a4e078c8970ed6c4cbad704c6a3600ffde0b5af`。
- r2 原生执行收据 SHA256：`43d000f88d4c71dd7f47872831c50bbc6dc989a0017ce97b7c27a5cc1c31646c`。完整原件发布于 [native-r2压缩包](native-r2/lf-contract-native-r2.tar.xz)，全部 met 身份保存在包内；[最终独立审阅](native-r2/final-native-review-v2.json)可离线重算。

新 overlay 只精确重定义 BOOTROM、DWAKEUP 的双极性到达预算及 ERST 的上升释放预算，后者用 `-add_delay` 保留原下降预算。HF150MHz、LF32.768kHz、JTAG及其余IO、uncertainty、transition、gating、负载与双库保持。没有新增 false path、multicycle、case analysis、异步时钟组或 ideal network。

## 数字合同验证与拒收记录

监控器正常用例及八项非法激励的预期拒绝通过：BOOTROM改变、DWAKEUP未知、过早ERST释放、DWAKEUP错边沿/短保持、ERST错边沿/短低脉宽/停钟释放。原任意相位及PMU数字回归另行保留。LF时钟合法性由固定测试台波形及受控停钟/恢复提供；pad监控器统计posedge和pad保持/相位窗，不能验证任意时钟毛刺或占空比。首轮 Icarus 拼接 `$isunknown` 临时值问题及最小复现保留，修正为标量判断后真X负例仍拒绝。

**原生 r1 整体拒收，状态为 `REJECTED_ERST_FALL_DELAY_LOST`。**虽然r1 coverage显示四项met，但其 `set_input_delay` 覆盖丢失 ERST下降预算，`partial_input_delay` 暴露了合同不完整；r1导出SDC及其重载补证也不作为通过证据。r2只修正overlay的 `-add_delay` 并重新收集完整原/新STA及14路径，没有通过改RTL、重综合或隐藏告警补救。r1默认负裕量筛选导致的8份无路径报告亦保留为不足证据。

## 当前结论与边界

已完成新合同下的原生完整 STA 汇总、七个精确目标的14份数值路径、数字合同正反用例和新CPU12复测。**独立身份审阅及导出SDC新进程重载均通过，状态 `LF_CONTRACT_NATIVE_AND_EXPORT_REPLAY_PASS`。**原固定SDC的严格unknown门禁保持拒绝，不将新合同冒充原条件闭合。

这是团队选择、需要外部源遵守的接口合同，没有官方板级规格或组委会认证。仍保留29,328项未测检查及逐项原因；生产加载、功耗、官方面积单位、正式样本与综合前后功能资格按各自已有证据报告。比赛范围为逻辑综合、综合阶段时序和功能验证；指南明确不含布局布线、物理验证及流片。板级实现、亚稳态/MTBF、CTS/SPEF/布局后多角可列为后续工程项目，不额外升级为比赛必做，也不宣称本轮已经证明。

交付入口：[完整v1 SDC](../../../submission/lf-input-contract-v1.sdc)、[版本清单](../../../submission/lf-input-contract-v1.json)。执行 `python3 -B tools/current.py verify-lf-contract` 可从压缩原件重算覆盖、约束极性、工具收据、导出回放和新CPU12，不需EDA许可证。复测后仅为历史binary复用增加了准入门禁；已测TB、监控器和binary未改，旧快照拒绝记录见 [replay检查](cpu-full12/replay-admission-check.json)。

交付的完整SDC将本轮实际执行的原精确SDC与v1 overlay直接串联，HF周期保持6.666666667ns、LF半周期保持15258.7890625ns。原生`write_sdc`另以六位小数序列化时钟（HF6.666667ns），其新进程回放作为移植性对照，检查汇总/状态与逐极预算保持；该舍入文件只保存在证据中，不代替精确源合同。
