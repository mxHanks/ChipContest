# 四驱动电容ECO独立复核

2026-10-18。独立只读代理检查实际报告/网表/Liberty，主代理整理；不重新运行EDA、不据审查生成功能PASS。

## 为什么新增候选

第三候选已覆盖setup/hold/removal及transition为正，但另行全网采集发现4驱动/8个rise/fall电容检查超限。采集首次因OpenSTA将相等rise/fall打印为单值被拒绝；保留旧collector与失败，实际单网报告和Tcl正负例资格化后用独立v2，完整扫描48378个输出网确认问题。

## 四个实际对应点

完整实例均以前缀`$abc$87792$auto$blifparse.cc:386:parse_blif$`起始。

| boundary匿名实例 | 完整名称后缀 | 原输出bit | 负载/变化 |
|---|---:|---:|---|
| `_75082_` | 129324 | 32218 | 24个Bias宏rd_en；NOR3_X1→X2，真实宏输入电容仍未知 |
| `_77380_` | 87939 | 34952 | 1BUF+5NAND3；NOR4_X1→X2 |
| `_78311_` | 88870 | 36056 | 6BUF+2MUX；NOR4_X1→X2 |
| `_79844_` | 90403 | 33796 | 9个控制逻辑输入；NOR3_X1→X2 |

共同named-bit与唯一源/负载pin签名实际核对，不按匿名编号偏移猜测。绑定targets保存完整expected_cell及原cap/mapping SHA；新生成器要求四个实际失败驱动集合吻合，原cell逐项相等，再允许明确NOR3/4同函数强度替换。脚本不自动推导匿名映射，该映射由已绑定plan和独立签名审查承担。

## 网表与电气结论

`a2a7cf86/result.json`的65输入/8产物、canonical identity和原生EXITED0/完成标记一致。原1836至新a2a7全部named-bit双射及逐cell/pin/参数/ports检查，严格仅上述4处type变化，无增删、72宏保持、标准单元46035。绑定Liberty中NOR3_X1/X2函数一致、NOR4_X1/X2函数一致；本步+3.724μm²，标准逻辑总57015.238μm²，相对原版+17.822μm²，不含SRAM。

`followup-20261018T045407.863054Z-3325e2ca/result.json`复用冻结v2，真实新STA `1f542ca4`明确绑定a2a7；boundary字节一致、SDC与原031137一致。33输入/11产物SHA、canonical identity/native/log一致，EXITED0、无中断/超时、48378行及唯一完成标记完整。独立纯Python重算inventory/parse得到同measurement：32类标准输出上限，0已知电容违例、0舍入边界，最小已知电容余量0.362942570fF。全网重扫包含X2上游新增输入电容。原始transition/clock报告为空，与0违例口径一致。

182个标准驱动连接宏输入、1152个宏输出驱动位继续UNKNOWN/BLOCKED；完整设计和官方电容仍BLOCKED，没有追加假set_load。接受仅同参考macro-cut/原wireload/SDC已知负载。新STA及功能必须分别读取新候选的实际结果，不能用本审查替代，也不能沿用第三候选12层PASS。

## 最终入口与功能补核

推广后的`qualified_cap_model.py`中五个解析/库存函数AST、Tcl及列常量与冻结v2一致；实际Make入口`a1c4d8a4`的模板/identity/boundary/原SDC/native/SHA均核对，独立纯Python复算48378网的结果一致。旧collector/失败没有被修改。

新网表`900bfc2c`确实编译a2a7来源、仅替换仿真top名；`a9782263`复用同一binary，task0–11全部结束、304128输出、1873549响应、9756保持、恢复1+1、末HI/ACK各12及finish完整。最终主机`045809`日志真实Ran204/OK；新索引`docs/runs/sram-reference-cap-closure-20261018.json`的596个唯一文件及报告SHA复核通过。旧614文件/202测试的恢复结果未扩大成当前源码包结果。

最终局部验收通过，范围仅参考标准逻辑所测功能、已覆盖STA和已知负载；1.379ps裕量、真实宏/PVT、全网四态及全输入形式限制继续保留。
