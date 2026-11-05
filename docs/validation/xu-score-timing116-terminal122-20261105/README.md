# xu实际116：同一最终映射的DC、PT与完整FM终态

实际116已完成，原终态为 `EXECUTED_SAME_MAPPED_DC_PT_AND_FULL_FM_NOT_QUALIFIED`。
DC/PT/FM各返回0、唯一原生完成标记各1次，完整FM原日志明确
`Verification SUCCEEDED`、41,462个passing compare points。122观察时原PID25920已退出。
这补齐121运行中快照缺少的FM终态与mapped/SVF/Tcl/TSV正文；**仍不是完整150MHz或比赛资格通过**。

|项目|实际结果|
|---|---|
|同一最终mapped|13,671,648字节，SHA `16d29dea71ed2668b33c893e1a38be01a6eea02ca190ba8aabcb4658fe610292`|
|自己的repair SVF|9,984字节，SHA `2574d971c759fc2650ed660b52b6219928c54117be156cdf616ccbea10f1d90a`|
|最终state|SHA `7da5adb892fcaa33b5876e4f8dcbd9467a09dd8b40687476de529d1f7bf3c84f`|
|组合死锥清理|5轮删除17、17、7、4、2个，合计47；第6轮删除0并收敛|
|reset缓冲|5个原精确端点各4对CLKINV，合计40单元|
|电气报告|max-cap/min-cap均无违例section|
|最差已报告setup / hold|0.00000000ns / +0.00601495ns；各50条均MET|
|分析coverage|294,473总检查；267,349 MET，0 violated，27,124 untested|
|removal / recovery|17,597 removal全部MET；2条PMU recovery仍untested|

每个被删单元都有实际native `is_sequential=false`、唯一owner、所有输出无接收者的预检。
完整FM使用自己的10段 `default→08→09→49→50→63→73→79→95→116` SVF链和原完整RTL输入；
没有借用61/FM66通过。最终mapped与repair SVF在PT及FM前后复核一致，274份冻结输入的
服务器before/after回执完全相同，`frozen_inputs_unchanged=true`且观察错误为空。

FM保留原 `synopsys_auto_setup`、原未解析模块black-box方式和SRAM抽象范围。
原日志另有17个未匹配reference寄存器、508个unread DFF及实现侧未匹配black-box对象，
原件没有隐藏；形式成功不能替代工艺SRAM行为、门级VCS或数值精度验收。

HF关联的外部reset到5端点recovery定向查询仍均为 `NO_PATH_UNKNOWN`；相应removal
slack为+0.13275149、+0.13641581、+0.22710226×3ns。LF watchdog到后三个AON端点的
recovery为+30516.76953125ns，removal为+0.56059015ns。缺路径没有被改成MET。
两个PMU recovery的summary与5次HF定向查询是不同统计范围，不能相互替换。

setup/hold未覆盖仍各3,790项，包括constant_disabled、既有精确first-D例外和24个
UART latch clock缺失；min-period有10,416项非激活宏模式；min-pulse-width有9,126项
untested。PTE-052时钟周期展开及PTE-060警告保留。0ns最差setup路径终点为负电平透明
clock-gate latch，完整报告保留借时，不能把0ns描述为充裕裕量。下一步需对同一映射
补宏模式、reset/RDC、脉宽、消费者和UART证据，不能新增无依据cut/case/clock来消除报告。

原包 `xu-server-terminal-20261105-122.tar.xz` 保持原字节，1,283,388字节，SHA256：

```text
654e1c7b3a4d22f41810b0d3a7c1a73de9707f79e879b254e558374cf5dd6c50
```

内部manifest绑定121项载荷、37,978,683字节。本checker重新读取并验证全部载荷，随后
核对116所有原报告/TSV、实际执行脚本、native log与最终mapped/SVF及清理/插入计数。
274份服务器冻结输入中仅4份正文在本包内，其余只有原回执；本地校验没有声称重新
读取服务器所有源、历史链和工艺DB。原包也含120活动输出，本目录只核验其原字节，
120的功能/活动语义由独立归档审查。

从任意目录只读复核：

```sh
python3 /home/mxhanks/Projects/ChipContest-xu-score-opt/docs/validation/xu-score-timing116-terminal122-20261105/check-evidence.py
```

结果见 `verification122.json`，独立分析见 `analysis116.json`。`tools/`保存实际116冻结
worker/launcher及export122工具，不会自动远程运行。原116已结束，不应重跑或覆盖其目录。
这是baseline116平台方法实验，不是S2e自身映射、面积、全SoC能耗或评分配置；本次没有
Chisel、RTL、数值格式、ABI、向量或SDC改动。
