# xu：实际117原生notifier与握手事件

117实际完成被动采集：117个原生节点、336次slice内value-change及117个终态snapshot，共453条事件。原编译参数与111相同，只有输出目录和新增只读VPI load不同；636份冻结文件前后身份相同。真实target为`DRNQV0_12TR40`。没有关闭timing/notifier，没有写、force或清零DUT节点。仍在与111相同的`9359423333333fs`、同TB216行因`unknown_shared_handshake`触发Fatal，真实进程返回0；25项原生hold告警均保留。**采集完成不等于task00、150MHz或能量验收通过。**

这些事件支持进一步查明故障，但不能将所有握手X归因于目标notifier。共享`rsp_ready`在`9359383413333fs`（serial175）已短暂X、`cmd_ready`在`9359383433333fs`（181）已短暂X，早于目标notifier；二者分别10ps后恢复已知。目标D也在195短暂X、201恢复1。

目标CK上升和D下降均在`9359390050000fs`（216/221），同tick记录NOTIFIER变化（224）与内部n0变X（225），Q和FIFO.o_vld在10ps后均变X（250/251）。随后FIFO.ren在261变X，下一上升沿后rptr_vec_r在277变X。共享cmd_valid于`9359416766667fs`（312）、rsp_ready于`9359416776667fs`（315）再次变X，直到Fatal仍为X。`event-selection.json`保留上述及相关事件的完整原生字段。

这支持“目标timing violation/notifier与Q/FIFO失知具有紧邻的原生事件链”，但**同tick callback serial仅是运行时通知顺序，不是完整物理因果证明**。本包没有原mapped网表正文或全部标准单元连接/模型正文，不能独立闭合notifier→n0→Q、FIFO→CPU→共享握手的全部因果连接，也没有排除更早的瞬态X等其它影响。应继续只读核查实际网表与库模型连接；不可直接禁用timing check作为修复。

`actual111-runtime-help.log`另记录原binary不支持`-help`，忽略后因缺任务参数在time0触发`only_frozen_task00`。它仅是帮助探测失败，不能当作功能运行或有效runtime帮助。原VCS命令行帮助另行保存。117 runtime tree成员集合仅在执行前检查；所有冻结文件执行后重哈希不等于再次检查新增成员。

原始simulation.log为263577字节，SHA256 `ecca99bd7acf7700c125a1f449010a73a9321bed1710cf6cf324cd83b682c825`；passive-event-review.json为167037字节，SHA256 `d24c39ff5647a34f03a77398721f16515e0cf50cc3c76886602281ae69b5b9fb`。本目录逐字选取121中的117原件；完整121清单保留，外包542668字节，SHA256 `07be4ca0267cdcbbec4263215c04e2dc5fdc8c6c5c544337d9d5da39898dbf14`。116和活动120原件不在本目录范围。

离线校验：

```bash
python3 docs/validation/xu-score-mapped117-server121-20261105/check-evidence.py
```

该命令重新解析所有原始事件、核对真实Fatal、冻结输入和原始121清单；不启动EDA。生产工具原字节及复现命令见[115/117工具交付](../xu-score-mapped-audit115-20261105/README.md)。新运行必须使用新编号隔离目录，保留原111/117日志。60项private gate与完整比赛资格仍待补齐。
