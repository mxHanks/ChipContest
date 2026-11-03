# xu S2b/S2c 同库面积与综合前后等价

同服务器、同SS0.99V/125℃工艺库的实际DC综合与Formality结果如下。面积只取新增accel_icb_slave层级（接口、计算、内部SRAM），不将固定E203/共享SRAM/外设计入加速器限额。

| 候选 | 加速器mm² | 占2.25mm² | 全SoC单元mm²（范围不同） | FM实际通过比较点 |
| --- | ---: | ---: | ---: | ---: |
| S2b packed | 0.2869364304 | 12.75273% | 3.357882716900 | 41550 |
| S2c auto+FIFO | 0.2948018380 | 13.10230% | 3.365797600429 | 42338 |

S2c比S2b加速器面积增加约2.74117%，其周期收益见各自开发VCS验收目录。两者面积均低于2.25mm²；不据此把所有剩余面积当成可兑现吞吐，最终仍需一致配置的时序和能量比较。

实际冻结源：S2b主a2a1f076060c43fcefb1148edaa83c89bb1d4320/子d5faa5e8c857fa35df62a68de667bdb8a6e954f7（无Chisel变化）；S2c主d276b55ffecbe8d620f9a361bf5d0859299ba7b5/子49a9436e01ea8ceeead94242e4a99c16e31a0865（GenerateRTL.scala和新增LinearAutoGroupCore.scala）。原始implementation冻结profile、库和source身份；标准DB SHA f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723、1024SRAM DB SHA c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f。

Formality使用每个候选实际DC写出的mapped.v/default.svf及同次物化RTL；输入前后摘要相同，实际退出0、唯一PASS marker、Verification SUCCEEDED。S2b为17136 black-box pins +144 ports +24231 DFF +39 latches；S2c为17136+144+25019+39。各有511 unread DFF和17 unmatched reference compare points（16个W valid_read、原固定PMU count[15]）原文保留。SRAM内部作为black box，auto_setup采用synthesis未驱动信号处理且直接未驱动输出不验证，因此这是**明确条件下全SoC数字逻辑综合一致性**，不证明厂商SRAM内部或全功能/时序资格。

PPA原始全propagated clock视图的setup/hold最差为S2b −20.583927/−21.374241ns、S2c −20.782385/−21.973709ns；未CTS全局时钟网络负载是诊断条件，不冒充布线后STA。696个no_clock pin条目仍待角色分类，原collector的report_exceptions -verbose兼容失败也保存。**没有宣称完整150MHz时序合格**，也未据此计算正式能耗或最终得分。源派生有限CDC/forwarded/ideal时钟审查和hold修复在另目录，不拼接为这两个候选已通过。

```bash
python3 docs/validation/xu-score-s0-soc-20261102/s2bc-area-formality-server-20261103/check-evidence.py
```

只读检查器逐项核41个原payload、DC报告与实际来源、唯一层级面积、FM输入冻结和全部比较点/未比较范围。原网表/SVF/DB字节没有取回本地，其SHA为实际服务器原receipt声明，不声称再次哈希未取得的二进制。原始script/绝对路径/日志时间及空白保持；最外层formality campaign snapshot仍在S1运行中，但所选S2b/S2c条目均已真实终态，未把snapshot误写成整个campaign已完。

复现须使用各冻结候选与原库，在新目录生成implementation、prepare/run PPA，再按原verify.tcl改为新物化路径执行 `fm_shell -f verify.tcl`。完整生成/prepare/run argv在两个原state，实际FM参考读取、库、SVF和网表路径在原verify.tcl。工具为DC T-2022.03-SP5-5、PT T-2022.03-SP5-1、FM R-2020.09-SP5；所有原命令与条件须保留，不能只凭read/link成功声称等价或时序。
