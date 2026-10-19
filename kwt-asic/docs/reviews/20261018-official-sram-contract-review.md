# 2026-10-18：official SRAM contract 入口独立审查

结论：**PASS，仅限开发 logical adapter 的 BACKEND=3 primitive/bank 入口资格化及已执行的拒绝路径。官方宏功能 NOT_RUN，官方工艺/PPA BLOCKED。** 本轮独立审查只读取已有源码、JSON、原生 state/log 和生成 binary，未重跑 HDL/EDA，未修改生产源。

最终证据为 [final-v2/result.json](/media/leo/Data/Vitis/RISC-V-forward-acceleration/artifacts/diagnostics/20261018-official-contract/final-v2/result.json)。父级资格化实际执行 8 个 CLI，再执行 `make test` 和 `make verify`；10 个父级命令退出码依次为 `2,0,1,1,1,1,1,1,0,0`，均为原生 `EXITED`、未超时、未中断。主机测试日志真实记录 `Ran 238 tests` / `OK`，这是软件回归数量，不是官方宏功能场景数。

## 来源与原生证据

- 独立重算父级及 8 个子报告的 17 个 canonical `source_id`，与保存的 identity JSON 一致；检查了 190 个去重文件的实际 SHA256 与字节数。所查对象包括输入、工具文件、报告、原生 state/log、8 个正常 binary、故障 binary 和生成重复 adapter。
- 父级 `source_id` 为 `3b864db1c71836a954fad940d9df97385247901bd3f71810d2673476abfe0f43`；绑定的 runner SHA256 为 `0227dea2a05c0c03ac942414a8aadae108e1e39d2de87960a2baabc2ba04fb71`。源码当前字节与绑定值一致，没有用更新后的源码解释旧报告。
- 逐项核对 56 个原生命令的保存 state 与报告内容，包括 `argv/cwd/status/exit_code/timed_out/interrupted/log`，并验证对应 state/log 的 SHA。8 个 CLI 各有唯一 `KWT_OFFICIAL_SRAM_CONTRACT_COMPLETE`，摘要路径和状态与实际子报告一致。
- [runner](/media/leo/Data/Vitis/RISC-V-forward-acceleration/scripts/verify/run_official_sram_contract.py:118) 在收集材料前保存三项 runner/helper 的 `initial_identity`；已收集源、TB、工具及运行时文件的完整 identity 在 supplied 扫描及首条 HDL 命令前保存。生成 duplicate 独立记录。正常终态和故障终态均复核已绑定输入及原生证据；每个正常 binary 在执行前后都保留并核对身份。该顺序与实际保存文件一致。

## 八个实际 CLI

| 场景 | 子报告状态 / 父 CLI 退出码 | 实际证据 |
| --- | --- | --- |
| 默认缺官方包 | BLOCKED / 2 | 0 个内部命令、0 binary、0 case，无 HDL 执行 |
| development good | PASS / 0 | 33 个内部命令，8 正例、23,177 checks、15 个预期拒绝 |
| development bad-data | FAIL / 1 | 编译 exit0，仿真 exit1；地址0 `got=7da7 expected=7da6` |
| development missing-adapter | FAIL / 1 | Icarus 编译 exit1，明确 `Unknown module type: kwt_official_sram_adapter` |
| development duplicate-adapter | FAIL / 1 | Icarus 编译 exit2，明确模块重复声明 |
| 普通 manifest 声明开发 fixture | FAIL / 1 | intake simulation 文件核验后，在 HDL 前因 fixture 禁入拒绝，内部命令0 |
| unbound include | FAIL / 1 | 在 HDL 前因缺显式辅助依赖支持拒绝，内部命令0 |
| invalid HDL | FAIL / 1 | Icarus 编译 exit2，真实 syntax error / invalid instantiation |

内部命令数依次为 `0,33,4,3,3,0,0,3`。FAIL 场景是被正确拒绝的资格化输入，不是已接受的设计 PASS。所有 8 个子报告均为 `official_validation=NOT_RUN`、`official_ppa=BLOCKED`，core/ICB/SoC/synthesis 均 `NOT_RUN`。

## 正常与拒绝场景

[good 子报告](/media/leo/Data/Vitis/RISC-V-forward-acceleration/artifacts/runs/20261018T051921.108279Z-official-contract-afdf0cfe/result.json) 的每次编译实际指定 `BACKEND=3`，使用冻结 primitive/bank、相应旧 TB 和显式开发 fixture。fixture 参数/端口符合已有 logical ABI，不增加虚构 reset pin；只接受 `16×128/1024/4096`，SYNTHESIS 分支主动失败。

| 正例 | 检查数 |
| --- | ---: |
| unit 16×128 / 1024 / 4096 | 144 / 1040 / 4112 |
| bank 16×3136 / 3200 / 2048 | 6277 / 6405 / 4101 |
| bank 40×32 / 41×512 | 69 / 1029 |

8 个正常日志均原生 exit0，具有唯一精确完成标记及 `$finish`。unit 检查数为 `DEPTH+16`，signature 为16位十六进制；bank 检查数为 `2×DEPTH+5`，宽度覆盖标记的 `bits_both` 等于完整 WIDTH。合计 23,177。

15 个拒绝分别为 unit128 的 ERROR_CASE `1/2/3/6/7/8/9`，以及非幂二 bank16×3200 的 `1..8`。原生均 exit1，FATAL 文本严格属于对应允许诊断，且无正常 PASS、fallthrough sentinel 或额外失败诊断。bank8 实际产生4条相同允许的 `KWT_SRAM_UNKNOWN_ENABLE` FATAL，故共18条 FATAL，但只计15个拒绝请求；这些检查证明项目 wrapper 防护，不代表供应商芯片对非法请求的保证。未将幂二 primitive 中会截断地址的 ERROR_CASE4/5 计作越界覆盖。

## 保留的限制与失败

- 开发 fixture 调用现有 behavioral 数组，只资格化逻辑契约与执行/判定入口。普通 supplied 模式拒绝此文件及其显式 sentinel；这种识别不是官方模型真实性证明。
- supplied 模式对 include、外部数据/SDF/DPI 等消费的扫描是当前保守支持边界，不是完整 HDL 安全或依赖闭包证明。含此类资料的真实包需要后续显式辅助依赖支持，不能跳过来源绑定。
- 现有 TB 未验证同地址改写不同值，也未在 reset 期间保持请求 enable 为高；未覆盖 INIT_FILE、真实宏引脚/电气/PVT、完整核心、ICB、SoC 或真实12层通过 official backend。不得把当前8个正例扩大成完整 SRAM 或比赛验收。
- [final-v1/result.json](/media/leo/Data/Vitis/RISC-V-forward-acceleration/artifacts/diagnostics/20261018-official-contract/final-v1/result.json) 的 **FAIL 保留**。首版父 reader 在第6个、已正确拒绝开发 fixture 的早期失败子报告中无条件读取 `identity`，触发 `KeyError: 'identity'`；该批只完成6个 CLI，未执行后续2个 CLI 与 host/verify，不能改称完整通过。final-v2 使用新增的早期身份记录，并实际完成全部场景。

在上述限定范围内，未发现尚需修复的阻断问题；本审查不授予官方功能或官方 PPA PASS。
