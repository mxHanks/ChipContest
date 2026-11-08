# S3 bias SRAM Chisel 接口

本文保留最初的接口设计与验证计划。当前分支已集成生成 RTL 与 MMIO，验证范围见 [S3-Y32 交接](s3-y32.md)。

`BiasSramPrefetch` 实例化一个真实 `memory.Sram1024x16`。每个 bias 使用 `3*index+{0,1,2}`，第三字高8位为0；使用0…767字。同步读只在显式 `readCapture` 且 `rvalid` 有效时采样。两份8×40暂存带5位组号、32位epoch与valid。24次组读取各占issue/capture两拍；未作读流水化。

`LinearAutoGroupCore(useBiasSram=true)` 默认使用此模块。`false` 使用旧 `BiasBankCache`，作为独立消融；旧 `LinearCachedCore` 和 `BiasBankCache` 的组合读接口保持不变。

## MMIO 必须接入的接口

旧偏移、40位写数据和5位byte mask映射保持；命令/响应时序改变：

| Core 信号 | 语义 |
| --- | --- |
| cacheWriteEnable | 写命令valid；descriptor保持到cacheCmdReady |
| cacheWriteAddr/Data/Mask | 接受时锁存的写descriptor |
| cacheReadEnable/ReadAddr | 读命令valid及索引；不能与写valid同时为1 |
| cacheCmdReady | 上述统一命令接口ready |
| cacheRspValid/Ready/Error | 读写统一响应，保持到握手 |
| cacheReadData | 读响应40位快照；不是组合回读 |
| cacheIdle | 所有host写/读已完成且其响应已退休；预取本身不使其变低 |
| cacheInvalidate | 撤销两份组暂存；保留尚未完成的组demand并重取 |
| cacheClearValid/Ready/Done | 显式清空全部768字和两个payload；完成为一拍 |

Wrapper 接收 CACHE_LO/HI descriptor 后，应阻塞该命令的主机响应，直至 `cacheRspValid`；再将数据/err放入原响应槽并向core回送ready。读必须选择正确32位/8位快照，不能直接读取live `cacheReadData`。允许同拍退休旧响应、接受新descriptor，但不能覆盖未退休响应。核心写完成不等于CPU响应已退休，wrapper还需保持原有ICB响应规则。

启动行或手动任务前，必须保证`cacheIdle`且没有其他参数写在途。计算期间禁止参数写和模式切换；新模块本身会对计算期间写返回稳定错误，wrapper可在更外层拒绝。现有行保护与原断言继续保留。CACHE_CTRL模式切换在core内使暂存失效；任务清空须驱动显式clear并等待done，不能用reset冒充清零。

Auto scheduler 的外部 `cacheInvalidate` 仅允许在 `!active && !manualPending && !manualRunning && !takeBias` 时使用，且不得与手动START或ROW_START同拍；`cacheEnable`变化遵守相同限制。两种START也不得同拍。上述是运行时断言合同，wrapper必须显式拒绝运行中操作及同拍配置/启动。独立 `BiasSramPrefetch` 的在途失效重试测试只证明存储模块协议，不授权Auto在INIT采样时撤回bias。

## 调度与采样

仅在目标组已请求、tag匹配、FIFO有空位且计算引擎空闲时launch。首组预热留在任务窗口内。手动START在启用缓存时同样先等组就绪，因此完成延迟不再是固定66拍。

`MacController`在start后一拍INIT才采bias。`groupTake=RegNext(computeLaunch && cacheEnable)`，使当前组保留到INIT采样边沿；不能直接连接launch。组拥有期间后台预取下一组。group31后不跨行预取group0，下一行的首组代价按实测保留。

## Linux 验证范围

- `BiasSramPrefetchTest`：256索引×全部32种mask，完整读回、接受后改变输入、响应背压、旧读响应退休与新读同拍接受、后台预取、32组、在途失效重试、计算期间拒绝写、reset保留SRAM、768字clear及全值读回。
- `LinearAutoGroupCoreTest`：SRAM和寄存器两种实现，同一组极值X/W/bias，两行全部32组、FIFO两槽背压、头稳定、所有signed48结果、切回手动START。写命令均等ready和响应退休，未缩减检查。
- 同一suite新增两个预期硬件断言失败用例：等真实computeStart后进入INIT，在其采样边沿分别注入外部失效和模式切换，要求异常确为对应合同消息。没有删除原有`takeBias -> groupValid`断言，没有引入第三份8×40暂存。

以上为原计划。当前功能结果和待完成的正式 PPA 资格以分支交接页为准。
