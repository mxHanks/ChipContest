# xu：174两候选实际接续原件

已取回并逐字节核对服务器progress174包：188212B，SHA
`df0166018b47d6ad78917928f23fc77c5a32213b8f386b56610f4e67fa64dfd4`。
74份载荷、5260127B全部与manifest一致；无source拒绝、无省略正文，全部source快照读取期间metadata均未改变。
31项missing是当时尚未出现的后续阶段/可选失败说明等；它们不会冒充已执行结果。
所有副本仍按live observation解释，不自动成为资格证明。

原件确认同一153控制器PID27671实际PID/startticks/argv匹配，29项注册保持原历史：

|阶段|本次原件状态|
|---|---|
|S2e164原报告审计|完整12任务/24份报告/540288个pin block；原554输入前后重哈希相同|
|S2c167|已采集原unknown fatal；完整VPI编译、VCS编译及仿真日志/TB/C/state在包内，功能门槛仍失败|
|S2e166同155图单层预检|唯一RUNNING任务，PID180321实际身份匹配，PREPARING166|
|S2e166完整12层|等待同图单层真实成功，尚无新155能量|
|173自动归档|已登记、等待167/full12终态与164成功；由同一总控执行|

164的两套服务器解析器逐块复核19326997752B原生报告，SHA和全部选定属性/统计一致；
本地复核的是已返回的原审计回执，约19.3GB原报告正文仍留在服务器。
每层仍有5280个Q出现TX，其中4256个全窗TX；getter的全部`x_probability=0`没有消除这些实际未知。
显式update_power前后选定属性相同；前一次getter已触发活动传播/平均功耗计算的事实保留。
未知Q、条件SRAM功耗、完整150MHz及门级功能仍未闭合，全部 **NOT_QUALIFIED**。

原图同口径比较见[165](../xu-score-two-candidate165-20261105/README.md)。
155面积0.3003096339mm²独立列出，不能拼接旧130能量。本次没有生产Chisel/RTL/ABI或数值变化。

本地复现全部返回字节和语义回执审查（输出目录须全新）：

```sh
python3 -B docs/validation/xu-score-progress174-20261105/analyze174.py --out /tmp/xu174-fresh-review
```

脚本读取本目录固定原包，先安全核对全部成员、长度、SHA、外层SHA及路径，再重建
`analysis174.json`和12层`per-layer164.csv`。不能据本脚本称本地重读了未返回的巨型报告。
`check-package.py`逐字节保留171 checker源码；`progress174.tar.xz`保存失败与原native日志。

服务器日常命令不变：

```sh
python3 -B "$HOME/Desktop/xu-campaign-batch154/campaign154.py" status
```

自动173最终包名为`B/xu-server-two-candidate-20261105-171.tar.xz`，不要手动提前写入这个名字。
本progress174使用独立名字，不影响已入队自动归档或任何native worker。
