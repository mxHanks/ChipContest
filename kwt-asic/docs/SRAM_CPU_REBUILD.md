# 从新工作区重建开发CPU验证链

本入口修复旧CPU脚本固定读取本机历史baseline的问题。旧`run_sram_adapter_soc.py`及其已接受证据保持原字节；新增`run_sram_adapter_soc_v2.py`显式选择当前baseline和平台。当前验证结果以PROGRESS为准，以下命令不是已完成运行的声明。

## 外部依赖与平台准备

源码包不含HDL工具、RISC-V工具链、平台、数据集或原始run目录。先按`env/README.md`准备HDL环境，再准备以下开发依赖；官方平台另行验收。

先运行`make test`检查源码和主机工具。包内harness保存历史任务记录，缺少原始run时`harness validate`会如实报告缺证据；这不应通过删除检查或改写旧PASS修复。按下列命令生成本机证据后，再登记新的运行；历史任务记录不等于新机器已接受功能结果。

- 开放E203 Fork：`mxHanks/e203_hbirdv2`，提交`35e7c960dc151d8ade9deffcb30cdc13c840d541`。只在自有副本应用项目开发接线，不修改队友原checkout。
- 已准备平台须匹配`configs/e203-development-platform.json`的136个相对路径、SHA与长度。位置可变，源版本及接线不能靠文件数量判断；该清单不是官方平台认证。
- 本机已用工具链为xPack RISC-V GCC `15.2.0-1`。历史归档433494794字节，SHA256 `aaaa8060c914851a3e5ee1ba82cc3d6f80972f90638a05c6e823a37557a33758`。取得合法工具包后核来源与SHA，放入项目`.tools/teammate/`，或向v2显式传编译器及objcopy路径。源码包没有自动安装此工具链，不改全局环境。

若从未融合的固定Fork副本开始，旧准备脚本会将收据写到固定子目录。**仅在新的工作区**先创建目录，再应用一次：

```bash
mkdir -p artifacts/integration/20261017-teammate
python3 scripts/integration/prepare_e203_fusion.py --root <自有平台副本路径>
```

已融合副本不重复执行；保留原收据，不用这条命令覆盖已验收目录。旧准备脚本没有事务回滚，若失败须检查副本实际内容，不能直接再次执行。平台精确清单检查由新baseline reader完成，失败不自动修补源文件。

## 顺序重建

进入新工作区，激活环境。先按原语和系统入口文档生成本机的新报告：

```bash
source env/activate.sh
python3 -B scripts/verify/run_official_sram_contract.py --development-qualification good
python3 -B scripts/verify/run_sram_adapter_system.py --development-adapter \
  --primitive-report <上一步实际输出的result.json>
```

再用已准备的同一平台副本，真实生成行为后端12层基线。这个命令包含CPU仿真，不是复制旧结果：

```bash
python3 -B scripts/verify/run_sram_soc.py \
  --platform <自有平台副本路径> --tasks 12 --backend behavioral \
  --vectors-dir sim/vectors/kwt-silence-v1
```

把新生成的完整报告显式传给v2。可先只读预检：

```bash
python3 -B scripts/verify/run_sram_adapter_soc_v2.py --development-adapter \
  --system-report <本机完整core及ICB报告> \
  --baseline-report <本机新行为CPU12报告> \
  --platform <相同平台副本路径> --preflight-only
```

预检的`status=PASS, acceptance=PREFLIGHT_ONLY`只接受输入和前置证据；`development_cpu_functional=NOT_RUN`且没有HDL命令。它不生成或继承CPU功能PASS。去掉`--preflight-only`才编译并运行新的BACKEND3 CPU12任务。

默认编译器在项目xPack目录；其他受控位置可追加`--compiler <gcc绝对路径> --objcopy <objcopy绝对路径>`。省略objcopy时，从编译器文件名末尾`gcc`推导同目录`objcopy`。新固件BIN/HEX必须匹配所选已接受基线，ELF保留独立SHA；编译器变化导致程序负载不同会拒绝，不偷偷改基线。

生成行为基线的旧`run_sram_soc.py`没有`--compiler`选项：它优先使用项目xPack；该目录未安装时才从PATH选择`riscv64-unknown-elf-gcc`或`riscv-none-elf-gcc`。在新工作区使用外部工具链时，先把其bin加入当前shell的PATH，再生成基线，向v2传入基线实际记录的同一编译器与objcopy。不删除或替换已有工具以强行改变选择；两阶段的工具与实际负载均须核对。

每条命令使用唯一输出目录，不改JSON路径搬迁旧PASS。新工作区必须实际生成自己的原语、系统、行为CPU及Adapter CPU证据；缺失依赖如实BLOCKED。首次完整执行预算包含两次CPU12层及核心/ICB前置，本机历史每次CPU约11分钟；这是运行预算，不是截止承诺。

## 验收范围

基线reader重新核当前平台精确源集、canonical身份、四条原生命令、原始日志、3份固件、二进制、48份实际向量、导出来源及Golden。v2随后继续原先的Adapter原语/核心ICB前置、固件负载、loop/latch完整告警比较、逐层写回及恢复门槛；不重绑旧模块的全局路径，也不更改计算RTL或Golden。

平台已有两条UNOPTFLAT和15条LATCH仍分类保留。两态CPU、禁用Fork内SVA、TB预装载和中断epoch不计开发窗口的边界不变。入口记录两份workload SHA及是否相同，周期相同不能自动证明同workload对照；即使同workload，也只代表当前开发模型的观测，不是正式宏功耗/时序或官方完整装载性能。

真实官方模型到位后，前置链使用真实manifest，去掉开发选项重新执行；官方引脚、PVT、总面积、功耗及正式平台仍须单独验收。开发夹具不能进入正式综合源集。


## 本次实际资格化（2026-10-18）

6个真实CLI门槛和324项主机检查、静态入口完成；缺包/缺系统前置/缺基线返回BLOCKED，坏基线与错误平台返回FAIL，全部0条HDL/工具命令。有效预检保持CPU NOT_RUN。记录在`artifacts/diagnostics/20261018-portable-cpu/gates-v1/result.json`。

在同一机器把核过SHA的平台源复制到独立`relocated-platform`目录后，实际生成新的行为CPU12基线`085210…sram-soc-8f007ab7/result.json`，CPU原生exit0/665.177秒。v2显式读取该新报告及平台路径，重新编译并完成`090411…adapter-soc-v2-6c7a24d6/result.json`，CPU原生exit0/652.876秒，内7条命令全exit0。不是搬迁旧JSON或将旧PASS改名。

两个后端各12任务/304128结果、275712装载提交、608256输出写响应、12 ACK及soft abort/pending响应外部reset恢复均通过；各自开发窗口21261300周期。48份X/W/Bias/Y逐文件相同，workload SHA同为`75f3d426fe696a7ced3c16e2a6c92e9e75ce962a701deb8a647988b2bd864986`。这只证明当前开发模型的功能与周期观测，不推断真实官方宏延迟、面积或能耗。

此次实证是同一OS/机器、复用已核工具，在不同平台目录以新的原生证据重建；并未声称另一台机器或另一OS完成CPU回归。源码交接包的异目录主机恢复另存收据，其范围不扩大为完整EDA环境镜像。旧v1及1830条来源记录保留，官方宏/正式平台/指定工艺验收仍未通过。
