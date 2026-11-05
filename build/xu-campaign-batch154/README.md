# xu：所有实验使用一个日常入口

服务器唯一日常入口：

```sh
python3 -B "$HOME/Desktop/xu-campaign-batch154/campaign154.py" status
```

首次`upgrade`会核验原4任务已终态、真实进程已退出，只停止原总控150的精确PID，
保留其完整快照后迁移到153，并向同一队列原子登记20个新任务。
候选worker、原结果和失败日志不被停止、删除、重启或覆盖。原150代码及旧快照保留。

```sh
python3 -B "$HOME/Desktop/xu-campaign-batch154/campaign154.py" upgrade
```

分离运行的服务器总控不依赖Codex在线、模型额度或本机继续发送命令。
它按依赖执行：接续S2e时序155→S2c完整原TB观察147→S2e原大报告独立流式复核156→
八候选各12个正式活动任务→各自同selected网表全SoC功耗、面积和逐层审计→自动生成统一报告。
8项活动任务按原候选顺序执行，功耗只依赖该候选自己的活动成功；独立候选失败仍保留并继续。
已有S2e130、134失败、baseline142及138全部接续在同一队列，不重复启动。

当前许可证总配额/余量未知，因此原生实验槽位上限1，整段worker（含Python重哈希空档）保留槽位。
内存下限16GiB、磁盘下限150GiB，实际余量每轮复查。不能把当前checkout数量当空闲许可证。
128/1024混合宏均按实际elaboration与selected mapped图全bijection核验，未知活动不补零。
8套活动任务使用相同服务器绝对VCS/SiFive路径及基线gcc/objcopy/objdump/VCS SHA，
不依赖交互shell的PATH选择工具。每项保留source、firmware、48张量、官方模型、SDC、SVF及日志身份。

所有结果保持`NOT_QUALIFIED`；诊断运行成功不代表完整150MHz、SRAM内部/未知Q能量或比赛资格。
面积使用同selected网表的新增加速器子树，2.25mm²限额；S2d与PE32修复图重新计面积。
当前没有新增生产Chisel/RTL修改。

如总控进程确已退出，再用同一入口`start`恢复总控并逐字节幂等登记原任务；
锁拒绝第二总控，不自动重跑实验或孤儿。`run`为前台控制器，便于有意调试。

```sh
python3 -B "$HOME/Desktop/xu-campaign-batch154/campaign154.py" start
```

自动总报告：`~/Desktop/xu-score-optimization-20261102/campaign-summary-20261105-154/`。
包含8候选对比CSV、96条逐层记录、原VCS/PT日志SHA、面积/诊断能量、资格状态和所使用JSON原字节快照。
原S2e/S2c/时序/诊断续行状态也纳入JSON快照，缺失或失败数值留空。
每个注册JSON的argv是实际复现命令；完整worker原结果和日志继续留在各自输出目录。
需要运行中快照时，可生成一个全新报告目录：

```sh
python3 -B "$HOME/Desktop/xu-campaign-batch154/campaign154.py" report \
  --report-out "$HOME/Desktop/xu-score-optimization-20261102/campaign-progress-NEW"
```

本地构建由`build_release154.py`复制并核验已提交的145/146/147/153/155/156，生成固定20jobs和
`release154.json`及归档。不得对已经冻结/部署的release覆盖修改；需要调整时使用新的编号输出。
