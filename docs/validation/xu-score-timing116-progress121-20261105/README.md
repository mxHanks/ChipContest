# xu actual116：progress121只读快照

这是服务器116在 **FM仍运行时** 的非原子快照。采集时state为
`RUNNING_NOT_QUALIFIED`、phase=`fm`、PID25920，live观察该PID存活。
没有FM终态、完整before/after核对或116资格通过结论；截断FM日志不能解释成失败或成功。

原包 `xu-server-progress-20261105-121.tar.xz` 未修改，542668字节，SHA256：
`07be4ca0267cdcbbec4263215c04e2dc5fdc8c6c5c544337d9d5da39898dbf14`。
内manifest绑定88份原件、24741085字节；原包同时包含117/120进展，本报告只分析116。
`tools/` 保存本地原export121及冻结116 worker/launcher；输入清单逐份保存哈希。

已实际核对DC/PT日志与state中的字节/哈希：两项returncode=0、errors为空、各1个完成标记。
实际执行脚本在state只有回执，121没有导出其正文。

|116实际PT结果|结果|
|---|---|
|constraints all-violators|min-cap、max-cap均无违例section|
|removal coverage|17597 MET，0 violated|
|setup报告最差slack|0.00000000 ns，50条均MET|
|hold报告最差slack|+0.00601495 ns，50条均MET|
|coverage|294473总检查，267349 MET，0 violated，27124 untested|
|recovery未覆盖|2条UNKNOWN保持|

HF reset五端点removal分别为+0.13275149、+0.13641581、+0.22710226×3 ns。
其五个定向recovery查询均为 `No constrained paths.`，不等于正slack。
LF watchdog到后三端点各有recovery +30516.76953125 ns、removal +0.56059015 ns。
所有这些只描述原工程约束下实际路径，不证明任意异步释放安全。

setup/hold未覆盖仍各3790条：constant_disabled3628、既有false_paths138、UART
no_endpoint_clock24；min_period10416未覆盖，min_pulse_width9126未覆盖。
min-cap/removal的这一进展没有清除coverage、reset/RDC、脉宽等独立义务。

**导出缺口：** export121的后缀白名单没有 `.tsv/.tcl/.v/.svf`。
因此没有最终mapped/SVF正文、cleanup-rounds/removed-cells、reset-paths/timing-slack TSV
或实际执行Tcl正文。`omitted121-bodies.json` 为空仅表示白名单内没有文件因大于8MB跳过。
目前不能从本包给出实际删除数量或逐轮列表。最终mapped回执SHA为
`16d29dea71ed2668b33c893e1a38be01a6eea02ca190ba8aabcb4658fe610292`，
repair.svf回执SHA为
`2574d971c759fc2650ed660b52b6219928c54117be156cdf616ccbea10f1d90a`；正文待后续取回。

复核命令（只读，无remote/EDA调用）：

```sh
python3 /home/mxhanks/Projects/ChipContest-xu-score-opt/docs/validation/xu-score-timing116-progress121-20261105/check-evidence.py
```

结果见 `verification121.json`。这仍是baseline116，不是S2e自身映射、完整VCS、面积预算、
功耗或最终评分的合格声明。本次没有Chisel修改；不引用整SoC area作为加速器面积。
