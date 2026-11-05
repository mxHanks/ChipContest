# xu 2026-11-05上午续接

最新用户指令的本机关机计划已再次核验：**2026-11-06 01:00 CST poweroff**，`/run/systemd/shutdown/scheduled` 为 `USEC=1793898000000000`、`MODE=poweroff`、`UID=1000`。不要取消、覆盖或重复设置。此前11月5日01:00记录属于历史。

工作树 `/home/mxhanks/Projects/ChipContest-xu-score-opt`，分支 `codex/xu-score-opt`。原始优化目标仍未完成；[中心台账](xu-score-experiment-ledger-20261104.md)已补actual116和120完整终态。新交付：`a1c2c06`、`8c16b8c`、`7fd085f`；并行新归档提交请读取当前Git log，不对他人的untracked目录清理或批量add。

服务器仍为Workspace1，base `~/Desktop/xu-score-optimization-20261102`。本次连接VNC PTY32648、FTP PTY84662；不要在grid传输过程中操作VNC或向图像窗口键入shell。取回仍用grid70及120秒客户端超时；FTP仅上传。连接参数沿用原受保护文件，密码只在进程内读取。

|实验|最近真实观察|下一步|
|---|---|---|
|116组合修复|自己的DC/PT/FM终态已归档；41462点FM成功，电气/removal无违例，27124 untested仍在|不重跑；不是S2e资格|
|120 S2e完整12任务|全部SAIF/log已取回独立逐bit复核；elapsed合计10420116|使用自己的89/109映射推进能量；125归档已提交|
|123静态连接|终态EXTRACTED_FROZEN_MAPPED_CONNECTIVITY123_NOT_QUALIFIED，PID132032已退出|129完整原件已取回，mapped agent独立归档；潜在路径不是动态X因果证明|
|124 S2e功耗初次工具|PID133531已退出；进入PT inventory前FAIL normalization raw/output identity differs|原失败保留；collector省略bytes而normalization含bytes，完整dict比较误拒|
|126只读coverage/RDC|PID134486；installed-docs rc0 marker1，diagnosis rc1 marker0，FAILED_NOT_QUALIFIED|原错误有SEL-005空集合及PMU第一个Q pin缺失；131取回后查实际属性/端口再做独立132，冻结126不改|
|128公共门级功能诊断|PID132851/child132876；08:24日志已到source REQUEST cycle1403985，仍RUNNING|原111同binary/TB/clocks/reset，仅文档支持的+notimingcheck；不能称150MHz/能量/完整功能通过，60 private门槛仍在|
|130 S2e独立功耗|PID135097；08:24日志REPLAYED task00，仍准备中|修正收据比较并增加Tcl语义重建guard，保持own89/109/120。观察原PID/driver进度，不能因output尚未创建重启|

129原包 `build/xu-score-resume-20261103/xu-server-connectivity-function-20261105-129.tar.xz`：57416B，SHA `0ab784c48fed419fbd70d5862a9f2be6bd8a2d82b550b6ed9ad05bffaea3b82b`。14项1063231B全部已校验，展开于同父目录`function129`。包含123完整、128运行中快照、124失败原log及冻结driver。没有vendor正文。

131已完整取回：305944B，SHA `64f1b81c1615bfe0708c902342ebb5551baa5eb67358307c9ebdf4d6816398b3`。原包为 `build/xu-score-resume-20261103/xu-server-coverage-progress-20261105-131.tar.xz`，展开于同父`coverage131`；全部49项21058148B已校验。包括126原报告/Tcl/属性表，排除`private-manuals`；128、130仍只是运行中快照。grid已q关闭，PTY17261已正常退出，可以继续VNC。

130冻结worker SHA `95caa5fab255c5126e5b51f6f0b06c9bf63283f9bbf89dd310202abc87515d46`，launcher SHA `82ed8f7db2bf88643d320ea9016b0435c2c6dc11363825d5a024efb4c2f2a3b2`。输出/launch编号130，不覆盖124。43项host checks通过，不代表服务器完整PT通过。12份raw重放全部完成后才创建output/preparation-state；之后inventory、last_prepared_task、execution.current_task_id依次出现。

这轮没有新增Chisel/生产RTL变更，尚未有合格全SoC能量或完整150MHz结果。main/S2e/baseline116的网表身份和证明必须独立，不能拼接。不要将诊断结果放入比赛评分或标记原目标完成。
