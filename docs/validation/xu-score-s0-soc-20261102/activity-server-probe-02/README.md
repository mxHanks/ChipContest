# xu 服务器VCS SAIF监控第二轮

实际VCS Q-2020.03-SP2-6、debug_access+all，微电路两个40ns活动窗口，实际SAIF精度1fs。只有`rtl_on`策略完整记录clk、q及count[0..3]，各位TC/T0/T1与独立手算一致；本地对原始SAIF重新解析也通过。默认策略仍只记录clk；`sv`扩展调用在本安装报错，原始日志保留。不能把这些失败配方改写为成功。

通过的调用顺序为`$set_gate_level_monitoring("rtl_on")`、`$set_toggle_region(scope)`、`$toggle_start()`、`$toggle_stop()`、`$toggle_report(file,1.0e-15,scope)`。无中途report的双窗口以及有中途report的双窗口均累计80ns，排除20ns暂停；重复report不清计数，stop后等待不增加时长。正式任务仍优先每任务新进程、单窗口采集，避免累计差分。

这是本安装SAIF能力验证，未执行SoC功耗/PrimeTime读入、宏功耗表及活动映射覆盖检查，不代表全SoC能量或比赛资格。`probe.json`保存真实源/二进制/命令SHA及所有策略结果；`independent-inspection.json`由本地同一严格解析器对取回原始SAIF重算。取回原包SHA256为`c3b32c127bd2cac189c4854da164ab0fb1041aa9052d4b13052857b15c89b935`，大小3884字节，每页CRC及完整SHA核对后解包。

复现使用当前仓库源码，输出目录须新建：

```sh
python3 tools/scripts/xu_soc_activity.py probe \
  --vcs /eda/synopsys/vcs/vcs_2020.03-SP2-6/bin/vcs \
  --source tools/ppa/xu_activity_probe.sv --recipe debug --monitor-policy all \
  --out /absolute/new/activity-probe
```

本文及派生核验文件以外均原字节保留。文件清单排除自身，不包含厂商库/模型负载。
