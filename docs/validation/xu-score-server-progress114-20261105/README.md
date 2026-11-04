# xu 实际114：S2e独立原件审计与UDP词法复查

本目录保存服务器实际114导出的原始压缩包，含actual109、actual113终态及同时取得的111/112进度快照。**109补齐的是同一S2e映射网表的原生Formality证据；113补齐的是固定标准单元源文件中的词法引用检查。两者均不授予完整150MHz、全SoC活动或能耗资格。**

`payload.tar.xz`为167,364字节，SHA-256：

```text
bc3188abb1448f993e71eb2e7e08a8aa76eac40c8be115806fc0697ae41618ab
```

40项载荷共5,371,538字节，逐项身份见`payload-manifest.json`，压缩包另含同一内部清单。原日志、状态和换行原样保留；本次导出范围的`omitted114-bodies.json`为空。**这不表示所有关联EDA输入正文都在包内**：标准单元库、完整映射网表、SVF和4138项验收文件的全体正文仍按既有归档/服务器原件保存。

## actual109：在服务器重新核对原始own-SVF证明

终态为`AUDITED_ORIGINAL_FULL_SOC_FORMALITY_PASS_NOT_QUALIFIED`。实际生产main为`5bf123bfead8f2a37f97f3234d4e40ce8201aae9`，child为`a0767db69628ef30e53de2d1e93dd0360c0ccf76`；原工具提交为`554267f0d34de30289ddd43babeb450da0d1dfc9`，无DC/FM重跑。

109先后两次在服务器重读实际源码、工具/工艺库、prepared输入、自己DC的mapped/SVF、完整Formality输入及VCS验收文件，两个审计上下文完全相同。返回收据冻结181项文件，其中原native FM冻结159项、campaign工具/约束冻结15项，两集合有重叠；额外绑定原状态、prepared/execution、DC/FM日志和验收收据。原VCS验收检查4138项文件，配对读取/旧调度真实12层分别为10,420,140/11,842,200周期。

| 绑定原件 | SHA-256 |
| --- | --- |
| S2e自己的mapped.v | `0cfac0b5e99ec05301ec8c0efde38ef2c96790dd1243e84727687b15b25c09d0` |
| 同次DC的default.svf | `1a00803ebb654285dad15c76978fe1da50dd9732860f6af82a9a2d9117e668a9` |
| 原生完整fm.log | `db12cfc23725e1ebfbacad6d8c4a0253487cb066ac47eea41b9e5648d789b174` |

离线校验器从[原始107归档](../xu-score-server-core107-20261104/README.md)重新读取完整99,524字节`fm.log`，独立核对唯一`Verification SUCCEEDED`、完整顶层、42,338个passing点及其组成：17,136个黑盒引脚、144端口、25,019 DFF、39锁存器；17个reference unmatched、511 unread、0个implementation unmatched均保留。SRAM内部仍按原库黑盒处理，不能因此声称宏内部也已等价证明。

原89的`formality/state.json=FAIL`和campaign失败状态没有改写。旧driver使用`\s*`，把末尾换行吃进正则匹配结果，随后与不含换行的字符串比较而误报失败；原生FM实际成功。109只采用显式水平空白来判定该原件，并重新核对全部关联身份，不是把旧失败状态直接改成PASS。离线复核可逐字核对已返回原件及181项收据关系，**不能冒充在本机重新哈希未返回的服务器正文**。

## actual113：独立标识符计数补查调用解析盲点

终态为`EXECUTED_READONLY_LEXICAL_COUNTS_NOT_QUALIFIED`。原普通标准单元库为2,198,450字节，SHA `9ceaac7085f267c9a2da19d86aa9d88ddb25894df4b2485e32d13e04d0e46581`。113生产脚本SHA `5563c46e3e2036c687eeee0c223c630120730e32c9ce530064b9028cf9b91c68`；它与原库、108 helper的输入前后身份完全一致，无厂商正文导出。

完整clean source，以及默认、`FUNCTIONAL`、`functional`、两符号同时开启四种条件选择，都得到：

| 完整标识符 | 总出现次数 | primitive定义名次数 | 定义行号 | 其它词法引用 |
| --- | ---: | ---: | --- | ---: |
| `udp_tlatrf` | 2 | 2 | 101797、101923 | 0 |
| `udp_tlatrf2` | 2 | 2 | 101830、101946 | 0 |

计数排除注释/字符串，识别普通及escaped完整标识符，不依赖108的模块/实例/调用语法解析器，因此匿名实例等形式不会仅因调用解析器未识别而漏过。完整未选择条件的源中也只有这两个定义名，支持**在该固定源文件的上述五种clean文本中没有其它词法引用**。条件选择仍使用SHA冻结的108预处理函数，不是第二套完整Verilog预处理器；其它文件、宏拼接、其它编译模式及运行时均超出该结论。

这补强了[108源调用检查](../xu-score-mapped-probes110-20261104/README.md)，但不会将其有限行为实验提升为完整等价：`udp_tlatrf2`两定义确有3,668/107,521采样步输出不同，原库在采样步中匹配最后声明；该原始事实仍然成立。113没有修改、删除或替换重复定义。

本地校验逐项检查返回计数、行号、clean文本哈希及producer绑定；厂商正文没有返回，因此不声称已在本地重新执行原库的词法扫描。

## 同包111/112快照的限制

- **111实际公共诊断未完成**。仿真在`9359423333333fs`因`XU_MAPPED111_PROTOCOL_REJECT unknown_shared_handshake`触发Fatal；前面有真实标准单元`$hold`告警。没有SOURCE/FINAL/公共完成标记，不能宣称task00或能量验收通过，也不能仅据此归因为数值或架构错误。VCS进程返回0，driver随后又因预期private gate非零返回码而报`required private gate unexpectedly returned zero`。原协议拒绝与后续分类错误均原样保存；导出时PID2955/2956均已退出。
- **112只是10/12任务的运行中快照**。state列出task00–09，launcher PID2501在导出时确实存活且命令为`xu_native_pin_audit112.py`。返回了这些任务的摘要及task00八份选定原始report块，不能据此宣称112全12任务完成或全SoC能量已合格。
- S2e活动工具部署状态为`TOOLS_READY_AUDIT_AND_ACTIVITY_NOT_RUN`。它仅完成工具准备；该状态不是实际活动任务执行的证据。

上述具体PID观察只描述本次114导出时点，不推断此后状态。

## 校验与复现

从仓库根运行：

```bash
python3 docs/validation/xu-score-server-progress114-20261105/check-evidence.py
python3 docs/validation/xu-score-server-progress114-20261105/check-evidence.py \
  --extract /absolute/path/new-xu-progress114
```

第二条要求目标目录不存在。校验器安全解包、逐项核对40份原始文件和5份公开工具；同时验证107原归档并独立检查原生FM日志。PASS的范围限于本说明列出的事实，不能代替完整资格检查。

`tools/`按SHA保留109审计器/启动器、113词法工具、108条件选择helper及114导出脚本。原服务器命令为：

```bash
python3 "$HOME/Desktop/launch_formal_audit109.py"
python3 "$HOME/Desktop/xu_udp_occurrence113.py"
python3 "$HOME/Desktop/export114.py"
```

所有生产器拒绝覆盖原输出。复现需保留相同服务器原件和上述固定身份，在干净快照执行；后继独立实验须另用新编号目录并记录新生产脚本身份，不删除或覆盖109、113、114原件。109审计器可通过`--source`、`--original-tools`、`--original`、`--out`明确路径；113支持`--base`、`--helper`和`--out`。
