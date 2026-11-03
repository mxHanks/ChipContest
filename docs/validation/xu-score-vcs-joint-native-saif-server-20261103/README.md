# xu actual VCS 联合回调、独立端口探针与 native SAIF 对照

实际服务器 micro34 完成两个严格 GCC/VPI 编译、VCS build、三个完整 mode 和一个故意不结束窗口的负例。第三方 VCS header 用 `-isystem` 分类；自身严格警告与 system 依赖冻结保留。27份 actual raw 对 strict export41 原件逐字节一致，未改原始日志、SAIF、联合统计或sidecar。

独立探针直接读取 owner 与 actual port 的 callback payload/current value。每个完整 mode 中，actual CLK、CEN、D 和 owner Q 共34 bit 的四态 dwell、16类 transition 均与成熟联合 collector 一致；全部8个独立探针 delivered/current 差异为0，最终状态与边界快照一致。mode0 在525ns的实际 owner CLK 与 actual CLK 都只观察到一个 0→1，owner Q/connected Q 都只观察到一次 X→0x2222；没有为匹配 Icarus 的不同结果补边沿。

native SAIF 与相同窗口的 VPI 仍有明确不同：

| mode0信号 | VPI已知01/10边沿 | native TC | native IG |
|---|---:|---:|---:|
| D[2] | 6 | 4 | 0 |
| D[3] | 5 | 3 | 0 |
| CLK | 514 | 513 | 1 |
| CEN | 6 | 5 | 1 |

共10 bit 的 native TC 与已知二值边沿数不同。D[2]/D[3] 在同一 timestamp 的两次实际 D 改变都有独立探针和collector记录，但 native TC/IG没有相同计数。这个反例禁止把简单 TC、TC+IG 或跨模拟器事件数当成通用转换。

mode0 另有3 bit 四态 dwell表示不同：CLK 的1ns X＋1ns Z在native SAIF记录成TX2ns；EMAW两bit各Z3ns记录成TX3ns。mode1/2这两类字段均一致；不能由此外推mode0或真实任务的定义一致。

mode1/2 的 CEN 和 GWEN 各自都正好一半0、一半1，native边际统计也相同；实际 joint 中 Liberty read 条件 `RET1N & !CEN & GWEN & !EMA[2] & !EMA[1] & !EMA[0]` 的占空却分别为0和1/2。这是不能把两独立SP相乘代替联合测量的实际反例。

`field-review.json` 保留逐字段差值和独立事件完整重构；`summary.json` 只汇总实际观测。`evidence-tools/` 包含本次真实输入及独立审计快照，离线重放不需要服务器路径存在。checker 重新计算全部字段，核对完整诊断和27个原件来源；`--self-test` 单独绕过来源hash层，验证5类原始字段破坏会被整数/边界/观测条件拒绝。

```sh
python3 docs/validation/xu-score-vcs-joint-native-saif-server-20261103/evidence-tools/recheck.py --self-test
```

该实验是开放微模块，未使用vendor SRAM模型。它支持上述actual VCS回调观测一致性和native SAIF差异结论，尚不证明完整任务的宏活动、PT条件功耗使用、全SoC单任务能量或完整150MHz资格。
