# xu S0 全SoC真实SRAM映射功能对照

服务器VCS Q-2020.03-SP2-6、同一SiFive GCC10.2.0和同一固件，完整12层对照PASS。原开发TB与独立全SoC top内336片指定SRAM宏版的每层输出、总周期、固件周期及所有PERF计数完全相同。1任务另加入仅共享端点行为RAM的harness对照，三者均1,375,864周期。

| layer | 原开发TB周期 | 真实宏版周期 |
|---|---:|---:|
| 0 | 1375864 | 1375864 |
| 1 | 1375860 | 1375860 |
| 2 | 1375864 | 1375864 |
| 3 | 1375860 | 1375860 |
| 4 | 1375864 | 1375864 |
| 5 | 1375860 | 1375860 |
| 6 | 1375864 | 1375864 |
| 7 | 1375860 | 1375860 |
| 8 | 1375864 | 1375864 |
| 9 | 1375860 | 1375860 |
| 10 | 1375864 | 1375864 |
| 11 | 1375860 | 1375860 |
| 总计 | 16510344 | 16510344 |

宏版包含ITCM32、DTCM32、shared256、weights16片RAMSP1024X16。真实厂商四态功能模型SHA81b55d87d5e6821d44037d6f0290ec89c9edb9582eb1932957f181aefc300d51；ARM_UD_MODEL，不启用INITIALIZE_MEMORY/SDF。未重新解释/缩放时钟：本次保持4ns HF、66ns LF的开发功能口径，不能标为150MHz合格、完整门级或功耗结果。所有304,128个48位结果对固定整数golden检查，608,256个Y写字退休。

`full-soc-campaign-01`保留Python3.6 keyword失败；`full-soc-campaign-02/nominal150-real12`保留VCS拒绝时钟声明顺序的编译失败，后续299a5b5修正仅修改生成TB。原始manifest逐文件SHA在解包时核对，本目录raw内容不覆盖旧日志。audit.json为独立逐层/汇总核对。厂商模型/二进制/数值向量未复制入本包，日志中的原始路径/SHA可在原服务器重放。

复现（原向量/RTL/固件冻结；目录须新建）：

```sh
python3 tools/ppa/xu_soc_ppa_verify.py --out /absolute/new/real12 \
 --sim vcs --clock-mode reference4ns --tasks 12 --variants reference macro \
 --firmware-schedule bias-hw-window --firmware-opt=-O2 \
 --firmware-experiment both-unroll-no-masks \
 --vendor-model /licensed/path/RAMSP1024X16.v \
 --cross-prefix /same/sifive-rv32-c/bin/riscv64-unknown-elf-
```

实际完整argv、源码/固件/日志SHA在原始result.json。相同源码于ac85d6a执行，后续299a5b5只修正nominal模式，reference4ns逻辑不变。包清单排除自身；不据本次PASS推定600样本、STA、缓存政策或全SoC能量通过。
