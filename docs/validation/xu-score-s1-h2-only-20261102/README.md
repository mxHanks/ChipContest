# xu S1：真正移除全 bias 缓存的 H2-only 本地筛选

本候选只完成独立副本的本地功能筛选。未运行本候选的服务器 VCS 12 任务、指定库综合/STA/等价或完整 SoC 能耗；没有比赛合格、功耗、面积收益或最终保留结论。S0 资格工作仍由主流程推进，不由这里的 PASS 代替。

## 冻结身份与实现

- 主仓基点 `e998479`；运行源码提交 `0f52ea3`，后续公共端口 gate TB 提交 `2805a42`。根任务要求的服务器兼容修复 `ac85d6a` 已 cherry-pick 为 `1caf5dc`，不改变本候选运行 RTL/固件。
- 独立 worktree：`/home/mxhanks/Projects/ChipContest-xu-s1-h2-only`，分支 `codex/xu-s1-h2-only`。子仓为独立 `--no-hardlinks` clone，没有修改原副本或其安装/构建缓存。
- 子仓固定基点 `f49a5fc914971426bd4530db39e270a84b41139f`；候选 `434628c1525931c15dfaf06b5586118eb530ccba`。
- 子仓提交严格只改 `rtl/e203/perips/LinearCachedCore.sv` 和 `rtl/e203/perips/accel_icb_slave.v`。其余 1,063 个跟踪路径的 tree records SHA256 均为 `5f84f4b3bbf168e2e1e637b722854fec2b3f02ff06df78aaa4d40b2cc3e77ceb`；E203 CPU、固定总线/平台、共享 SRAM 和其他加速器模块均未改。
- 冻结原 signed16 X/W、signed40 bias、signed48 result、8 PE、向量和 MMIO 地址。

恰好修改两份 Chisel 主源码：`src/main/scala/linear/LinearCachedCore.scala` 加入默认 `true` 的 elaboration 参数 `enableBiasCache`；`src/main/scala/GenerateRTL.scala` 加入 `LinearH2OnlyCore` 生成目标并传入 `false`。现有 `src/test/scala/linear/LinearCachedCoreTest.scala` 用同一套非零点积、signed40 边界与组 0/15/16/31 检查两个硬件参数。

关闭硬件缓存时，生成的 `LinearCachedCore` 只有一个 `LinearComputeCore` 实例，bias 直接连接原八槽输入，缓存读口固定零，不实例化 `BiasBankCache`，没有全数组存储或 bias 选择 mux。旧默认 `LinearCachedCore` 生成目标的全部 12 份 SV 与固定子仓逐字节相同。子仓仍保留未实例化的旧 `BiasBankCache.sv` 源文件；这不形成硬件单元。

ICB wrapper 删除缓存地址/使能寄存器、上传写数据/掩码逻辑，保留 0x40–0x4c 地址为读零/写无副作用的保留区。CAP=0x58550002：高 16 位签名 0x5855，bit0 缓存缺失，bit1 结果窗口存在。0x80–0xbc 结果窗口及旧索引结果接口不变。固件检查签名及当前编译调度所需 feature bits；H2 不再要求 bit0，H1 请求缺失 bit0 时在参数上传前返回 -4。

## 已取得的本地结果

| 检查 | 原始结果 |
| --- | --- |
| 完整 Chisel 回归 | 10 suites、14/14 PASS；ScalaTest 报告 54.260 s；包括完整 99×256 输出检查 |
| numeric 既有回归 | 42/42 PASS |
| 冻结真实整数向量核算 | 12 层、304,128 输出 PASS；不是浮点 NRMSE 评估 |
| H2 E203 direct wrapper | accepted=retired=4,007；明确 `XU_BIAS_CACHE_UNSUPPORTED ... cache_checks=not_run` |
| H2 gate 公共端口 TB 的 RTL 回放 | accepted=retired=13,708；13,706 trace rows 加两笔流水请求；含非零 MAC、符号极值、跨 SRAM 边界及连续两任务 |
| 固定 f49 combined 兼容回放 | E203 wrapper accepted=retired=4,909；gate TB accepted=retired=17,151，trace rows=17,149 |
| Yosys 结构检查 | 从 `accel_icb_slave` hierarchy 无 `BiasBankCache` module/cell；`LinearCachedCore` 恰好一个 `LinearComputeCore` cell |
| gate evidence 既有检查 | 5/5 PASS；这里没有运行综合后回放 |
| 真 SoC real1，Verilator behavioral RAM | 25,344 输出、50,688 字写回 PASS；开发窗口 1,927,329 cycles |
| 实际 H1 固件负控制 | runner 保留 FAIL、exit=1；simulator exit=-6，`firmware failure gp=14 completed=0`；按预期拒绝不支持的缓存 |

real1 使用 `bias-dtcm-window / -O2 / both-unroll-no-masks`，实际计数为 3,168 starts/dones、130,982 MMIO writes、23,232 shared reads、50,688 shared writes。该周期是当前本地 GCC/Verilator 开发平台结果，TB 共享夹具预装载不计时；不能当作服务器 VCS 周期或正式吞吐量，也不与历史不同工具结果拼接。

全部存储模型在本地沿用基线 behavioral RAM。未用二态 Verilator 验证 vendor 四态宏；此处不作指定宏合规结论。没有扩展 SRAM bias 存储设计。

## 证据与复现

机器摘要见 [summary.json](summary.json)，上层命令见 [commands.json](commands.json)。[xu-h2-only-local-evidence.tar.xz](xu-h2-only-local-evidence.tar.xz) 保留原始日志、每条 direct wrapper compile/sim argv/cwd、SoC result/固件编译身份、transaction traces、Yosys 脚本与结构 JSON、每个 Chisel 测试的编译/运行日志和执行脚本；逐成员 SHA 在 [archive-files.json](archive-files.json)。不含二进制仿真器、vendor 模型、指定库、凭据或远端内容。

[xu-e203-h2-only.bundle](xu-e203-h2-only.bundle) 提供仅含两份加速器文件改动的子仓提交，以固定 f49 为 prerequisite。子仓可在独立 clone 中 `git fetch /绝对路径/xu-e203-h2-only.bundle HEAD` 后检出上述候选提交。父仓 evidence 文件 SHA 见 [evidence-sha256.json](evidence-sha256.json)。

在独立副本、正确候选 gitlink 下，用新的输出目录复现：

```bash
scala-cli run . --server=false --jvm system -M GenerateRTL -- LinearH2OnlyCore
cmp generated/LinearH2OnlyCore/LinearCachedCore.sv third-party/e203_hbirdv2/rtl/e203/perips/LinearCachedCore.sv
scala-cli test . --server=false --jvm system
python3 -m unittest discover -s tests/numeric
XU_WRAPPER_LOG_DIR=build/xu-h2-replay-wrapper python3 -m unittest discover -s tests/e203 -p test_cached_wrapper.py
python3 tools/scripts/e203_soc.py --mode check-vectors --tasks 12 --out build/xu-h2-replay-vectors
python3 tools/scripts/e203_soc.py --mode real --tasks 1 --sim verilator --firmware-schedule bias-dtcm-window --firmware-opt=-O2 --firmware-experiment both-unroll-no-masks --out build/xu-h2-replay-real1
python3 tools/scripts/e203_soc.py --mode real --tasks 1 --sim verilator --firmware-schedule bias-hw --firmware-opt=-O2 --firmware-experiment both-unroll-no-masks --out build/xu-h2-replay-reject-h1
```

最后一条必须失败并出现上述 gp=14；不能把它计作数值 PASS。运行器的 `make clean/install` 只作用于该独立子仓 `vsim/install`，构建缓存只在该 worktree 的 `build/e203`。

保留两项探索性产物以避免混淆：首次 Yosys `write_json` 因遗漏 `proc` 失败，补上 process lowering 后结构检查通过；`gate-rtl-combined-reference` 曾导出当前 HEAD，实际是重复 H2 检查，只有明确标注 `*-combined-f49a5fc` 的固定导出是 combined 对照。

后续服务器 VCS12、同库 PPA、综合前后功能一致性和全 SoC 能耗由根任务执行。当前全 SoC 配置 guard 固定 f49；接入本候选需显式核对仅允许上述两份 accelerator 文件差异，继续保护固定 CPU/平台，不能直接放宽为任意 child commit。
