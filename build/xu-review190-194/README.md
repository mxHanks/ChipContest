# xu194：190同方法S2c功耗工具的独立本地审查

结论：**本地审查通过，可以纳入既有153单槽总控；尚未运行190原生PT，继续NOT_QUALIFIED。** 审查对象提交 `2d61547`，本审查未改190代码、生产代码或服务器状态。

冻结190入口 `b8b1ab702fd86e83e0cb0eeb1bf760fc8e00f47ae86a7f3008fde39ca4c4176f`，manifest `93678963b27f474a5f16dc57c7d86852a03bda6e5e7f91193c3bad0a0cc20378`。preflight job `2de85d705e6ae974a1e0a5efb1af42a4b94f2a8455b003ca980efacfe20047ee`，full12 job `1287aea85259c269b1268e1bd682789de3fea8398386193842803ff1782ce987`。

独立消费47份实际返回原件，共115,160,645字节；全部按69/09/22/178各自原manifest重核，清单与哈希在`review194.json`。178原压缩包另外与既存SHA `da981b5e…`相符。这里没有宣称本地重核未返回的367份服务器输入或原SAIF正文；这些文件必须由190在服务器启动前后重核。

实际证据的交叉核对包括：

- S2c自己`9c16d5ec…`映射、`404c7de9…`SDC、同336宏/22,512pin的原20 native TSV与inventory JSON逐位全等。原57每层measured表均是同22,512个唯一pin，全部bit的T0+T1+TX+TZ+TB守恒。
- 原own S2c FM日志唯一成功marker、实际42,338 passing compare points、before/after相同和自己的PPA映射身份。自己的面积原报告给出加速器0.2948018380mm²、SoC3.365797600429mm²。没有借S2e155或baseline116图。
- 原57完整12层，每层990,656周期、6,604,373,333,334fs。每层原Tcl严格只允许把all-clock propagated替换为45037c forward scope、SAIF物理路径、completion marker三项变化；归一相同SHA的SDC物理路径后，时钟块与实际178返回的166 Tcl逐字节一致。没有改原SAIF信号值或未知统计。
- 每层仍有5,280个Q含正TX，其中4,256个全窗口TX。该方法对齐不解除未知Q、条件边沿/内部功耗、映射后功能fatal、150MHz覆盖或真实时钟活动的缺口，不产生新功耗结果、改善百分比或评分。

源码审查确认：190会逐字节重核原57的367输入，并额外核对自身完整runtime、原own FM/PPA/area/source、原12层SAIF/bridge/measured、实际PT和两库；新原生inventory必须与原336/22512图逐位全等。prepare/verify/run/campaign保持自己的输入前后哈希，按层保存PT marker/version/returncode、27份期望原报告及两份22,512pin/336macro原生完整性，原大报告用流式哈希和扫描。任何失败停止并保留，timeout留PID/命令/实际returncode/日志identity；fresh输出与flock拒绝重复/覆盖。

full12必须重新检查实际成功的同图/同方法task0；不是仅检查终态字符串。另做两项独立测试，其中preflight测试包含1正例及8负例：prepared-only、错context、变log receipt、before/after改变、错frozen digest、错taskset、变报告、缺实际marker均拒绝。此测试明确模拟native文字并隔离prepared_verify，不能作为EDA通过证据。

18项190 hostchecks独立重跑通过；actual metadata join也通过。metadata join对未返回的服务器文件SHA有明确mock，只证明JSON结构可联接，未用于宣称服务器文件或原生通过。运行时Python脚本经Python3.6 grammar检查；same-PID runpy让每个job的`/proc`参数只含自己的output root，full12的preflight路径只在冻结command JSON中，防止总控误认另一个worker。job依赖保持186 terminal→190 task0 success→190 full12，均native占单槽。

复现（本地、只读，不启动EDA）：

```sh
python3 -B /home/mxhanks/Projects/ChipContest-xu-score-opt/build/xu-review190-194/review194.py --out /tmp/xu-review194-fresh.json
python3 -B /home/mxhanks/Projects/ChipContest-xu-score-opt/build/xu-review190-194/test194.py
python3 -B /home/mxhanks/Projects/ChipContest-xu-score-opt/build/xu-s2c-common-power190/test190.py
python3 -B /home/mxhanks/Projects/ChipContest-xu-score-opt/build/xu-s2c-common-power190/check_metadata190.py
```
