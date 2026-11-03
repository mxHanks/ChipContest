# xu S3 32PE 本地独立筛选

状态：`LOCAL_SCREEN_PASS_NOT_QUALIFIED`。执行代码主提交 `d46486c9820e909ab9469a5fa1f10eee022988c3`，E203 子提交 `fc3977d0a6d5f85fbfd871fd9439c01c9acab5f5`，来自 S2c 主 `d276b55` / 子 `49a9436` 的独立分支 `codex/xu-s3-pe32`。本次追加交付提交只冻结日志、严格重放器和说明，不更改已测实现。

## 实际结果及范围

同一真实 `kwt-silence-v1` layer00、同 GCC14.2.0 / Verilator5.032：

| 物理架构 / 调度 | 任务周期 | MAC beats | 实际 enabled-lane MAC | POP 退休 |
| --- | ---: | ---: | ---: | ---: |
| 默认8PE / 原 auto | 1,013,171 | 202,752 | 1,622,016（8×beats） | 3,168 |
| 新32PE / 原 auto | 1,013,171 | 202,752 | 1,622,016（逐拍32个真实 PE enable 求和） | 3,168 |
| 新32PE / wide auto | 957,040 | 50,688 | 1,622,016（逐拍32个真实 PE enable 求和） | 792 |

wide 相对同物理32PE旧调度减少 **56,131 周期，5.5401309354491985%**；这里没有4倍整体提速。两个32PE调度使用同一仿真可执行文件 SHA256 `f06162cf4dd98ed1d03f80288b677c0afe981fb6273c0eebf041de2457b6bbb0`，默认8PE使用不同物理架构 binary。三个实验的向量、源文件、工具、runner、contract及固件源身份相同；固件调度选择及物理编译 define 作为独立变量明确记录。两个旧 auto 对照的全部 PERF 计数相同。每项25344个signed48输出、50688次Y写回、23232次共享源读均相同，均包含本任务W/bias上传；所有实际PE工作可见，没有计算24路后丢弃结果却只统计8路的额外MAC。

这是原开发时钟HF4ns/LF66ns、从首共享读接受至最后Y响应退休的单层筛选。没有开启正式任务前物理清空/首REQUEST窗口；不是完整150MHz STA、服务器GCC10.2/VCS完整12层、实际面积、映射一致性或全SoC能耗证据。未保留为最终参赛配置，不能将旧8PE面积/能量搭配这些周期评分。

实际补充检查：Chisel定向1项PASS；host62项PASS，其中包括实际Icarus新wrapper宽/兼容两个direct；numeric42项PASS；**新32PE wrapper上的真实SoC原始assembly legacy5** PASS。host中mock测试打印的PASS不作为legacy执行证据；实际baseline每项make命令均携带 `XU_ACCEL_PE32=1`，见 `raw/screen/pe32-legacy5/`。新wrapper的wide direct两行/16组/512结果、27次计算、11124接受=退休；compat direct两行/64组/512结果、99次计算、11737接受=退休。direct也记录实际lane活动，并覆盖有符号边界、FIFO满、POP退休、背压、旧结果保持、写阻塞及mode边界。

原始失败原文保留：`raw/direct-01/wide/simulation.log` 是初版宽TB仍使用旧寄存器地址导致的定向检查失败，修正测试地址后direct02和final host03 PASS；`raw/host-01/host.log` 是新增schedule后两条旧期望列表未更新的失败。后续修正及所有原文各自保存，未用PASS覆盖FAIL。没有未披露的生产RTL修补。

## 改了哪些 Chisel

- `src/main/scala/GenerateRTL.scala`：新增32/64几何的显式生成入口；本实验只集成、生成和验收32PE，64PE不因入口存在而成为已验收候选。
- 新增 `src/main/scala/linear/XuParallelCore.scala`：固定64×256权重矩阵几何；32个单独W bank、32个MacPE、单套X及256×40bias缓存；带mask的旧8lane兼容；32lane输出及两槽FIFO/自动8group调度。旧手工结果子组在capture时锁存；POP只在响应退休后释放槽。
- 新增测试 `src/test/scala/linear/XuParallelAutoGroupCoreTest.scala`，不属于生产电路。

新RTL只有一套W/compute阵列。每W bank逻辑512×16、指定1024×16接口一只，32bank总32KiB逻辑/64KiB物理，A9恒0。全SoC预期352个1024宏（固定320+新增W32），这只是源结构，尚无实际综合面积。原生成SV、原wrapper的15份旧文件逐字节与子49a9436一致，严格重放器会重新核验。新手写 `xu_pe32_icb_slave.v`、固定perips中原实例处的可选define、固件与TB/runner/计数contract配套改动均在上述两个代码提交中；未改CPU、互连或共享SRAM。

## 证据和复现

`raw/manifest.json` 逐个冻结111份原始payload的大小/SHA256；`raw/source-sha256.json` 冻结本候选改动文件。`local-comparison.json` 是严格重放产物。重放器验证原文哈希、完整TASK/PERF/AUTO/PE、source/runner/contract、ELF/image、日志哈希、同物理binary、实际legacy5以及旧文件字节。独立源结构review及穷举地址映射保存在raw，标明静态review范围。

在本交付分支执行严格重放：

```bash
python3 docs/validation/xu-score-s3-pe32-local-20261103/audit_local.py \
  --root "$PWD" --raw "$PWD/docs/validation/xu-score-s3-pe32-local-20261103/raw" \
  --out /absolute/new/xu-pe32-local-replay.json
```

重新运行本地真实layer00时，每个out用全新目录。相同32PE控制保持variant=pe32，仅改schedule为 `bias-hw-autogroup-window`；默认8PE控制再改variant=pe8：

```bash
python3 tools/scripts/e203_soc.py --mode real --tasks 1 --sim verilator \
  --accel-variant pe32 --firmware-schedule bias-hw-pe32-autogroup-window \
  --firmware-opt=-O2 --firmware-experiment both-unroll-no-masks --out /absolute/new/xu-pe32-wide-real1
python3 tools/scripts/e203_soc.py --mode baseline --sim iverilog --accel-variant pe32 \
  --firmware-schedule bias-hw-pe32-autogroup-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks --out /absolute/new/xu-pe32-legacy5
scala-cli test . --server=false --jvm system --test-only linear.XuParallelAutoGroupCoreTest
python3 -m unittest discover -s tests/e203 -p 'test_*.py'
python3 -m unittest discover -s tests/numeric -v
```

服务器增量部署包单独准备，必须先验证源身份并以实际VCS强制宽/兼容direct、完整8步acceptance及同32PE/默认8PE的两项full12 control。其执行结果、同库面积/时序/全范围能耗待后续独立归档；本说明没有宣称服务器验收已通过。
