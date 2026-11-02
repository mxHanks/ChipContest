# xu 独立任务SAIF采集器的host证据

这组证据只证明本地准备、观察器和生成器检查；没有VCS完整SoC执行、SoC SAIF或PT功耗结果。

- `host-tests.log`：5项测试通过；实际12层fixture的全部四类文件逐字节映射、global/local ID拒绝、精确活动锚点、合成336宏SAIF时长/实例缺失拒绝。
- `passive-probe.sv`和`passive-probe-*.log`：真实Icarus运行同一个SV被动观察器。mode0完整上传16384W、256bias、6336X并START3168次通过；mode1缺W、mode2缺bias、mode3缺X、mode4错误W、mode5窗口前W写均按预期fatal，返回1。
- `generator-iverilog-build.log`和`generator-compile-identity.json`：使用原始私有厂商模型，对生成的完整336宏SoC做Icarus elaboration通过；只用`XU_TASK_ACTIVITY_HOST_CHECK`屏蔽不受Icarus支持的SAIF系统任务。保留Icarus原始constant-select提示，没有当成运行结果。
- `host-preparation.json`：固定f49子仓、12层304128个Y的独立整数golden核验和12项原始/本地layer0映射，以及真实RISC-V固件构建身份。固件为`bias-hw-window/-O2/both-unroll-no-masks`；固件日志和内存统计另存。
- 采集器及其四个既有helper经当前host Python按3.6 grammar解析通过；未运行真正Python3.6解释器。

厂商源只保留路径/SHA和命令，不含vendor文件字节。`manifest.json`绑定本目录全部证据（排除自身）。采集器和测试的快照与仓库新增源码相同；完整用法见`xu-soc-task-activity.md`。正式缓存清空/失效政策、实际SoC SAIF、PT映射/宏功耗表、150MHz STA和门级一致性均仍未由这组host证据证明。
