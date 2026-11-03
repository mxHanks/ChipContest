# xu PE64 独立PPA准备及服务器验收门槛

状态：**HOST_PREPARATION_PASS_NOT_EDA**。本提交新增工具 profile、真实源码冻结检查和服务器启动器；没有执行 DC/PT，不产生面积、时序或全 SoC 能量结论。本工具没有改 Chisel、RTL 或固件。硬件变更仍来自独立 PE64 候选，需按其提交与原始证据报告。

批准的候选主仓为 `3443fad8945577626d226b1cd53eadec89331a20`，E203 子仓为 `7aae96776e116d5e95d6ebb49d29a5fccce04ab9`。主仓在 6f47746 的基础上仅修复新增测试/部署 producer 的 Python3.6 subprocess 接口、切换全新 02 部署目录并记录本地复查，硬件和数值未变；首轮服务器失败仍需保留并另行归档。`s3-pe64` profile 只允许相对冻结 f49 子仓的 14 个精确文件 delta，核验完整实际文件字节、模式、符号链接及 Git 对象；主仓也必须匹配批准对象和实际内容，不能借助 `assume-unchanged`、`skip-worktree`、替换对象或额外活动源码隐藏变化。固定 CPU 与共享存储源码不在允许 delta 中。

综合必须使用精确三个 define：`SYNTHESIS`、`DISABLE_SV_ASSERTION=1`、`XU_ACCEL_PE64=1`，保留 accelerator 参考 `xu_pe64_icb_slave*`。manifest、mapping identity、source freeze 同时绑定 variant、define 和几何。W 仍为 32 KiB 逻辑容量，64 bank × 256 × 16 bit；实际使用 64 只 1024 × 16 宏，物理容量 **128 KiB**，padding **96 KiB**。全 SoC 共 **384 只**宏，其中 ITCM 32、DTCM 32、共享存储 256、权重 64。实际 elaborate/map 后仍须由服务器核对这些宏数量及层级，不能把准备合同当成已映射结果。

原 PE32 profile 保留自己的 `XU_ACCEL_PE32=1` 和 352 宏几何。所有旧 profile 的 template、macro-check Tcl、mapping identity 与父提交 `d933d62211c30b35b094ece5e6638d8e8c63af85` 保持一致；`prepare`、`memory_checks`、`clock_contract_checks`、`guarded_tcl` 函数 AST 也未变。新增 `verify` CLI 只核验已有准备清单及真实输入，不运行 EDA。旧 VCD power 入口拒绝 PE64：其缺少候选专用清零及首 REQUEST 至末结果 RETIRE 的活动，不能复用 8/32 PE 能耗。

实际本地检查日志位于 `raw/`：20 项主仓 guard（PE32、PE64 各 10）、5 项 PE64 profile 测试（含 11 次重新签名后的几何/define/层级篡改）、7 项服务器拒绝测试以及 33 项原 PPA 回归均 PASS。原 6f47746 通过 CLI `generate-02 → prepare-02 → verify-02`，三步 exit 0；这批原文保留，不改成新 main。更新 pin 后，`raw/revalidation-03/` 用实际 3443fad 重新执行 generate、prepare、verify 三个 CLI，均 exit 0，冻结 384 宏和精确 PE64 配置；7 项 server gate 测试亦重新通过。所用 DB 为明确无效的 host dummy 文本，绝非工艺库。首次 `verify-01.log` 因工具在准备后发生变化而正确拒绝，原文保留。`payload-manifest.json` 逐项记录原始 payload 的 SHA256 与字节数；复制的 RTL 留在本地 build，清单与 Tcl 可按下列命令重建。

`raw/candidate-reprepare-02/` 保存新候选部署 receipt 及本地 prepare-only 原始日志/状态。包为 680660 bytes，SHA256 `b6252dad7bb2fad8d3ff3320863e952567613f7f65bf483a061897bbb7a3edf7`；真实 clone / checkout 后核验 2713 个路径，状态 `PREPARED`，未运行 EDA。完整层仿真仍由服务器新 02 作业执行。

复现本地准备（输出目录必须全新）：

```bash
python3 docs/validation/xu-pe64-ppa-host-20261103/host_prepare.py \
  --candidate /absolute/ChipContest-xu-s3-pe64 --out /absolute/new/xu-pe64-host-prepare
python3 -m unittest discover -s tests/host -p 'test_xu_pe*_main_source_guard.py' -v
python3 -m unittest discover -s tests/host -p test_xu_soc_pe64_ppa_profile.py -v
python3 -m unittest discover -s tests/host -p test_xu_soc_pe64_ppa_server.py -v
python3 -m unittest discover -s tests/host -p 'test_xu_soc_ppa*.py' -v
```

服务器启动器 `tools/ppa/xu_pe64_ppa_server.py` 在创建任何输出或进程前，要求冻结候选实际 VCS 完成三种 physical64 direct 模式、三模式 boundary、stock 八步以及四项完整 real12 控制。它从原始日志重算 TASK/PERF/AUTO/PE，检查 ELF、image、simulator binary、build receipt、源文件和工具版本，以及同 physical64 的三份运行共用 binary、physical32/8 使用不同 binary、同 schedule 的逐层结果完全相同。只有全套终态验收才能新建 PPA 作业；RUNNING、缺少控制、非 VCS、源码变化或缺原日志均拒绝。

在服务器恢复独立 producer checkout 后执行：

```bash
python3 /absolute/producer/tools/ppa/xu_pe64_ppa_server.py \
  --producer-root /absolute/producer \
  --source /storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/ChipContest-s3-pe64-02 \
  --acceptance /storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/s3-pe64-accept-02 \
  --out /storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/s3-pe64-ppa-campaign-20261103-02
```

默认 detach 并保存 PID、argv 和 driver.log；`--foreground` 用于外部作业管理。标准单元 DB 与 SRAM DB 必须匹配此前服务器冻结的 SHA，继续用同一 SMIC SS / 0.99 V / 125 °C 工艺。作业完成状态最多为 `EXECUTED_NOT_QUALIFIED`；完整 150 MHz、映射一致性、候选专用活动和全 SoC 单任务能耗仍需各自证据，不能据此宣布保留或达成最高评分。
