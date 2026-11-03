# xu S3 独立64PE本地筛选

状态为 `LOCAL_SCREEN_PASS_NOT_QUALIFIED`。实际测量主提交 `286b95a4e0b05b78f39ef4d648d1f922e684d7fc`，子提交 `7aae96776e116d5e95d6ebb49d29a5fccce04ab9`，独立分支 `codex/xu-s3-pe64`；本交付只追加证据、严格重放器和服务器启动器，没有修改已测电路或固件。源自32PE主 `94ce6f0` / 子 `fc3977d`。

同一真实 `kwt-silence-v1` layer00、GCC14.2.0 / Verilator5.032，得到五项实测：

| 物理PE / 调度 | 总周期 | MAC beats | 实际 enabled-lane MAC | POP退休 |
| --- | ---: | ---: | ---: | ---: |
| 64 / 新64wide | 945,952 | 25,344 | 1,622,016 | 396 |
| 同64 / 原32wide | 957,040 | 50,688 | 1,622,016 | 792 |
| 同64 / 原8auto | 1,013,171 | 202,752 | 1,622,016 | 3,168 |
| 独立物理32 / 原32wide | 957,040 | 50,688 | 1,622,016 | 792 |
| 独立物理8 / 原8auto | 1,013,171 | 202,752 | 1,622,016 | 3,168 |

64wide 相对同物理64上的32schedule只减少 **11,088 周期（1.1585722644821532%）**，相对8auto减少 **67,219（6.6345167794972415%）**。三种64调度使用同一个实际仿真binary；物理32、8各使用不同binary。32schedule在64/32上的全部TASK/PERF完全相同，8schedule在64/8上的全部TASK/PERF完全相同。五项向量、工具、源文件、runner/contract、固件源相同，只有明确记录的物理variant和固件schedule不同。所有模式均实际计算1,622,016个有效lane MAC，完整检查25,344个signed48结果及50,688次Y写回，包含本任务W/bias上传。

这里只测真实layer00，开发HF4ns/LF66ns和旧首shared读接受窗口。未做正式任务前物理清空/首REQUEST窗口、服务器VCS完整12层、映射一致性、完整150MHz STA、实际面积或全SoC能耗；`retained=false`，不能将旧8/32PE面积、能量与本周期拼接评分。

补充实际证据：Chisel定向1项PASS（穷举W映射、有符号结果、8/32/64模式和背压）；最终host68项PASS（先前host67原文亦保留）；numeric42项PASS。新64wrapper的Icarus direct三模式分别两行/8、16、64组，分别15、27、99次真实计算，接受=退休分别11031、11131、11731。每项记录实际64个MacPE的enable求和，并覆盖FIFO满、结果稳定、POP响应退休、立即再启动、窗口边界、写阻塞及模式互斥。另追加边界测试1项实际Icarus PASS：单instance逐模式检查42次未对齐/排他上边界读，保持旧未知读0且不移动FIFO head；三个错误mode读显式报错，各自正确POP只在退休后推进。该独立补测不改已冻结生产源码；追加后stock host实际68项全部PASS（57.328s），服务器启动器同样要求68项完成。**实际物理64 wrapper上的原assembly legacy5全部PASS**，每个真实make命令都有 `XU_ACCEL_PE64=1`；host mock打印不作为该证据。

初始负例原文保留：`raw/direct-01/` 和 `direct-01.log` 记录初版缺少模块和预处理语法错误，生成SV和修正TB后direct02三模式PASS；`host-01.log` 是新增64schedule后两条旧测试期望列表缺项，修正测试后host02 PASS。`wide64-real1-01` 是提交前相同RTL的初筛，正式五项比较采用提交后 `wide64-real1-02`，没有用前次结果冒充提交后测量。

生产Chisel改动仅：

- `src/main/scala/GenerateRTL.scala`：64生成入口改用独立64调度器。
- 新增 `src/main/scala/linear/XuParallel64Core.scala`：单套64lane阵列的8/32/64显式分组、模式锁存、两槽64×48结果FIFO及POP退休所有权。复用原参数化compute/bias/weight bank基础。

新增 `src/test/scala/linear/XuParallel64AutoGroupCoreTest.scala` 是测试。原32 `XuParallelCore.scala`、原32四个SV和wrapper、原13个SV均未改变。新增四个64SV及手写 `xu_pe64_icb_slave.v`；固定perips仅在原插槽加入可选 `XU_ACCEL_PE64`，默认8和32路径保持。没有改E203、互连或共享512KiB SRAM。

逻辑W仍32KiB，64bank×256×16；每bank使用指定1024×16宏，两个高地址位接0。W物理128KiB、padding96KiB；全SoC预期384宏（固定320+W64），这是源结构，必须再以真实映射确认。数值仍16位X/W、40位bias、48位结果，任务维度及固定向量不变。

`raw/manifest.json` 逐个冻结177份payload大小/SHA256，原始日志保持原文；`raw/source-final.json` 冻结2,522个Git条目（2,521个文件/链接和1个gitlink）。重放器重新核对Git commit/blob/mode、所有字节及符号链接目标、完整TASK/PERF/AUTO/PE、日志、ELF/image、向量、同binary、实际legacy5和原32源保持。重放产物为 `local-comparison.json`。`audit-rejection.json` 保存实际五项拒绝：原文byte篡改，以及重新签署SHA后的周期、direct实际lane工作、legacy物理define、边界mode伪造；均被语义检查拒绝。

```bash
python3 docs/validation/xu-score-s3-pe64-local-20261103/audit_local.py \
  --root "$PWD" --raw "$PWD/docs/validation/xu-score-s3-pe64-local-20261103/raw" \
  --out /absolute/new/xu-pe64-local-replay.json
python3 tools/scripts/e203_soc.py --mode real --tasks 1 --sim verilator \
  --accel-variant pe64 --firmware-schedule bias-hw-pe64-autogroup-window \
  --firmware-opt=-O2 --firmware-experiment both-unroll-no-masks --out /absolute/new/xu-pe64-real1
python3 tools/scripts/e203_soc.py --mode baseline --sim iverilog --accel-variant pe64 \
  --firmware-schedule baseline --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks --out /absolute/new/xu-pe64-legacy5
scala-cli test . --server=false --jvm system --test-only linear.XuParallel64AutoGroupCoreTest
```

服务器交付包单独生成，内含已提交的 `tools/scripts/xu_s3_pe64_server.py` 作为 `launch.py`、增量Git bundles、全树mode/byte身份和包SHA。启动器强制SiFive GCC10.2/VCS2020、actual direct64wide/32compat/8compat，stock host/numeric/vector/doctor、physical64 legacy5、synthetic1/2和wide64 real12，然后运行同64物理32/8schedule及独立物理32wide/8auto四项real12对照。仅能在新目录执行；前后全树冻结，所有实验分别记录工具/向量/源身份、逐层PERF、实际lane工作和原始日志。该启动器尚未在服务器执行；候选全范围能耗另需正式活动collector及同配置映射，不能使用wrapper功耗。

重新生成服务器部署包（必须已提交、主/子树均clean，输出目录全新）：

```bash
python3 tools/scripts/xu_prepare_pe64_deployment.py --root "$PWD" --out "$PWD/build/xu-pe64-new-server-package"
```

生成的 `.receipt.json` 给出最终主/子提交、包字节及SHA256；包内 `launch.py --prepare-only` 可在新路径验证真实Git clone/checkout及全部源mode/byte身份，该检查不执行EDA。服务器可上传包及 `tools/scripts/xu_s3_pe64_bootstrap.py`，以receipt中的 `--sha256` 和 `--bytes` 启动；bootstrap只接受七个固定普通文件成员，拒绝额外路径、链接和不匹配身份。
