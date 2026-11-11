# 2026-11-11 面积优化实验进度证据

本目录保存A/B完整本机筛选、已核验的48位基线原生PPA，以及候选的实际综合输入与接续工具。A/B同条件DC及PT采集已在服务器完成，原件回传中断，**尚未完成候选PPA审计或最终选型**。软件仍使用发布48位回退父d60e0e0、子a80dd184。本轮实验分支的发布不等于新生产硬件发布。

完整12任务304,128输出逐位正确，主口径428,915拍（含真实clear12,336），逐层、gap、固件区间和总线工作量均与回退相同。见cpu-validation-summary.json和独立review。假定150MHz换算4196.64task/s；实际150MHz未通过。

## 归档与身份

所有本目录文件的字节数和SHA见SHA256.json。README及SHA256.json不参与其自身递归哈希。历史source manifest保留测量时路径和父子身份，不以当前HEAD重写。

- `sim-candidates-r1.tar.gz`：607文件delta，14,917,124B，SHA `885d595a33b6dbfb682f5e9555f15872ac63521654bcf0a3b36556cabbd028bd`。包括候选生成器/补丁/SV、默认48位逐SHA检查、原始模块/DMA/CPU日志、ELF/image、几何/AST/数值证明、比较器与REPLAY入口。
- 仿真共享来源：`docs/validation/s3-y32-4k-20261110/frozen-delivery.tar.gz`，SHA `464bea138c254d842b1db656da0e8feb42e04e509f9ab85d92e0cd30736b543f`。解压delta后`python3 REPLAY.py`核对身份；`--prepare-only`结合该来源包恢复实际源码/向量，A/B均已逐SHA验证。显式`--run`才启动新仿真，须遵守截止和新目录检查。
- `r5-mini-native.tar.gz`、`r5-leaf-native.tar.xz`：48位基线metadata、32.5MB完整leaf清单、完整DC日志/面积/引用报告与mapped.sdc。叶面积已独立重算，总计523,712.858238库单位。原R5 collector因映射后额外查询停滞，由负责人停止；FAILED/退出码1、owner-stop和Signal15原件保持。
- `pt-r4-native.tar.xz`：48位基线全部46项原始PT输出，SHA/bytes已核验。setup−10.66794014ns、hold−0.13472039ns，211项检查违例，时序未闭合。review/triage保留674宏CEN/RET1N原计数及逐项分类，337实际CLK均关联；不豁免其他检查。
- `native-frontend-failures.tar.gz`：早期DC前端失败原件及审计。`r5-transfer-incomplete.json`保留旧大包102/3745块中断，不冒充完整回传。
- `candidate-a-ppa-inputs-r3.tar.xz`、`candidate-b-ppa-inputs-r3.tar.xz`：实际242项远端输入。与完整243项方案精确对照；仅省略保存在仿真包内的两份非编译大XML，并加入重建sidecar。158条编译源、compile策略、SDC、DB、宏及几何保持同条件。输入冻结/AST证明不是测量结果。
- `ppa-tools-r1.tar.xz`：早期22份执行/审计工具及记录。新候选PT审计、最终比较和安装工具使用下面的progress工具包；旧包不单独代表全部收尾工具。
- `progress-tools-r1.tar.xz`：219个regular成员，263,392B，SHA `e8c180cfa47570b5d3bcec312a8548f6785543595b4c77c5d18c896bc8d5fa8e`。包含202项冻结工具/身份、最新面积/PT审计与比较器、五源码补丁/安装审计、最终打包准备、执行记录、候选native分片索引和中断记录、只读reports-only r4脚本。内部MANIFEST独立覆盖217项payload；全包逐成员SHA复核。**它是可接续进度包，不是最终选型或候选PPA通过记录**。未封存final-tools-r2。

## 当前回传缺项与接续

A/B实际串行链均已完成正常映射及PT采集。A原生屏幕计费面积初值515,134.996638库单位，约比基线低1.64%；候选leaf尚未独立回传重算，不能将初值认作最终面积收益。B数值尚未完整返回，不作选型。

候选完整native r3包6,260,784B，SHA `4fc0a9ae3c1ae54f9e080f5ed1202a2c7862dbe9d8c44edfbc7df9f06679ca6b`，24个独立SHA分片。索引已核验，仅0、1片完整，第2片在25/32块后超时，完整包未拼装/解压/审计。随后VNC TCP连接成功但RFB头超时；凭据未改，不重启或终止其他作业。候选mapped.v/ddc以及完整r3包保留远端；基线mapped.v/ddc也尚未本地逐字节验证，缺项明列。reports-only r4只读小包准备尚未执行，不需要重跑EDA。

恢复原连接后先取回所需全部leaf/DC/PT原件并核对SHA，再运行progress包内的audit_native_area.py、audit_candidate_pt.py和compare_area_report.py。比较器采用计费范围作分母，并保守加计范围外逻辑正增长；PT采集完成不代表时序闭合。选型/安装/父子提交后才封最终tools包、发布最终硬件。自有VNC v5临时SendCutText状态仍待恢复，入口见[handoff](../../s3-y32-area-opt-handoff.md)。

库面积单位、官方SRAM计价、2.25mm²判定和宽口平台资格未确认。所有当前工具自检仅验证工具行为，不代替候选实测PPA。新实验截止2026-11-11 23:59上海。
