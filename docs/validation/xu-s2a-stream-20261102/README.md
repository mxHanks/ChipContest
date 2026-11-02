# xu S2a 本地筛查记录（2026-11-02）

本记录验证独立 S2a 标量流候选；不改变主工作树或 S0 资格结论。被测源码为主仓 `01a6a5de083e52b2b71e21e70722009ef6dfdcc9`、E203 `faaa3e3d8b7832012fe48a8e27f684e5b5706306`；相对起点分别为 `74e011813dbf215327e59016d34136a36e87ba05`、`f49a5fc914971426bd4530db39e270a84b41139f`。此后证据提交只补充文档/原始输出。

实际改动的 Chisel 文件：**无**。E203 子仓只改 `rtl/e203/perips/accel_icb_slave.v`；没有修改 PE、计算 core、SRAM 端口/容量或生成的 Chisel RTL。signed16 X/W、signed40 bias、signed48 Y、共享槽格式和固定向量均保持原定义。

## 结果与比较边界

旧 ABI 控制组使用本候选 RTL 的 `bias-hw-window`，候选使用 `bias-hw-stream16-window`；两组都是 GCC 14.2.0、Verilator 5.032、`-O2`、`both-unroll-no-masks`。完整 RTL/TB、模拟器二进制、runner、事务契约源码、工具版本和 layer_00 向量哈希逐项相同。比较只覆盖固定 silence 样本的第 0 个独立 FFN1 层，不外推其余 11 层。

| 实测项（layer_00） | 旧 ABI | S2a | S2a 减旧 ABI |
| --- | ---: | ---: | ---: |
| 完整窗口周期 | 1,387,720 | 1,286,374 | -101,346 |
| 固件 mcycle 差 | 1,387,823 | 1,286,455 | -101,368 |
| W 装载周期 | 299,301 | 229,385 | -69,916 |
| X 装载周期 | 114,906 | 88,407 | -26,499 |
| bias 装载周期 | 7,773 | 7,773 | 0 |
| 计算/等待周期 | 218,592 | 218,592 | 0 |
| 写回周期 | 663,663 | 661,419 | -2,244 |
| 其他周期 | 83,485 | 80,798 | -2,687 |
| MMIO 写 | 55,720 | 33,094 | -22,626 |
| MMIO 读（实测，未固定） | 76,032 | 76,032 | 0 |
| 共享读 | 23,232 | 23,232 | 0 |
| 共享 Y 写字 | 50,688 | 50,688 | 0 |
| START / done | 3,168 / 3,168 | 3,168 / 3,168 | 0 / 0 |
| busy / MAC 有效拍 | 215,424 / 202,752 | 215,424 / 202,752 | 0 / 0 |
| 共享背压周期 | 9,374 | 24,780 | +15,406 |
| MMIO 命令背压周期 | 0 | 0 | 0 |
| 精确 signed48 输出 | 25,344 | 25,344 | 0 |

窗口减少 **7.303058%**，以首个共享输入/参数读接受为起点、最后一个 Y 写响应退休为终点。六个阶段之和严格等于该窗口。TB/ITCM 预装载、任务间 host 装载及兼容性 CAP 探测位于窗口外；W/X 游标初始化、全部共享数据读、实际内部写口提交、轮询和 Y 写回位于窗口内。旧完整 W 循环的首 BANK/ADDR 两写在窗口外，新 W_CURSOR 在窗口内，故 22,626 是窗口差值。固件 mcycle 包含不同的前后开销，不能代替窗口周期。

本地共享存储采用既有 modulo-7 背压，流命令改变相位后共享背压数量也改变，表中保留实际观测值。`mmio_stall=0` 不表示流接口没有延迟；接受后提交的周期仍属于装载阶段。pending 期间命令 ready 为 0，普通串行 `STREAM_STATUS` 读只能在 pending 清除后接受。

## 完整性检查

- host 51 项、numeric 42 项全部通过，原始完整 unittest 输出保存在 `raw/local/`。
- 旧 cached-wrapper TB：接受/退休均为 4,909，覆盖旧模式、mask、bias cache、结果窗口和背压。
- 新 stream-wrapper TB：接受/退休均为 17,828，实际写口共 16,454 次（W 16,387、X 67），START 33 次。独立 row/column 模型遍历 16,384 个 W、64 个 X 和全部 32 个 group；覆盖符号极值、终点不回卷、非法 mask、忙时/越界错误、旧/新指针独立、捕获后提交、响应背压及最后一写后 START 顺序。
- 5 项旧 Icarus 用例通过：`rv32ui-p-add`、`accel_mmio`、`accel_compute`、`accel_multigroup`、`accel_repeat_x`。
- 5 种旧 schedule 各选默认 `-Os/none` 和 `-O2/both-unroll-no-masks`，共 10 组装载字节与基线一致。该检查比较 loadable bytes；ELF 元数据可以不同，不声称所有编译器/选项组合都已验证。
- 两组 SoC 日志均通过原 `check_log`、`check_performance` 和 `xu_perf_report.summarize`；源文件/日志/ELF/镜像/向量哈希与结果记录逐项相符。独立无限精度整数 `check_vectors` 各检查 25,344 个 XW+b 输出。
- 对真实候选结果/日志作 10 种破坏：少一 MMIO 写、少一阶段周期、少一 MAC 有效拍、错误 schedule、少一输出、少一 Y 写、缺失/重复 PERF_TASK、缺失/重复 TASK_PASS，全部被原严格检查器拒绝。没有修改或降低检查条件。
- 独立只读复核确认流映射、原子错误、W1C、提交/响应保持及 START 顺序契约一致，并核实 Chisel 改动列表为空。

## 证据与复现

`comparison.json` 保存逐层/逐阶段机器可读比较和严格检查结果；`sha256.json` 保存全部原始证据及该比较文件的 SHA-256。`raw/oldabi-real1/`、`raw/stream-real1/` 的原始 `result.json` 包含完整实际 RTL/TB、固定向量、编译命令、ELF/镜像、模拟器、工具版本与日志哈希。`raw/legacy-baseline/` 保留旧用例结果；`raw/local/` 保留直接 TB、host/numeric 与旧固件装载字节证据。原始日志的绝对路径来自本次独立工作树，未重写。

| 二进制身份 | SHA-256 |
| --- | --- |
| 旧 ABI 固件 ELF | `343a1be00d5aca2c17b8dc8672043ca602fa34b6da6383c20300d3d003620f8d` |
| S2a 固件 ELF | `21db6a925f65a47183aac4ceb0883501b30630dedd481460858d71ae0d96ddd0` |
| 共用模拟器 | `75f75486ebba9e341a7c3ef64ad4528187ff86a5e50f0ca37abf82591e33564d` |

在被测提交及已初始化的子仓下复现；输出目录必须尚不存在：

```bash
python3 -m unittest discover -s tests/e203 -p 'test_*.py' -v
python3 -m unittest discover -s tests/numeric -v
python3 tools/scripts/e203_soc.py --mode baseline --sim iverilog --out build/xu-s2a-legacy-baseline-repro
python3 tools/scripts/e203_soc.py --mode real --tasks 1 --sim verilator \
  --firmware-schedule bias-hw-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks --out build/xu-s2a-oldabi-real1-repro
python3 tools/scripts/e203_soc.py --mode real --tasks 1 --sim verilator \
  --firmware-schedule bias-hw-stream16-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks --out build/xu-s2a-stream-real1-repro
```

本记录未运行远程工具、VCS、formal、综合、布局布线、STA 或功耗分析。没有 S0 资格、服务器同配置 (T,E,A)、时序闭合、保留、得分、PPA 或正式精度评测结论。
