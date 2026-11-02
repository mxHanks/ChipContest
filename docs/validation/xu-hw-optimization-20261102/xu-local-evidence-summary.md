# xu 本地硬件验证证据摘要

执行命令：`scala-cli test . --server=false`。观察到 10 个 suites、13 个测试全部通过，ScalaTest 报告运行耗时 75 秒。各测试独立 wall time 未记录，以下不从文件时间戳推算。此次仅打包已有产物，没有重新运行测试。

| Suite | 测试名称 | 条数 | 独立耗时 | 范围 |
| --- | --- | ---: | --- | --- |
| dotproduct.DotProductEngineTest | 应该可以输出正确的计算结果 | 1 | 未单独记录 | 64轮、8路点积；bias初始化、结果保持、done回空闲 |
| dotproduct.DotProductEngineTest | 应该能以合理的时序发送预处理信号 | 1 | 未单独记录 | INIT预取k=0；RUN预取k+1；末轮关闭权重读使能 |
| dotproduct.MacPEArrayTest | 应该能正确执行 8 路并行乘累加 | 1 | 未单独记录 | 8 PE一次并行MAC及关闭enable后的结果保持 |
| linear.LinearLayerEngineTest | 应自动遍历两行两组并正确输出结果 | 1 | 未单独记录 | 2行×2组×8路=32结果；rowLoaded/resultReady握手与done |
| linear.BiasBankCacheTest | keeps every bank and group distinct through masked writes and task refresh | 1 | 未单独记录 | 256项全写；256次固定种子随机字节掩码写；256项第二任务刷新；全32组×8路校验及signed40边界 |
| linear.LinearComputeCoreTest | 应正确从存储器读取数据，完成两组 8 路点积 | 1 | 未单独记录 | group0/1、正负权重、16个结果；每组启动至done观察66周期 |
| linear.LinearComputeCoreTest | 应正确计算跨 SRAM 边界的两个 group | 1 | 未单独记录 | group15/16跨SRAM0/1边界、16个结果 |
| linear.LinearCachedCoreTest | selects legacy or per-group signed40 biases without changing MAC results | 1 | 未单独记录 | 2任务×2bias模式×4组（0/15/16/31）=16组、128结果；非零MAC及signed40极值 |
| memory.WeightBankArrayTest | 能否正常完成读写操作 | 1 | 未单独记录 | 8 bank独立写入后同地址并行读与rvalid |
| memory.XRowBufferTest | 应该正常的读写 | 1 | 未单独记录 | 64个signed16值全写及组合读取 |
| memory.WeightBankTest | 应该可以按照规定的时序读出和写入 | 1 | 未单独记录 | 单地址负数同步读写、rvalid失效 |
| memory.WeightBankTest | 应该正确完成写入、连续读取和跨 SRAM 边界访问 | 1 | 未单独记录 | 0/1/1023/1024/1025/2047地址；连续读取与两块SRAM切换 |
| lineear.LinearLayerFullTest | 应自动计算 99x256 个输出并与参考结果一致 | 1 | 未单独记录 | 99行×32组×8路=25,344个结果；完整W/X装载及独立BigInt参考结果 |

原始逐测试编译、仿真、协议执行日志位于 `chiselsim/`，共13组、39个文件。ScalaTest汇总来自此前工具stdout的观察，已在 `xu-chisel-observation-receipt.json` 中明确标记为观察收据。空的simulation-log.txt保留原始字节及SHA。

独立ICB wrapper测试不计入上述13项；Icarus真实RTL仿真通过，接受/退休均4,909次，原始输出位于 `direct-wrapper-iverilog/`。覆盖新旧bias模式、全缓存与字节掩码、连续结果窗口、背压和同拍退休/接受。

`xu-chisel-observation-receipt.json` 包含工具版本、生成命令、旧九份计算核SV及mem_1024x16逐字一致结果、新两份SV哈希。`SHA256SUMS` 严格覆盖档内全部普通文件（清单本身除外）。仅扫描已有证据文件，未读取凭据文件；未发现凭据标记或受保护访问文件路径。

本地证据不代替服务器VCS性能和物理面积/功耗/时序结果。
