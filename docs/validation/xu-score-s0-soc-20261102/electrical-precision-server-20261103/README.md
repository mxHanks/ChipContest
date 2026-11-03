# xu 同09网表的高精度电气约束诊断

实际 PrimeTime T-2022.03-SP5-1 已在新目录完成高精度约束报告：**56个max_capacitance和1404个min_capacitance违例pin块**仍在。它们不是低精度打印为0.00即可忽略的数值。

- max_capacitance负slack范围−0.00129576至−0.00025722pF；例如加速器U42/ZN实际负载0.05278776pF，限制0.05149200pF。
- min_capacitance的1404项均为−0.00050000pF；典型为输出负载0.00000000pF、库最小值0.00050000pF。是否为无负载端点/前物理模型须实际连接审查，本报告不自行豁免。
- 十类时序覆盖仍为已测数据/门控无违例、5个reset removal负slack、27127项未测。电气pin块与时序检查计数单位不同。

本次`report_constraint -all_violators -verbose -significant_digits 8`使用同09网表SHA `5610f32b23220c87d39b45f24133adbf867d7faeb7284eed5f75d84b77ef4fca`、原analysis SDC SHA `404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98`及原有限scope16。没有改变阈值、reset约束或增加豁免。布局前ideal clock分析，不声明布线后结果。

实际执行退出0，原完成标记一次，未检出Error，全部输入执行前后SHA相同。新脚本显式配置同服务器Library Compiler环境。前一诊断12虽PT返回0，但报`PT-063`缺LC路径，已保留在原export13，不能充当成功证据；本次14为新目录独立执行。未复用其报告代替本次报告。

原始文件来自603824字节export15，SHA `75d76d05b6492ebc79442b51c90bb9a1fe2b8cae39fa866747f17ecafe61cf98`；全66项manifest已严格核对。本目录只选择诊断14文件，大报告XZ无损保存，展开SHA/字节和原manifest一致，保留原空白。大网表与DB未本地重取，身份由实际执行冻结回执支持。

`verification.json`逐项列出1460个pin与实际slack。此诊断不修改Chisel/RTL、不证明功能一致或全SoC能量，状态保持`NOT_QUALIFIED`。增量design-rule修复另起新目录，不能改写这些原件。

```sh
python3 docs/validation/xu-score-s0-soc-20261102/electrical-precision-server-20261103/check-evidence.py
```

同服务器重放：审阅`evidence-tools/launch_timing_drc_precision14.py`和`raw/.../sta.tcl`的绝对输入路径，换全新输出目录，配置其中原LC环境后运行`pt_shell -f sta.tcl`。历史脚本默认输出已存在会拒绝，禁止覆盖原件。
