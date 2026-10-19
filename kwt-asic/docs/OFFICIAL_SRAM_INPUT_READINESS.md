# 官方SRAM材料的分阶段预检

这是**文件准入工具**，不运行HDL、不认定官方来源真实性、不证明模块/引脚/功能、PVT或PPA正确，不设置旧后端的READY。当前官方文件仍未收到，实际预检应为BLOCKED。

本轮审计发现旧`configs/sram-backends.json`/`sram_sources.py`的官方分支有四个待接入缺口：纯仿真要求所有PPA材料齐备，综合共用功能源，同一Liberty跨角色被误拒绝，engine/ICB/SoC CLI尚未接通official。旧默认BLOCKED没有变成设计假PASS；给旧配置写READY也不等于真正编译成功。为保留已验收的源身份，本轮新增独立材料清单/预检，不改冻结的旧选择器、计算RTL或回归生产脚本。

## 使用方法

从项目根目录执行：

```bash
source env/activate.sh
python3 -B scripts/verify/official_sram_inputs.py
make -f scripts/official-sram.mk inspect-official-sram SRAM_STAGE=simulation
```

默认读取`configs/official-sram-package.json`。没有材料时退出码2、状态BLOCKED属于预期；错误配置/哈希/路径退出1；所选阶段文件核验完成退出0。每次创建唯一`artifacts/runs/*-official-sram-inputs-*/`，保留完整阶段状态、选中源集、源SHA和清单身份。`--stage all`要求四阶段文件均齐；`--stage simulation`只核仿真输入，不等待面积或功耗材料。独立Make入口用于保护旧Make及已冻结生产证据，未替换现有`make regress`。

## 清单填写

每个文件引用为`{"path": "项目内相对路径", "sha256": "实际文件的64位SHA256"}`。`provenance`另填真实提供方/版本和原始交付说明引用；`logical_adapter_module`必须为当前逻辑Wrapper要求的`kwt_official_sram_adapter`，不是官方宏名字。实际官方引脚保持未知，不能从此模块名推测。

| 阶段 | 必需文件角色 | 仍不由文件预检证明的内容 |
|---|---|---|
| simulation | 交付说明、引脚手册、adapter源、functional源 | Verilog语法/模块/端口、读延迟/Q保持/碰撞、全部数值 |
| synthesis | 上述来源/手册、adapter源、独立synthesis源、setup Liberty | 模型是否适合综合、重复模块、宏保留、实际映射 |
| timing | synthesis材料及hold Liberty | 指定PVT、单位/弧、真实负载、完整150MHz |
| ppa | timing材料及power Liberty、面积表 | 真实宏面积/功耗、活动覆盖及正式统计窗口 |

仿真源与综合源分别输出，不能把一方存在等同另一方正确。同一个条件编译文件可以被互斥用途分别引用；每个实际编译集合中的重复文件拒绝。setup/hold/power允许引用同一份真实Liberty，报告保留角色映射，文件依赖按路径去重；同角色重复路径拒绝，重复模块定义和实际库角选择仍须由后续构建核实。Liberty必须`.lib`，RTL必须`.v/.sv`，面积表为`.json/.csv/.tsv`；扩展名/非空/SHA一致仍不是内容正确性证明。

路径采用受控导入策略：只接受项目内相对普通文件，拒绝`..`、绝对路径、软链接及目录。实际官方文件在许可允许时原样导入`tech/official_sram/`；自研adapter放`src/rtl/`。如果交付限制必须使用外部授权目录，先记录来源并单独评审外部依赖策略，不能用软链接绕过当前检查。工具不复制、改写或自动打包官方材料。源码包仍只收技术README/轻量配置，不能据源码包存在声称工艺文件也已恢复。

## 状态含义和下一步

`FILES_VERIFIED`只表示该阶段需要的文件路径、身份及分类通过；报告始终保留`official_validation=NOT_RUN`、`official_ppa=BLOCKED`。测试中的非HDL/非Liberty小文件只资格化分类/拒绝逻辑，从不进入加速器或成为官方模型。

官方包到位后，依次进行：

1. 人工核定原始来源/许可/SHA及真实手册，填写清单，分阶段预检。
2. 按真实宏编写adapter；以实际编译工具核模块定义、端口、重复定义和宏形状。
3. 为官方模式接通独立原语/bank/core/ICB/SoC入口，使其消费已核准的源计划。当前旧CLI仍只支持behavioral/FF，不能只改旧READY就宣称这一步已完成。
4. 运行[官方接入手册](OFFICIAL_SRAM_INTEGRATION.md)全部受影响功能，再执行指定工艺/全部宏边界的时序、面积、功耗。模型若不同步一拍，先重构等待/metadata而不是只移动valid。

此轮没有接入真实官方宏，也不解除S5。旧开发RTL/SoC/参考ECO证据仍按各自来源保留；新清单不得静默替代它们。


原语/bank层现有独立[BACKEND=3契约入口](OFFICIAL_SRAM_CONTRACT_RUNNER.md)，默认消费simulation材料计划，缺包不启动HDL；显式开发夹具资格化不算官方宏通过。旧核心/ICB/SoC CLI仍保持开发源集，真实模型及后续接线尚待完成。


后续新增[Adapter核心/ICB功能入口](SRAM_ADAPTER_SYSTEM.md)，消费simulation源计划并重核同输入原语报告后才运行BACKEND3；开发夹具的14核心任务和四态ICB已资格化。旧CLI保持原字节；真实宏/CPU/正式SoC和指定PPA仍需实际文件及新验证，不能把文件核验或开发PASS当作官方通过。
