# xu S3 PE32 独立PPA准备支持

状态：**HOST_PREPARATION_PASS_NOT_EDA**。这是工具扩展及其本地准备证据，没有执行服务器DC/PT，没有新面积、时序、能量或资格结论。工具分支从主 `28e394a0c2e748841fb17ef5736f2f530b572de0` 创建，工具子仓保持f49；测量源码单独指向候选主 `94ce6f0f54fffdd590ff9a3ebad0197ec0fd9114` / 子 `fc3977d0a6d5f85fbfd871fd9439c01c9acab5f5`。本工具提交不改Chisel、RTL、固件、既有collector或alias helper。

新增显式 `s3-pe32` profile。完整子仓tree、9文件精确delta、模式和每一实际文件字节都须匹配批准的fc3977d；CPU/固定存储不在允许delta，perips的唯一架构选择为已有实例 `u_accel_icb_slave` 的PE32条件分支。拓扑检查识别新wrapper、scheduler、compute及W适配层。标准单元和1024×16 SRAM继续使用同一服务器DB及已冻结SHA；此阶段不增加128深宏库。

manifest必须冻结批准的候选main commit、`SYNTHESIS`、`DISABLE_SV_ASSERTION=1`、**`XU_ACCEL_PE32=1`** 这三个精确define及32PE配置；source_freeze与mapping identity均绑定define、variant和几何，不能用新代码静默综合旧8PE，也不能复用只绑定旧映射文件的8PE证明。新的accelerator retained参考为 `xu_pe32_icb_slave*`，实例层级不改。

W保持**32KiB逻辑容量**，32bank×512×16；使用32只1024×16宏，因此物理64KiB、padding32KiB。权重宏只允许在新compute的banks层级；全SoC **352只**1024×16宏，其中CPU/shared固定320只。生成的DC/PT在elaborate后和map后逐组核对实际宏、去重、要求全部RAMSP命名空间恰好被分组；少宏、额外/错误引用、隐藏未分组宏都会失败。inventory直接识别fc3977d，将物理W数报告为32及全SoC352，区分逻辑/物理/padding，不沿用旧16/336数字。这些是准备合同，真实mapped结果仍须服务器运行证明。

最终本地验证：15项profile/篡改检查、3项implementation、10项PPA flow及5项server launcher拒绝测试均PASS（raw/revalidation-03）。集合Tcl和DB均为明确标识的HOST fixture，不是EDA结果。另对实际候选通过真实CLI运行完整sourceguard、clock/topology review、dummy DB的generate→prepare→verify_prepared，成功冻结352宏及精确PE32 define；implementation-cli.log保留实际argv/输出。CLI的批准profile列表直接从实现集合导出，测试实际调用`--help`检查一致，避免新增profile只在Python函数中可用。旧baseline/H2/SRAM-bias/S2b/S2c五个profile的template和macro-check Tcl与28e394a逐字节相同；source-clock collector、SDC、alias helper未改。第一批13项及第二批14项profile测试、其各自工具hash及准备证据保留原文；payload-manifest.json列出所有保留raw payload的SHA/字节。准备归档包含manifest/Tcl/日志和明确无效的dummy DB，完整复制RTL留在本地build目录，可按命令重新生成。

旧VCD power入口对本profile明确拒绝：它缺少PE32候选专用clear/首REQUEST活动及全范围覆盖。后续须接入新候选的真实活动、映射、完整150MHz检查和全SoC单任务能量；不允许将旧8PE功率配上新32PE周期。新32PE源码对应的Chisel为此前代码提交d46486c中的GenerateRTL.scala和新增linear/XuParallelCore.scala，本工具没有增加第三份硬件候选。

复现本地准备（out必须新目录，DB故意无效，脚本绝不运行DC/PT）：

```bash
python3 docs/validation/xu-pe32-ppa-host-20261103/host_prepare.py \
  --candidate /absolute/ChipContest-xu-s3-pe32 --out /absolute/new/xu-pe32-host-prepare
python3 -m unittest discover -s tests/host -p test_xu_soc_ppa_profiles.py -v
python3 -m unittest discover -s tests/host -p test_xu_soc_implementation.py -v
python3 -m unittest discover -s tests/host -p test_xu_soc_ppa_flow.py -v
python3 -m unittest discover -s tests/host -p test_xu_soc_pe32_ppa_server.py -v
```

服务器独立launcher：`tools/ppa/xu_pe32_ppa_server.py`。它先验证冻结候选实际VCS完整8步+两项full12 control，重放wide/旧auto32/默认8的TASK/PERF/AUTO/PE、source/log/ELF/image哈希和同32/异8 binary；两个direct必须是实际VCS。接受未完成、控制缺失或源身份改变即拒绝启动。随后新建独立目录，以服务器原SMIC标准单元和RAMSP1024 DB的原SHA生成manifest并运行DC/PT；返回状态最多 `EXECUTED_NOT_QUALIFIED`，不能当成时序/功率/最终保留通过。

在服务器、工具提交已恢复到producer checkout后执行（默认detach并保存PID/log；`--foreground`便于外部作业管理）：

```bash
python3 /absolute/producer/tools/ppa/xu_pe32_ppa_server.py \
  --producer-root /absolute/producer \
  --source /storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/ChipContest-s3-pe32-01 \
  --acceptance /storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/s3-pe32-accept-01 \
  --out /storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/s3-pe32-ppa-campaign-20261103-01
```

若只上传launcher脚本到Desktop，仍须传入实际 `--producer-root`，使PPA模块和工具资产来自已合并本提交的独立工具checkout。原PT collector已知未闭合项保留，不为得到绿色状态隐藏exceptions、hold、coverage或未测路径。实际服务器报告随后单独归档。
