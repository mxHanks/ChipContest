# 最终 DMA4/storage21 综合输入与时序接管

已封唯一生产源包 `build/s3-y32-final/ppa/production-r1/`，输入清单 SHA256
`0330a268da42961b636c0a2c9fc72432277ed611164ba3d45be119143ed1e8aa`。
这一步只完成生产源冻结和本地结构预检，没有启动 DC/PT，没有新的面积或时序成绩。

159 个生产编译源的完整 SET、次序、逐字节 SHA 和6个生产 defines 均已登记。
相对原353输入，生产 RTL 恰好只有合并 core、DMA4、4槽 ingress 三个变化，
CPU/LSU/BIU、原 fabric、物理 SRAM adapter、原150MHz SDC和工艺库身份保留。
没有使用只覆盖 core/DMA 的旧 storage 封包方法，也没有测试 loader define。

单核 Verilator XML 实际枚举已通过：ITCM32、DTCM32、shared256、W16、bias1、
X16、result21，共374颗宏；内部54颗，64个MAC，无旧 DotProductEngine；生产
入口仲裁实际端口宽度为2/64/64，确认 N2。逐宏路径及命令、XML SHA 在
`docs/validation/s3-y32-final-ppa-preparation-20261113/preflight-result.json`。

GPIO CPU runner 直接消费该密封源包。完整12通过后，运行最终
`experiments/s3-y32-final/ppa/prepare.py --source-package ... --cpu-full12 ...`
生成新的 `cpu12-bound-r1/`；该包保留相同生产 RTL/defines/SDC，加入实际完整12
日志、checker、ELF和image，并刷新非RTL PPA工具。初包SHA与最终完整源SET同时绑定，
避免把CPU结果自己的hash写进自己所执行的输入包形成循环。

原生启动硬门禁会在访问工具/库之前重放同一生产配置完整12原始日志，核对304128个
输出、12层计数/周期、真实374宏、N2和源SET/defines/编译顺序。已实际验证初包
`--run`因缺少CPU12被拒绝，且没有创建 execution.json 或 libraries.tcl。

最终 DC 沿用 `compile_ultra -no_autoungroup`、原SDC、原两DB及最多2核策略，
显式生成自己的 `final.svf` 并 `set_svf -off` 刷盘。非空SVF是DC必需输出，
PT receipt绑定同一map/ddc/sdc/SVF的原始SHA。报告保持8位有效数字，PT动态登记
所有实际required/global/group报告，并由runner/reviewer逐项核对；真实违例、DRC和
未解释覆盖仍是拒绝时序通过的条件。全局时钟、IO、gating、uncertainty和例外不放宽。

## 旧595条时序证据的使用边界

旧353原生结果中的595项由以下部分组成；它们用于确定诊断优先级，不能直接作为
最终374的违例清单，更不能用旧数字减掉某些项声称新配置已经通过。

| 类别 | check 数 | 独立目标 |
| --- | ---: | ---: |
| W SRAM D hold | 384 | 192 pin |
| bias SRAM D hold | 32 | 16 pin |
| GPIO/PWM/QSPI/AON/JTAG hold | 146 | 按原catalog分组 |
| gate enable hold | 27 | 15 pin |
| reset removal | 5 | 5 pin |
| debug clock output setup | 1 | 1 endpoint |

先对最终map做完整DC/PT采集，再依据真实路径进行修复。旧debug输出setup最差
−5.16538525ns，GFCM U8/Z驱动21519个load；应按同local net segment/层级构造
真正buffer树，并测量根扇出/负载变化，不能只修改GPIOA[27]约束。W/bias应从新map
重定位目标并在load侧加真实characterized延迟；gating只动latch Q→AND enable
支路，保护clock/latch EN；接口同步和reset先明确实际契约，不删除同步级或用
全域false-path掩盖。固定延迟本身不证明异步复位相位安全。

r4原件archive SHA为
`c65efa4c735bdc97251125444e8c7eee3bcacd22815940477f2b67751d7a745d`，
34/34 receipt输出已逐项SHA和大小重放。原生单BUFV2探针返回0、无工具错误、无源
漂移；确实增加一颗0.957600原始库面积单位的非反相buffer，导出changes。
其 endpoint TSV 的4段各有128条path、8个clock/edge上下文：

| phase | 最差 slack/ns |
| --- | ---: |
| before_min | −0.102850 |
| after_min | −0.060515 |
| before_max | 4.087441 |
| after_max | 4.041418 |

单buffer使该端点改善但仍负；它没有证明全局修复，也没有证明DC持久化/新PT重载。
每个上下文可有多条path，不能按“一上下文一条path”摘要。旧ECO脚本限定353，
须按最终374及新bias/result层级适配guard和目标发现，不能关闭guard硬套旧pin。
正确持久化路径仍是PT `write_changes -format dctcl`→DC读取原mapped.ddc回放→
另存map/ddc/SVF→全新PT重载，保留连接、面积和所有检查。既有r4成功不替代最终
RTL→mapped formal证明。

最终面积必须重新枚举所有leaf和54颗内部宏。原始库面积单位与官方宏计价/mm²尚需
独立核定；旧353面积、旧GPIO活动和功耗结果都不继承给最终候选。

## 后续已核验进展（等待生产完整12，尚未执行最终EDA）

本地 `bind_when_ready.py` worker 正等待实际GPIO完整12的PASS；完成后自动生成新的
`cpu12-bound-r1`，重放原始CPU日志并生成输入传输包和逐文件transfer manifest。
该worker不启动EDA，也不上传文件。完整12未完成时不生成成功结果或替代数字。

已补核真正回传的旧353 bias终态：16384条path按16个pin、每pin8个min/max交替
阶段、每阶段128条path重放，与summary逐项一致；每pin3颗BUF，共48颗，原始
characterized面积增加45.964800单位。最终目标最差min为+0.037193ns，max为
+3.912694ns。全量all-violators中的bias路径32→0、timing行583→551，三类DRC
数量全不变；全局hold仍−0.13322231ns。回传14件不含after coverage，不能据此独立
宣称coverage计数595→563，也没有DC持久化或fresh PT。完整复核在
`bias-terminal-review.json`，这些结果仍只属于旧353。

最终374诊断/ECO工具已放在 `experiments/s3-y32-final/ppa/eco/`。它要求最终map和
PT报告SHA绑定的显式target plan；先只读诊断真实pin/local net/clock/latch拓扑，
再同plan单buffer探针、受限hold延迟实验、DC回放及自己的eco.svf、fresh PT重载。
没有旧pin默认值，GFCM clock-root仅导出实际local segment成员，未自动建树。
Python/Tcl语法、旧595项parser完整重放、故意缺失一项时拒绝，以及复用的buffer
contraction检查器selftest均通过；没有最终map原生探针或修复PASS。
