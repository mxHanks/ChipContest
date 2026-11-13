# S3 Y32 最终整合候选：报告同步快照

截至 2026-11-13（本次提交时），本分支已整合入口/DMA流水与结果/bias指定SRAM整改。**这是报告编写用的阶段快照；最终生产吞吐和新配置PPA尚未完成。** 后台生产GPIO/CPU验收继续运行，结果另行追加，旧证据不覆盖。

分支：父仓和子仓均为 `codex/s3-y32-final-20261113`。父快照以本文件所在提交为准；冻结RTL子提交为 `b0a0e47df4431ee8c459c7c0df2fe919e7b0d477`。主工作目录旧S2e未改动。

## 报告目前可以引用的内容

| 项目 | 已验证结果 | 适用范围 |
|---|---|---|
| 历史入口优化性能 | 3,568,690 → 1,691,172拍；504.3868 → 1064.3506 task/s；2.1102倍；304,128个Y32一致 | 优化前/后开发配置，三源测试loader，150MHz假定换算；不是当前374宏生产成绩 |
| 当前整合版DMA完整12任务 | 304,128个Y32逐位一致；clear＋DMA共1,219,801拍，其中clear12,300、DMA1,207,501拍 | DMA＋入口＋原fabric＋共享端点单元验证；不含GPIO/CPU输入装载，不能作为最终端到端吞吐 |
| 复位/错误恢复 | 3阶段在途复位后76,032个结果一致；7地址错误恢复177,408个结果一致；前6类错误发生时各有3笔accepted owner | 独立有序台账、排空及新参数恢复；末Y错误时仅1笔在途 |
| 末Y背压 | 最后写响应真实背压97拍，正确退休后完成 | 当前DMA单元验证 |
| 指定宏存储 | 全SoC实际XML枚举374颗：CPU64＋shared256＋W16＋bias1＋X16＋result21 | 生产N2/PW1，64PE；不是mapped宏清单或面积通过 |
| 真实物理clear | 每任务W16384＋bias768＋X16384＋result21504＝55,040次16位零写；控制/ACC/装配/owner另核验 | 当前DMA回归已过，GPIO暖机也已观察到 |
| 生产GPIO正式task0 | 25,344个Y写及CPU读回一致；首GPIO→末Y为1,416,697拍，含clear为1,417,788拍；条件吞吐105.8801／105.7986 task/s | 实际374宏生产配置，暖机后非零前态clear；完整12尚未完成，不能当最终成绩 |

所有task/s均为按假定150MHz的周期换算；本候选尚无有效完整STA通过，不能写成已实现150MHz性能。

## 架构与数值边界

保留原32位SystemBus、原CPU/LSU/BIU、原mem_fab源码及在途参数、512KiB共享端点和完整99×256 Y32格式。入口owner FIFO和DMA有序kind/index队列均为4槽，队列只保存必要控制元数据。W两半及bias物理提交、X双set、99行尾组和错误排空契约均保留。

结果使用21颗指定SRAM；issue/retire列索引独立，同一宏Q行保持到最后一列写响应退休。没有结果寄存器FIFO、Y整行快照或bias预取slot。必要的单笔32/40位装配状态及生命周期列于[源清单](../experiments/s3-y32-final/rtl/manifest.json)。

生产验证与PPA共同使用159项逐字节封签RTL和同六项defines：`SYNTHESIS DISABLE_SV_ASSERTION=1 XU_MATRIX_DMA XU_MATRIX_DMA_SYSBUS32 XU_MATRIX_X_SRAM XU_MATRIX_STORAGE_SRAM`。没有`XU_SYSBUS_TEST_LOADER`。初封源包manifest SHA256为 `0330a268da42961b636c0a2c9fc72432277ed611164ba3d45be119143ed1e8aa`。

## 尚不能写成完成的项目

- **整合后的最终生产吞吐**：真实GPIO→CPU→原总线加载的正式task0已PASS（GPIO加载1,315,983拍、DMA100,625拍、clear1,027拍）；同binary完整12正在运行，两个wait31排队。完整12通过后重放原始日志，另封CPU12绑定包；同时列每任务窗口求和、clear、gap及连续campaign跨度。验证专用读回/poison开销不会混入单任务性能。
- **最终DC/PT**：尚未启动。门禁要求上述同源CPU12先通过；之后沿用原150MHz SDC、相同库和`compile_ultra -no_autoungroup`，同一时间仅一个自己的最多2核EDA阶段，产生自己的`final.svf`及新map全量STA。旧353的595项时序违例不是新374结果。
- **面积≤2.25mm²**：尚无新map面积；库面积单位和官方宏计费仍需核定，不把原始库单位换名为mm²。
- **RTL→mapped与功耗**：已取回本轮Formality只读API文档，尚未执行设计一致性验证；最终全SoC活动将重新采集u_soc和u_shared，不复用旧374 FST，当前尚无本轮功耗/能耗通过结果。
- **官方最终600样本**：未完成。公开开发数据的数值格式证明不能替代官方评测或CPU实际600×12。

## 旧bias实验终态已接管

原生收据、14件返回文件逐SHA/长度核对通过。旧353 map对16个bias D pin每pin加入3个buffer，共48个；目标最差hold变为+0.037193ns，32条bias timing path违例消除。但all_violators仍有551条其他timing path、全局hold仍为负，DRC未改善；尚无DC持久化和fresh PT重载，也不是最终374修复。完整coverage未包含在本次返回子集中，不能独立宣称595减到563。见[bias终态审查](validation/s3-y32-final-ppa-preparation-20261113/bias-terminal-review.json)。

## 证据入口与复现

- [历史1064开发性能报告](s3-y32-ingress-perf-results.md)及[原始摘要](validation/s3-y32-ingress-perf-20261113/summary.json)。该报告中的“本轮不推送”是旧阶段记录，本次已按用户要求推送阶段快照。
- [当前DMA12/错误/复位摘要](validation/s3-y32-final-20261113/dma/summary.json)、[源身份与装配状态](../experiments/s3-y32-final/rtl/manifest.json)。
- [生产GPIO正式task0 PASS](validation/s3-y32-final-20261113/gpio-task0-pass/summary.json)及[命令与计时边界](../experiments/s3-y32-final/validation/README.md)。本机实际运行为`gpio-task0-r2`；r1测试台语法失败原件保留。
- [最终PPA输入/门禁说明](s3-y32-final-ppa-preparation.md)、[Formality准备说明](../experiments/s3-y32-final/formal/README.md)。
- [旧bias接管收据及原件](validation/s3-y32-final-20261113/remote-takeover/bias-takeover.json)。

队友可通过本分支递归获取子模块：

```sh
git clone --branch codex/s3-y32-final-20261113 --recurse-submodules git@github.com:mxHanks/ChipContest.git
```

本次发布包含源码、脚本、小日志和审查证据；不包含凭据、厂商DB/lib/alib、原始数据集、build中间物或大型活动文件。
