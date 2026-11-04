# xu actual36 / actual48 原件离线纠偏审查

本包保留 actual36 的 24 份和 actual48 的 12 份原始导出文件。所有原始字节逐一匹配 export-51 的 size / SHA256；较大文件只做可逆 xz 压缩，`original-export-manifest.json` 仍记录原始字节身份。旧 `FAIL`、损坏字符串以及旧工具均未修改。私有 SRAM 模型不入 Git。

## 已证实的范围

- actual36 实际 VCS 全 SoC task00 通过。输入/参数首个 REQUEST 为 tick `9359903333333`，最终 Y 响应 RETIRE 为 `15964276666667`，持续 `6604373333334 fs` / `990656` elapsed cycles。原生 SAIF 的时标和持续时间一致。任务开始前的 CPU 33697 次清零及实际 W/X/bias 提交检查在原日志中通过。
- `task-joint.stats.jsonl` 原件 SHA256 为 `7873dd56bdd18592cb9162f05a6f6e53906a8071da6b4e5104e1edfc484fc3aa`。第一行的 `begin_transaction` 错成 `task-joint`，`end_transaction` 含机器码样字节且 UTF8 在 position350 失败。完整原始头以 hex 保留，未用替换字符解码，也未制造新交易头。
- 其余 336 宏及 footer 均为严格 ASCII JSON。336×67 真实 pin dwell/transition、336×34 projection 及 336×121 = 40656 个 arc 实例通过整数守恒与边际重构。宏集合与实际 RTL / mapped binding 完全相同。
- 168 个宏满足固定 `ARM_UD_MODEL` 下 CEN=RET1N 全程已知1、包括零占时边沿在内 CTRL / CLK 无未知的保持前提，可条件关闭 2688 个 Q 内部边沿能量项。其中 2656 个 Q 位的绝对值仍未知，不赋 SP0.5，也不关闭下游标准单元的绝对状态影响。
- 其余 Q 的原始边沿也可分解为可执行计数界：已知二值 rise=8,357,710、fall=8,357,671；非二值转换仅 X→0=709 / X→1=315，全部1024位的条件前后已知真，无 known→X/Z。若补齐可访问物理地址的清零来源及固定模型首次读取证明，rise 为 [8,357,710, 8,358,025]、fall 为 [8,357,671, 8,358,380]。此条件计数区间不等于已完成能量资格；每位的原始解析计数已存入收据，供实际 library 表计算能量上下界。
- actual48 的 PT `returncode=0` 且存在独立 DONE 行。REJECT 字样仅出现在回显的 Tcl catch 分支，旧 FAIL 与真实完成证据矛盾。12 份原件不足以恢复旧 runner 的完整误判代码，因此纠偏收据不改原 FAIL。
- actual48 的全部 606 条查询、每阶段121个 arc 与数值均通过独立复核：84个已断言 arc 前后保持，其中2个 leakage、26个完整二值活动 arc 全为 default(A10+WEN16)，56个仅诊断子集。54个被注释的非平凡条件动态 arc 全属于诊断子集。其余37个 arc 从 UNINITIALIZED 变为工具 Default，不是 measured joint。

## 仍然缺少的证据

- export-51 未携带 actual36 的 `task-joint.simultaneous.jsonl`：服务器报告原件 12,303,644,205 bytes / 24,674,210 事件行。本包不从 projection 重建该 sidecar，不声称边界初态平衡、全同时刻分类或完整事件 replay 已通过。
- actual36 的完整 after-run freeze 未导出；actual48 的 before清单58项中只有 query/projection 两项有正文可在12文件包中核验，缺少 after / 完整源文件冻结。
- actual48 的 set/get 一致只证明条件 API 接收并保存这些数值，不证明 power engine 的全部 joint 语义。fixture 功率 `6.777e-04 W` 伴随默认 toggle/SP、无 clock 警告，不能用作全 SoC 能量。
- 比赛能量仍须覆盖同一任务窗口内 CPU、互连、SRAM、加速器，并处理下游绝对未知状态、实际工艺功耗及 STA 资格。

## 复核与服务器下一步

在仓库根目录用新的输出路径运行：

```bash
python tools/ppa/xu_joint_activity/xu_sram_joint_actual_review.py \
  --raw-dir docs/validation/xu-score-joint-actual36-48-offline-20261104/raw \
  --manifest docs/validation/xu-score-joint-actual36-48-offline-20261104/original-export-manifest.json \
  --out /tmp/xu-actual36-48-review.json \
  --expanded-out /tmp/xu-actual36-body-audit.json.xz
python -m unittest discover -s tests/host -p test_xu_joint_actual_review.py -v
```

可选 `--vendor-model <私有模型原件路径>` 会额外验证 SHA `81b55d87d5e6821d44037d6f0290ec89c9edb9582eb1932957f181aefc300d51`，不复制模型。`vendor-hold-development/` 保留先前本地官方模型正例与破坏前提反例；其工具平台为 Icarus，不能充当服务器 VCS 资格。

服务器恢复后，仅对已存在的 actual36 sidecar 做流式复核：

```bash
python3 tools/ppa/xu_joint_activity/xu_joint_sidecar_stream_review.py \
  --stats <actual36>/task_00/task-joint.stats.jsonl \
  --sidecar <actual36>/task_00/task-joint.simultaneous.jsonl \
  --out-dir <新收据目录>
```

该工具逐行计算完整原件 SHA、检查336宏首尾672条原始行、局部事件 replay 和直接转换计数平衡，只保留固定大小的宏计数，不加载整个12.3GB文件。它不穷尽跨宏全局 ordinal 唯一性，也不将 sparse sidecar 称为完整波形。

动态字符串诊断只有一个极短仿真，无 SoC / SRAM 模型。三组完全保持历史 begin/end 的3参数/2参数形状，分别使用原顺序、先收全部 handles、反向取值，对动态 `$sformatf` / 预存 SV string / literal 比较；所有实际返回字节以 hex 保留：

```bash
python3 tools/ppa/xu_joint_activity/xu_joint_string_probe.py \
  --include /eda/synopsys/vcs/vcs_2020.03-SP2-6/include \
  --out <新的短probe目录>
```

`string-probe-host/` 的18项只是严格 C 编译 + Icarus host预检。需 actual VCS 回执后才决定生产修复；即便小例通过，也不回填历史 actual36 交易身份，不为旧 FAIL 重跑20分钟仿真。

`xu_pt_q_absolute_sweep.py` 仅生成三个全新 fixture Tcl：原始 baseline、Q16 SP0/TR0、Q16 SP1/TR0，供恢复后批次执行。它保留原48的84个SSA和606个条件query，记录所有 Q 设置的副作用和输入 before/after SHA；不能证明 actual Q 的真实值或真实零切换。先验证 power engine 对原 conditional 注入的消费，再决定其 measured joint 适用范围。

对非 hold 宏的下一步按收据 `Q_initial_resolution.rows` 的1024位分别取真实 mapped Q arc，获取其实际 Liberty rise/fall energy 表及已验证的 slew/load 范围。未知首次解析的附加项保守取 `[0, X→1次数×E_rise上界 + X→0次数×E_fall上界]`，与已知二值计数项分开累加。下游标准单元取实际 SP0/SP1 sweep 或逐项绝对状态极值；多个独立 Q 的相关状态需逐单元做保守极值，不能把全0/全1两点自动称为全局最大/最小。未证明无读取赋值的未解析 Q 仍须保持 hold / 读取机会数界，不用 X 自环计数0冒充物理零切换。最终比较可使用有来源的全 SoC 能量区间，不要求猜测初始位。

## 文件

- `review.json`：336宏体、Q保持分类、actual48的606条数值及121 arc资格收据。
- `body-audit.json.xz`：完整展开的336宏121arc整数审查，明确不是修复后的原始capture。
- `raw/`：36份原件，可逆压缩后仍按原始 SHA 核验。
- `evidence-tools/`、`tool-identities.json`：本次工具与测试精确字节。
- `verification.log`：本次实际离线审查和7项正反例验证。
