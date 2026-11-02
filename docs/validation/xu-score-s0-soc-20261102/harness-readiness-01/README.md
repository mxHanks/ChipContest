# xu 全SoC harness 冻结前检查

`readiness.json`记录当前源码SHA、7项host guard和已核对SHA的两个Icarus unit probe：真实厂商宏1024字与4个含X字的物理preload回读；2,000,000个标称150MHz半周期的绝对相位和30个复位上升沿。

`nominal-full-soc-result.json`只证明本次生成的nominal150 TB、真实厂商模型和全部SoC源码能被四态Icarus编译，不是SoC仿真通过。保留编译警告和生成TB。当前runner关闭子进程stdin，复位在绝对120ns/200ns释放，记录完整运行命令和公开任务边界；厂商宏拒绝二态Verilator。

下一步由服务器VCS执行真实1任务，通过后执行12任务；完整四态SoC、缓存清空、门级等价、150MHz STA和全范围活动/功耗均需后续证据。旧Verilator宏失败及停止目录保留原文。
