# 服务器到位后的 C 角色接手

接续 `feature/e203-c-integration`，本轮前期准备在 **feature/e203-server-prep**。计算 RTL、MMIO ABI 与 E203 子模块提交保持原样。先复现开发平台，再接官方平台；源码和历史证据的详细范围见 [C 集成说明](e203-integration.md)。

## 一条命令重新验收

从仓库任意路径启动脚本均可；脚本自动定位仓库。需要 Python3、Git、Make、Icarus/vvp、支持 `--binary --timing` 的 Verilator、g++ 和 RV32 GCC/binutils。每次 `--out` 必须是尚不存在的目录。

```bash
git clone --recurse-submodules --branch feature/e203-server-prep https://github.com/mxHanks/ChipContest.git
cd ChipContest
python3 tools/scripts/server_accept.py
```

顺序执行主机检查、真实12层参考向量独立核算、实际固件构建/子模块预检、原SoC五项测试、合成单层和真实12层仿真。任何一步失败即停止，`acceptance.json` 记录失败步骤、命令和日志位置；退出码非零。总结果不能拿旧机器的 PASS 代替。

扩展验收增加真实单层 Icarus 四态仿真和 README 的全部 Chisel 测试，耗时明显更长：

```bash
python3 tools/scripts/server_accept.py --full
# Scala/Chisel/firtool 依赖已事先缓存且服务器不联网时：
python3 tools/scripts/server_accept.py --full --offline
```

`--offline` 只控制 Scala 缓存，不会安装任何工具或补齐依赖。保持 project.scala 中的 Scala/Chisel 版本。无预缓存时先在可联网环境按 quickstart 安装并完成一次 Chisel 回归。

工具链名称不同可传 `--cross-prefix /绝对路径/bin/riscv-none-elf-`。doctor 现在会核对子模块确实是独立仓库、HEAD 等于主仓库 gitlink，并实际构建固件、核对结束地址；只发现一个叫 gcc 的程序不算通过。

## A 交付向量后先核算

本分支的 GitHub Actions 会自动运行主机检查和真实12层整数核算；使用固定版本的 checkout、只读仓库权限及 Python 标准库，不需要仿真器、交叉编译器或额外凭据。它覆盖交接工具与夹具，完整硬件回归仍由上述服务器验收入口执行。

```bash
# 内置夹具，只有 Git/Python 即可核算：
python3 tools/scripts/e203_soc.py --mode check-vectors --tasks 12
# 新交付的同格式数据：
python3 tools/scripts/e203_soc.py --mode check-vectors --tasks 12 --vectors /数据目录
python3 tools/scripts/e203_soc.py --mode vectors --tasks 12 --vectors /数据目录
```

独立核算使用 Python 无溢出整数逐项计算 XW+b，检查全部304128结果并记录各文件SHA256；不生成供 CPU 使用的结果。格式、符号位或参考值错误会定位到文件或层/行/列。它证明整数夹具自洽；浮点 NRMSE、量化参数来源和官方样本精度需由模型评估另外验收。

## Git 原生离线交接包

交接包只包含已提交的两个公开团队仓库及对应提交，不包含本地工作区、凭据或工艺库。在完成提交后，仓库根目录执行以下 Linux 命令。`out` 使用绝对路径且尚不存在：

```bash
(
set -eu
out="$PWD/build/handoff-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$PWD/build"
mkdir "$out"
git bundle create "$out/ChipContest.bundle" HEAD
git -C third-party/e203_hbirdv2 bundle create "$out/e203_hbirdv2.bundle" HEAD
git rev-parse HEAD > "$out/main.commit"
git -C third-party/e203_hbirdv2 rev-parse HEAD > "$out/e203.commit"
git bundle verify "$out/ChipContest.bundle"
git -C third-party/e203_hbirdv2 bundle verify "$out/e203_hbirdv2.bundle"
(cd "$out" && sha256sum *.bundle *.commit > SHA256SUMS)
)
```

传输该目录后，在新 Linux 目录恢复。所有 clone/fetch 来源均为本地文件，不运行会联网的子模块更新：

```bash
(
set -eu
bundle=/交接包的绝对路径
(cd "$bundle" && sha256sum -c SHA256SUMS)
git clone "$bundle/ChipContest.bundle" ChipContest
git clone "$bundle/e203_hbirdv2.bundle" ChipContest/third-party/e203_hbirdv2
cd ChipContest
test "$(git rev-parse HEAD)" = "$(cat "$bundle/main.commit")"
test "$(git -C third-party/e203_hbirdv2 rev-parse HEAD)" = "$(cat "$bundle/e203.commit")"
git submodule absorbgitdirs
python3 tools/scripts/e203_soc.py --mode doctor
python3 tools/scripts/server_accept.py
)
```

bundle 内只导出 HEAD，因此恢复时可能处于 detached HEAD；需要修改时先 `git switch -c feature/实际任务名`，E203 有修改也需单独建分支。bundle 的 origin 是本地文件，回团队仓库提交前按 README 设置团队 Fork 的 origin。恢复验收本身不需要修改远程地址。

本机另已缓存发布方校验通过的 [xPack RISC-V GCC 15.2.0-1 Linux x64 完整工具链](https://github.com/xpack-dev-tools/riscv-none-elf-gcc-xpack/releases/tag/v15.2.0-1)。交接目录可附该原始发行包及其 SHA256；解压后用 `--cross-prefix` 指定其 bin 前缀。该工具包含自身许可证，不代替服务器上的 Python/Git/Make/g++/仿真器，也不包含 Scala 依赖缓存；其他CPU架构/系统需对应发行包。

## 官方材料收到后必须完成的事项

| 收到的材料/责任方向 | 接手动作 | 通过条件 |
| --- | --- | --- |
| 官方 SoC/SDK、启动/链接文件、地址图和数据装载接口（C） | 先保留开发参考路径，再按官方平台连接系统存储/驱动；核对复位、符号位、端序、结束信号 | CPU 实际装载 X/W/bias、启动硬件并写回全部99×256结果；12次独立参数任务通过 |
| 官方 SRAM 模型、16位×128/1024/4096宏、时序与接口说明（B，C联调） | 用真实宏适配替换行为存储，保留同步读延迟和单端口约束 | 宏仿真与RTL逐位一致；完整SoC写回回归通过 |
| 官方标准单元库、约束、PVT/RC角及工具脚本（B） | 对正式源集综合、时序与面积分析，隔离测试平台行为RAM | 指定工艺下150MHz；增量加速器/接口/内部SRAM面积≤2.25mm²；共享512KB SRAM按赛题口径处理 |
| 官方功耗场景及活动格式（B、C） | 按官方计时窗口导出活动，覆盖参数装载、CPU、互连、存储和完整写回 | 按官方PVT及完整系统范围出功耗报告；不得只报MAC核心 |
| 官方600样本、真实checkpoint/导出脚本与浮点参考（A） | 固定模型/数据/量化版本，逐层比较，保留每样本/层误差；转换为本集成的严格mem格式 | 按官方口径计算最大层NRMSE≤3%；RTL结果与软件整数模型逐位一致 |
| 官方性能计时起止和评分脚本（C） | 替换开发TB预装载路径，计入官方要求的装载、CPU、总线、计算、写回 | 12任务各有完整输入身份、起止周期和最终写响应证据 |

以上外部材料未到齐，不能用 Nangate45、行为SRAM、两态仿真周期或单个静音样本替代正式结论。当前没有向未知官方平台写入数据或猜测宏引脚。

本轮实际验证与离线恢复的证据索引见 [server-prep-20261027](validation/server-prep-20261027/summary.json)。
