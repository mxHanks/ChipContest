# xu 32PE 实际同库综合面积

32PE 候选真实加速器层级面积 **0.5186033811mm²**，占2.25mm²预算 **23.0490%**；完整数字SoC为3.589560839551mm²。预算排除复用CPU、512KiB共享SRAM及固定外设，不能用完整SoC面积判定加速器超限。面积本身在限额内，尚不表示该候选完整参赛资格通过。

同服务器S2c 8PE自动分组面积0.2948018380mm²；32PE增加约75.916%。对应真实服务器12层周期从11842200降至11376501，减少3.932537873%。这项吞吐/面积取舍必须继续结合32PE自身全SoC单任务能量评估，不能沿用旧8PE或wrapper功率来选型。

冻结主仓94ce6f0f54fffdd590ff9a3ebad0197ec0fd9114、子仓fc3977d0a6d5f85fbfd871fd9439c01c9acab5f5，profile `s3-pe32`；实际producer为6798c492136db3f1f944b8d2eb19d940bb85e64a。库仍为同一SMIC SS标准单元DB（SHA f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723）和指定RAMSP1024X16 DB（SHA c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f）。实际DC T-2022.03-SP5-5、PT T-2022.03-SP5-1。

只选定SYNTHESIS / DISABLE_SV_ASSERTION=1 / XU_ACCEL_PE32=1三个defines。实际DC综合前后宏清点均为ITCM32、DTCM32、共享256、权重32，总352；W逻辑32KiB，物理64KiB，padding32KiB。比8PE多出的16个1024深权重宏与32PE/FIFO/选择逻辑均计入加速器面积，没有把padding容量当成零面积。

本次没有修改Chisel或RTL，综合的是此前已通过三路服务器VCS的同一32PE候选。对应生产Chisel改动为GenerateRTL.scala及新linear/XuParallelCore.scala，具体电路/逐层周期与完整功能证据见相邻 `../../../xu-score-s3-pe32-server-20261103`；该证据中原2510路径部署清单与冻结Git完整匹配。实际PPA launcher重新检查强制direct、完整12层及两个对照后才运行。

## 仍未闭合的范围

原PT使用全传播、未布CTS的时钟模型，setup最差−21.954998ns / hold最差−25.257580ns；analysis coverage总342065，met216444、violated97285、untested28336。这里原样保留，不解释为布CTS后的真实结论，更不写成150MHz通过。已另开该候选自己的ideal preCTS hold/gating修复；结果不能回填本批原PPA。

FM17为另一新作业，尚不纳入本目录。原mapping review、宏内部功能、STA覆盖/复位/UART/电气检查及同配置正式clear/REQUEST窗口的全SoC能量仍待验收。后来的ba9d89a主仓字节guard修复是另一工具身份，不能追溯赋给本次6798运行；本目录不把该工具改进误写成服务器已有源变更。

73份选择原件来自829064字节export18，SHA f61f6a53bb94f24b32b38a878bf6f457997438b15bf18503e6ff8d29cdbfd772；全部97项原manifest先严格核验，再只选32PE终态目录。大文件XZ无损保存，展开SHA及字节数精确相同，日志空白和告警保留。`verification.json`列出已取回报告、未取回报告的服务器receipt。

完整PT log、463MB约束报告等大文件没有本地下载，不能声称逐字重放它们；其退出码、SHA与执行状态来自服务器回执。原mapped.v/SVF/商业DB/未取回RTL的SHA同样只是冻结回执身份。本目录核对已取回实际DC log、宏计数、实现几何、面积层级、源/工具声明、已取回报告哈希、原时序表、三步状态和VCS前置结果，不运行EDA。`evidence-tools`保存与实际producer SHA相同的三个生成/启动源文件。

```sh
python3 docs/validation/xu-score-s0-soc-20261102/pe32-area-server-20261103/check-evidence.py
```

同服务器复现：以新的干净工具树checkout6798c49、原候选94ce6f0/fc3977d和原库SHA，在新out运行evidence-tools/xu_pe32_ppa_server.py，明确`--producer-root`指向该工具树。该脚本要求原完整VCS验收输入、ELF/镜像和声明SHA匹配；原实际三步argv、prepare Tcl及全部固定路径在raw/state.json / prepared.json / synth.tcl / sta.tcl中。重放须使用新out，禁止覆盖本批原件。
