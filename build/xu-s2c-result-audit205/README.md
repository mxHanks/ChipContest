# xu：实际190全12层独立审计及S2e/S2c同方法对比

`actual191-attempt02/audit205.json`为实际原包审计及joint结果。独立审计不导入190/130/166；只使用Python标准库和逐字节冻结的safe171。没有远程操作、原生EDA或生产代码变更。原始179输出保持不变，其中对旧57时钟方法的历史警告仍有效；本次单独以新190与实际166比较。

| 同一forwarded-clock分析方法 | S2c own9c16 | S2e final155 |
|---|---:|---:|
| 真12层周期 | 11,887,872 | 10,420,116 |
| 全SoC任务诊断能量 | 2.638447146666933mJ | 2.3659452273331971mJ |
| 同各自测能网表的加速器面积 | 0.2948018380mm² | 0.3003096339mm² |

S2e周期减少12.3466673%，吞吐增加14.0857933%，本轮同方法**诊断能量**减少10.3281174%，面积增加1.8683045%。两组均低于2.25mm²限制。这里的能量从native已舍入的W值乘各自原始fs窗口重算，不声称比原报告更多测量精度。

**所有结果仍为NOT_QUALIFIED，不能作为比赛能耗或评分通过。** 各层5376个Q中5280位TX>0，4256位全窗TX；x_probability=0不证明物理Q已知。映射VCS fatal、完整150MHz资格、SRAM条件功耗及修补逻辑活动尚待解决。CPU pretask clear在SAIF测量窗外，无clear-phase能耗。

原包191为13,216,384字节，SHA `44770417f09a4244cbeea5690b4f21923e5d641de365094010ca7eeaf7c998b3`，392payload/367,456,367字节。safe171重新逐文件核验全部包体及新解包目录，路径/重复JSON键/软硬链接等守卫保留。190 task0/full12分别624/678份服务器冻结输入before=after；外部网表/RTL/SVF/库/SAIF正文未回传时，这些是服务器回执，不能冒称本地重hash。

本地逐字节核对59份保留reference，包括原57、原09完整不可变FM snapshot、native own42338 FM log、面积、原native336宏/22512pin TSV/JSON、12层原始measured统计与bridge。为避免复制115MB历史文件，references205.json固定repo相对路径及逐份bytes/SHA；运行会重hash所有引用正文及原manifest，不依赖194结论。

新190再次从native TSV重建336宏/22512pin，与原own57匹配；12层源SAIF精确SHA、统计及未知保持连续。190的每个power Tcl与原57逐字节比较，仅允许forward scope替代allprop、同字节SAIF的新路径和唯一完成marker三个变化；全部12对实际166/190的clock contract相同，SDC404c7d与scope45037c保持冻结。任务窗口S2c为6604373333334fs/990656cycles，S2e为5788953333333fs/868343cycles。

每层27份report中21份本地正文重扫，6份仅服务器稳定bounded SHA（两个约0.8GB pin report与四份超过16MiB报告）。190全12 output-manifest共298份本地body、72份hash-only、12份未打包SAIF；三类明确分开。没有把约20GB的pin原件声称为本地复扫。task0通过、完整12输出、原生log marker/version/rc、同网表面积、native宏power列表、每层Decimal P×time及总和均独立核对。

实际packet正例通过，13个必要反例全部拒绝：借网表、可变FM state、删层、inclusive周期、抹未知Q、漏runtime冻结、外部after改变、失败task0、借面积、hash-only pin回执改动、资格抬升、错误原包SHA、W改mW。反例只在内存改解析副本，原件未改。

复现输出目录/文件必须不存在：

```sh
cd /home/mxhanks/Projects/ChipContest-xu-score-opt
python3 -B build/xu-s2c-result-audit205/safe171.py unpack --archive build/xu-score-resume-20261103/xu-server-two-candidate-final-20261105-191.tar.xz --sha256 44770417f09a4244cbeea5690b4f21923e5d641de365094010ca7eeaf7c998b3 --out /tmp/xu191-safe-fresh
python3 -B build/xu-s2c-result-audit205/audit205.py --evidence-root /tmp/xu191-safe-fresh --archive build/xu-score-resume-20261103/xu-server-two-candidate-final-20261105-191.tar.xz --sha256 44770417f09a4244cbeea5690b4f21923e5d641de365094010ca7eeaf7c998b3 --s2e-audit build/xu-score-resume-20261103/audit179-final171/audit179.json --s2e-evidence-root build/xu-score-resume-20261103/final171 --s2e-archive build/xu-score-resume-20261103/xu-server-two-candidate-20261105-171.tar.xz --s2e-sha256 2f46075e337a21608faf8dc4f4308e90a31c610e6dd5d1dec4a4fb7bb17ae515 --out /tmp/xu205-audit-fresh
python3 -B build/xu-s2c-result-audit205/negative205.py --evidence-root /tmp/xu191-safe-fresh --archive build/xu-score-resume-20261103/xu-server-two-candidate-final-20261105-191.tar.xz --sha256 44770417f09a4244cbeea5690b4f21923e5d641de365094010ca7eeaf7c998b3 --out /tmp/xu205-negative-fresh.json
```

原包171/191及外部历史reference保持原归档位置，不另复制到205。第三方工艺库、模型、手册正文和凭据不在205中。
