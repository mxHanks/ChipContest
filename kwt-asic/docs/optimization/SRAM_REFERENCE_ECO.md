# SRAM参考网表最小延迟候选

日期：2026-10-18。只针对已接受Nangate45参考网表，保持RTL、Golden、16/16/40/41/48数值、20bank、72opaque宏和原SDC。**官方宏/PVT/真实互连尚缺，不是正式150MHz/PPA结论。** 当前状态以PROGRESS和本页末尾结果索引为准。

## 实际改动与来源链

原缓冲映射：`20261018T022812.829729Z-sram-blackbox-501ae448`。后续全部独立新目录，不覆盖原版。

| 阶段 | 实际修改 | 实测结果/当前边界 |
|---|---|---|
| reset强度探针 | 宏切口视图BUF_X1→X8/X16，保存后新进程重读 | 电气改善但min仍负；诊断后不晋升 |
| 完整候选1 | reset BUF_X1→X16；其输入串6个BUF_X1；accumulate_valid D支路1个BUF_X1 | removal+0.055262ns；余下counter hold -0.004303ns，未接受 |
| 完整候选2 | b_loaded[0]/x_loaded[0] D支路各1BUF_X1 | setup+4.652084、data hold+0.001379、removal+0.055262ns；1/12层回放通过，但另发现11个transition违例 |
| 完整候选3 | 唯一NOR4_X1、10负载（二BUF_X1+8NAND2_X1）驱动改NOR4_X2 | 同库函数相同、逐pin图保持；1/12层回放及已覆盖时序通过；后续全网max-cap发现4驱动超限，不能接受完整参考电气 |
| 完整候选4 | 依据真实cap失败将另外2个NOR3_X1、2个NOR4_X1改X2 | 新网表1/12层回放通过；已覆盖时序保持，48378标准输出全网已知cap/transition/clock无报告违例；182宏负载/1152宏输出仍未知 |

第四候选相对原版共9个新增BUF_X1、reset一处X1→X16、3个NOR4与2个NOR3从X1→X2，46035标准单元；标准逻辑57015.238μm²=0.057015238mm²，对原56997.416μm²增加17.822μm²。宏面积、功耗保持未知。中间counter报告的`logic_area_delta_um2=11.438`来自继承的第一步字段；第二步额外1.596、累计13.034，第三步额外1.064、累计14.098，第四步额外3.724、累计17.822。不能把旧继承字段当最终累计值。

插入的是库中真实非反相buffer，不是RTL `#delay`、恒等表达式或通过keep阻止无意义代码优化。ECO在最终技术网表阶段执行；未来重新综合或改库必须重新生成/验证，不假设工具会自动保留物理修复。

## 可复现入口

```bash
source env/activate.sh
make synth-minimum-reference MAPPING_REPORT=<原缓冲mapping的result.json>
make synth-counter-hold-reference MAPPING_REPORT=<上一步新result.json>
make synth-slew-reference MAPPING_REPORT=<上一步新result.json>
make sta-logic MAPPING_REPORT=<第三候选result.json>
make check-reference-electrical STA_REPORT=<实际新STA的result.json>
make synth-cap-reference MAPPING_REPORT=<第三候选result.json> CAP_REPORT=<该候选真实cap失败报告> CAP_TARGETS=<已核定的四驱动plan.json>
make sta-logic MAPPING_REPORT=<第四候选result.json>
make check-reference-electrical STA_REPORT=<第四候选实际新STA的result.json>
make test-mapped MAPPING_REPORT=<第四候选result.json> MAPPED_TASKS=1 SRAM_VECTORS=<已验证真实导出目录>
make test-mapped MAPPING_REPORT=<第四候选result.json> MAPPED_REUSE=<已通过1层result.json> MAPPED_TASKS=12 SRAM_VECTORS=<同导出目录>
```

每步打印新report路径，下一步必须使用其实际路径。默认静音向量与真实语音向量范围不同；本轮真实语音来自`artifacts/runs/20261015T091234Z-speech-smoke/export`，不代表完整validation RTL回放或600官方样本。

生成器按驱动/端点实际连线检查目标，不根据旧Verilog的匿名实例编号盲改；输入结构不符直接拒绝。新增cell/net名称不重用，分配bit时包含无驱动旧别名。Yosys JSON回写可重排bit编号，因此用所有命名bit双射核每个cell/pin和外部ports，不以原始编号相同冒充图一致。

前两候选另用`check_sram_eco_identity.py`折叠新增非反相buffer、对照原mapped图，证明状态/端口图身份；该结论不是RTL→ABC形式证明。后续NOR strength替换由真实Liberty函数相同及其余图逐pin保持证明，不冒用只允许BUF替换的投影结果。第四步targets同时绑定原mapping/cap身份及完整expected_cell；匿名实例到完整实例的映射由实际bit/连接签名及独立审查承担，不靠匿名编号推算。新工具或重新生成网表后须重做映射，不能只复制旧plan。

## 接受边界与回滚

- 功能仅在同Liberty功能模型、共同一拍逻辑SRAM和零延迟条件下回放；全网四态/完整形式等价仍未证明。
- 局部STA使用原6.666666667ns、0.1ns uncertainty、ideal clock和5K_hvratio_1_1统计wireload；不等于真实clock tree、提取寄生、官方PVT或完整宏路径。hold只有1.379ps余量，不能称有稳健工艺裕量。
- 第四候选实扫48378个标准输出，32类输出上限，已知cap无违例/舍入边界，最小已知电容余量0.362942570fF；包括X2的上游输入负载变化。182个驱动接真实宏输入负载未知、1152宏输出驱动未知，完整电容/官方电气仍BLOCKED。
- 原RTL/SoC证据按未变来源保留；每份新网表必须重新做对应网表功能和参考STA，不能继承前一候选的PASS。
- 回滚只改调用所选mapping report回原`501ae448`；原文件未覆盖。官方库发布后按真实门/宏时序重做ECO，不搬用这些精确cell名或delay级数当作正式实现。

第三候选历史索引`docs/runs/sram-reference-eco-20261018.json`保留；第四候选`a2a7cf86`的最终12层为`artifacts/runs/20261018T045551.554590Z-mapped-replay-a9782263/result.json`，304128输出、1873549响应、9756保持检查、恢复1+1、末HI/ACK各12。源模型/实际binary/native退出和完整标记绑定。参考电气正式Make入口`045757…reference-electrical-a1c4d8a4`通过，完整新索引`docs/runs/sram-reference-cap-closure-20261018.json`；所有失败保留。通用采集代码在`scripts/verify/reference_electrical/`，大型原始报告始终放artifacts。
