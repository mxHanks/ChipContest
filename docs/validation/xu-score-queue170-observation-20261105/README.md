# xu：两候选任务170实际启动观察

服务器在2026-11-05 16:08 CST打印的只读172查询，随后通过VNC截图核实：

|项目|实际观察|
|---|---|
|原153总控|PID27671，PID/startticks/argv身份匹配为true|
|S2e164原生报告审计|COMPLETED，24份原报告、12任务；worker已退出|
|S2c167被动未知状态定位|RUNNING_CHILD，PID172967，同一worker真实存活|
|S2e166同155图单层预检|WAIT_DEPENDENCY|
|S2e166同155图完整12层|WAIT_DEPENDENCY，严格要求单层成功|

这是**UI观察证据**，不是已取回的服务器原JSON或完整native验收。
`status172-command.txt`保存精确只读查询；`status172-ui.png`保存原像素，
`observation172.json`仅逐字段转录可见输出。外层SHA列表绑定本地文件字节。
后续通过171原件包独立核对控制状态、注册回执、原native日志及哈希；不能仅以截图提升资格。

新批次提交`b958d39`；独立审查`9f22fe3`，166为`0e4cd37`、167为`ee510f7`+`e0a2d0e`。
仅S2e/S2c追加，同一153总控、同一输出目录和一个native槽位；旧实验不重启。
没有新增生产Chisel/RTL/ABI/数值/向量/时钟约束变更。

原图比较仍见[165](../xu-score-two-candidate165-20261105/README.md)。
155的0.3003096339mm²面积独立于原130能量；新图完整12层能量尚未产生。
完整150MHz、门级功能及未知SRAM Q资格仍待闭合，全部NOT_QUALIFIED。
