# xu167：S2c原147未知状态的被动定位

本工具只服务S2c对照组的资格定位，所有终态均为 **NOT_QUALIFIED**。
它不修复网表，不提供新的活动、功耗、能耗或完整功能/时序通过结论。
生产Chisel、RTL、数值格式、向量、时钟与reset流程均不修改。

actual159原147在 `9359423333333fs` 执行原有
`XU_CANDIDATE_REJECT unknown commit/FIFO ownership state` fatal；之前同一FIFO的
`qout_r_reg[0]` 有CK/D同刻hold告警。原日志SHA256为
`3a231022be64a2a8a2e341f9f1c86023c16bd53d9c029d2c60b5c0b41f86c6b3`。
该次VCS实际退出码为0；因此本工具核对完整native fatal源文件、行号、消息、时间及
`$finish` 原块，并原样记录退出码，不能凭退出码代替原fatal。
历史原件与归档见 `docs/validation/xu-score-failed159-20261105/`。

适配范围：

- SHA固定并导入原147六runtime文件；原147生成的完整TB在本地与actual159逐字节复现。
  所有87条147 fatal（86条原TB加原147资格fatal）、3个原always和3处原采样调用保留。
  TB仅在原prepare调用后加只读观察注册，并在原联合unknown fatal之前加八信号四态显示和快照。
  两处转换均检查可完全逆向恢复原147生成字节。
- 八信号为 `w_commit/x_commit/bias_commit/row_active/row_count/row_running/row_produced/row_retired`。
  每信号保存原task-local显示、已采样TB寄存器及当前native端点的 `aval/bval`；
  明确报告native与原采样值之间的差异，不重新采样来改变原断言。
- 观察原native FIFO和目标寄存器模块内的net/reg，显式要求目标 `CK/D/Q/NOTIFIER`，
  以及共享存储的12个原端口（含 `rsp_ready`）。完整scope、名字、宽度、类型和句柄绑定写入日志。
- 固定 `9359300000000..9359500000000fs` 窗口记录value-change回调；窗口内第一个事件保存全节点快照，
  原fatal之前再保存一次全部节点。日志序号仅为回调派发顺序，**不能证明scheduler phase或因果**。
  若原fatal时刻移出窗口，fatal快照仍保留，结果明确报告窗口不覆盖。
- 新观察C没有 `vpi_put_value`、force、`vpi_control`、延迟回调、reset或timing控制。
  原147的TB采样寄存器复制及原111已经固定的288个SRAM预装入流程保持原样；
  不写DUT FF/Q，不用替代RTL或两态转换，不禁用timing check，不屏蔽原fatal。

前台CLI供现有同一总控登记，不自建后台进程，不重试/覆盖输出目录：

```sh
python3 -B "$HOME/Desktop/xu-s2c-unknown167/unknown167.py" --describe

python3 -B "$HOME/Desktop/xu-s2c-unknown167/unknown167.py" \
  --adapter147 "$HOME/Desktop/xu-campaign-batch154/private147" \
  --out "$HOME/Desktop/xu-score-optimization-20261102/s2c-passive-unknown-20261105-167" \
  --run
```

默认采用原147的capture、mapped9c16、vendor/standard模型、VCS、SDK、preload proof与原task00命令。
可透传原147参数进行只生成检查（省略 `--run`）。输出目录必须全新；已有目录拒绝覆盖。
状态文件为 `state.json`；原生步骤和身份前后核对仍由原147 `EvidenceRun` 记录。

总控可将 `COLLECTED_ORIGINAL_UNKNOWN_FATAL167_NOT_QUALIFIED` 作为**诊断采集终态**；
异常、句柄/宽度/名字不匹配、快照不完整或原fatal证据缺失为
`FAIL_OBSERVATION167_NOT_QUALIFIED`。如果原流程后来到达原EXU halt资格fatal，
保留原147诊断终态，仍为NOT_QUALIFIED。`--describe`返回完整合同。
unknown分支和原EXU halt分支共用同一份新observer READY、完整scope和绑定检查；
新observer的句柄、读取或回调拒绝均导致FAIL，不能因为原147到达诊断终点而跳过。

本地复现（从本功能树根目录）：

```sh
python3 -B build/xu-s2c-unknown167/host_checks167.py \
  --out build/xu-s2c-unknown167/host-check-fresh
```

`local-review167-v2/`保存最新prepare、整C `gcc -Werror`、完整TB的Icarus结构语法检查、
7种合成VPI对象、17项unknown恶意日志及8项EXU halt分支observer拒绝测试的日志及SHA。
另测试X/Z保持和当前native/已采样TB差异；首次本地审查的`local-review167/`原样保留。
Icarus结构fixture与合成VPI对象均不会作为服务器DUT输入；
`synthetic-parser-fixture.log`是明确的本地混合解析fixture，不能当native仿真结果。
本地通过不证明服务器句柄存在、native调度、物理存储读回、时序、活动或能耗资格。

部署仅需 `unknown167.py`、`observer167.c.in` 及 `manifest167.json`，另依赖六个原147固定runtime；
`UPLOAD-SHA256SUMS`同时列出本地审查源码/日志供审阅，不需上传hostchecks。
本交付尚未远程部署、登记或运行；由主线程统一加入原持久队列。
