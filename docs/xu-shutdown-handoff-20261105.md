# xu 2026-11-05关机续接

用户已安排本机01:00 CST自动poweroff，不修改或取消。当前工作树`/home/mxhanks/Projects/ChipContest-xu-score-opt`，分支`codex/xu-score-opt`；最新结果与资格边界见[xu台账](xu-score-experiment-ledger-20261104.md)。目标仍未完成。

服务器Workspace1、base `~/Desktop/xu-score-optimization-20261102`。先观察既有分离进程，不因连接/观察超时重启：

|任务|目录|已观察进程|最后证据|
|---|---|---:|---|
|S2e完整12任务活动|s2e-formal-activity12-20261105-120|18987|00:50真实cmdline存在，121仅RUNNING；需取result.json/原SAIF/日志|
|同网表清理+reset DC/PT/FM|full-soc-timing-combined-20261105-116|25920|121快照DC/PT完成、FM运行；需当前state/fm.log终态及自己的mapped/SVF|
|门级原库被动因果采集|mapped-causal-native-20261105-117|20538已退出|121完整原件已回本地，不作功能/时序/能量通过|

已完成的104 task00、109独立FM审计、112报告重放、113词法审查、115失败审计不重跑。实际111未知握手失败不能改写；60项private观测门槛仍未闭合。116是baseline95派生，不能借作S2e证明。

本地原始121：`build/xu-score-resume-20261103/progress121`，88项24741085B，外包542668B，SHA256 `07be4ca0267cdcbbec4263215c04e2dc5fdc8c6c5c544337d9d5da39898dbf14`。119：59项46164286B，外包872692B，SHA256 `ec9657776616f72bc98bb7c876acf71a77bdc9614ab31b9581f4c780c3acb934`。已逐文件核验。原生vendor库正文没有导出。

访问凭据路径`/home/mxhanks/.local/state/xu-eda-access/session-auhyuhkh/access.json`，仅进程内读取，禁止回显；helpers在`/home/mxhanks/.local/share/xu-eda-access`。VNC客户端原PTY59749关机后需重连。FTP只上传，RETR拒绝；取回使用grid70及120s客户端超时。不要向打开的grid窗口键入shell。服务器shell为tcsh，直接运行Python，不用bash的2>&1。

下一步：观察116和120原PID/child，取回各终态；逐文件SHA和各自源/网表身份核验，再推进全SoC同配置能量。117的早期握手瞬态X早于目标notifier，须补完整连接/事件分析，不能简化归因。保持150MHz完整覆盖、未知Q/宏能量及官方数值证据门槛，不拼接不同网表的通过结果。
