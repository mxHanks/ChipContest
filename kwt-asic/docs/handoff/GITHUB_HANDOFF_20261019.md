# 给队友的进度说明与GitHub交接清单

日期：2026-10-19（Asia/Shanghai）。本轮只准备交接说明与文件清单，没有执行git commit、push或改写队友仓库。

## 可以直接转发的进度介绍

现在已经把KWT加速器里面的存储从计算核心中拆出来了，原来的FF+MUX版本保留，新增了行为仿真、综合黑盒和官方SRAM的接入边界。当前是双行复用的16个MAC，内部20个逻辑bank，数据容量50.75 KiB，按指定容量形状拼接后是72个存储原语、56.5 KiB。用仓库现有Nangate45参考库综合，最终候选的标准逻辑面积约0.057 mm²，但还不含真实SRAM，不能直接拿它和之前2.16 mm²的FF存储版本比较，也不能据此宣布总面积达标。

功能方面已经不只是构造数据了，真实KWT的12层权重和输入已做过回放，完整99×256矩阵逐位核对通过；软件侧还跑了4445条validation，最大逐层聚合NRMSE约0.01328%。E203这边也已经通过ICB接进去了，CPU实际完成参数装载、启动、读取结果和写回。最新行为基线和开发Adapter各跑完12层、304128个输出，并检查了全部写响应、最后ACK、soft abort和复位恢复。最新CPU对照用的是静音smoke输入，不是官方600样本评测。

后面主要是接真实官方SRAM和确认正式E203平台，再用指定工艺重跑完整时序、总面积和功耗。参考网表已覆盖的setup、hold和reset removal检查目前为正，12层门级零延迟回放也通过了，但宏时序和负载还缺，不能说正式150 MHz已通过。目前代码、测试和重建说明已整理好，可以先交接给队友继续接官方材料；正式性能还需要按装载到全部结果写回的统一窗口重新测量。

依据：[当前状态](../../PROGRESS.md)、[开发CPU重建](../SRAM_CPU_REBUILD.md)、[参考PPA](../../reports/PPA_PRELIMINARY.md)、[数值评估](../optimization/DATASET_EVALUATION.md)。这些是已有运行结论，本轮没有重跑长仿真或EDA。

## 传到哪个仓库、哪个目录

本地核验的主仓库是`https://github.com/mxhanks/ChipContest`，E203是其`third-party/e203_hbirdv2`子模块。本次GitHub网页读取失败，因此不声明远端当前内容与本地快照完全一致。

建议新建交接分支，将当前独立工程放到主仓库的`kwt-asic/`目录：

```text
ChipContest/
  src/main/scala/                 # 队友原Chisel工程保持原样
  third-party/e203_hbirdv2/        # 保留原子模块引用
  kwt-asic/                       # 本次新增的SystemVerilog开发工程
    Makefile
    README.md
    PROGRESS.md
    DECISION.md
    src/rtl/
    soc/
    model/
    sim/
    scripts/
    tests/
    configs/
    env/
    constraints/
    tech/official_sram/README.md
    docs/
    reports/PPA_PRELIMINARY.md
    harness/
    vendor/
```

不要把本项目的`src/`、Makefile、scripts直接覆盖主仓库同名目录，也不要放入主仓库已忽略的`migration-v0.2/`。`kwt-asic`是本次建议的新目录，不表示远端已经建立。

这次无需修改或推送E203子模块。平台接线由`prepare_e203_fusion.py`应用到接收者自己的副本，再由runner生成运行私有替换；准确步骤见`docs/SRAM_CPU_REBUILD.md`。以后若决定将接线正式纳入E203 Fork，另做受控变更：先推E203提交，再更新主仓库gitlink，不能反过来。

## 主要上传什么

逐文件名单是同目录的`GITHUB_FILES_20261019.txt`，每行相对于当前工程根目录，复制后目标前缀统一为`kwt-asic/`。它保留已验开发源码包的目录布局，排除根目录原始ZIP和赛题PDF；这是交接源码清单，不是最终比赛提交清单。

| 内容 | 源路径，也是kwt-asic下的相对目标路径 | 用途 |
|---|---|---|
| 计算候选与旧基线 | `src/rtl/`，重点`kwt_linear_engine_rowpair_sram.sv` | 计算、调度及可回退对照 |
| 存储边界 | `src/rtl/memory/` | 1RW Wrapper、bank拼接、综合Black Box；真实官方Adapter尚未交付 |
| CPU接口与固件 | `soc/` | ICB、寄存器头文件、启动代码、链接脚本、CPU控制程序 |
| 数值真值 | `model/` | 固定点编码、精确计算和Golden |
| 仿真与小向量 | `sim/`，含`sim/vectors/kwt-silence-v1/` | 原语、核心、ICB、SoC及回归输入 |
| 执行与验证入口 | `scripts/`、`tests/`、`Makefile` | 不能只传RTL而漏掉runner、reader、测试和平台准备脚本 |
| 构建配置与说明 | `configs/`、`env/`、`constraints/`、`tech/official_sram/README.md` | 后端选择、136平台源清单、环境及缺料说明 |
| 阅读入口与证据摘要 | `README.md`、`PROGRESS.md`、`DECISION.md`、`docs/`、`reports/PPA_PRELIMINARY.md`、`harness/` | 现状、决策、接口、重建、原始结果的索引；历史PASS不等于接收方已重验 |
| 固定依赖及许可证 | `vendor/kwt1-237e4097/`、`vendor/fpt-r1/`、`vendor/engineering-skills-20261018-r1/` | 模型/向量来源、现有static检查依赖及只读经验引用，不递归编译vendor |

不上传`.tools/`、`.venv*`、`ChipContest/`嵌套仓库、`integration/`平台副本、原始`artifacts/`、大型数据集、波形或本机凭据；未知官方工艺文件也不在本次清单内。参考Nangate库继续从主仓库已有`assets/libs/nangate45/`取得，不额外复制。旧参考综合脚本仍硬编码子项目根下`ChipContest/assets/`，没有库路径CLI选项；本次保留冻结脚本，不声称迁移后`make synth-logic`可直接运行。需要重跑参考综合时，可在新clone的`kwt-asic/`内建立本机忽略的`ChipContest -> ..`目录别名以定位同一份参考库；它不提交到Git，也不代表官方工艺接入。CPU则按重建说明显式传准备后的平台路径。

## 怎么提交（以下命令由提交者执行，本轮未执行）

建议在新的clone里操作，不在当前无有效Git的工作区执行`git init`，也不改队友原checkout。示例新目录必须尚不存在：

```bash
set -eu
kwt_src=/media/leo/Data/Vitis/RISC-V-forward-acceleration
kwt_repo=/tmp/ChipContest-kwt-handoff-20261019
test ! -e "$kwt_repo"
git clone --recurse-submodules https://github.com/mxhanks/ChipContest.git "$kwt_repo"
git -C "$kwt_repo" switch -c feature/kwt-sram-handoff-20261019
mkdir "$kwt_repo/kwt-asic"
rsync -a --files-from="$kwt_src/docs/handoff/GITHUB_FILES_20261019.txt" \
  "$kwt_src/" "$kwt_repo/kwt-asic/"
```

`rsync`若未安装可用Python按同一清单逐文件复制；不要退回整目录`cp -r`把工具和原始运行一起复制。补充新子项目的本机输出忽略规则，只写新clone：

```bash
cat >> "$kwt_repo/kwt-asic/.gitignore" <<'EOF'

# Local development outputs and external platform copies
/artifacts/
/ChipContest/
/integration/
/.venv*/
/tech/official_sram/private/
EOF
cd "$kwt_repo/kwt-asic"
make test
make verify
```

`make test`是主机测试，`make verify`是原导入资料的static完整性检查；二者通过也不能称CPU/EDA在新clone重跑通过。历史harness缺少不随源码上传的原始run时会报告缺证据，不应删检查或改旧PASS。功能复现继续按`docs/SRAM_CPU_REBUILD.md`生成本机原语、核心/ICB、行为CPU和Adapter CPU报告。

确认差异只在`kwt-asic/`，然后暂存、检查并提交分支：

```bash
git -C "$kwt_repo" add -- kwt-asic/
git -C "$kwt_repo" diff --cached --check
git -C "$kwt_repo" diff --cached --stat
git -C "$kwt_repo" status --short
# 应只有kwt-asic/新增，不应出现third-party/e203_hbirdv2的gitlink变化。
git -C "$kwt_repo" commit -m "feat: add SRAM-isolated KWT ASIC development project"
git -C "$kwt_repo" push -u origin feature/kwt-sram-handoff-20261019
```

随后在GitHub用该分支向`main`发PR，队友审查后合入。若没有主仓库写权限，推到自己的Fork再发PR。当前只提供命令，不代表已完成clone、commit、push或PR。

## 队友接手先看什么

先看本文件和`PROGRESS.md`，再看`docs/SRAM_CPU_REBUILD.md`。硬件负责人看`docs/SRAM_AUDIT.md`、`docs/OFFICIAL_SRAM_INTEGRATION.md`；系统负责人看`soc/include/kwt_accel_regs.h`；数值负责人看`docs/design/NUMERIC_CONTRACT.md`与`docs/optimization/DATASET_EVALUATION.md`。旧`soc/README.md`及融合日志含历史状态，不能据此覆盖最新进度。
