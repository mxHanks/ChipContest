# xu S3 32PE 服务器完整12层独立实验

真实服务器结果：新32PE wide调度 **11,376,501周期**，同32PE RTL旧auto及默认8PE旧auto均 **11,842,200周期**。wide减少 **465,699周期，3.932537873%**。三项均完成304,128个signed48结果、608,256个Y写字并通过逐位比较。此为开发窗口的服务器性能结论，仍未保留为最终参赛配置。

冻结主提交 `94ce6f0f54fffdd590ff9a3ebad0197ec0fd9114`、E203子提交 `fc3977d0a6d5f85fbfd871fd9439c01c9acab5f5`，独立分支 `codex/xu-s3-pe32`；生产实现来自主代码提交 `d46486c9820e909ab9469a5fa1f10eee022988c3`，94ce6f0只补本地证据。实际同SiFive GCC-Metal10.2.0-2020.12.8、VCS Q-2020.03-SP2-6_Full64、`-O2` / `both-unroll-no-masks`。三路的157个实际RTL/TB源、固件源、runner/contract、工具、fixture及48个向量SHA相同。物理variant和固件schedule分别记录；两个32PE调度使用相同仿真binary声明SHA，默认8PE使用不同binary。两个旧auto对照的全部逐层PERF计数也相同。

| 层 | 默认8PE旧auto | 同32PE旧auto | 32PE wide | wide减同32PE旧auto |
| --- | ---: | ---: | ---: | ---: |
| 0 | 986850 | 986850 | 948039 | -38811 |
| 1 | 986850 | 986850 | 948042 | -38808 |
| 2 | 986850 | 986850 | 948042 | -38808 |
| 3 | 986850 | 986850 | 948042 | -38808 |
| 4 | 986850 | 986850 | 948042 | -38808 |
| 5 | 986850 | 986850 | 948042 | -38808 |
| 6 | 986850 | 986850 | 948042 | -38808 |
| 7 | 986850 | 986850 | 948042 | -38808 |
| 8 | 986850 | 986850 | 948042 | -38808 |
| 9 | 986850 | 986850 | 948042 | -38808 |
| 10 | 986850 | 986850 | 948042 | -38808 |
| 11 | 986850 | 986850 | 948042 | -38808 |
| 总计 | **11842200** | **11842200** | **11376501** | **-465699** |

完整逐层PERF/AUTO/PE保留在原simulation.log、verification.json及per-layer-comparison.csv。wide每层实际MAC拍从202,752降至50,688，POP/launch/done从3,168降至792；通过真实32个PE enable逐拍求和，wide与32PE兼容调度均为每层1,622,016次enabled-lane MAC，未隐藏额外24路运算。共享读仍23,232、共享写仍50,688，MMIO读从54,648降到52,272、写从15,497降到13,121。12层compute_wait从539,352降到197,208，writeback仍7,985,759周期，说明写回/CPU搬运仍占较大部分；这些重叠活动不能再加到阶段周期中。本机GCC14.2/Verilator单层曾改善5.54%，保留原证据，不能替代本次服务器3.9325%的结论。

改动的生产Chisel如下，代码与本地筛选相同，服务器验收未再修补RTL：

- `src/main/scala/GenerateRTL.scala`：新增显式32/64几何生成入口；本轮只集成和验收32PE。
- 新增 `src/main/scala/linear/XuParallelCore.scala`：固定64×256矩阵、单套32PE compute及32个W bank、X及bias缓存，旧8lane兼容mask，32lane输出、两槽结果FIFO和自动8group调度；旧子组结果捕获时锁存，POP在响应退休后推进。
- 新增 `src/test/scala/linear/XuParallelAutoGroupCoreTest.scala` 为测试，不计生产电路。

手写新增wrapper、固定perips中原实例的可选 `XU_ACCEL_PE32` 分支、firmware/TB/contract配套修改均在冻结提交中。子仓相对f49的精确9文件delta在git-source-audit.json；CPU、共享SRAM和互连实现不在允许delta。W逻辑32KiB（32bank×512×16），沿用1024×16宏使物理容量64KiB、padding32KiB；源结构预期固定320+W32=352宏，实际映射面积仍需该候选自己的EDA结果。

强制direct wide和compat均真实使用VCS，主direct及host再次执行的两套compile/simulation原文齐全。wide验证2行/16组/512结果、27次launch/done、11124接受=退休；compat为2行/64组/512结果、99次launch/done、11737接受=退休。实际lane活动、满FIFO、背压、POP退休、旧结果保持和mode边界在冻结TB中检查。cached wrapper实际VCS也通过4909接受=退休。host62项、skipped3（Icarus辅助）；numeric42、vectors12、doctor、新32PE上的真实assembly legacy5、synthetic1/2、wide real12及两项control real12，十步全部PASS。legacy每个实际make命令携带`XU_ACCEL_PE32=1`，不采信host里的mock PASS代替assembly运行。

本目录129份原服务器payload来自279572-byte传输包，SHA256 `5330f5c8b03d9a8f8077f1dbc51908881bb9d472ebad3c3b4fd73d81aa180336`；原manifest全部174份严格校验后只选择S3验收和启动目录，未混入同时传输的时序/功耗probe。原始空白与字节保持不变。部署归档245598 bytes/SHA `c3c50ffc24e1cd2c3f7eaaf1a293162f103ee04d875bc25778309cf4a3fef997`的原receipt、2510路径源清单及launcher保存在deployment。

准备脚本独立从冻结Git读取全部2510路径，4个工具树符号链接按Git目标解析，逐项匹配部署源清单；199个实测/复现Git源blob打包在frozen-git-sources.tar.xz。只读重放校验全部原payload、源/日志声明、完整TASK/PERF/AUTO/PE/SOC、direct/legacy后端及实际计数、三路身份和服务端比较，重新计算固定304128个整数输出，并拒绝86种从实际日志构造的缺失/重复/计数/PE工作量/POP/重叠/FATAL破坏。check-evidence.py不运行EDA或仿真。

未取回ELF、装载镜像、simulator二进制或实际server向量文件，其声明SHA不冒充本地重哈希。原TB为HF4ns/LF66ns、从首共享源读接受至最后Y响应退休，并非候选正式任务前物理清空/首REQUEST窗口。完整150MHz STA、mapped一致性、同配置面积、全SoC单任务能量及正式资格仍须独立完成；不能把旧8PE面积/功率与这些32PE周期拼接评分。

```bash
python3 docs/validation/xu-score-s3-pe32-server-20261103/check-evidence.py
```

同服务器版本工具链、冻结checkout与全新out复现wide标准八步及两个control（cross-prefix见原state argv）：

```bash
python3 tools/scripts/server_accept.py --sim vcs --cross-prefix "$xu_cross_prefix" \
  --accel-variant pe32 --firmware-schedule bias-hw-pe32-autogroup-window \
  --firmware-opt=-O2 --firmware-experiment both-unroll-no-masks --out "$xu_new_wide_out"
python3 tools/scripts/e203_soc.py --mode real --tasks 12 --sim vcs --cross-prefix "$xu_cross_prefix" \
  --accel-variant pe32 --firmware-schedule bias-hw-autogroup-window \
  --firmware-opt=-O2 --firmware-experiment both-unroll-no-masks --out "$xu_new_same32_control_out"
python3 tools/scripts/e203_soc.py --mode real --tasks 12 --sim vcs --cross-prefix "$xu_cross_prefix" \
  --accel-variant pe8 --firmware-schedule bias-hw-autogroup-window \
  --firmware-opt=-O2 --firmware-experiment both-unroll-no-masks --out "$xu_new_default8_control_out"
```

完整强制两个direct、源冻结和上述十步的部署复现入口为deployment/launch.py及其原package清单；direct编译/运行精确argv也在各direct日志首行。所有重新执行目录必须全新，保留失败和负结果。
