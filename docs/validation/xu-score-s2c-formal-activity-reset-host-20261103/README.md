# xu S2c 活动观察复位修复：实际失败与本地完整验证

实际服务器首次 `task00` 在 `203333333 fs` 报 `unknown commit/FIFO ownership state`。原始失败日志、状态、VCS 构建及对应身份保留在 `server01-failure`；所选 S2c 原导出共 16 个文件逐项 SHA256/字节核对通过。没有使用该导出中其他仍在运行的 PE32 日志作为稳定证据。

根因是外部 TB reset 已解除时，实际加速器 `bus_rst_n` 的20级同步链及 gated core clock 还没有完成同步 FIFO reset。修复只改变被动 observer 的就绪判断：必须先在真实 `ACCEL.clk` 上采到 asserted `ACCEL.rst_n`；内部 reset 释放前不允许任何 accelerator/source request；首次释放就绪立即执行原全部 clear/commit/FIFO known/ownership 断言；后续 reset reassert/X 仍失败。既不 force DUT，也不把初始 X 清零。

干净 producer `446cb4332f05ed51b9ba00783376b5934fc8e582` 的完整11项测试在152.189秒全部通过，无跳过。真实 fixed reset链和真实 S2c wrapper 的停止时钟 fixture 保留初始 FIFO X，随后观察22个实际 asserted-reset采样边沿、27个启动观察边沿并通过。8个 reset/request/FIFO/commit 破坏例全部按预期失败。独立真实wrapper正例仍完整覆盖99行、3168组/POP退休、50688返回字和所有实际数据提交；另9个协议/数据破坏例拒绝。

`raw` 是本次原始命令/日志/生成物，`evidence-tools` 是被测实现源码。`summary.json` 记录冻结源/工具身份；`manifest.json` 对本目录其他全部文件记录 SHA256 和字节数。旧 baseline helper 及 guard 原样冻结，没有加入后续 joint mode observer。本次只是本地开发验证，不说明实际服务器 VCS/SAIF/完整 STA/能耗合格。

复现（干净、已提交的独立工具树）：

```sh
XU_S2C_SOURCE_ROOT=/home/mxhanks/Projects/ChipContest-xu-s2c-autogroup \
XU_CANDIDATE_ACTIVITY_TEST_EVIDENCE="$PWD/build/xu-s2c-reset-full-tests-new" \
python3 -m unittest discover -s tests/host -p test_xu_candidate_task_activity.py -v
```

后续服务器应以本 producer 或所有实现字节相同的干净独立工具树，在新的 `--out` 重跑 `--task-ids 0`，不能覆盖或重标原失败 `...-01`。完整命令见 `evidence-tools/xu_candidate_task_activity.md`；使用同一冻结 `d276b55/49a9436` 源、S2c mapped netlist、原分析 SDC、真实 SRAM 模型和服务器工具链。
