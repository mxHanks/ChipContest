# xu：统一实验总控153

这是已冻结150的独立修复版本，保留原150源码、服务器原件与历史记录。日常仍只有
`xu_experiments.py` 一个入口；继续使用原 `unified-experiment-control-20261105-150`
目录，不重新初始化、不重建队列、不重跑原实验。Python3.6+，仅标准库，不访问网络。

153只修复排队恢复机制，保持16GiB内存、150GiB盘余量及本用户一个原生实验槽的策略。
许可证余量仍未知，所有候选和控制器状态仍为 `NOT_QUALIFIED`。

- 注册先写入并fsync不可见于 `*.json` 扫描的临时文件，再原子发布和fsync目录；
  同ID仅接受逐字节相同的重试，失败临时文件保留。
- 持久启动意图之后的异常保留槽位并继续观察；即使某行已记录终态，也重新核对真实
  worker/子进程是否仍在。找不到进程且宽限120秒已过时保留孤儿待审，绝不自动重试。
- 新worker保存 `/proc` 的PID、UID、startticks及完整argv；恢复时从已冻结的spawn
  receipt读取身份，数字PID复用或命令变化不能成为原worker。相同process birth命令
  改变、或原句柄暂时不可读时继续保留槽位。既有150行的历史身份不被编造。
- `success` 依赖若已失败、孤儿或拒绝，后继终态为
  `BLOCKED_DEPENDENCY_NOT_QUALIFIED`；其它独立任务继续。`terminal` 资源顺序依赖仍可
  接续已失败的独立诊断。原失败结果、原日志与路径保持。

先上传三个文件到服务器独立目录 `~/Desktop/xu-experiment-control153/`：
`xu_experiments.py`、`migration153.py`、`bundle-manifest153.json`。
核对 `UPLOAD-SHA256SUMS` 后，只有确认原150控制器进程已停止时，执行一次：

```sh
python3 -B "$HOME/Desktop/xu-experiment-control153/migration153.py" \
  --out "$HOME/Desktop/xu-score-optimization-20261102/unified-experiment-control-20261105-150"
```

迁移器不会停止任何进程。它持有原 `controller.lock` 和 `register.lock`，另持迁移锁；
验证原150 SHA `d7813ac3745ff1aa5b5efc92eef298a6577abef774259f9285aae605c466db2f`、
原state、已登记的逐字节注册及真实进程命令。仍有原控制器或锁占用时立即拒绝。
随后在原目录的兄弟目录 `*.before153-<唯一ID>/` 保存完整文件树快照和逐文件SHA256；
若文件或树成员在复制期间变化则拒绝迁移。迁移只将 `state.worker` 绑定新脚本，
保留全部jobs/runs，另保存迁移回执。释放原控制器锁后才分离启动新控制器，由原锁继续
拒绝重复运行，并核对新PID/startticks/argv及state中的当前controller身份。

成功回执状态为 `MIGRATED_SAME_OUT_CONTROLLER153_RUNNING_NOT_QUALIFIED`。
迁移原件和新启动日志采用唯一文件名，不覆盖原 `controller.log`。
迁移若在身份重绑后失败，不再次init或再次迁移；先查看同次迁移回执、原快照和新PID。
只有确认控制器已退出时，用同一153冻结脚本 `run --out <原目录>` 恢复；worker仍不重试。

迁移后日常查看和入队：

```sh
python3 -B "$HOME/Desktop/xu-experiment-control153/xu_experiments.py" status \
  --out "$HOME/Desktop/xu-score-optimization-20261102/unified-experiment-control-20261105-150"

python3 -B "$HOME/Desktop/xu-experiment-control153/xu_experiments.py" register \
  --out "$HOME/Desktop/xu-score-optimization-20261102/unified-experiment-control-20261105-150" \
  --job /absolute/frozen-job.json
```

新候选各自使用唯一output根目录作为 `process_contains`，提交真实CLI、逐文件冻结输入、
结果state、成功/失败状态及依赖；不注册空计划。153不补造领域证据，不将局部功能、
未知活动、wrapper功耗或诊断完成提升为150MHz、完整功能、面积或全SoC能耗资格。

本地复现：

```sh
python3 -B /home/mxhanks/Projects/ChipContest-xu-score-opt/build/xu-experiment-control153/test_control153.py
```

检查仅使用临时文件及普通Python stand-in进程，实际验证互斥锁、原子注册可见性、
启动后持久化失败、终态活worker保槽、PID/命令身份、依赖失败与完整迁移。它不运行
EDA或服务器实验，不证明任何候选的比赛资格。原150两故障的独立复现保存在
`build/xu-mapped-private147/independent-control150-review147.json`，原150不修改。
