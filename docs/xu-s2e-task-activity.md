# xu S2e 独立正式任务活动采集104

本工具只采集冻结 S2e：main `5bf123bfead8f2a37f97f3234d4e40ce8201aae9`、child `a0767db69628ef30e53de2d1e93dd0360c0ccf76`，固件 `bias-hw-autogroup-paired-hi-window/-O2/both-unroll-no-masks`。生产候选、旧 S2c 采集器、旧 common 实现均不修改。本阶段没有 Chisel 改动；新增文件均为独立测量工具及其验证。

完整 VCS 开发验收的10,420,140周期不是此工具的正式能量窗口结果。正式采集前，必须验证该候选自己的实际 DC mapped.v、自己的 default.svf、完整原 RTL、两份原库和完成的全SoC Formality。不能引用 S2c 网表或旧证明，也不能把本地几何模型当作 vendor 仿真。

实际107导出的89原始FM日志已经显示`Verification SUCCEEDED`、42,338个passing、511个unread和17个reference unmatched；原producer以`\s*`捕获末尾换行后与不带换行的字符串比较，误记为FAIL。独立109审计重新核对原source、DC、own mapped/SVF、全部159个FM冻结输入、完整native scope和4,138个VCS runtime raw，生成新审计receipt。原89的FAIL receipt及全部日志不覆盖、不重跑FM。采集器只有显式提供通过的`--formality-root`、并再次执行上述实际绑定审查时才接受该审计；不能仅凭手工更改状态放行。未完成109实际服务器重哈希前，`--prepare-only`同样不绕过gate。

`checked_mapped_context`要求 terminal campaign 的 source_before/after 与当前冻结 profile完全一致；重验 prepared 源、生成脚本和原名义150MHz SDC。它实际重新哈希 tool/library、DC、own-SVF、full-FM 所有输入，并核对原始 FM state 与 campaign state、完整输入集合、原始FM版本/唯一PASS标记/返回码/错误及日志SHA。再检查 DC 日志版本/唯一完成标记、execution/netlist/mapped-SDC/analysis-SDC及证明上下文。equal before/after receipt本身不能替代磁盘字节复核。全部原件再作为运行冻结输入，在编译和每任务运行前后复验。这个 gate 只证明身份和原有映射功能证明，不宣称时序或能量资格。

采集保持原测量口径：

- 一任务一个新仿真进程，先使用CPU的旧MMIO执行33,697个零写；观察真实W16,384、X64、256个40位bias及旧8路bias提交。首先检查真实内部bus reset采样、FIFO head/tail与空所有权；不强制初始化没有物理reset的FIFO数据寄存器。
- 原始向量不变，正式窗口从第一源数据读REQUEST开始，包含未ACCEPT等待，至最后Y写响应RETIRE；所有W16,384、X6,336、bias256的真实提交都必须在窗口内。clear在窗口外，跨任务不复用缓存。
- HF150MHz、LF32,768Hz按绝对相位产生，1fs精度；LF边沿不能累计周期舍入。保留旧ACCEPT窗口诊断，单独记录正式整数fs/elapsed/inclusive计数。
- paired-HI对应38,016次实际结果读取：25,344个旧LO和12,672个packed HI。每个packed响应持有两lane高位的pending mask；阻塞期间数据不能改变，只有实际响应退休后才增加两个逻辑字的所有权。每组仍须全`16'hffff`才可POP，全部3,168组、50,688逻辑字和signed48结果逐一核对。重复/缺失/错误读数、未退休响应、提前POP都失败。
- SRAM保留同336个RAMSP1024X16、每宏67bit，共22,512个真实pin alias。不修改vendor模型、不设置`INITIALIZE_MEMORY`、不将X/Z/B改为0。raw SAIF不变，normalized SAIF仅作双射归一化，仍需以后独立审查PT映射与有效活动覆盖。

部署新的干净工具树后，先以独立109审计原89。该命令没有EDA调用，只有实际重哈希和原件检查，输出目录必须新建。

```bash
B="$HOME/Desktop/xu-score-optimization-20261102"
python3 "$B/ChipContest-s2e-activity-tools-109/tools/ppa/xu_s2e_formality_audit.py" \
  --out "$B/s2e-own-formality-audit-20261104-109"
```

只有109实际终态通过才先执行task00：

```bash
B="$HOME/Desktop/xu-score-optimization-20261102"
python3 "$B/ChipContest-s2e-activity-tools-109/tools/ppa/xu_s2e_activity_server.py" task00 \
  --source-root "$B/ChipContest-s2e-74" \
  --ppa-root "$B/s2e-ppa-campaign-20261104-89" \
  --formality-root "$B/s2e-own-formality-audit-20261104-109" \
  --out "$B/s2e-formal-activity-task00-20261104-104"
```

仅在task00原件通过，且源代码、工具HEAD及实际mapped/proof上下文完全相同时，才允许后续12项命令。不要在两次命令之间修改或提交这个工具checkout。task00证明和所有raw identity会被重验。

```bash
python3 "$B/ChipContest-s2e-activity-tools-109/tools/ppa/xu_s2e_activity_server.py" tasks12 \
  --source-root "$B/ChipContest-s2e-74" \
  --ppa-root "$B/s2e-ppa-campaign-20261104-89" \
  --formality-root "$B/s2e-own-formality-audit-20261104-109" \
  --task00-proof "$B/s2e-formal-activity-task00-20261104-104" \
  --out "$B/s2e-formal-activity12-20261104-104"
```

默认后台启动并打印真实PID；`--foreground`可保留在当前进程。所有输出/driver log必须新建，旧失败原件不会覆盖。`--prepare-only`仅表示不调用VCS，不能产生活动或能量结果。实际使用原服务器GCC10.2和VCS2020.03-SP2-6，原vendor1024模型SHA固定`81b55d87d5e6821d44037d6f0290ec89c9edb9582eb1932957f181aefc300d51`。

本地复现使用当前机器上的Icarus、RISC-V GCC，范围只到工具及真实RTL观察器筛查：

```bash
XU_S2E_SOURCE_ROOT=/home/mxhanks/Projects/ChipContest-xu-s2e-paired-hi \
XU_S2E_ACTIVITY_TEST_EVIDENCE=build/xu-s2e-activity-local104/reproduction \
python3 -m unittest discover -s tests/host -p test_xu_s2e_activity.py -v
```

测试包括实际99行/3,168组算术及响应退休、10个破坏性协议/数据故障、实际20级reset链及8个故障、22,512 alias未知保留及篡改拒绝、全SoC336宏/全部alias路径elaboration、真实paired固件和原clear wrapper编译、隐藏tracked main/child篡改拒绝、10,000个LF边沿及原件重哈希。全SoCelaboration特意使用只有端口/存储几何的open stand-in，不运行任务、不代表vendor行为。尚未执行服务器104，不登记任何S2e全SoC正式活动、PT功率、能量或最终评分。
