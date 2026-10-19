# Chisel 与现有 KWT 数值工程的真实向量交接

2026-10-17，Asia/Shanghai。实现位于独立副本 `integration/ChipContest/`，来源提交 `30e737ca37bc7d3077db1877ee89072ac4dfc723`。原 `ChipContest/` 保留队友提交。当前验证入口为 `src/test/scala/linear/LinearLayerRealVectorTest.scala`；实际执行状态以绑定源码 SHA 的 `artifacts/integration/20261017-teammate/chisel-fusion-r2.json` 为准。

## 输入与数值

测试接受本工程现有 `kwt_ffn_export_v1` 导出目录。`KWT_VECTOR_ROOT` 设置该目录的绝对路径；未设置时，从当前目录向父目录寻找 `sim/vectors/kwt-silence-v1`。本轮优先使用真实非静音语音导出：

```text
artifacts/runs/20261015T091234Z-speech-smoke/export/
```

该输入包含固定官方 KWT 提交 `237e4097afd4f6851e0b82f0a8d65c2dfe8eae30` 的12层权重，以及同一波形在各层第一前馈层之前的真实 X。它是单波形、真实权重的跨实现回放；不代表完整验证划分、官方600样本精度或SoC结果。输入的 TensorFlow 环境限制沿用原导出 manifest，不因 Chisel 回放通过而取消。

各层文件保持原统一布局：

| 文件 | 元素数/位宽 | 文件地址 | 解码 |
|---|---|---|---|
| `x.mem` | 6,336 / signed16 | `row*64+k` | `code*2^x_exp` |
| `w.mem` | 16,384 / signed16 | `k*256+column` | `code*2^w_exp` |
| `bias.mem` | 256 / signed40 | `column` | `code*2^(x_exp+w_exp)` |
| `y.mem` | 25,344 / signed48 | `row*256+column` | `code*2^(x_exp+w_exp)` |

每行固定小写hex补码，位数依次4/4/10/12；拒绝错误数量、空行、未知态、非hex和越界高位。解析时按指定位宽显式减 `2^bits` 得到负整数，禁止以 JVM `Int` 容纳40/48位。fixture manifest必须为PASS、正确schema/format、全部12层0..11、正确形状及结束标记；每个mem重算SHA。测试前以独立 BigInt 为所有304,128个参考输出重新计算 `bias+ΣX*W`，避免把仅自洽的文件名当成正确参考。测试结束再次核对全部输入和manifest SHA，输入运行中变化会失败。

数值固定 `fixed16_acc48_v1`：X/W16、bias40、精确48位累加和输出，无中间截断或舍入。浮点到整数的RNE、饱和和尺度选择由原导出完成；测试不重新标定、调参数或传播量化输出到下一层。原导出中的每层 `bias_exp`/`y_exp` 必须等于 `x_exp+w_exp`。

## 从统一布局到队友的物理 bank

ChipContest 的 `WeightBank` 使用列连续布局。对逻辑 `W[k,column]`：

```text
bank  = column % 8
group = column / 8
addr  = group*64+k
data  = w.mem[k*256+column]
```

本工程 banked/rowpair 内部地址 `k*32+group` 与其不同，不能拷贝已经分bank的文件。新测试只通过公开加载端口转换逻辑索引，不访问或直接初始化内部存储；硬件必须真实执行全部乘加。

每层都重新装载全部16,384个W；随后按 `rowLoadRequest` 装载每行64个X，再发 `rowLoaded`。每组按当前 `group` 提供8个对应bias，保持到INIT采样完成；全部256个bias每层均来自独立文件。层间不保持可用于跳过装载的参数缓存，也不把上一层 Y 当作下一层 X。

输出第 `row,group` 组的8路按 `y.mem[row*256+group*8+bank]` 逐位比较。测试检查row/group身份、第99行、最后通道以及全部304,128项，不接受只比较前几项或聚合校验和。

## 握手、复位与失败条件

固定随机种子 `0x4b575431` 为各组设置0–2拍结果回压；每层首组17拍、末组11拍，逐拍验证 `resultValid`、row/group、8路结果不变且done未提前。只有比较完成后才给一拍 `resultReady`；最后组消费之后要求done有效一拍，再恢复空闲并开始下一层。

另一个独立用例在计算进行20拍后复位，再完整重载新X/W/bias，以 signed16正负极值、signed40正负极值验证8路恢复结果。payload存储未承诺复位清零；复位后的有效性由完整重载重新建立，不能依赖旧内容。它验证中止任务不污染新计算，不宣称核心自身已具备防御错误装载的MMIO接口。

计算等待有100拍上限；结果输出回压为有界激励，不会以无限等待掩盖死锁。有效完成必须同时有 ScalaTest 13项全通过、12条 `KWT_CHISEL_LAYER_COMPLETE`、一条 `KWT_CHISEL_REPLAY_COMPLETE layers=12 outputs=304128`、一条 `KWT_CHISEL_RESET_COMPLETE`，退出码0及输入/源码SHA稳定。任一缺失均不是PASS。

## 资源、修改范围和运行

融合副本修复原 `WeightBankArrayTest` 未清写使能的问题，修正全矩阵测试 `lineear` 包名，并将所有测试接入 `verification.BoundedChiselSim`。该trait使用 Chisel 7.16.0 的 `svsim.CommonCompilationSettings.AvailableParallelism.UpTo(2)`，在继承的CLI设置后施加上限。API已对下载的固定版本jar类签名核对；运行产物中的make命令还应核实实际为至多2个编译worker。附加 `JAVA_TOOL_OPTIONS=-XX:ActiveProcessorCount=2 -Xmx4g` 约束JVM并行和堆；ScalaTest不启用并行suite执行。重型EDA不得与该回归同时运行。

`project.scala` 删除原多余snapshots仓库声明，保留原Scala/Chisel/plugin版本；JSON解析显式增加与原Chisel依赖相同版本的测试依赖 `ujson:3.3.1`。主Scala设计源无修改。原始错误激励回归已单独保留为 `chisel-original.json/log`（10通过、1失败），修复不覆盖它。首次融合编译因新trait遗漏ScalaTest self-type失败，也保留为 `chisel-fusion.json/log`；随后补齐self-type再运行r2。

从本工程根目录设置环境后，在 `integration/ChipContest` 运行：

```bash
source env/activate.sh
export KWT_VECTOR_ROOT="$PWD/artifacts/runs/20261015T091234Z-speech-smoke/export"
export COURSIER_CACHE="$PWD/.tools/teammate/coursier"
export XDG_CACHE_HOME="$PWD/.tools/teammate/cache"
export JAVA_TOOL_OPTIONS='-XX:ActiveProcessorCount=2 -Xmx4g'
export PATH="$PWD/.tools/teammate/bin:$PATH"
cd integration/ChipContest
scala-cli --power test . --server=false --jvm 21 --offline
```

`--offline`用于依赖已准备的复现；首次安装需要允许访问固定Maven/JDK/firtool来源，不能用离线报缺项代替测试失败。原主仓库未改动，修复差异和新源码SHA应随集成报告交接。

日志里的 `testbench_cycles` 包括该测试台权重、逐行输入加载、核心调度和结果握手，仍未包含CPU指令、ICB等待、真实总线装载或系统最后写确认；不能作为比赛吞吐/能耗数据。Nangate代理面积、正式SRAM映射、150 MHz和整机功耗均由其他独立证据决定。
