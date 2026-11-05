# xu：服务器统一实验总控150

唯一日常入口为`xu_experiments.py`。该标准库脚本在服务器分离运行，不依赖模型继续调用，
统一观察已有任务、依赖、资源、原件状态、失败与日志；`state.json`、`events.jsonl`和
`SUMMARY.md`持续保存进度。输入、任务注册和控制器字节均冻结；单个任务失败保留原件，
独立后续任务可继续。缺少实现的阶段必须先补上真实runner，不能靠总控猜命令。

当前四个注册：接续原S2e130、接续八候选138冻结/ownFM收据，原130终态后运行自己的S2e134，
134终态后运行独立baseline142报告诊断。134和142仅串行资源顺序，142不借134网表或证明。
八候选145正式活动、146全SoC能量、S2c147私有检查适配将以同一注册机制添加。
任何诊断完成都保持`NOT_QUALIFIED`，没有自动计算正式比赛得分或解除未知Q/150MHz门槛。

服务器96逻辑核、约709GiB可用内存、工作盘约1.54TB可用；原生查询只能证明当前license
checkout，无法读取配额。总控**不声明许可证余量**，只允许本用户已有一个EDA实验或
一个新实验占用整段原生槽位（含Python重哈希/阶段间空档）。内存下限16GiB、盘余量150GiB。
不扩大并发；真实native进程、已登记worker和启动意图都保留槽位。

首次将整个目录复制到服务器`~/Desktop/xu-experiment-control150`后：

```sh
python3 -B "$HOME/Desktop/xu-experiment-control150/xu_experiments.py" status \
  --out "$HOME/Desktop/xu-score-optimization-20261102/unified-experiment-control-20261105-150"
```

由首次bootstrap完成init、四项register及分离run。日后查看用上述唯一入口。
若控制器进程确已退出，可用同一冻结脚本`run --out <同目录>`继续，文件锁拒绝重复控制器。
已启动/完成任务不会重启；缺进程/不完整回执保留`ORPHAN_REVIEW_REQUIRED`，不因观察超时重跑。
新增真实适配器需生成唯一ID注册JSON，再用同一入口`register --out … --job …`，后台自动读取。
同ID注册允许逐字节重试，拒绝替换。不同候选可将来按许可证可观测配额扩展调度；当前上限1。

本地检查：

```sh
python3 -B /home/mxhanks/Projects/ChipContest-xu-score-opt/build/xu-experiment-control150/test_control150.py
```

14项反馈覆盖资源守卫、阶段间worker预留、真实进程退出/终态回执组合、失败保留、改动输入拒绝、
注册替换拒绝及重复init拒绝。没有将机制反馈当作服务器执行结果。所有子worker继续执行各自
完整before/after、网表/活动/证明身份及原生返回码/marker检查，总控不替代领域验收。
