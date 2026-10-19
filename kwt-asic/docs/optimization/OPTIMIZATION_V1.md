# AI Engine 第一轮实测优化

日期：2026-10-15。当前目标是指定150 MHz下，新增核心、接口和内部SRAM的面积合计严格小于2.25 mm²，并以完整任务窗口优化吞吐和单任务能耗。以下结果只证明独立RTL功能和结构，正式SoC、面积、时序及功耗尚未取得证据。

## 已经实现并实测

保留 `kwt_linear_engine.sv` 迁移基线，新增两个候选：

- `kwt_linear_engine_opt.sv`：bias每个输出组首拍读取并保持；可选乘积寄存级，保留16位输入/权重、40位bias和48位精确累加。该流水切开乘法与累加之间的组合路径，不是乘法器内部部分积的多级流水。
- `kwt_linear_engine_banked.sv`：在上述基础上，将W/bias定义为各generate lane内部的一维数组，保留独立bank边界。数值、读使能和周期保持一致，仍需接入官方SRAM宏。

最新同一组源码的16次回归全部通过，合计逐位比较4,359,168个输出：包含10组完整12任务无停顿对照，banked的8/16路随机回压、12层真实权重静音，以及Icarus四态复位/回压。每次均有3处在途/输出复位、非法装载、末行末输出、忙时拒绝装载检查。静音回放仍不是验证集精度结论。

| 配置 | 单任务无回压核心周期 | 相对8路基线周期 | 每任务bias逻辑读字数 |
|---|---:|---:|---:|
| baseline，8路 | 231,264 | 100.00% | 1,622,016 |
| opt / banked，8路，PIPE_MUL=0 | 231,264 | 100.00% | 25,344 |
| opt / banked，8路，PIPE_MUL=1 | 234,432 | 101.37% | 25,344 |
| baseline，16路 | 128,304 | 55.48% | 1,622,016 |
| opt / banked，16路，PIPE_MUL=0 | 128,304 | 55.48% | 25,344 |
| opt / banked，16路，PIPE_MUL=1 | 129,888 | 56.16% | 25,344 |

读取按RTL使能统计，bias字宽40位；下降98.4375%不等于整机节能98.4375%。流水每个tile多一拍排空，8路增加1.37%、16路增加1.23%核心周期。固定150 MHz时，是否保留流水要由实际关键路径和能耗决定；不能把“可提高最高频率”推断为本题吞吐收益。以上不包含E203、总线及系统写回，不能作为比赛端到端性能。

## 工具实际找出的结构瓶颈

本地新增固定包的Yosys/ABC，保留RAM做10组结构综合并核对全部373,760 bit载荷存储。原baseline/opt的W和bias被收集成8R/8W或16R/16W的大数组。banked候选形成17/33个同步1R/1W逻辑存储，消除了该警告，避免后续盲目展开为大量寄存器。

乘积流水增加259/515 bit寄存器（8/16路）。banked使8路流水结构单元数从371降至357，16路从578降至548；这些是未映射RTLIL单元数量，不能换算物理面积或拿来比较工艺成绩。工具的有限语法转换和四态适用范围见 [结构综合说明](STRUCTURAL_SYNTHESIS.md)。

按指定宏深度取整的最小容量方案，8路需要50.5 KiB、16路56.5 KiB，而逻辑载荷仅45.625 KiB；差异主要来自细分bias bank。最小容量方案不保证最小面积。逐宏方案、端口假设和未知面积字段见 [SRAM预算](SRAM_AREA_BUDGET.md) 与 `configs/optimization-area-budget.json`。

## 下一步按证据选择

1. 将banked连接到官方宏封装；先证明端口、读延迟和使能一致，再映射指定标准单元库。
2. 在同一库角/负载/SDC下比较PIPE_MUL=0/1。若未流水已达150 MHz且能耗更低，保留未流水；若路径仍违例，按乘法、累加反馈、地址选择或广播路径分别优化。
3. 用真实语音验证划分补齐每层NRMSE和活动。公开benchmark入口及工具一手资料见 [基准与工具](BENCHMARKS_AND_TOOLS.md)。数据下载完成后必须核对官方归档SHA；不能用部分下载或静音替代验证集。
4. 若宏面积占比高，先评估bias集中存储/预取与macro拼接；若输出等待占比高，再加结果缓冲。双行复用仍是后续候选，尚未实现。
5. 接入E203后统一从开始装载到最后写事务确认的周期/功耗窗口，再选择总吞吐、能耗和面积的折中。缺失库/宏/接口不得按零面积或零功耗计入。

## 复现与证据

```bash
source env/activate.sh
python scripts/verify/run_engine_benchmark.py --engine banked --lanes 8 --tasks 12
python scripts/verify/run_engine_benchmark.py --engine banked --lanes 16 --tasks 12 --stalls random
python scripts/verify/run_engine_benchmark.py --engine banked --lanes 8 --tasks 12 --vectors kwt-silence
python scripts/verify/run_engine_benchmark.py --engine banked --lanes 8 --tasks 2 --stalls random --simulator iverilog
python scripts/synth/run_structural.py --variant banked --lanes 8 --pipe-mul 1
```

最新证据汇总为 `docs/runs/optimization-v1/summary.json`，十配置同输入对照为同目录 `comparison.json`。报告绑定原始命令、退出码、完整结束标记、日志、输入、源码和工具哈希。早期报告仍保留于artifacts；扩展runner后已重跑当前16组验证和10组综合，不能混用早期runner哈希。
