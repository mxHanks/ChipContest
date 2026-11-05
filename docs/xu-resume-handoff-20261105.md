# xu 2026-11-05上午续接

最新用户指令的本机关机计划已再次核验：**2026-11-06 01:00 CST poweroff**，`/run/systemd/shutdown/scheduled` 为 `USEC=1793898000000000`、`MODE=poweroff`、`UID=1000`。不要取消、覆盖或重复设置。此前11月5日01:00记录属于历史。

工作树 `/home/mxhanks/Projects/ChipContest-xu-score-opt`，分支 `codex/xu-score-opt`。原始优化目标仍未完成；[中心台账](xu-score-experiment-ledger-20261104.md)已补actual116和120完整终态。新交付：`a1c2c06`、`8c16b8c`、`7fd085f`；并行新归档提交请读取当前Git log，不对他人的untracked目录清理或批量add。

服务器仍为Workspace1，base `~/Desktop/xu-score-optimization-20261102`。本次连接VNC PTY32648、FTP PTY2326（旧84662已失效）；不要在grid传输过程中操作VNC或向图像窗口键入shell。取回仍用grid70及120秒客户端超时；FTP仅上传。连接参数沿用原受保护文件，密码只在进程内读取。

|实验|最近真实观察|下一步|
|---|---|---|
|116组合修复|自己的DC/PT/FM终态已归档；41462点FM成功，电气/removal无违例，27124 untested仍在|不重跑；不是S2e资格|
|120 S2e完整12任务|全部SAIF/log已取回独立逐bit复核；elapsed合计10420116|使用自己的89/109映射推进能量；125归档已提交|
|123静态连接|终态EXTRACTED_FROZEN_MAPPED_CONNECTIVITY123_NOT_QUALIFIED，PID132032已退出|129完整原件已取回，mapped agent独立归档；潜在路径不是动态X因果证明|
|124 S2e功耗初次工具|PID133531已退出；进入PT inventory前FAIL normalization raw/output identity differs|原失败保留；collector省略bytes而normalization含bytes，完整dict比较误拒|
|126只读coverage/RDC|PID134486；installed-docs rc0 marker1，diagnosis rc1 marker0，FAILED_NOT_QUALIFIED|原错误有SEL-005空集合及第二个PMU单元Q pin缺失（实际为QN）；131/132已归档，冻结126不改|
|128公共门级功能诊断|PID132851/child132876；08:24日志已到source REQUEST cycle1403985，仍RUNNING|原111同binary/TB/clocks/reset，仅文档支持的+notimingcheck；不能称150MHz/能量/完整功能通过，60 private门槛仍在|
|130 S2e独立功耗|PID135097；08:24日志REPLAYED task00，仍准备中|修正收据比较并增加Tcl语义重建guard，保持own89/109/120。观察原PID/driver进度，不能因output尚未创建重启|

129原包 `build/xu-score-resume-20261103/xu-server-connectivity-function-20261105-129.tar.xz`：57416B，SHA `0ab784c48fed419fbd70d5862a9f2be6bd8a2d82b550b6ed9ad05bffaea3b82b`。14项1063231B全部已校验，展开于同父目录`function129`。包含123完整、128运行中快照、124失败原log及冻结driver。没有vendor正文。

131已完整取回：305944B，SHA `64f1b81c1615bfe0708c902342ebb5551baa5eb67358307c9ebdf4d6816398b3`。原包为 `build/xu-score-resume-20261103/xu-server-coverage-progress-20261105-131.tar.xz`，展开于同父`coverage131`；全部49项21058148B已校验。包括126原报告/Tcl/属性表，排除`private-manuals`；128、130仍只是运行中快照。grid已q关闭，PTY17261已正常退出，可以继续VNC。

130冻结worker SHA `95caa5fab255c5126e5b51f6f0b06c9bf63283f9bbf89dd310202abc87515d46`，launcher SHA `82ed8f7db2bf88643d320ea9016b0435c2c6dc11363825d5a024efb4c2f2a3b2`。输出/launch编号130，不覆盖124。43项host checks通过，不代表服务器完整PT通过。12份raw重放全部完成后才创建output/preparation-state；之后inventory、last_prepared_task、execution.current_task_id依次出现。

这轮没有新增Chisel/生产RTL变更，尚未有合格全SoC能量或完整150MHz结果。main/S2e/baseline116的网表身份和证明必须独立，不能拼接。不要将诊断结果放入比赛评分或标记原目标完成。

## 09:05后续进展与批量授权

用户已授权主线程统一安排其余8候选，先核实内存、许可证和磁盘，再受控并发；候选内依赖仍顺序执行。S2e130保留，S2c资格继续，不重复启动已存在任务。

- `6eb1410`：actual132完整135包及独立脚本/analysis逐字节复现。416 active MET、10416常量禁用周期；27124 untested多重集未变，5HF+2PMU recovery仍缺路径。10000 ATTR-1来自timing_arc不支持full_name，不能隐藏。新142正在准备仅改变report查询的filtered/unfiltered对照，不能添加cut/case/clock或放宽约束。
- `9891813`：[141完整原件](validation/xu-score-resource-function141-20261105/README.md)，75952B SHA `7ae96540131c6aa45594eefb80f040f637aeadcf650192e45cc5ca129c59600d`，39项1534258B全部校验。128已真实终态：公共任务25344结果/50688写/elapsed990656，原私有门槛Fatal仍执行，`+notimingcheck`不能当150MHz或完整功能通过；636冻结身份服务器回执相同。
- 同包actual133提取目标9c16网表60引用：58保留名称、1物理重建候选busy、1仍缺直接busy操作数的row_start_accept。独立审计通过，0门槛解除，60运行时门槛仍在。目标正文未下载；inventory SHA `14a0aec91b4ceca013861ce7f4703142e90a8c762fe8c6da632f28a13ccdabb9`。
- own134当前工具提交`a15b747`+`2d691e6`，20本地检查通过，9普通文件已上传`~/Desktop/xu-s2e-timing134/`。actual136 readonly/preflight均rc0，完整原89/109/74/109输入可用；**尚未启动134**，许可证余量未知前不新增并行EDA。worker SHA `dcf5341fb9c09cb7db545fb2a208a1c204e2a14309c4741a4c5cd63c0f8364ef`。
- 141于08:56观察原130 PID135097真实存在、current_task_id=4；00—03已有原生PT输出，整个12层仍未终态，不能重启。最终需own130原生报告流式独立审计，不能直接换旧112目录（新duration5788953333333fs）。
- actual137资源：96逻辑核、MemAvailable743526596KiB、工作盘available1539212050432B。139/140未找到可执行lmutil/lmstat，admin目录部分无读权限。actual143/144 nativePT的list_licenses/license_users均已执行rc0，仅说明当前checkout、不提供总配额。144观察两组他人DC及本用户两份PrimeTime（含临时查询）与Primepower，不能推断余量。先按本线程总native上限1，现有130结束前新native等待；本地/server冻结核对无需许可证。
- `1bd053d`：八候选[137身份草案](../build/xu-batch-candidates137/README.md)：H1+H2、S1移bias、S1 SRAM bias、S2b、S2d、32PE、64PE、compact32/128；S2c/S2e续行adopt，S2a无独立mapped排除。baseline原PPA main未知留null，S2d/32PE原area与修复FM图分列，不能拼接。138可执行freeze队列正在完成，**尚未服务器入队**；七候选正式活动采集缺兼容入口，不能仅换S2e source-root。

上述09:05记录保留为当时状态。不要再设置/取消用户关机计划。

## 09:30统一调度已实际运行

用户要求尽量以一个脚本控制所有实验，模型额度耗尽后仍可运行。`f8c6875`的150已上传并分离启动，
PID159584真实`/proc`核验存在；日常唯一入口为`~/Desktop/xu-experiment-control150/xu_experiments.py`。
输出`B/unified-experiment-control-20261105-150`持续保存`state.json`、`SUMMARY.md`、`events.jsonl`及每项启动日志。
已有4注册：接续130、接续138终态、130终态后自动启动134、134终态后自动启动142。
**不要手动再launch134/142**；不重新init。需要恢复控制器时先确认原PID及文件锁，以同一冻结脚本run同一out。

149原包96952B，SHA`60c25e5ddcd243a924adf00278aacd47c546ed9aa33693aed9794642094b84e4`，
96payload/5719875B全部独立哈希核验。见[149实际归档](validation/xu-score-queue-control149-20261105/README.md)。
138八候选已实际完成全部freeze/adopt（不是仅plan入队）：每项before==after、errors为空，
selected_mapped、有序SVF与各自FM日志绑定。正式活动/全SoC能量及资格仍待后续runner；S2d/PE32须在修复图重测面积。
服务器原路径`B/eight-candidate-freeze-queue-20261105-138/ID/{freeze.json,adopt-own-fm.json}`；
本地已安全解包于`build/xu-score-resume-20261103/queue149/`。

149快照130 PID135097真实alive，current_task_id=11，tasks11，最后一层PT正在执行；09:29总控状态仍RUNNING_ADOPTED，
无native进程的哈希空档也正确保留worker槽位。保留原130，不重启。
143/144已退出的原native日志随149归档，当前checkout不等于余量。继续总native cap1。

145负责8候选自己的fullSoC formal150活动采集，146负责相同mapped/活动全SoC功耗和面积，147补原S2c私有检查。
三者本地开发中，需完成真实CLI/manifest/hostchecks后冻结上传，再通过150逐候选register。
每候选依赖activity→power；process_contains必须为唯一output_root字符串，不能全用同一个脚本名。
所有同ID注册逐字节幂等，拒绝替换；失败/孤儿不自动重试，独立后继可继续。
本机VNC Workspace1、PTY32648/FTP2326继续；grid149已q关闭，当前可用终端。
