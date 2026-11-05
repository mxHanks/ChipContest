# xu186：own S2e final155 覆盖缺口的只读原生查询

该工具只诊断 S2e 自己 final155 的覆盖缺口，不改 Chisel、RTL、网表、SDC、时钟方法、库、模型、TB 或数值格式。未执行远程操作，未启动 PT，未解除资格门。所有状态保持 `NOT_QUALIFIED`。

冻结身份：final mapped `3440182e…`、原 SDC `404c7de9…`、audit-forward scope `45037c4a…`、同两份工艺 DB 和同 PT `T-2022.03-SP5-1`。启动前后逐字节重核 14 份原生输入和完整 runtime；own155 的 42,338 项 FM 通过是原冻结 state 的回执，不将本查询表述为再次运行 FM。独立 task0 preflight166 原件必须终态成功、before/after 相同且绑定同一 target/capture。

继承185对原报告的逐项分类：9,219条 `no_clock` 全是 min-pulse 检查，其中 RDN(low) 8,766、SDN(low) 429、UART E(high) 24。不能称为9,219个实际 CK 缺钟。查询对9,257个精确 native 对象执行唯一性核对，并对全部9,219个 pulse pin 记录实际 cell/ref/library pin、clock/case/constant、库 min-width 属性。按库 pin 缓存属性读取，按 net 去重深遍历，避免每个 reset load 扫描同一大扇出。

深查询包括24对 UART E/D、两项 PMU unknown recovery、原五对 HF_RESET 来源/目的、相应 CK、五个 GPIOA 未约束输出和三个 PLIC min-cap 输出。保留 driver/load、actual startpoint、native/library arc owner/index/from/to/condition 和无 slack/max_paths/nworst 限制的 reset 查询。Tcl 不访问 `timing_arc full_name`，不把字面点转成层级；仅枚举后作字面 exact 匹配。库仅输出所选元数据，不导出 DB、模型或完整库正文。

可选属性在 native `redirect -variable` 内读取，原始诊断及 catch 码写入 `attribute-diagnostics.tsv`。不支持/空属性分别保持 `UNAVAILABLE` / `ABSENT_OR_EMPTY`，不当成0，也不因预期缺属性污染 mandatory 命令错误判据。mandatory report 缺失、失败、为空或包含 `Error:`，原生非零退出、错误版本、缺/重复实际 completion marker，以及未归属 mandatory 边界的原生 `Error:` 都失败并保留原件。全部9,257个 native metadata 行和9,219个 pulse 的实际 libpin 映射再次核对。查询成功仅表示取得指定诊断，不表示脉宽、recovery、150MHz、功能或能耗合格；zero-path、缺属性、static 常数和 UART 是否运行时失活继续开放。

入口只接受 fresh absolute 输出目录；存在即拒绝，不重启旧 worker。前台执行一次 PT，超时终止并保留失败结果。`state.json`、`query-status.tsv`、`attribute-diagnostics.tsv`、各原报告、`pt.log`、`output-manifest186.json` 保存状态、输入前后哈希、原生 PID/命令/耗时、可选缺口及原报告哈希。

本地检查与生成（没有远程启动）：

```sh
python3 -B /home/mxhanks/Projects/ChipContest-xu-score-opt/build/xu-s2e-coverage186/coverage186.py --describe
python3 -B -m unittest discover -s /home/mxhanks/Projects/ChipContest-xu-score-opt/build/xu-s2e-coverage186 -p test186.py -v
python3 -B /home/mxhanks/Projects/ChipContest-xu-score-opt/build/xu-s2e-coverage186/job186.py
```

`freeze186.py` 仅从185/178/159原件派生 target/reference JSON。运行时需要 manifest 列出的7个文件加 `manifest186.json`，部署至服务器 `~/Desktop/xu-s2e-coverage186/` 后，由主线程向既有153总控登记冻结的 `s2e_coverage186.json`。本工具不自行注册，不启动第二控制器。该 native job 占既有单槽，依赖 `s2c_readonly177` 终态及 `s2e_final155_preflight166` 成功；唯一进程标识为自己的输出路径。不得绕过总控手动启动。

原生输出路径：`~/Desktop/xu-score-optimization-20261102/s2e-own155-coverage-readonly-20261105-186/`。
