# xu：仅S2e主方案与S2c对照的同口径比较

用户2026-11-05明确只保留S2e和S2c。以下是**各自原网表**的已测正式窗口与诊断能量，
不是新评测、比赛资格或得分承诺。表中的每行面积和能量绑定该行同一映射身份。

|指标|S2c对照原图9c16|S2e主方案原图0cfac|变化|
|---|---:|---:|---:|
|12任务elapsed总周期|11,887,872|10,420,116|减少12.3467%|
|各层elapsed周期|990,656|868,343|每层少122,313|
|12任务全SoC诊断能量合计|2.755345mJ|2.454516mJ|减少10.9180%|
|加速器面积|0.294801838mm²|0.2950003804mm²|增加0.06735%|

固定HF150MHz/LF32768Hz、1fs、signed16/40/48、同12组X/W/bias/Y、任务前清零及
首源REQUEST到最后Y响应RETIRE窗口。清零不计入该原任务窗口；正式指南口径和未知活动资格继续核验。
12份原PT功耗采用工具报告的舍入精度，长小数仅用于复现乘法，不代表额外测量精度。
每组5280个SRAM Q存在TX、4256个整窗TX；条件功耗和下游未知状态未解除，表中能量不可代入评分。

**最新S2e时序修复图155（3440182e…）必须单列**：
其加速器面积为0.3003096339mm²（低于2.25mm²），完整own FM 42338点成功，
但该图的全SoC能量尚未测。不能把它的面积和原130能量拼接为一个配置。
其27217个未测检查、31未约束端点及3项PLIC mincap仍未闭合，不能宣布完整150MHz通过。

`per-layer.csv`列出12对任务周期、两组功耗/诊断能量、原VCS/PT/power报告SHA。
`comparison.json`记录三张映射身份；155能量保持null。
`inputs/`是上游归档选取的原报告/回执或独立已验证CSV，`source-manifest.json`保存原路径及逐文件SHA。
本checker重新核对全部输入字节、面积报告与执行回执的绑定、130完整输入前后身份、逐层算术与日志收据，
不会把未包含的24份原大pin report或工艺库当作在此重读。

复现本比较：

```sh
python3 -B /home/mxhanks/Projects/ChipContest-xu-score-opt/docs/validation/xu-score-two-candidate165-20261105/check-comparison.py
```

原始上游独立验证与服务器命令见：

- [正式周期比较](../xu-score-formal-cycle-comparison-20261105/README.md)
- [S2c完整12任务原功耗审查](../xu-score-s2c-full-soc-power-server-20261104/README.md)
- [S2e130终态原件](../xu-score-terminal151-20261105/README.md)
- [155完整终态与147/156失败原件](../xu-score-failed159-20261105/README.md)

后续只推进两组自己的资格与同图测量，不对其它候选追加实验。本轮未新增生产Chisel/RTL修改。
