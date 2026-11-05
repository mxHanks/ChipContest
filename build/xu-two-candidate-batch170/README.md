# xu：仅S2e/S2c的总控接续170

本批次只向已运行的冻结153总控登记三个新任务，不启动第二个总控，不重跑既有任务。
所有状态保持`NOT_QUALIFIED`。166/167已完成独立本地审查；本地检查不代替服务器原生运行。

顺序为：164原报告审计终态 → S2c167被动未知状态定位 → S2e166同155映射task0功耗预检 →
预检成功后完整12层。S2e预检另要求自己的155时序/FM任务诊断成功；S2c定位失败保留原件，
不阻挡独立的S2e功耗实验。full12在task0失败后被总控阻断。

三个job均占用完整native槽位，保持同一时刻一个实验。`run170.py`在同一进程内运行原166 CLI，
其kernel命令行只包含当前唯一输出目录，避免`--preflight-root`/`--target-root`使153把其它已完成
job误识别为正在运行。原CLI参数完整保存在两个`*-command.json`，entry、wrapper和命令文件均冻结。
不使用exec或新子调度器；EDA子进程仍完全由原166负责。

服务器唯一日常入口不变：

```sh
python3 -B "$HOME/Desktop/xu-campaign-batch154/campaign154.py" status
```

本批次登记命令：

```sh
python3 -B "$HOME/Desktop/xu-two-candidate-batch170/register170.py"
```

登记脚本严格校验原153 SHA及PID/startticks/argv、两候选scope163回执、完整manifest及全部runtime SHA。
先检查全部三个job，再使用153原子register；同ID仅允许逐字节幂等，已存在输出禁止重新启动。
原始注册、输出与失败不覆盖。登记回执位于`B/two-candidate-registration-20261105-170.json`。

本地生成和复核：

```sh
python3 -B build/xu-two-candidate-batch170/build170.py
python3 -B build/xu-s2e-final-power166/verify_manifest166.py
```

`manifest170.json` SHA为`8a3e6ac5b4cd7ba3cf039d4a00b653825f541b5375911775337a13d472cc7808`。
14文件部署原包`runtime170.tar.gz`为38185字节，SHA
`d07498667307816b6fce000d5bbd6427a5e787469ad079b16ba05be6adb32bed`。
原包只含runtime、manifest和job配置；不含凭据、库或工艺模型正文。
服务器部署/登记/原生执行状态以实际回执为准，不能仅凭上传或送键认定运行。

本批次没有新增生产Chisel、RTL、MMIO、向量、数值格式或时钟约束改动。
