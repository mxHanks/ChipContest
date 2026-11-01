# 服务器到位后的 xu 接手

服务器适配使用 `codex/xu-platform-eval`，从主仓 `ddcf6cc5ea9119b3dd162249be8c4521eef45da2` 与 E203 子模块 `e36d34a52e6eef93fd0bdfed1b13009e1056bea3` 起步。计算 RTL、MMIO ABI 与子模块基线保持原样。先复现开发平台，再接官方平台；源码和历史证据的详细范围见 [xu 集成说明](e203-integration.md)。

## 已接入服务器的 VCS 路线

服务器实测环境为 Python 3.6.8、glibc 2.17、主机 GCC 4.8、Git 1.8.3、JRE 8。本轮使用 VCS；主机 GCC 版本不能代替独立 RISC-V GCC/binutils 的检查，JRE 8 也不代表 Scala/Chisel/firtool 链已就绪。主机测试使用 Python 3.6 支持的 subprocess 参数及 Git 1.8 支持的分离式 `--cacheinfo` 参数，保留校验失败、未初始化子模块及 gitlink 不匹配等负例。

2026-11-01 已在该服务器完成 VCS 一键验收：host 19/19、numeric 34/34、独立12层整数核算、原 SoC 5/5、synthetic1 和 real12 均通过。real12 检查 304128 个结果、608256 次写字；篡改参考值与超时两个实际 VCS 负例也通过。完整范围与复现位置见 [本轮验证记录](validation/platform-vcs-20261101/README.md)。原版 `--full`、Chisel、浮点 validation 和正式 SRAM/PPA 不包含在此 PASS 内。

在已恢复的工程中运行：

```bash
python3 tools/scripts/server_accept.py --sim vcs \
  --cross-prefix /实际RV工具链/bin/riscv-none-elf- \
  --out "$PWD/build/acceptance/vcs-$(date -u +%Y%m%dT%H%M%SZ)"
```

该路线顺序执行主机检查、标准库数值模型回归、真实12层向量核算、doctor、VCS 原SoC五项测试、合成单层及真实12层矩阵回归。doctor 只预检实际使用的 Git、RV GCC/objcopy/objdump，并实际构建固件、检查子模块；baseline 和矩阵阶段仍须找到并成功运行 VCS。缺工具或失败步骤均退出非零。VCS 编译、许可证和服务器兼容性以实际命令及日志为准。

`--sim vcs` 与 `--full` 互斥；其 `acceptance.json` 使用 `profile: vcs-platform`，并以 `not_run: [icarus1, chisel]` 记录范围。原默认与 `--full` 路线保留，待相应工具链可用后另行运行。以下历史记录和旧机器的 PASS 不能替代本服务器的新结果。

## 原默认路线与完整扩展验收

从仓库任意路径启动脚本均可；脚本自动定位仓库。需要 Python3、Git、Make、Icarus/vvp、支持 `--binary --timing` 的 Verilator、g++ 和 RV32 GCC/binutils。每次 `--out` 必须是尚不存在的目录。

```bash
git clone --recurse-submodules --branch feature/e203-xu-server-prep https://github.com/mxHanks/ChipContest.git
cd ChipContest
python3 tools/scripts/server_accept.py
```

顺序执行主机检查、标准库数值模型回归、真实12层参考向量独立核算、实际固件构建/子模块预检、原SoC五项测试、合成单层和真实12层仿真。任何一步失败即停止，`acceptance.json` 记录失败步骤、命令和日志位置；退出码非零。总结果不能拿旧机器的 PASS 代替。

扩展验收增加真实单层 Icarus 四态仿真和 README 的全部 Chisel 测试，耗时明显更长：

```bash
python3 tools/scripts/server_accept.py --full
# Scala/Chisel/firtool 依赖已事先缓存且服务器不联网时：
python3 tools/scripts/server_accept.py --full --offline
```

`--offline` 只控制 Scala 缓存，不会安装任何工具或补齐依赖。保持 project.scala 中的 Scala/Chisel 版本。无预缓存时先在可联网环境按 quickstart 安装并完成一次 Chisel 回归。

工具链名称不同可传 `--cross-prefix /绝对路径/bin/riscv-none-elf-`。doctor 现在会核对子模块确实是独立仓库、HEAD 等于主仓库 gitlink，并实际构建固件、核对结束地址；只发现一个叫 gcc 的程序不算通过。

本轮旧系统使用 SiFive GCC-Metal 10.2.0-2020.12.8 的 CentOS6 发行版。固件命令显式指定 `rv32imac_zicsr2p0_zifencei2p0`，使旧汇编器与当前 GCC 都使用相同 CSR/fence 扩展版本；不依赖旧工具链缺失的默认扩展版本。独立目录中的工具子集仅支持本工程 freestanding C/汇编，保留原始发行包来源、SHA256 和逐文件哈希，不声称完整 Newlib/SDK 就绪。

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

以下固定基线包只包含已提交的两个公开团队仓库及对应提交，不包含本地工作区、凭据或工艺库。出包前必须核对两个明确 ref，不能从当前功能分支的 `HEAD` 推测基线。平台适配提交另行交付，不能混入该冻结包。`out` 使用绝对路径且尚不存在：

```bash
(
set -eu
main_sha=ddcf6cc5ea9119b3dd162249be8c4521eef45da2
e203_sha=e36d34a52e6eef93fd0bdfed1b13009e1056bea3
main_ref=refs/remotes/origin/feature/e203-xu-server-prep
e203_ref=refs/remotes/origin/feature/e203-xu-integration
test "$(git rev-parse "${main_ref}^{commit}")" = "$main_sha"
test "$(cd third-party/e203_hbirdv2 && git rev-parse "${e203_ref}^{commit}")" = "$e203_sha"
test "$(git ls-tree "$main_sha" -- third-party/e203_hbirdv2 | awk '{print $3}')" = "$e203_sha"
out="$PWD/build/xu-handoff-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$PWD/build"
mkdir "$out"
git bundle create "$out/ChipContest.bundle" "$main_ref"
(cd third-party/e203_hbirdv2 && git bundle create "$out/e203_hbirdv2.bundle" "$e203_ref")
printf '%s\n' "$main_sha" > "$out/main.commit"
printf '%s\n' "$e203_sha" > "$out/e203.commit"
# 空仓验证证明两个 bundle 不依赖本机已有对象。
verify=$(mktemp -d)
trap 'rm -rf "$verify"' EXIT
(cd "$verify" && git init -q && git bundle verify "$out/ChipContest.bundle" && git bundle verify "$out/e203_hbirdv2.bundle")
(cd "$out" && sha256sum *.bundle *.commit > SHA256SUMS)
)
```

传输该目录后，在新 Linux 目录恢复。以下命令兼容 Git 1.8.3，不使用 `git -C`、`switch` 或 `absorbgitdirs`。所有 fetch 来源均为本地文件；校验成功前不创建目标，不运行会联网的子模块更新或自动验收：

```bash
(
set -eu
bundle=/交接包的绝对路径
(cd "$bundle" && sha256sum -c SHA256SUMS)
main_sha=ddcf6cc5ea9119b3dd162249be8c4521eef45da2
e203_sha=e36d34a52e6eef93fd0bdfed1b13009e1056bea3
test "$(cat "$bundle/main.commit")" = "$main_sha"
test "$(cat "$bundle/e203.commit")" = "$e203_sha"
target="$PWD/ChipContest"
test ! -e "$target" && test ! -L "$target"
mkdir "$target"
(
cd "$target"
git init -q
git bundle verify "$bundle/ChipContest.bundle"
git fetch --no-tags "$bundle/ChipContest.bundle" refs/remotes/origin/feature/e203-xu-server-prep:refs/heads/handoff-main
git checkout --detach "$main_sha"
test "$(git rev-parse HEAD)" = "$main_sha"
test "$(git ls-tree HEAD -- third-party/e203_hbirdv2 | awk '{print $3}')" = "$e203_sha"
(
cd third-party/e203_hbirdv2
git init -q
git bundle verify "$bundle/e203_hbirdv2.bundle"
git fetch --no-tags "$bundle/e203_hbirdv2.bundle" refs/remotes/origin/feature/e203-xu-integration:refs/heads/handoff-e203
git checkout --detach "$e203_sha"
test "$(git rev-parse HEAD)" = "$e203_sha"
)
git submodule init
git checkout -b codex/xu-platform-eval
test -z "$(git status --porcelain)"
)
)
```

显式 fetch 不依赖 bundle 的默认 HEAD；恢复后主仓在 `codex/xu-platform-eval`，E203 保持 detached HEAD 和独立 `.git`。需要修改子模块时先在其中使用 `git checkout -b codex/xu-实际任务名`。恢复命令不创建 origin；回团队仓库提交前按 README 设置团队 Fork 的 origin。恢复只证明源代码身份，之后再按上面的 VCS 或完整扩展命令验收。

本机另已缓存发布方校验通过的 [xPack RISC-V GCC 15.2.0-1 Linux x64 完整工具链](https://github.com/xpack-dev-tools/riscv-none-elf-gcc-xpack/releases/tag/v15.2.0-1)。交接目录可附该原始发行包及其 SHA256；解压后用 `--cross-prefix` 指定其 bin 前缀。该工具包含自身许可证，不代替服务器上的 Python/Git/Make/仿真器，也不包含 Scala 依赖缓存。服务器 glibc 2.17 下须实际运行所选工具链并完成 RV32 固件构建，不能仅凭 Linux x64 标签认定发行包可用。

## 官方材料收到后必须完成的事项

| 收到的材料/责任方向 | 接手动作 | 通过条件 |
| --- | --- | --- |
| 官方 SoC/SDK、启动/链接文件、地址图和数据装载接口（xu） | 先保留开发参考路径，再按官方平台连接系统存储/驱动；核对复位、符号位、端序、结束信号 | CPU 实际装载 X/W/bias、启动硬件并写回全部99×256结果；12次独立参数任务通过 |
| 官方 SRAM 模型、16位×128/1024/4096宏、时序与接口说明（B，xu 联调） | 用真实宏适配替换行为存储，保留同步读延迟和单端口约束 | 宏仿真与RTL逐位一致；完整SoC写回回归通过 |
| 官方标准单元库、约束、PVT/RC角及工具脚本（B） | 对正式源集综合、时序与面积分析，隔离测试平台行为RAM | 指定工艺下150MHz；增量加速器/接口/内部SRAM面积≤2.25mm²；共享512KB SRAM按赛题口径处理 |
| 官方功耗场景及活动格式（B、xu） | 按官方计时窗口导出活动，覆盖参数装载、CPU、互连、存储和完整写回 | 按官方PVT及完整系统范围出功耗报告；不得只报MAC核心 |
| 真实 checkpoint、可用开发样本、导出脚本与浮点参考（A） | 固定模型/数据/量化版本，逐层比较，保留每样本/层误差；转换为本集成的严格mem格式 | 按赛题口径核算最大层NRMSE≤3%；RTL结果与软件整数模型逐位一致 |
| 官方性能计时起止和评分脚本（xu） | 替换开发TB预装载路径，计入官方要求的装载、CPU、总线、计算、写回 | 12任务各有完整输入身份、起止周期和最终写响应证据 |

官方600样本清单在评测结束后公布，不是当前等待交付的开发材料，也不能作为推进开发的前置条件。当前使用可获得的开发样本、真实 checkpoint 和软件参考完成量化与整数逐位验证，保留输入身份及误差记录；官方评测结果按评测阶段单独确认。

官方平台、库和宏的结论须用相应材料实际验证；Nangate45、行为 SRAM、开发仿真周期和单个静音样本各自保留其验证范围。当前没有向未知官方平台写入数据或猜测宏引脚。

历史服务器准备与离线恢复的证据索引见 [server-prep-20261027](validation/server-prep-20261027/summary.json)。当前服务器验证另存本轮报告，不能混用两次运行身份。

2026-10-27 本轮已完成：主机12/12、原SoC5/5、Chisel11/11；真实12层一键验收与Icarus四态完整单层均通过。离线新目录在GCC13.2及备用xPack GCC15.2下分别构建并通过真实单层，内置12层参考另经独立整数核算。GitHub自动检查也已实际通过。完整两态12层、四态单层及软件精度评估各自的范围保持独立，原始日志和文件哈希随索引保留。
