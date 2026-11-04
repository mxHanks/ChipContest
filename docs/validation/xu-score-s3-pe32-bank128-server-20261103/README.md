# xu：紧凑W32的服务器VCS对照

指定128×16宏的单bank、wide32、compat8定向检查，以及完整SoC开发验收和三配置12层对照均通过。相同32PE调度的总周期保持 **11,376,501**；原32PE权重宏组织与紧凑128宏组织逐层相同。紧凑硬件使用旧8宽调度为 **11,842,200**。本项在功能/周期方面未观察到代价，面积与全SoC能量收益仍待各自实测。

| 配置 | layer0 | layer1–11每层 | 12层合计 |
|---|---:|---:|---:|
| 紧凑128宏 / 32宽 | 948039 | 948042 | 11376501 |
| 原1024宏 / 32宽，同主仓 | 948039 | 948042 | 11376501 |
| 紧凑128宏 / 旧8宽 | 986850 | 986850 | 11842200 |

`per-layer-comparison.csv`保存12行比较，`per-layer-performance.csv`保存三配置共36行phase、访存和工作量。本次没有导出实际Y逐值字节；实际冻结TB对每个输出上下32位逐字比较整数golden，并等待最终响应退休后才接受ACK。三个12层运行各检查304128个输出、608256个写word。离线另外从固定向量独立重算304128个整数golden，不能替代官方浮点600样本评测。

## 代码和Chisel变更

主仓固定`f75880d4f06ccb7f1c16115bee501f53d9a2abb7`，E203子仓固定`52cfbea1f79f10e44f7d1696f54015797f886b96`。相对原32PE候选，生产Chisel改动为：

- `src/main/scala/GenerateRTL.scala`：新增紧凑128宏的生成入口，原32PE入口保留。
- `src/main/scala/linear/XuParallelCore.scala`：权重bank增加独立128深度实现选择；32个bank各4片128×16，注册地址返回选择保持原1周期延迟。默认原组织保留。
- 新增`src/main/scala/memory/Sram128x16.scala`：指定128×16单读写口封装。

对应新增定向测试覆盖全部512个逻辑地址、127/128等深度边界、交错读写、未初始化Q、one-hot使能、延迟及wide/compat结果退休。W逻辑和物理容量均32KiB，原32PE方案物理64KiB；此容量比较不代替综合面积。固定SoC的320个1024×16宏不改，权重使用128个128×16宏，合计448宏是结构预期，实际PPA须另审报告。

## 实际工具及验收范围

服务器使用VCS `Q-2020.03-SP2-6_Full64`和SiFive GCC10.2。所有固件采用`-O2 / both-unroll-no-masks`。同主仓原32和紧凑32的wide固件image相同；紧凑硬件两调度使用同一个simulator，原32使用独立simulator。12层比较保存源码、工具、固件、向量及日志身份。

完整顺序为：generated/designated的单bank、wide、compat共六项强制定向VCS路径，随后host69（skip3）、numeric42、vectors、doctor、legacy5、synthetic1/2、wide real12，再原32wide与紧凑旧auto两项完整12层控制。skip仅为可选辅助环境项；指定128模型路径不能跳过。

官方128模型为`/storage1/admin_public_dir/SRAM_Lib_2025/RAMSP128X16/verilog/RAMSP128X16.v`，89548字节，SHA256 `f9d6d881746681dacd4f3851467561e441ee7190776ab566b1f0a729aa3ddb4d`。模型正文未放入仓库。六项定向日志校验generated和designated分别编译，designated只加入官方模型及adapter，不允许同名behavioral shadow。单bank实际检查512逻辑字、520写、524读、4次未初始化读取、唯一选片和1周期延迟；wide/compat各检查512个lane结果与完整接受/退休计数。

**完整SoC开发周期使用生成的memory模型；指定工艺宏的六项定向测试不能解释成mapped全SoC仿真。** 本归档不证明综合前后一致性、完整150MHz、SRAM时序资格、面积或全SoC单任务能量，也不宣布最终保留。

## 原件、哈希和复现

`original-export-manifest.json`绑定export46全部167个payload；本归档选择147个验收原件及3个外层部署原件。传输tar为117416字节，SHA256 `d9c4470ef190ef40ebce4a5d21dfd5fd37e6f83ca0b4aa8f15735cd824cb5e79`。逐份原件字节和SHA在`selected-manifest.json`，未重排或清理日志正文。

`deployment/source-files.json`记录2637个tracked blob的字节、mode和symlink目标；子仓gitlink另由`full-git-objects.json`和固定child核对。准备阶段与独立复查均实际读取固定提交的不可变Git对象。`frozen-git-sources.tar.xz`包含测量和复现相关源文件；其准确集合在`git-source-audit.json`，没有声称所有2637个文件正文均放在此tar。

离线重放（无需EDA）：

```sh
python3 check-evidence.py --out /absolute/new-bank128-verification.json
```

另对全部2637个原始Git blob重新核验，主仓须含指定main和child对象：

```sh
python3 check-evidence.py \
  --git-root /home/mxhanks/Projects/ChipContest-xu-pe32-bank128 \
  --out /absolute/new-bank128-git-verification.json
```

`verification.json`是本次实际带`--git-root`的复核结果，包括声明日志SHA、测量源SHA、固定golden、五次完整任务运行的计数、六项实际宏定向路径、三配置逐层比较，以及四项实际日志语义破坏的拒绝结果。

服务器复现入口为`deployment/launch.py`，完整命令在`deployment/README.md`；需要原32PE的干净checkout作为增量bundle先决对象、指定官方128模型、同一SiFive前缀及全新source/out。完整原始部署包保存在候选工作树`build/xu-pe32-bank128-server-deploy-20261103-02.tar.gz`，480601字节，SHA256 `dcaf81fc89bd9845905d1d5c706ef81962b85a8783a9b42cf345bbb55eee3a60`。不能使用`--prepare-only`冒充VCS执行。
