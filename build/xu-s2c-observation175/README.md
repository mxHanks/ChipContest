# xu175：S2c167 原生未知状态独立分析

原174包已重核：188,212 B，SHA `df0166018b47d6ad78917928f23fc77c5a32213b8f386b56610f4e67fa64dfd4`；
74个payload共5,260,127 B逐项SHA/字节数一致。分析只读本地原件，没有远程操作或新EDA实验。

**原fatal仅由 `bias_commit=x` 触发。** `w_commit/x_commit` 均为0，row相关量全部已知0。
八信号的task-local显示、原TB采样寄存器及同次快照当前native值逐项一致，
`current_native_vs_sampled_differences=[]`。当前证据不支持用改变TB采样来消除此fatal。

原VCS在 `9359423333333 fs` 执行第214行原unknown fatal，之后 `$finish` 时间相同；
实际模拟器退出码为0。这个0只记录VCS行为，不表示完整功能成功。
原147全部87条fatal、3个always边沿和3处采样调用仍保留；实际TB/C与批准的167被动变换逐字节相同。
服务器634输入前后身份回执完全相同、identity_errors为空。没有返回的634项服务器文件没有在本地重新哈希，
此处明确区分“复核服务器原回执”与“独立重读实际文件”。

167实际绑定131个节点，原日志与state的566条事件逐条相同：初始快照131、value-change304、fatal快照131。
12个shared端口均有初始/fatal值，所有已发生的转换均保存在 `events175.json` 和 `analysis175.json`。

|观察|native时间/fs|记录|
|---|---:|---|
|窗口首个事件的全节点快照|9359300000000|目标CK=1、D=0、Q=0、NOTIFIER=x；FIFO o_vld=0；shared rsp_valid=0、rsp_rdata全x|
|较早D瞬态x|9359383443333|D短暂为x；9359383453333恢复1，不能省略此更早瞬态|
|同刻CK上升/D下降与native hold告警|9359390050000|原模型给出hold limit=10000 fs；同tick观察NOTIFIER变0，内部n0从1变x|
|目标Q首次观察为x|9359390060000|比上述tick晚10000 fs；同tick FIFO o_vld也变x|
|shared cmd_valid变x|9359416766667|shared请求控制/地址等随后也有x；此前shared rsp_ready/cmd_ready曾短暂x并恢复|
|bias_commit首次观察为x|9359416896667|当前native io_cacheWriteEnable=x|
|原TB采样与fatal快照|9359423333333|TB的bias采样=x；其余七项仍已知，原fatal执行|

目标Q在本窗口起始是已知0，NOTIFIER起始为x；不能把“NOTIFIER初值x”直接称为首发错误。
shared rsp_rdata起始全x时rsp_valid=0，FIFO o_dat也含未有效Z位；不将这些未有效/未使用数据直接定为协议错误。
窗口起点native x_commit=1、TB采样=0，是观测到的采样差异；fatal时该差异已不存在。

原日志共有25处native timing violation：24处早期UART、1处目标FIFO；全部保留。
目标NOTIFIER/n0/Q的观察与hold模型污染的假设相符，**尚不能证明NOTIFIER到bias的实际连接或因果链**。
同一tick内serial仅表示回调派发顺序，未标注scheduler phase；不同tick的先后也不能替代电路连接和布尔敏化证明。
更早瞬态、窗口之前的未知以及未观察的信号锥仍有缺口。

`CLEAR_LAST_WRITE`已观察到33,697次清零写入，但没有原 `XU_TASK_CLEAR_OBSERVED`、`XU_SOURCE_REQUEST`/`XU_SOURCE_ACCEPT`、upload-pass、TASK_PASS或SOC_PASS。
因此此次诊断在正式单任务窗口前就拒绝，未取得完整功能、150MHz或能耗资格。

174中九个167文件的source fd/path metadata在复制期间均未改变，复制字节SHA也一致。
原171明确称其为live source snapshot；metadata稳定不使原件成为terminal freeze。
快照记录167队列为诊断完成、原PID现场观测为空；这属于174时刻的观测，不表示本机当前重新查询过服务器。

最小后继应先做同9c16的只读连接/时序查询，尚未实现或运行：

1. 从现有123原件复用同图身份，确认目标组件为
   `.../u_sirv_gnrl_rsp_fifo/dp_gt0.vec_31_dfflr/qout_r_reg[0]`，ref=`DRNQV0_12TR40`。
   `dp_gt0.vec_31_dfflr` 是一个含字面点的escaped instance，不是两个层级。禁止全局dot→slash。
   123静态记录D接局部n5、CK接clk、RDN接rst_n；Q至FIFO o_vld只有层次输出关联。
   这些是静态潜在连接，不包含Boolean敏化、UDP语义或时序结论。
2. 在原S2c映射SHA `9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892`、
   自己SDC SHA `404c7de9…`、原两库和明确冻结的ownS2c时钟方法上，查询该D的实际驱动、
   CK实际源/时钟路径，并报告该D的native minimum-delay数据与时钟完整路径。
   原名字只作为候选，native枚举后需断言对象唯一、pin/ref/方向正确；不能用通配符误选。
3. 服务器只读核对相同标准单元模型的NOTIFIER/n0/Q specify/UDP关系及SHA；不下载模型正文、不改模型。
   再核Q经FIFO协议到bias写使能的连接，遇到未观察或stateful边界明确停止归因。

具体目标组件、候选pin名、ownS2c SDC/库身份和待冻结输入已写入 `analysis175.json` 的
`next_minimal_readonly_query`。不借baseline116或S2e155的图、修复或时钟资格；
不先改TB采样、不禁timing check、不初始化/force、不加任意delay。后续native仍由原单槽总控登记。

复现命令（从功能树根执行）：

```sh
python3 -B build/xu-s2c-observation175/analyze175.py
```

也可使用 `--evidence-root`、`--archive`、`--out` 指向相同原字节的独立目录。
脚本核包与74项副本、原fatal、源码变换、634身份回执、131绑定/566事件及四态，然后生成两个JSON。
`events175.json`保留事件原aval/bval、解码四态、日志行号与原serial；所有输出继续 **NOT_QUALIFIED**。
