# ChipContest / E203 与当前工程融合运行记录

日期：2026-10-17（Asia/Shanghai）。队友仓库快照来自 `ChipContest` 主仓库 `30e737ca37bc7d3077db1877ee89072ac4dfc723`，E203 gitlink/Fork 为 `35e7c960dc151d8ade9deffcb30cdc13c840d541`。原目录只读；融合在 `integration/ChipContest/` 归档副本和当前工程新增 `soc/`、`sim/` 文件中完成。

## 按 quickstart 的实际运行

| 入口 | 结果 | 证据 |
|---|---|---|
| E203 `make clean && make install && make compile SIM=iverilog && make run_test SIM=iverilog DUMPWAVE=0` | PASS | `artifacts/integration/20261017-teammate/e203-original.json`；日志包含唯一 `TEST_PASS`，退出码0。每次从 clean 副本安装，避免 `install/rtl` 陈旧嵌套。 |
| ChipContest 原版 `scala-cli test . --server=false --jvm 21` | FAIL（10成功、1失败） | `chisel-original.json`；`WeightBankArrayTest` 在保持 `loadWen` 时切读，触发 `ren && wen` 断言。失败是测试激励错误，不删除断言。 |
| 融合副本 Chisel 全回归 | PASS | `chisel-fused-final.log`；13 tests、9 suites、0 failed，包含新增真实12层测试。运行前把项目 `.tools/bin` 放入 PATH，使用 bounded ChiselSim 将并行度限制为2。 |
| `GenerateRTL` DotProductEngine/LinearComputeCore/LinearLayerEngine | PASS | `generate-*.log`；生成文件在 `integration/ChipContest/generated/`。 |
| SDK Hello World（Ubuntu 裸机 GCC） | BLOCKED | `sdk-hello-original.json`、`sdk-hello-zicsr.json`。裸机 GCC 首先缺 `zicsr` 默认扩展，显式扩展后又缺 SDK 所需 `errno.h`/Newlib。已下载并 SHA 核验 xPack `riscv-none-elf-gcc-15.2.0-1`，尚未改写 SDK 工程做正式固件构建。 |
| 当前工程 E203 融合副本 | PASS（开发平台） | `soc-build/fusion-result.json`；Verilator 编译退出0，1个任务、25,344个48位输出全部写回并校验，`PASS E203_KWT_SUITE`，完整开发窗口1,670,319周期，报告频率150 MHz。 |
| Nangate45 `area_eval.sh DotProductEngine` | TIMEOUT / NOT_RUN | `area-DotProductEngine.log`；Yosys0.33在ABC映射阶段超过约5分钟后停止。该脚本没有超时/资源保护，也没有SDC、SRAM宏或功耗入口。 |

E203 融合任务的窗口从 CPU 读共享模型中的 X/W/bias、逐字写 ICB、启动、轮询/读低高结果、逐字写回，到 `WRITEBACK_ACK` 后邮箱完成；不是只测 MAC 核心。开发共享存储是 512 KiB 行为模型，不能计为指定 SRAM 宏。

## 融合了什么

- 当前工程的 `kwt_linear_engine_rowpair`（2行×8列、16 MAC、双结果缓冲、41位内部累加、48位输出）通过 `soc/kwt_icb_slave.sv` 接入 Fork 的 o15 ICB 预留口。
- o15 在融合副本中改为 `0x10042000`、4 KiB（`REGION_LSB=12`），补上独立 adapter；原队友 Fork 没有此 RTL，原仓库不改。
- `soc/include/kwt_accel_regs.h` 冻结 32位寄存器协议：输入 staging low/high + COMMIT，状态 sticky，48位结果先 LO 后 HI，最后以 `WRITEBACK_ACK` 标记软件写回完成。错误访问不会发 engine 握手。
- `sim/tb_e203_kwt.sv` 与 `sim/kwt_shared512_model.sv` 是开发验证文件，不进入指定 SRAM/比赛综合文件集；固件在 `soc/firmware/`。
- Chisel 版本保留为交叉参考和真实向量验证，不与 rowpair 同时进入最终综合；两者都使用 signed16 / signed40 / signed48 的整数契约。

## 必须转换的接口差异

| 项目 | 队友 Chisel | 当前 rowpair / 融合协议 |
|---|---|---|
| X | 当前行64×16寄存器，逐行装载 | 任务级99×64 bank，rowpair奇偶读；ICB按线性 X 地址装载 |
| W bank布局 | `bank=c%8`，bank内地址=`group*64+k` | 对外逻辑 `W[k,c]`，rowpair内部 `k*32+group` | 
| bias | 外部每组8×40，无完整内部缓存 | 256项40位装载并在8 bank保存 |
| 输出 | 一组8×48 valid/ready | 单48位流，`out_index/out_last`；ICB分LO/HI并保持响应背压 |
| 完成 | Chisel `done`单拍 | adapter `core_done` 和 `software_done` 分离；软件写回确认后完成 |

因此不能直接复制队友的 `.mem` 到当前 bank。统一真值为 `W[k,c]`，装载转换必须显式记录并用真实向量验证。队友历史 LinearComputeCore 面积日志使用旧存储并展开为大量 DFF/MUX；不能与当前 rowpair 的结构单元或宏容量直接比较。

## 参考器件库的使用边界

`ChipContest/assets/libs/nangate45/NangateOpenCellLibrary_typical.lib` 是公开 Nangate45 typical 标准单元参考库；仓库没有指定 SRAM `.lib/.lef/.db/.v` 或完整 SDC。其 `area_eval.sh` 会把行为 SRAM 展开后做 DFF/MUX 映射，且没有150 MHz时序、SAIF/VCD功耗、E203/互连/完整窗口统计。该库可用于同一参考库下定位控制/算术逻辑瓶颈，不能产生赛题正式面积、功耗或宏时序结论。

当前正式 PPA 状态仍由 `docs/optimization/PPA_INPUT_CONTRACT.md` 的 fail-closed 工具控制：未知库/宏/网表/SDC/活动覆盖保持 `BLOCKED`，不以0补齐。取得组委会材料后，优先把 rowpair 的 X/W/bias/result 逻辑 bank 替换为指定16×128/1024/4096宏，再在同一配置下做综合、STA和完整窗口功耗。

## 下一步

1. 使用 xPack 工具链完成 SDK 固件的可复现构建，并将真实固件入口替换开发 smoke；固定 SDK 提交和 `-march/-mabi`。
2. 将 o15 adapter 的开发端口映射到组委会正式 E203 平台；当前开放 Fork 只证明接口方向和协议测试。
3. 获取指定 SRAM/标准单元/SDC/PVT，执行宏映射和150 MHz STA；Nangate 参考 ABC 超时记录为工具限制，不能当失败面积。
4. 用12个独立层任务替换当前1任务开发运行；每次都统计装载、CPU调度、所有结果写事务和软件 ACK。
