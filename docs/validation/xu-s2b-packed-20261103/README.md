# xu S2b 本地筛查记录（2026-11-03）

本记录完成独立 `codex/xu-s2b-packed` 的本地筛查。三组实际 SoC 运行均测量主仓 `b625b49f4a14496c41a9914f2de484e83933014c`、E203 `d5faa5e8c857fa35df62a68de667bdb8a6e954f7`；结果和日志在中断前已经完成，本次直接复核并原样归档，没有把不完整运行当作 PASS。此后的改动为直接 packed TB 的 busy 时数据读覆盖及本证据，没有改变已测 SoC RTL、固件、runner 或数值向量。

实际改动的 Chisel 文件：**无**。相对 S2a 父提交 `3c13930c1f36d6516577d33d8587d89a86b49563` 和子仓 `faaa3e3d8b7832012fe48a8e27f684e5b5706306`，子仓只改 `rtl/e203/perips/accel_icb_slave.v`。PE、计算 core、SRAM 宏/端口/容量、signed16 X/W、signed40 bias、signed48 Y、共享槽格式和固定向量保持原定义。接口契约详见 [`docs/xu-s2b-packed.md`](../../xu-s2b-packed.md)。

## 实际结果与比较边界

旧 ABI、S2a、S2b 都运行本候选 RTL、GCC 14.2.0、Verilator 5.032、`-O2`、`both-unroll-no-masks`，分别使用 `bias-hw-window`、`bias-hw-stream16-window`、`bias-hw-pack32-window`。全部 RTL/TB、模拟器二进制、runner、事务契约、固件源、工具版本和固定 layer_00 向量身份逐项相同。固件 ELF 因 schedule 不同而不同。

| 实测项（layer_00） | 旧 ABI | S2a | S2b |
| --- | ---: | ---: | ---: |
| 完整窗口周期 | 1,387,720 | 1,286,374 | **1,250,899** |
| 固件 mcycle 差 | 1,387,823 | 1,286,455 | 1,250,988 |
| W 装载周期 | 299,301 | 229,385 | 183,516 |
| X 装载周期 | 114,906 | 88,407 | 71,279 |
| bias 装载周期 | 7,773 | 7,773 | 7,773 |
| 计算/等待周期 | 218,592 | 218,592 | 218,592 |
| 写回周期 | 663,663 | 661,419 | 663,597 |
| 其他周期 | 83,485 | 80,798 | 106,142 |
| MMIO 写 | 55,720 | 33,094 | **21,734** |
| MMIO 读（实测，未固定） | 76,032 | 76,032 | 76,032 |
| 共享读 / Y 写字 | 23,232 / 50,688 | 相同 | 相同 |
| START / done | 3,168 / 3,168 | 相同 | 相同 |
| busy / MAC 有效拍 | 215,424 / 202,752 | 相同 | 相同 |
| 共享背压周期 | 9,374 | 24,780 | 9,400 |
| MMIO 命令背压周期 | 0 | 0 | 0 |
| 精确 signed48 输出 | 25,344 | 25,344 | 25,344 |

S2b 相对旧 ABI 减少 **136,821 周期（9.859410%）**，相对 S2a 减少 **35,475 周期（2.757752%）**；MMIO 写分别减少 33,986 和 11,360。该结果仅覆盖固定 silence 样本的第 0 个独立 FFN1 层，不外推另外 11 层。

窗口从首个共享输入/参数读接受，到最后一个 Y 写响应退休；六阶段之和严格等于窗口。TB/ITCM 预装载、任务间 host 装载和兼容性 CAP 探测位于窗口外；游标初始化、共享数据读、内部两拍提交、轮询和 Y 写回在窗口内。旧 W 首 BANK/ADDR 两写在首共享读之前，不能把完整 W 函数的写数混入窗口差值。

既有共享存储使用 modulo-7 背压，因此指令/事务相位改变后共享背压数量也改变。S2b 装载阶段比 S2a 少 62,997 周期，而其他阶段多 25,344、写回多 2,178，表中保留完整窗口结果。`mmio_stall=0` 不代表 packed 提交没有延迟；接受后的两个内部提交边沿仍计入装载阶段。

## 完整性与兼容性

- 最终 host **54 项**、numeric **42 项**通过，完整输出保存在 `raw/final-local/`；中断前的完整输出保存在 `raw/original-local/`。
- 直接 packed TB 接受/退休均为 **9,653**，实际写口提交 16,457 次（W 16,390、X 67），START 33 次。独立映射和模型检查完整 16,384 W、64 X 及全部 32 group，覆盖符号极值、bank 对、255 边界、最后 pair、旧/标量/packed 混用和指针独立、mask/奇数/终点/越界/busy 错误、W1C、捕获后毒化 live 输入、两次分离提交、held valid、响应背压以及最后提交后的 START。新增断言明确在 busy=1 时读 W_PACK32/X_PACK32 都返回 0。
- 原 cached TB 接受/退休 **4,909**；原 scalar TB 接受/退休 **17,828**、提交 **16,454**，全部通过。
- 5 项旧 Icarus 用例通过：`rv32ui-p-add`、`accel_mmio`、`accel_compute`、`accel_multigroup`、`accel_repeat_x`。
- S2a 父提交的 6 种既有 schedule，各选默认 `-Os/none` 和 `-O2/both-unroll-no-masks`，共 **12 组**装载字节逐字节一致；24 次编译的源快照、命令、ELF/二进制、日志保存在原始归档。该比较针对 loadable bytes，不要求 ELF 元数据相同，也不声称所有选项已验证。
- `check-results.py` 使用原 `check_log`、`check_performance` 和 `xu_perf_report.summarize` 重新验收三组实际结果。它逐项核对实际 RTL/TB、日志、固件源/build/ELF/镜像、固定 fixture/向量和归档模拟器二进制的哈希，并对三组向量各自独立重算全部 25,344 个 XW+b 输出。
- 对实际 S2b 记录或日志作 **29 种**破坏均被拒绝：MMIO 写±1、阶段缺口/重叠、MAC 有效拍±1、共享读/写与 START/done 各±1、错误 schedule、少一输出/Y 写、缺失/重复 TASK/PERF/SOC、PERF 层号/周期不符或字段缺失/多余、SOC 总量错误、附加 FATAL。没有修改或放宽生产检查器。
- 独立只读复核再次确认上述源码/向量/固件/模拟器身份和数值结果，并确认 Chisel 改动列表为空。

## 证据与复现

`comparison.json` 保存完整逐阶段比较、身份和负例结果；`sha256.json` 覆盖本目录的全部其余文件。`raw/{oldabi,scalar,packed}-real1/` 原样保留结果、日志、固件 ELF/镜像和 build 元数据，各自的 `vectors.tar.xz` 无损保存实际输入/输出向量。`raw/simulator.tar.xz` 保存三组共用模拟器；校验脚本只在内存读取该二进制以计算哈希，不执行它。`raw/legacy-baseline/` 是最终旧用例结果，`raw/original-local/` 与 `raw/final-local/` 保留两轮本地检查。所有历史日志的绝对路径原样保留。

在已初始化的子仓和同一工具链下复现，输出目录必须尚不存在：

```bash
python3 -m unittest discover -s tests/e203 -p 'test_*.py' -v
python3 -m unittest discover -s tests/numeric -v
python3 tools/scripts/e203_soc.py --mode baseline --sim iverilog --out build/xu-s2b-baseline-repro
python3 tools/scripts/e203_soc.py --mode real --tasks 1 --sim verilator \
  --firmware-schedule bias-hw-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks --out build/xu-s2b-oldabi-real1-repro
python3 tools/scripts/e203_soc.py --mode real --tasks 1 --sim verilator \
  --firmware-schedule bias-hw-stream16-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks --out build/xu-s2b-scalar-real1-repro
python3 tools/scripts/e203_soc.py --mode real --tasks 1 --sim verilator \
  --firmware-schedule bias-hw-pack32-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks --out build/xu-s2b-packed-real1-repro
python3 docs/validation/xu-s2b-packed-20261103/check-results.py
```

最后一条复核已归档证据与当前源码；源码哈希表包含 `vsim/install/rtl/`，新 checkout 需要先执行既有 `make -C third-party/e203_hbirdv2/vsim install`，或先完成任一 SoC 复现运行。归档自身 SHA-256 可独立按 `sha256.json` 检查。

本记录没有运行远程工具、VCS、formal、综合、布局布线、STA 或功耗分析；没有 S0 资格、服务器同配置 (T,E,A)、时序闭合、保留、得分、PPA 或正式精度评测结论。
