# xu：actual115失败审计与117被动采集工具

本归档保存服务器**实际115**的完整原始state、failure-review、launcher state及stdout，以及其所审查的111八份原件、本地21项负例和117工具/回调机制检查。115只读重哈希与描述已有失败，没有重跑VCS，没有修改111、网表、工艺库、时钟、复位或timing check。**111仍为失败；60项private gate仍pending。117在本归档中只有工具和本地机制证据，没有服务器117结果。**

实际115终态为`AUDITED_ACTUAL111_NATIVE_UNKNOWN_SHARED_HANDSHAKE_FAILURE_NOT_QUALIFIED`。服务器重读8份111原件及628份原冻结输入，执行前后共636份身份完全相同，runtime tree的56个成员前后检查亦未发现变化。launcher两份helper前后SHA相同、子进程返回0；该返回值表示审计器完成，不能解释成111功能通过。本地校验可重哈希本归档正文并重放完整失败解析，不能冒充重新读取未返回的628份服务器正文。

实际115四份正文逐字选自119导出，`source-export119-manifest.json`保留整份原导出清单；本目录只包含其中115的四项。119原包为872,692字节，SHA256 `ec9657776616f72bc98bb7c876acf71a77bdc9614ab31b9581f4c780c3acb934`，其余112和S2e原件由各自归档负责。这里不从清单推导未归档正文已经在本目录存在。

## actual111的真实失败

VCS原生在`9359423333333fs`从冻结TB第216行、`tb_xu_soc_ppa.public_scoreboard`触发`XU_MAPPED111_PROTOCOL_REJECT unknown_shared_handshake`。这是原first source REQUEST前480ns；日志没有SOURCE_REQUEST、FINAL_Y_RETIRE、PUBLIC_COMPLETE或REQUIRED_GATE_PENDING，没有完成task00。VCS进程返回0，而原driver又因预期private gate非零而抛出`required private gate unexpectedly returned zero`；两项原始事实均保留，没有以退出码覆盖原生Fatal。

原日志还包含25项真实`$hold`告警：24项UART启动，1项response FIFO `dp_gt0.vec_31_dfflr.qout_r_reg[0]`。后者CK/D均在`9359390050000fs`变化，limit10000fs，距协议拒绝约33.283ns。时间先后只支持继续调查，**不证明该notifier已使Q变X并传到握手**；需要117的原生事件和实际连接分析。

| 原始正文 | SHA256 |
| --- | --- |
| 111 simulation.log | `c7d9933f20be539b11534ce9318f22dd9166747b0b096f169ff0c426514b3832` |
| 111 state.json | `3f0ec494e0fa06efcd5617242c358b1e6242a9eea69b3acffdfcacbbe99ed414` |
| 115 state.json | `d669181cc5edf925d490181b1be1adb8241f37555f1ddcaa9ab3b910dcbbb59c` |
| 115 failure-review.json | `544c96a8734cd8c20025be45f4079c5814eb41f6c143bcd4202fe908b13b6385` |

## 117的范围

117使用同一111原网表、模型、TB、adapter及原编译参数，独立输出目录，仅增加read/callback VPI；采集target FF、FIFO本地节点、共享接口以及加速器clock/reset，保留aval/bval和serial/tick。原生help独立保存，工具不会据help自动加禁止timing/notifier的选项。C中没有put、force或simulator control API。所有数值/150MHz/能量资格仍待完整验证。

`local-callback117-v1`保存GCC strict编译、Icarus真实callback正例和missing-target负例的原日志与源fixture。正例中的notifier/Q/握手X是**synthetic机制检查**，不是厂商库或mapped DUT的因果证据；负例明确failed=1。原工具执行后会重新哈希所有冻结文件，但117对runtime tree成员集合只在执行前检查；后续审计还应独立检查成员集合，不能把该限制隐去。

`tools/reference-candidates115.json`逐项列出原72处observer引用和源码候选。除111已有12项public观测外，60项仍未完成mapped运行时核对。原clear observer需要的是core真实提交输入，无需先读取全部X/bias FF；但源码端口存在仍不等于mapped端点已经验证。`TECHNICAL-NEXT.md`保留完整接续说明。

## 本地校验与服务器复现

离线校验不启动EDA或远程进程，重读原件得到与实际115逐字段相同的report，并重放原21项语义/身份负例；117只核对已存在的本地机制记录。

```bash
python3 docs/validation/xu-score-mapped-audit115-20261105/check-evidence.py
```

原服务器启动命令为：

```bash
python3 "$HOME/Desktop/launch_mapped_audit115.py"
python3 "$HOME/Desktop/launch_mapped_causal117.py"
```

工具按部署原字节归档，SHA见manifest。它们拒绝覆盖既有115/117目录；不可为复现删除原件，也不可在观察超时时擅自重启。新实验需使用新编号/隔离目录并记录新工具身份。此归档未改生产RTL/Chisel或全局台账，不授予完整比赛资格。
