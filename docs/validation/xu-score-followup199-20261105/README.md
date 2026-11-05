# xu 两候选后续登记原件199独立审查

199证明四项后续任务已登记到原153控制器，并保持冻结输入；它是 **2026-11-05 17:42:49 CST 的历史快照**，不代表当前状态或终态资格。后续结果须引用各自终态原件。

原包 `followup199.tar.xz` 为85220字节，SHA256：

```text
3c611c7363caa21f4bed62ec4f2b5001a1ac0962ffee56b3b57d04d80e6e89e5
```

独立审查204重新验证全部21份载荷、2125299字节，20份源文件复制均有一致的读前/读后fd及读后路径元数据；无省略原件、无拒绝源。另有40项可选文件/目录在采集当时尚未出现，不能将它们视为运行失败。

四项登记原字节、guard和runtime198完全一致，runtime198的24份文件也与当前本地源码逐字节吻合。实际安装回执绑定158795字节压缩包，SHA256 `745bb90101f26e968d75f4f1a77bba8cb0e789750d0856df8fe90a4458c01407`；先前192安装回执保留。检查本地固定installer字节和既有独立审查过的无覆盖安装机制；199没有返回服务器installer正文，实际执行历史仍以服务器回执为证。

198回执的48项冻结输入读前/读后记录一致，包括原153、scope163和182登记身份。它记录0次直接启动实验、0次重启、0次发信号。原153的PID27671、uid14023、start_ticks118631998、完整argv与采集时原生进程观察相同。此结论只适用于该时刻，不能外推为持续存活证明。

| 登记任务 | 依赖 | 17:42:49的状态 |
| --- | --- | --- |
| s2e_coverage186 | 177终态；166预检成功 | WAIT_DEPENDENCY |
| s2c_common_preflight190 | 186终态 | WAIT_DEPENDENCY |
| s2c_common_full12_190 | 190预检成功 | WAIT_DEPENDENCY |
| two_candidate_finalpack191 | 177、186、190完整12项终态 | WAIT_DEPENDENCY |

每项使用前台独立输出根、`process_contains`等于自身输出根；190预检和12项运行使用新198运行时目录，保留旧192部署。既有177登记原字节未变。166在此包中仍为`RUNNING166_NOT_QUALIFIED`、power阶段、task11；没有终态全12项能耗。此处不判断177/186之后运行结果，也不计算新配置的能耗改善或评分。

48份远端before/after哈希属于服务器回执证据。未回传的网表、工艺库及scope163/182正文没有在本地重读。本地字节复核覆盖199整个包及runtime198全部正文。所有结论保持`NOT_QUALIFIED`。

审查器是只读离线工具，不连接服务器。11项检查覆盖真实原包，以及重封装元数据后的信号计数、冻结后输入、祖先哈希、安装器声明、安装清单、PID重用、僵尸进程、队列伪终态、快照语义、原始源码改动等负例。两次独立输出逐字节一致。

复现命令（在同一工作树，生成全新临时目录）：

```bash
cd /home/mxhanks/Projects/ChipContest-xu-score-opt
xu_followup_repro=$(mktemp -d /tmp/xu-followup199.XXXXXX)
python3 -B build/xu-followup199-audit204/audit204.py \
  --archive docs/validation/xu-score-followup199-20261105/followup199.tar.xz \
  --workspace /home/mxhanks/Projects/ChipContest-xu-score-opt \
  --out "$xu_followup_repro/audit"
cmp "$xu_followup_repro/audit/audit204.json" docs/validation/xu-score-followup199-20261105/audit204.json
cmp "$xu_followup_repro/audit/registrations204.csv" docs/validation/xu-score-followup199-20261105/registrations204.csv
python3 -B build/xu-followup199-audit204/test204.py
sha256sum -c docs/validation/xu-score-followup199-20261105/SHA256SUMS
```

`audit204.json`保存完整复核计数和24份当前运行时源文件哈希；`registrations204.csv`保存四项登记哈希、依赖及独立输出根。原包及派生物均保留，不修改历史证据。
