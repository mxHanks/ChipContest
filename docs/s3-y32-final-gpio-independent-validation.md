# GPIO374独立配置：完整12任务生产验证

本报告仅适用于 `codex/s3-y32-final-20261113` 的GPIO374独立配置，**不是1064.35 task/s原N3候选的性能或综合结果**。N3主结果、面积和DC/PT不能从本报告继承；本证据发布不触发N3或GPIO374的EDA。

真实GPIO→原CPU/LSU/BIU→原32位SystemBus→共享SRAM的完整12任务已实际PASS。**304,128个Y32写及CPU逐项读回完全一致**。最终末Y写在24,427,459拍接受、24,427,465拍响应退休，DONE在24,427,468拍，尾部响应没有被提前算成完成。

## 吞吐与计时边界

全部task/s仅按假定150MHz换算，尚无本配置150MHz STA通过。

| 测量窗口 | 12任务周期 | 条件吞吐 task/s | 边界解释 |
|---|---:|---:|---|
| 各任务首GPIO输入→末Y响应求和 | 17,000,358 | 105.880123 | 包含每任务全部GPIO握手、CPU加载、提交、DMA和等待 |
| 各任务clear→末Y响应求和 | 17,013,456 | 105.798610 | 加入每次真实物理清零及clear后加载前控制 |
| 连续首GPIO输入→第12任务末Y响应 | 21,242,272 | 84.736699 | 保留完整campaign中间的全部间隙 |
| 连续首次clear→第12任务末Y响应 | 21,243,363 | 84.732347 | 再包括首次clear及首次输入前控制 |

11段任务间隙每段384,537拍，共 **4,229,907拍**。间隙包含本验证使用的CPU全Y读回、下一任务Y poison、任务控制和握手，单列为验证campaign开销。不能将单任务窗口求和当作连续campaign跨度，也不能把验证读回/poison隐去后称同一测量。

12任务GPIO加载共 **15,791,784拍**，DMA工作共 **1,207,506拍**，真实clear共 **12,324拍**。实际GPIO/CPU加载占据大部分输入窗口；本结果不能继续沿用开发三源loader版1064.35数字。

| 层 | GPIO加载 | DMA工作 | clear | 首GPIO→末Y | clear→末Y |
|---:|---:|---:|---:|---:|---:|
| 0 | 1,315,983 | 100,625 | 1,027 | 1,416,697 | 1,417,788 |
| 1 | 1,315,981 | 100,626 | 1,027 | 1,416,696 | 1,417,788 |
| 2 | 1,315,983 | 100,625 | 1,027 | 1,416,697 | 1,417,788 |
| 3 | 1,315,981 | 100,626 | 1,027 | 1,416,696 | 1,417,788 |
| 4 | 1,315,983 | 100,625 | 1,027 | 1,416,697 | 1,417,788 |
| 5 | 1,315,981 | 100,626 | 1,027 | 1,416,696 | 1,417,788 |
| 6 | 1,315,983 | 100,625 | 1,027 | 1,416,697 | 1,417,788 |
| 7 | 1,315,981 | 100,626 | 1,027 | 1,416,696 | 1,417,788 |
| 8 | 1,315,983 | 100,625 | 1,027 | 1,416,697 | 1,417,788 |
| 9 | 1,315,981 | 100,626 | 1,027 | 1,416,696 | 1,417,788 |
| 10 | 1,315,983 | 100,625 | 1,027 | 1,416,697 | 1,417,788 |
| 11 | 1,315,981 | 100,626 | 1,027 | 1,416,696 | 1,417,788 |

## 完整功能与身份

- 每层重新加载独立X/W/bias，先通过完整warmup建立公开产生的非零前态；warmup另报并排除主性能。
- 每层实际55,040次16位物理零写：W16,384、bias768、X16,384、result21,504；正式12层共660,480次，另有warmup55,040次。bias宏末256个地址未映射为任务数据，不声称已经清零；ACC/装配/描述符/owner及全部4槽请求元数据另核验。
- 正式12层180,480次DMA读取、304,128次Y写，合计484,608笔请求/响应在独立四槽kind/index台账中全部退休；各层峰值在途3。宏Q整行保持到第7列响应退休，末Y索引25,343退休先于DONE。
- 实际宏leaf枚举374颗：ITCM32、DTCM32、shared256、W16、bias1、X16、result21，完整原始路径在PASS收据中；没有靠常数替代真实枚举。
- 全部159项生产编译源、编译顺序和6项defines与sealed PPA输入逐项一致：`SYNTHESIS DISABLE_SV_ASSERTION=1 XU_MATRIX_DMA XU_MATRIX_DMA_SYSBUS32 XU_MATRIX_X_SRAM XU_MATRIX_STORAGE_SRAM`。没有测试loader；只有启动固件进入ITCM，张量均由GPIO输入、CPU原总线写入。
- 冻结RTL子提交：`b0a0e47df4431ee8c459c7c0df2fe919e7b0d477`。初始PPA package-files SHA：`0330a268da42961b636c0a2c9fc72432277ed611164ba3d45be119143ed1e8aa`。
- 完整12原始PASS收据SHA：`4038368430973760c3a304c51d4ad2489334ba7783fe971a2c02f9c06fa16c2f`。导出器重新校验全部source/vector/binary/ELF字节，并用冻结checker独立重放原始日志，结果逐项等于原PASS收据。

## 证据与复现

[完整12摘要](validation/s3-y32-final-20261113/gpio-full12-pass/summary.json)、[原始日志](validation/s3-y32-final-20261113/gpio-full12-pass/simulation.log)、[完整收据](validation/s3-y32-final-20261113/gpio-full12-pass/result.json)、[冻结checker](validation/s3-y32-final-20261113/gpio-full12-pass/check_results.py)。

[完整离线源/CPU12安全封包](validation/s3-y32-final-20261113/gpio-full12-source-package/README.md)与[196成员独立allowlist/SHA审计](validation/s3-y32-final-20261113/gpio-full12-source-package/allowlist-audit.json)可用于脱离旧build目录复查；封包不含厂商库、凭据或原始向量。

[生产验证命令](../experiments/s3-y32-final/validation/README.md)与[独立导出器](../experiments/s3-y32-final/validation/export_functional_evidence.py)。本机实际base为`gpio-task0-r2`，full12为`gpio-followups-r1/full12`；重放使用同一binary，不重编译、不重跑已完成任务。

第一次小证据导出遇到replay目录没有独立`source-manifest.json`，已在[失败收据](validation/s3-y32-final-20261113/gpio-full12-export-attempt-r1/export-failure.json)保留原件。导出器改为生成已经逐文件验证的完整源hash表，随后重放导出PASS；这不是RTL仿真失败，没有重复运行CPU12。

两个独立wait31均已实际PASS，并用同一冻结checker重放原始日志、复核同一binary/固件/生产源身份：

| 强制场景 | 实测目标端点等待 | 首GPIO→末Y | clear→末Y | 相对基线总增量 |
|---|---:|---:|---:|---:|
| DMA首次读取wait31 | 31拍 | 1,416,732 | 1,417,823 | +35拍 |
| CPU首次加载wait31 | 31拍 | 1,416,732 | 1,417,823 | +35拍 |

DMA场景的加载阶段仍为1,315,983拍、DMA为100,660拍；CPU加载场景的加载阶段1,316,014拍、DMA为100,629拍。目标等待确为31拍，整体窗口还保留总线/CPU相位产生的额外开销，没有强行写成“总增量只能等于31”。[两项原始日志、收据及独立重放摘要](validation/s3-y32-final-20261113/gpio-wait31-pass/summary.json)。

活动版现已进入单核编译，尚无活动PASS。它从同一159源/6defines/固件重新采集完整u_soc与u_shared，保留全部实际宏pin及初值，分别串行取clear和实际GPIO窗口，不使用旧374 FST。GPIO374离线CPU12绑定包已生成，未运行EDA。

本报告没有本配置STA、面积、RTL→mapped等价、功耗或J/task通过结论。公开开发向量的逐位一致也不等于官方最终600样本验收。
