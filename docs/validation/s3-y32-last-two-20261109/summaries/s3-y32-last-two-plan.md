# S3-Y32 后续数据流计划最后两项执行

2026-11-09。用户明确选择“两行×八列／DMA＋41位内部累加”，继续落实此前仅模型评估/暂缓的两项。并非综合/正式验收；原“不综合、不改CPU/fabric”约束保留。

固定父基线e984bad936855debfc5fa01f04bcbc6252d59ecc，E203 dba1b5f82395b762f126387a1840e6a843e3a01a。当前8PE READY/packed-clear/bias-demand每层payload422,768＋真实clear66,802＝489,570，full12为5,874,840；304,128 Y32逐位一致。

## 两行×八列与搬运

在隔离模块中共享一套8路WeightBankArray和BiasSramPrefetch，两个X行缓冲和两个8PE引擎，同时算两个不同行。交错输出row0/group0、row1/group0、row0/group1…；99行末尾只允许row0有效。真实单层输入/权重/bias/golden驱动，检查25,344个结果、物理读取次数、尾行、背压、reset与真实clear。

专用搬运沿现有NICE/LSU端口，实验独立0x25指令和PAIR_ENABLE默认关闭；两行目的地址相距1024字节。每组8lane完整快照、下一拍POP、逐字等待响应、末写之后completion、首次错误中止/不重试保持。新cap和row身份防旧wrapper或错行数据冒充。CPU/LSU/BIU/仲裁/在途不变，无新bus master；这条路线称NICE专用跨行搬运，不冒称独立DMA。

低成本边界为真实RTL模块/组合单层。若没有真实CPU+固件+全任务同条件证据，模块周期/读取减少绝不当整SoC加速或与当前489,570直接比较。只有证据完整且有收益时才推进正式候选，否则保留可运行独立架构原型与明确限制。

## 41位内部累加

通用MacPE默认48位保持，参数链显式生成41位特化；signed16乘法、signed40 bias、最多64项MAC、48位输出/resultReg/FIFO及Y32/RNE不变。独立数学界证明每个0..64 prefix安全；真实41/48RTL逐prefix比较极值、正负、ties、init/reset/enable停顿，40bit反例应溢出。

同条件CPU单层检查数值、全部计数、实际clear/gap；41位是面积方向，允许周期相同但须明确只有原始ACC寄存位384→328、省56bit，未综合不承诺面积/频率/能耗收益。完整12层验证作为可选候选的功能证据，默认交付不自动替换为41位。

## 交付标准

1. 两条隔离真实RTL原型及明确接口，数值/所有权/错误/复位/尾部/真实clear有意义验证，失败保留。
2. 41位完整域证明与同源生成、single/full12；两行/跨行组合真实单层与同模块对照，所有指标范围清楚。
3. 独立源码/协议/计数/边界审查，固定baseline源与candidate精确SHA、C/TB/ELF/image/工具/输入核验。
4. 将可选源码/测试/补丁/报告和复验材料本地提交，默认最优8PE保持可回退；不覆盖旧证据、无推送/PR/外发/综合/官方EDA。

clear政策REVIEW_PENDING、FIFO payload physical zero UNPROVEN、两态Verilator/无STA/PPA/官方资格限制均保留。

## 完成结果

- [x] 共享W/bias的真实两行16PE原型，10个同模块sink对照，每次25,344raw48精确；实际宏读、尾行、reset、dirty真实clear与物理端口/寄存器观察通过。
- [x] 新可选0x25跨行NICE，613协议场景及31native流程，真实speech task0、旧ABI双向拒绝、512写错误位置、复位/背压/末响应通过。
- [x] 41位可选参数链、65prefix完整域证明和3345RTL边沿回归，单层及full12 304,128输出/每层周期/窗口/clear/全计数不变。
- [x] 独立严格对照和损坏证据负例，源/生成RTL/CPU不变与代码审查；默认installed171源保持。
- [x] 永久可复现脚本在正式合并源码上分别重跑，default48/41/rowpair12/12/11生成SV与实测匹配。

本轮实现/验证交付是可选原型，保留8PE48位当前生产基线5,874,840拍。两行没有真实CPU/MMIO接入和SoC端到端收益证据；独立DMA受不改fabric约束不接入；41位只证原始8ACC少56bit，不宣称PPA。见[结果](s3-y32-last-two-results.md)。本地Git、紧凑/便携证据和最终迁移校验由外层handoff收据锁定。
