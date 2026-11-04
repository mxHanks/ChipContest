# reset61：原5项removal已消失，PT仍因2项recovery未测而失败

此为独立mapped延迟实验，**不是完整150MHz通过**。原始 `state.json` 保持 `FAIL / pt failed`。26份actual64原件共14,333,450字节，逐份XZ无损保存；每个展开SHA见[manifest.json](manifest.json)。完整源包43份payload已逐字节验证，233312字节tar.xz SHA256 `27322529f381e7795b8a2fa39321dc36db4f2e203874ebfc7ba81d17c7d3cea8`。

在清理50网表上，工具原生`insert_buffer -inverter_pair`为5个具体reset接收端各插入4对CLKINV0，总40个单元。DC return0、唯一marker、无Error；逐支路8单元、相同原driver、端点、唯一owner和全部新增连接均由执行Tcl检查。库和原RTL/SDC未修改。原55因DC缺省`dont_use`空值在插入前失败；61准确记录空值，依据同DB的实际PT palette false并要求native insertion验证，不把缺失属性声称为DC显式false。

PT在检测首个PMU recovery缺失时return1、marker0，因此后续10项逐sink报告和汇总尚未完成。失败之前实际产生的完整coverage为：

| 检查 | 实际结果 |
|---|---|
| removal | 17597 met、0 violated；原5项违例消失 |
| recovery | 17595 met、2 untested；两PMU SDN的`sdf_cond(ENABLE_NOT_D===1'b1)`为unknown |
| 全部check | 294473 total / 267349 met / 0 violated / 27124 untested |
| 电气 | 0 max-cap、187 min-cap |
| 已报告最差min slack | +0.00601495ns |

这不等于全部检查合格，0 violated不能掩盖27124个untested。时序场景仍为原70个first-D cut、6个forwarded-clock实验、原SDC和0.1ns uncertainty，不能推广为任意异步reset释放相位安全。两个PMU寄存器是异步置1、两级同步释放，一级D=0、二级D=一级Q；需进一步核查实际库条件和常量，不直接豁免unknown。mapped编辑自己的完整SVF链Formality另行执行，不能借用49/50的证明。

[实际执行helper](tools/launch_reset_buffer61.py) SHA `ce16e8e6f0e4cd1746a29c786b3cd3fccbb92713470ef5895420e5ab2a475339`。服务器命令（独立复现需改新输出名，禁止覆盖原目录）：

```bash
python3 "$HOME/Desktop/launch_reset_buffer61.py" 50 4
```

离线原件及实际结果复核：

```bash
python3 docs/validation/xu-score-reset-buffer-server-20261104-61/check-evidence.py
python3 docs/validation/xu-score-reset-buffer-server-20261104-61/check-evidence.py \
  --source-export build/xu-score-resume-20261103/next-results-export-64
```

该checker核对原件和范围，不运行EDA，不把原PT失败改为成功，也不认证SRAM内部、能耗或最终比赛资格。
