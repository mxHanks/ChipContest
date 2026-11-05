# xu201：映射后功能资格的只读诊断

原111/147/167构建argv、运行argv、已返回TB/C、input receipt中，没有显式SDF注释证据；没有把服务器尚未返回的mapped/model全文算作本地扫描。
三次原生构建报告TimeScale is10ps/1fs，CLI和TB有自己的1ns/1fs；不能把全设计理解为统一1ns默认延迟。
原25条native timing violation证明specify检查生效，原模型ARM_UD_MODEL的实际语义仍须结合模型元数据核验。
两条UDP override告警保留，不据此直接判模型错误。

同147被动观测167中，FIFO CK上升/D下降同刻的native hold10000fs告警，NOTIFIER/n0同刻变化，Q在10000fs后为X，再经协议出现bias_commit未知fatal；只有事件关联，不构成因果证明。
更早D瞬态X、无效read-data X与未观察锥均保留。128的+notimingcheck只是原诊断，不能解除strict功能/时序门槛。

当前可检验假设（均未证明）：

1. 原模型默认延迟/实际时钟到达关系使无显式SDF的门级路径出现hold告警；先核同图实际clock/D路径与模型检查条件，不能直接关闭检查。
2. 自己同corner映射最短路径确有hold不足；需共同scope的native min路径与完整、同corner、可核注释的延迟诊断才能区分。
3. 更早有效上游未知独立影响协议；需扩大纯被动观察锥，保留有效条件和事件时间。
4. 模型宏/UDP覆盖选择或corner对应有差异；须核原模型元数据、实际编译分支与SS DB对应，不能凭宏名猜测。

后续207先修复查询API、分别保留旧S2c时钟方法与共同scope同图查询。实际报告取得前不宣布任何假设成立。
本目录不运行EDA、不改生产代码、模型、初始化、TB采样、SDC或检查开关，所有资格保持NOT_QUALIFIED。

复现（全新输出目录）：

```sh
python3 -B build/xu-mapped-function-diagnosis201/diagnose201.py --out /absolute/fresh201
```

actual201三份输出已经由root在fresh/tmp再次逐字节重现。16份本机源身份列在source-manifest201，服务器未返回的模型/网表/输入只核历史回执。
