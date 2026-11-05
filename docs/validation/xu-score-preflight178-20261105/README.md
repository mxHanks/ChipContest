# xu：178同155图单层原生功耗预检

已取回原包 **1313588B**，SHA
`da981b5ed9d5c07524ece0b454fa7273f61e222917db9037d4155407e0a7ee1a`。
110份载荷41417609B全部逐字节校验；原包保留171快照语义，超限源报告及两份pin正文仅带服务器有界SHA。
独立审计代码提交`3d6dddd`，没有导入166/130运行时代码来重复其结论。

|单层task0|实际值|
|---|---:|
|formal elapsed|868343 cycles|
|窗口|5788953333333 fs|
|全SoC原生报告功耗|0.0341 W|
|诊断能量，报告P乘原窗口|0.1974033086666553 mJ|
|同图加速器面积|0.3003096339 mm²|
|出现TX的Q/全窗TX的Q|5280 / 4256 bit|

目标155映射SHA`3440182eca862290a874bedc4eb3f94168681a7028d584d15217a13dbeafa794`；
capture仍是120/own89/109，目标通过自己的三段有序SVF、42338点原生FM绑定。
336宏/22512pin TSV与JSON重建一致。21份原生报告正文已本地重扫，6份仅核稳定server boundedSHA与execution回执。
完整12层在本次快照时仍准备中，总能量为null；不能从单层外推完成。

这份新155测量采用原SDC和forwarded-clock scope；旧S2c57/130采用all-clock propagated方法。
审计明确`analysis_method_mismatch=true`，故不据新图数值计算相对旧图的节能百分比或比赛得分。
2.25mm²面积限额下该综合面积有余量；未知Q、条件SRAM功耗、门级功能及完整150MHz仍待验收。
所有结果 **NOT_QUALIFIED**。

复现（解包及审计输出目录必须全新）：

```sh
python3 -B docs/validation/xu-score-preflight178-20261105/check-package.py unpack \
  --archive "$PWD/docs/validation/xu-score-preflight178-20261105/preflight178.tar.xz" \
  --sha256 da981b5ed9d5c07524ece0b454fa7273f61e222917db9037d4155407e0a7ee1a \
  --out /tmp/xu178-evidence-fresh
python3 -B build/xu-s2e-result-audit179/audit179.py \
  --evidence-root /tmp/xu178-evidence-fresh \
  --archive docs/validation/xu-score-preflight178-20261105/preflight178.tar.xz \
  --sha256 da981b5ed9d5c07524ece0b454fa7273f61e222917db9037d4155407e0a7ee1a \
  --out /tmp/xu178-audit-fresh
```

native PT日志SHA和原功耗报告SHA在`task0.csv`；原SAIF、网表、库、SVF及巨型pin报告正文仍在服务器，
输入前后SHA相同是原服务器记录回执，不声称本地重新读取这些未返回正文。
