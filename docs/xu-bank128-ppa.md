# xu：紧凑 W32 的混合 SRAM 全 SoC PPA

此工具分支从 `e19304cb3f1f45ad2b691a9e316702ff2aeea9d1` 派生，只增加显式 `s3-pe32-bank128` profile 和独立服务器入口。候选主仓固定为 `f75880d4f06ccb7f1c16115bee501f53d9a2abb7`，E203 子仓固定为 `52cfbea1f79f10e44f7d1696f54015797f886b96`。工具和被测源码各用独立目录；候选源码不修改。

该候选的 Chisel 改动在候选分支中的 `src/main/scala/GenerateRTL.scala`、`src/main/scala/linear/XuParallelCore.scala` 和新增 `src/main/scala/memory/Sram128x16.scala`。本工具提交不改 Chisel、固件、数值格式、向量或 CPU。32 个 W bank 各由 4 个单读写口 128×16 深度片构成，读延迟为 1 周期；W 逻辑与物理容量均为 32 KiB、零填充。固定 SoC 使用的 320 个 RAMSP1024X16 保留，新增 128 个 W RAMSP128X16，共 448 个宏。宏总数增加不表示面积增加；需要真实库映射报告判断。

`xu_weight128_sram_adapter.sv` 与冻结候选用于 designated-model direct 测试的 adapter 完全相同，SHA256 为 `13e1077201f8eb751d34eee718b34d350cc5dfbc58cf0d853933b010c29faa79`。综合时替换生成的 `mem_128x16.sv`，不把商业仿真模型或第二个同名 behavioral memory 加入综合源。

`tools/ppa/xu_bank128_ppa_server.py` 在任何 DC/PT 命令前重新核对完整实际验收：

- 主/子 Git 原始对象、全部 tracked bytes/modes/symlink/gitlink、未跟踪 active source、定义及宏组配置。
- Generated 与 designated 模型分别完成单 bank 全 512 地址边界、wide32 和 compat8，共 6 个实际 VCS direct 编译/执行日志，7 个 direct tests 无跳过。指定模型只允许官方 `/storage1/admin_public_dir/SRAM_Lib_2025/RAMSP128X16/verilog/RAMSP128X16.v` 的固定 bytes/SHA，同时绑定状态记录及编译 argv，禁止 behavioral shadow；同时核对每项工作量、重叠和响应退休计数。
- host 69、numeric 42、固定 12 层 304128 输出、doctor、5 个 legacy、synthetic1/2、real12，加 `old32-wide-real12` 和 `bank128-oldauto-real12` 两个完整控制组全部终止并通过。
- 从原始日志重算逐层性能、PE/FIFO 工作量；核对 SiFive GCC 10.2、VCS Q-2020.03-SP2-6、源码、固件、ELF/image、模拟器本体及 build receipt。三组共同来源一致，原32与紧凑32使用相同 wide 固件 image，紧凑32的 wide/旧调度共用同一个模拟器。
- 所有读取的日志、ELF/image、模拟器和指定模型在审查结束再次核对；三份真实 DB 在 PPA 前后核对相同路径、bytes 和固定 SHA。

指定官方128模型的实际记录为 89548 bytes、SHA256 `f9d6d881746681dacd4f3851467561e441ee7190776ab566b1f0a729aa3ddb4d`；服务器入口在任何 PPA 前核对该固定身份，拒绝其他路径或自洽替换的模型记录。

真实 DB 身份如下；SRAM 仅进入 link_library，不进入标准单元 target_library。

| role | SHA256 |
| --- | --- |
| standard_cell | `f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723` |
| sram (1024×16) | `c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f` |
| weight_sram128 | `821c9344b787ecaae7ce222b9c5ab339b223759411dc20812f06210448a71bbe` |

同一服务器环境中，在 actual `s3-pe32-bank128-accept-02` 完成后执行（输出目录必须是新目录）：

```bash
xu_base="$HOME/Desktop/xu-score-optimization-20261102"
xu_tools="$xu_base/ChipContest-bank128-ppa-tools-01"
python3 "$xu_tools/tools/ppa/xu_bank128_ppa_server.py" \
  --producer-root "$xu_tools" \
  --source "$xu_base/ChipContest-bank128-02" \
  --acceptance "$xu_base/s3-pe32-bank128-accept-02" \
  --out "$xu_base/s3-pe32-bank128-ppa-campaign-20261103-01" \
  --weight-sram128-db "$xu_base/s1-ppa-campaign-01/xu-ramsp128x16-ss-0p99v-125c.db"
```

入口默认后台运行，写入 `boot.json` 的 PID 和持久 `driver.log`；`--foreground` 可用于已设置独立会话的任务。入口拒绝覆盖旧 campaign。复核接受日志或任一 EDA 步骤失败时保留原始输出，不宣称面积或时序通过。

本地验证命令：

```bash
python3 -m unittest discover -s tests/host -p 'test_xu_soc_*ppa*.py' -v
```

已有 profile 的 template、mapping identity 和宏检查 Tcl 与父提交逐字节一致；`prepare`、`memory_checks`、`clock_contract_checks`、`guarded_tcl` 的 AST 保持相同。新增 geometry/library/adapter/main/define 的重新签名篡改也必须拒绝。实际冻结候选的 CLI generate → prepare 使用三份明确标记的 dummy DB 跑通 164 个 SV 输入和 448 宏配置，此结果只证明工具源与 CLI 接线。它不是 DC/PT、mapped consistency、150MHz closure、面积或能耗证据。

所有 PPA 结果保持 `EXECUTED_NOT_QUALIFIED`；完整时序覆盖、SRAM PVT、综合前后一致性、正式 clear/request 窗口的全 SoC 单任务能耗以及最终保留判据仍需各自的实际证据。原8PE活动或 wrapper功耗不能代入该候选能耗评分，旧 VCD 入口对本 profile 明确拒绝。
