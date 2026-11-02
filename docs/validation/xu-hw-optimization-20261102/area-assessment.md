# xu 加速器面积评估：2.25 mm² 限额

**使用服务器工艺库综合，完整候选加速器单元与SRAM宏面积合计为 0.293988516 mm²，满足本次用户指定的 2.25 mm² 综合面积上限。占限额13.0662%，余量1.956011484 mm²。**

| 项目 | 软件最优版所用旧硬件 | H1+H2新硬件 |
| --- | ---: | ---: |
| 标准单元面积 | 0.035154454 mm² | 0.147612125 mm² |
| 16个内部权重SRAM宏 | 0.146376391 mm² | 0.146376391 mm² |
| 合计 | **0.181530845 mm²** | **0.293988516 mm²** |
| 对2.25 mm²限额的占比 | 8.0680% | 13.0662% |

综合顶层为 `accel_icb_slave`，包含MMIO包装、8 PE计算、X行缓冲、256×40-bit bias缓存、结果窗口和全部16个权重SRAM宏；不包含E203 CPU、系统互连及共享系统RAM。新旧采用同一SS/0.99V/125°C SMIC40 RVT标准单元和RAMSP1024X16库、同一6.666666667ns时钟及IO约束。

本次额外确认了面积单位，避免仅凭DC数值猜测：从服务器S40工艺归档读取匹配RVT单元LEF，对NAND2、INV、DFF和BUF四种单元逐项核对 `SIZE` 宽×高与mapped-reference报告面积。例如NAND2为0.57×1.68＝0.9576 µm²，DFF为3.61×1.68＝6.0648 µm²。SRAM LEF尺寸为82.46×110.945 µm，面积9148.5247 µm²，与**去除注释后精确定位cell(RAMSP1024X16)**的Liberty面积一致；DB宏面积和物理乘积的微小差异为浮点精度。LEF `SIZE` 使用微米，依据为[Cadence LEF/DEF 5.7参考第183页](https://www.ispd.cc/contests/18/lefdefref.pdf#page=183)。因此按1 mm²＝1,000,000 µm²换算。

完整候选硬件增加112,457.671128 µm²，主要来自Reg缓存及选择逻辑；同时包含H2/MMIO包装及综合映射变化，总面积比旧版增加61.9496%，仍低于2.25 mm²。保持8 PE不等于硬件面积不变；本次周期改善34.6162%是以较大的寄存器/选择逻辑成本换取bias复用。

这是**综合单元与宏占地之和**，不是布局布线后的core/die包围盒面积。尚未加入放置利用率、通道、时钟树、hold修复、tap/filler等物理开销；新硬件仍有−0.118136ns保持时间违例，部分时序检查未测，不能把综合面积满足预算解释为整项物理签核通过。用户先前提出2.5 mm²，随后明确更正为2.25 mm²，本报告按更正后的2.25 mm²比较。原始源端物理证明收据中2.5 mm²及其当时比例/余量保留原字节；本地独立预算核验使用相同面积，按[当前限额记录](area-requirement.json)重新计算，不把旧收据中的预算当作最新要求。

证据与复现：

- [源端物理单位及限额收据](area-compliance.json)，包含LEF/Liberty/工艺归档成员SHA和四种标准单元尺寸，不包含厂商库全文。
- [独立面积限额核验](area-limit-verification.json)：原mapped-reference字节、物理乘积、SRAM库身份、µm²→mm²、余量和预算判定全部PASS。
- [原始精确面积/STA报告](ppa/paired-exact-summary.json)、[完整PPA核验](ppa-verification.json)、[服务器DC/PT复现命令](ppa-reproduction.md)。

独立复核命令（输出文件须不存在）：

```bash
xu_report=/绝对路径/docs/validation/xu-hw-optimization-20261102
python3 "$xu_report/evidence-tools/xu_verify_area_limit.py" \
  --report "$xu_report" --out /临时新目录/xu-area-limit-verification.json
```
