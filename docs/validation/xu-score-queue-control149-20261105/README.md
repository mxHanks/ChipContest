# xu：八候选冻结与统一总控149实际证据

原包`server149-original.tar.xz`为96952B，SHA256
`60c25e5ddcd243a924adf00278aacd47c546ed9aa33693aed9794642094b84e4`。
96项载荷共5719875B，独立检查包路径、重复名、manifest、逐项长度与SHA均通过。
包括138八候选全部freeze/adopt收据、148启动记录、150总控状态/注册、143/144许可证原生日志、
130运行中执行收据及已产生的逐层power/log；不含vendor模型、库或手册正文。

138实际状态为`INPUTS_AND_ADOPTIONS_COMPLETE_REMAINING_PHASES_PENDING_NOT_QUALIFIED`。
八项服务器before/after完全相同且errors为空；本地核对的是服务器原回执，
不声称本机持有并重哈希全部源代码/网表/库正文。

|候选|冻结输入数|原生FM通过点|选定网表等于原面积网表|
|---|---:|---:|---|
|H1+H2|369|41462|是|
|H2-only|320|31213|是|
|SRAM bias|327|32748|是|
|S2b|320|41550|是|
|S2d|330|43440|否，选repair19|
|32PE|336|47758|否，选repair21|
|64PE|344|55537|是|
|compact32/128|351|52334|是|

各FM原日志只有一次成功标记，按本候选有序SVF及selected_mapped接续；SRAM内部仍为
`BLACK_BOX_NOT_PROVED`。S2d和32PE的功耗、面积必须在选定修复网表重新测量。
正式活动、能量、完整资格在此快照仍待实现/依赖；冻结和接续成功不是比赛资格。

150总控PID159584在实际`/proc`中存在，冻结worker SHA
`d7813ac3745ff1aa5b5efc92eef298a6577abef774259f9285aae605c466db2f`。
它已接续原130 PID135097、138终态；随后自动执行自己的S2e134，再执行独立baseline142。
快照时130进入task11（第12层）、11层已有执行回执，未宣告12层结束。
总控持久化状态、启动意图、冻结注册及append-only events；分离服务器进程不依赖模型在线。

当时96逻辑核、MemAvailable761591107584B、磁盘余量1522007015424B。
143/144只读原生查询完成，只报告当前checkout，不能证明许可证总配额或空闲数量。
总控按本用户一个原生实验槽位调度，阶段间Python重哈希也保留槽位；不扩大EDA并发。

本地复核：

```sh
python3 -B /home/mxhanks/Projects/ChipContest-xu-score-opt/docs/validation/xu-score-queue-control149-20261105/check-evidence.py
```

服务器唯一日常入口：

```sh
python3 -B "$HOME/Desktop/xu-experiment-control150/xu_experiments.py" status \
  --out "$HOME/Desktop/xu-score-optimization-20261102/unified-experiment-control-20261105-150"
```

新增可执行145/146/147适配后用同一入口register；不要重新init或手动启动已登记实验。
当前生产Chisel/RTL没有改变，全部结果保持`NOT_QUALIFIED`。
