# 形式验证与源码身份审阅

官方原件仅通过工作区 3 界面读取，保留在服务器。本文件记录核对结果及证明边界。

## 证明链

| 比较 | 官方目录 | 原生结果与范围 |
|---|---|---|
| 官方 SRAM 适配后的 B41 RTL → 双角基线 24de7510… | `fm-dc-dual-rtl-resume-r2` | complete=true、native_exit=0；58,332 passing；无 failing、aborted、unverified。18 个参考 DFF 未匹配，见下节 |
| 双角基线 → 最终物理候选 2d5adc61… | `xu-fm-final-20261112-r6` | complete=true、native_exit=0；58,332 passing；无 failing、aborted、unverified。1 个实现空壳及 5 个输入引脚未匹配，输出未连接 |
| 最终物理候选 → 当前功能副本 d8e1c611… | `xu-fm-functional-20261112-r1` | complete=true、native_exit=0；58,337 passing；无 unmatched、failing、aborted、unverified |

三步的脚本、原生日志 SHA 与当前回执均已核对。RTL 接续 r2 的回执 SHA 与 result.json 一致，prior receipt 与 r1 当前回执一致，所恢复 r1 的 formality_auto.fss 流式 SHA 与 r2 result.json 一致。原始首轮退出 124、未验证 2,141 点，r1 complete=false/exit=1；这些历史失败保持原样，完成依据为接续 r2 的实际通过。

双角基线完整 SHA256：`24de75106e74b3f0f4a83c36cea7e5f9e32eccdc520c2636ba836fa8cb5cc6a`。最终物理候选完整 SHA256：`2d5adc613980dc21dc1f0aaa398045252911a5c67594349630ff35d78688a220`。功能副本完整 SHA256：`d8e1c611016b0baa943115078ad49f6e0a147980a7e9fe13df5d3e5827da95ac`。

## SRAM 与未匹配范围

RTL → 基线的 black_boxes 报告只列两端的 `RAMSP1024X16_SS_0P99V_0P99V_125C` 技术库，每端 337/337 个宏。此处 SRAM 内部行为是技术库抽象；不能把逻辑等价说成已证明 SRAM 的全部晶体管或四态行为。

18 个参考端未匹配 DFF 为：内部 bias SRAM 的 1 个 valid_read、8 组权重 bank 各两个 SRAM 的 16 个 valid_read，以及 AON PMU `u_pmu_core/count_reg[15]`。17 个 valid_read 来源已定位到 mem_1024x16 宏适配器：它寄存 `RW0_en & ~RW0_wmode`，无效读期间参考输出为 X；综合可将这一无关条件优化。PMU 源码采用 `tick = ((count ^ (count + 1)) >> insn_dt)[0]`，最高位在异或中抵消，GEN_6 只有声明和赋值、无使用。已对全部 32,768 对高位翻转状态穷举，16 位 tick 表达式及低 15 位下一状态均不依赖该位；记录见 pmu-count15-scope.json，绑定冻结 PMU 源 SHA。未匹配位依然如实列出。

最终网表的额外空壳为 PLIC `flop_o_irq.plic_irq_prio_dffr`，模块 sirv_gnrl_dffr_DW3 声明 qout[2:0]，但实际实例没有连接 qout。5 个未匹配实现输入为 dnxt[2:0]、clk、rst_n；该空壳输出不进入可观察逻辑。它与 337 个 SRAM 宏的抽象分开记录。

## 与冻结 RTL 的逐文件比对

冻结软件验证输入的 source/rtl 共 167 个文件；官方综合参考 source/rtl 共 165 个文件。通过完整路径及 SHA 表逐项比对：162 个字节相同、3 个修改、2 个验证夹具缺席，无额外 RTL 文件。

- 缺席的 generic_ramsp_non_ppa.sv 和 tile_physical_observer.sv 不在正式编译列表中。
- 修改的 mem_1024x16.sv 将行为存储映射到官方 SRAM 宏，保留同步有效读和无效读 X 契约。
- 修改的 sirv_sim_ram.v 将 ITCM/DTCM 行为数组映射到物理宏，并含保留读地址后同地址写入的字节转发逻辑；该适配须与厂商模型检查、实际门级读写一同审阅。
- 修改的 e203_subsys_main.v：冻结夹具增加共享存储时钟/复位、CPU CSR 时钟观察端口；正式参考将同一作用域的一组 637 字符归一化声明前移。去除观察导出、注释、空白并分别移除同一声明块后，其余全部 token 的 SHA 完全相同，为 `26a6a3d1b34b178bd69877d0e527ad7a90dbfd6a043904dec6ce3171455d4338`。此结论不靠文件名猜测。
- 编译列表共 158 个文件，额外于 frozen source/rtl 的入口为 ppa/xu_soc_dma64_ppa_top.sv，负责完整 SoC 和共享 SRAM 的 PPA 边界。

## 当前结论

逻辑比较已取得完整原生通过。源码身份与适配边界已明确，SRAM 宏行为与完整三固件功能继续由同版本厂商模型门级验证验收。时序覆盖及功耗有效性另见 STA-AUDIT.md 和最终活动审阅，不由 Formality 状态替代。
