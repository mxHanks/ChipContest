# xu 64PE 实际同库综合面积

64PE 候选加速器层级综合 cell area 为 **0.9184209509 mm²**，占 **2.25 mm²** 限额的 **40.8187%**；完整数字 SoC cell area 为 **3.989337870903 mm²**。面积使用完整 `u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_accel_icb_slave` 层级行的 Global cell area，包含64PE、bias缓存、调度、FIFO/MMIO以及全部64个W SRAM宏。CPU、固定外设和512KiB共享SRAM属于完整SoC，不计入该加速器预算行。该面积满足综合单元面积限额，不能据此宣称完整参赛资格通过。

同服务器32PE的加速器面积0.5186033811mm²；64PE增加 **77.0951%**。服务器真实12层从11376501降至11301600周期，仅减少 **0.658383452%**；相对8PE自动分组的11842200周期减少4.565030146%。这些周期对应同一冻结64PE源码中真实运行的物理64/32/8以及三种调度对照，完整功能/逐层表位于相邻 `../s3-pe64-server-20261103`。本目录尚无64PE自身正式clear/REQUEST窗口的全SoC单任务能量，不能仅以吞吐或面积判断最终评分或淘汰方案。

| 项目 | 实际结果 |
| --- | ---: |
| 加速器 Global cell area | 918420.9509 µm² |
| 完整SoC Total cell area | 3989337.870903 µm² |
| 加速器限额 | 2.25 mm² |
| 宏数量：ITCM / DTCM / shared / W | 32 / 32 / 256 / 64 |
| 全SoC宏总数 | 384 RAMSP1024X16 |
| W逻辑 / 物理 / padding容量 | 32 / 128 / 96 KiB |
| 初始传播时钟 setup / hold 最差 | −23.631557 / −29.837738 ns |
| analysis checks：总计 / met / violated / untested | 397782 / 234973 / 131624 / 31185 |

冻结主仓 `3443fad8945577626d226b1cd53eadec89331a20`、子仓 `7aae96776e116d5e95d6ebb49d29a5fccce04ab9`；原实际producer为 `e19304cb3f1f45ad2b691a9e316702ff2aeea9d1`（服务器 Tool06），profile `s3-pe64`。仅选择 `SYNTHESIS`、`DISABLE_SV_ASSERTION=1`、`XU_ACCEL_PE64=1`。DC T-2022.03-SP5-5与PT T-2022.03-SP5-1在相同SS库执行，DB SHA为标准单元 `f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723`、SRAM `c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f`。

面积从唯一完整加速器层级行解析，按1mm²=1000000µm²使用Decimal换算，未采用 Local cell area、CPU行或完整SoC行替代。`report_units`本身没有声明面积单位；µm²依据是同一库此前实际四种标准单元LEF宽高乘积与mapped library area相符，以及精确RAMSP1024X16 Liberty cell面积9148.5247与LEF 82.46×110.945µm相符。该原始单位收据保存在 `context/prior-area-compliance.json`，SHA `8df6f900caf17e522ee4342295480bd605a62a0c1049b4a4ed5ba2414330cf3c`。其中历史2.5mm²上限原样保留，本目录只复用物理单位证明，预算使用用户更正的2.25mm²。当前references报告中的DRNQV2和BUFV2RD单元面积也与该单位证明匹配；所有384个实际宏的DB浮点占地均已计入area报告，没有把96KiB物理padding当成零面积。

本目录只归档既有64PE的实际综合结果，没有改Chisel或RTL。该候选生产Chisel改动为 `src/main/scala/GenerateRTL.scala` 及新增 `src/main/scala/linear/XuParallel64Core.scala`，与32PE已有共用计算/缓存构件配合；具体并行度、供数和三种ABI的功能证据仍以相邻64PE完整VCS目录为准。

79份原件来自export41，整包945596 bytes、SHA `1dd38367c7e76f59e11ce5ecd7a970c75e6ec78894ee497824b3becc31f69bfb`。归档前重新核验全部148项原manifest，再只选择终态PE64 PPA目录；选择的原始总字节为38273013。超过阈值的大文件用XZ无损保存，展开字节数和SHA与原件完全相同，日志空白、警告和负面报告保留。

本地校验覆盖实际DC和PT完整log、综合前/后及PT的384宏清点、两个工具版本、实际producer源码SHA、源/定义/宏组/library冻结、唯一面积层级、单位、31份返回reports及原始负时序与覆盖。另将原PPA launcher审查的123项VCS prerequisite identity与既有完整VCS归档交叉比较，120份返回原件SHA完全一致，3份simulator build receipt未取回。本目录保存原验收state字节；不能把这些server-side receipt当作本地已下载的ELF或模拟器本体。

主仓1637个entries与子仓1076个entries的完整source manifest fingerprint，与实际PPA source freeze逐项一致；本地再次对原始Git对象重放，检查bytes、mode、OID和gitlink。163个prepared输入中24个实际SV返回文件逐字节核对，其他139个输入的SHA为服务器冻结回执，原始候选Git与producer来源可复原对应内容。商业DB、原mapped.v/SVF、638987063-byte约束报告和37383529-byteviolations报告没有取回，本目录明确保留对应receipt，不宣称本地逐字重放。

初始PT为传播、尚未布CTS的时钟诊断，所有负面setup、hold、reset、gating、pulse-width、untested细节仍在raw；`report_exceptions -verbose`实际不支持`-verbose`，原CMD-010报告及unavailable提示保留。此批结果不代表完整150MHz时序通过。后续repair、FM37或其他mapped一致性作业为不同证据，本目录不合并或回填。宏内部功能/PVT、完整STA覆盖及64PE正式全SoC能耗仍待资格验收。

```bash
python3 -B docs/validation/xu-score-s0-soc-20261102/s3-pe64-ppa-server-20261103/check-evidence.py
python3 -B docs/validation/xu-score-s0-soc-20261102/s3-pe64-ppa-server-20261103/test-semantic-evidence.py
```

45项semantic negative在内存中修改面积作用域、面积换算、宏数量/几何、完整性、源/库/定义/adapter身份、单位、STA资格及VCS对照，并重新签名可用的execution/generated-control/report receipt；全部被拒绝。原始文件未被更改。`payload-manifest.json`记录本目录交付物SHA；`selected-manifest.json`记录每个原件的储存/展开身份。

服务器复现需干净的新Tool06等价工具树checkout原producer `e19304c`，原候选 `3443fad`/`7aae967`、原完整acceptance、GCC/VCS及上述原DB。使用新的输出目录，禁止覆盖历史原件：

```bash
xu_base="$HOME/Desktop/xu-score-optimization-20261102"
xu_tools="$xu_base/ChipContest-ppa-tools-20261103-06"
python3 "$xu_tools/tools/ppa/xu_pe64_ppa_server.py" \
  --producer-root "$xu_tools" \
  --source "$xu_base/ChipContest-s3-pe64-02" \
  --acceptance "$xu_base/s3-pe64-accept-02" \
  --out "$xu_base/s3-pe64-ppa-reproduce-new-directory"
```

完整原始三步argv、源路径、库路径和Tcl参数均保存在raw的state.json、prepared.json、synth.tcl、sta.tcl中。`evidence-tools`是原producer的精确源码快照，不替代完整工具树。
