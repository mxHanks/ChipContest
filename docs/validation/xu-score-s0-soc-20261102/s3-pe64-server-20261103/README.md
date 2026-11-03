# xu：64PE 服务器完整五配置 VCS 对照

实际服务器 VCS 验收完成：64PE 全宽 12 层总计 **11,301,600 周期**，比同服务器的物理32PE全宽少 **74,901 周期（0.6583834519945984%）**，比物理8PE自动分组少 **540,600 周期（4.565030146425495%）**。在同一物理64PE RTL 上使用32/8宽调度，逐层周期与相应物理32/8PE控制完全一致。

这是开发平台功能与吞吐证据，**不是完整150MHz、面积、全SoC单任务能耗或比赛评分验收**。64PE 仍未决定保留；不能根据周期较少，直接断言总分更高。

| 物理PE / 固件调度 | layer0 | layer1–11（各层） | 12层合计 |
|---|---:|---:|---:|
| 64 / 64宽自动分组 | 941,800 | 941,800 | 11,301,600 |
| 64 / 32宽自动分组 | 948,039 | 948,042 | 11,376,501 |
| 64 / 8宽自动分组 | 986,850 | 986,850 | 11,842,200 |
| 32 / 32宽自动分组 | 948,039 | 948,042 | 11,376,501 |
| 8 / 8宽自动分组 | 986,850 | 986,850 | 11,842,200 |

`per-layer-comparison.csv` 有全部12行；`per-layer-performance.csv` 有五配置共60行原始 phase / MMIO / SRAM / MAC 计数。每个12层配置都报告 `SOC_PASS tasks=12 outputs=304128 writes=608256`，全部逐层 TASK / PERF / AUTO 与适用的 PE 实际观察记录由冻结 runner 独立重放解析。

## 冻结的代码与硬件变更

- main：`3443fad8945577626d226b1cd53eadec89331a20`，功能分支 `codex/xu-s3-pe64`。
- e203 child：`7aae96776e116d5e95d6ebb49d29a5fccce04ab9`。
- 32PE 对照代码起点：main `94ce6f0f54fffdd590ff9a3ebad0197ec0fd9114`，child `fc3977d0a6d5f85fbfd871fd9439c01c9acab5f5`。

相对上述32PE起点，生产 **Chisel 只改两处**：

1. `src/main/scala/linear/XuParallel64Core.scala`：新增独立 `XuParallel64AutoGroupCore`。一个64-bank W阵列；显式8/32/64 lane mask；对应每行32/8/4组；两个64×48位结果槽；按实际 POP 退休推进；旧 ABI 地址映射和旧8-lane result subgroup 在 capture 时锁定。复用原32PE文件中的参数化 compute / bias / bank 组件，没有编辑原 `XuParallelCore.scala`。
2. `src/main/scala/GenerateRTL.scala`：64PE生成入口改为上述独立 scheduler；32PE入口保持原生成器。

另新增 `src/test/scala/linear/XuParallel64AutoGroupCoreTest.scala` 验证三种宽度的调度与退休。

child 相对32PE起点新增四份64PE generated SV 与 `xu_pe64_icb_slave.v`，并修改 `e203_subsys_perips.v` 和 `run.makefile` 以显式选择 `XU_ACCEL_PE64`。旧8PE、32PE generated 文件保持原字节；本归档未修改这些代码。

设计逻辑 W 仍32KiB，64-bank×256×16位；按指定1024×16宏映射预计物理128KiB、padding96KiB，固定SoC320宏加W64宏预计384宏。这里是源代码与部署配置的几何记录，**没有用它替代真实工艺库面积或宏实例验收**。

`source-files.json` 的完整冻结包含 **2,713条**：main 1,637条（含准确child gitlink），child 1,076个blob；合计2,712个blob，含4条以 symlink target 字符串保存的链接。归档准备和 `replay-full-git.py` 都逐项对不可变 Git object 的 mode、OID、字节数、SHA 做了独立复核。服务器冻结 launcher 在验收前后执行 `verify_sources()`，检查 tracked 路径集合、commit、gitlink、mode、文件类型、字节与 clean status；终态只在末次检查完成后写入。

`frozen-git-sources.tar.xz` 保存242个测量 / 复现源码blob，包括162个实际 measured RTL/TB key、runner、contract、固件、Chisel、direct TB 与固定向量压缩包。其余完整源的本地 Git 复核记录在 `full-git-replay.json`；没有宣称全部2,712个文件字节都包含在此tar。

## 实际工具、工作量与输出

实际 VCS 版本为 **Q-2020.03-SP2-6_Full64**，服务器 SiFive GCC-Metal **10.2.0-2020.12.8**；host GCC/G++ 为4.8.5。每个运行保存版本、工具路径、simulator SHA、firmware ELF / image声明SHA与source / log SHA。五配置的 main、child、全部测量源码、runner、contract、工具、向量、固件源码与编译选项一致；同物理64PE三种调度使用同一个simulator SHA，物理32与物理8分别使用不同simulator SHA。

完整顺序为 direct64/32/8及boundary实际VCS、host68（skip4）、numeric42、固定vectors、doctor实际固件构建、legacy5、synthetic1/2、64全宽real12，再四项完整real12控制。四项skip是服务器没有Icarus的可选辅助路径；三宽度与边界的实际VCS路径是强制项，不能以skip代替。

| 每层实际观察 | 64宽（物理64） | 32宽（物理64/32） | 8宽（物理64/8） |
|---|---:|---:|---:|
| MAC beats | 25,344 | 50,688 | 202,752 |
| starts / dones | 396 / 396 | 792 / 792 | 3,168 / 3,168 |
| W / X / bias shared reads | 16,384 / 6,336 / 512 | 同左 | 同左 |
| 输出word writes | 50,688 | 50,688 | 50,688 |
| MMIO writes | 12,725 | 13,121 | 15,497 |
| 实际 lane MACs（有PE观察器时） | 1,622,016 | 1,622,016 | 物理64兼容8为1,622,016 |

原物理8PE的TB路径没有 `PE_TASK` 记录；其固定8PE工作量由相同已冻结 RTL 与202,752个MAC beats约束，而不是伪造一个实测lane计数。非8PE四种配置的lane MACs由实际enable求和观察，不把64PE兼容32/8误算为所有64 lane同时工作。

direct VCS 两行512 lane结果也完整通过：64/32/8模式分别8/16/64组，15/27/99次launch与done；accepted=retired分别11,031 / 11,131 / 11,731。boundary三模式各14次unknown address读取、一次错误模式请求与一次POP退休；共42次unknown读取、3次mode error。host中再独立跑同组direct VCS日志。

TB对每个共享Y写word按固定顺序用 `!==` 检查48位golden的符号扩展上下32位；累计完整50,688词后等待最终response退休，才接受软件ACK与TASK_PASS，最终还验证firmware gp与完成任务数。每配置12层的304,128个输出均由这份冻结TB在实际VCS中检查。**实际服务器输出值没有逐值打印或下载**，因此离线并未声称重放那些实际Y字节。

另外，离线 checker 从随归档冻结的向量包重新加载48份tensor，独立计算 `XW+b` 的304,128个整数golden输出并匹配原vector报告。这证明固定整数golden一致，不替代前述实际TB比较，更不代替官方600样本浮点精度评测。

64宽每层 `writeback=665478`，约占941,800周期的70.66%；W加载183,502周期。增大PE主要减少compute / control，输出搬运开销仍高。这解释本次64相对32的实测收益较小；不能将PE数量倍率直接换算为吞吐倍率或能耗倍率。

## 首轮失败及修复范围

首轮 `s3-pe64-accept-01` main为 `6f47746a916e14d0bbdcbb799c6338acd5c979a7`，child与本次完全相同；完整状态仍为 **FAIL at host**。direct三模式及boundary已经跑过，但host68在 `test_original_generated_and_chisel_files_remain_frozen` 发生服务器Python3.6 `subprocess(..., text=True)` 的 `TypeError`，`FAILED (errors=1, skipped=4)`。该轮没有进入完整real12，不可当作完整验收或12层性能结果。

`server01-to-02.patch` 是不可变Git两提交间完整原始patch。生产相关修复仅将新增测试及部署producer的 `text=True` 改为 `universal_newlines=True`，bootstrap改用全新的02 source / output / deploy路径，另增三份原失败说明与本地兼容检查证据。没有改Chisel、child RTL、向量、数值或固件。本目录保留首轮36份原件与原兼容源码tar，没有把失败状态覆盖为PASS。

## 原始证据、负测与局限

共保存 **206份原始payload，2,751,275字节**：

- export28选取170份：原transport265,524字节，SHA `b5f00d48912278915a8236e3bcc7b1080e0b3eaa02126539984a8e04b51ea1d7`，原manifest188项。
- export22选取首轮失败36份：原transport807,588字节，SHA `a6dd89390d2ba93c10f5d207e3111833d62bbab96772dee9787d6a7987401d7d`，原manifest142项。

准备时校验两个导出的全部原payload；本目录只包含PE64选取部分，未纳入其他实验。`selected-manifest.json` 记录每个原始日志 / 结果的原字节数与SHA；两个原export manifest原文也保留。未经trim或换行规范化。

实际验证记录：112个声明日志SHA、1,295个measured source SHA吻合；82项实际日志语义破坏全部拒绝，另有210项存储 / 路径破坏拒绝和10项Git byte / mode / OID / duplicate path破坏拒绝，共302项负例。`verification.json`、`storage-tests.json`、`full-git-replay.json` 可重算，`review-receipt.json` 记录检查脚本与派生产物SHA。

当前HF时钟为原开发4ns、LF为66ns，计时起点为第一次共享源读**接受**，终点是最后Y响应退休；TB preload在窗外，没有候选formal clear / 首输入请求协议。服务器simulator、ELF / image及安装向量字节未随导出取回，不能把receipt中的声明SHA说成本地重新哈希。面积、mapped一致性、完整150MHz STA、全SoC能耗与最终保留决定须以同候选独立完成。

## 复现命令

在完整仓库复核原始证据、整数golden和302项负例：

```bash
xu_evidence=docs/validation/xu-score-s0-soc-20261102/s3-pe64-server-20261103
python3 "$xu_evidence/check-evidence.py" --out /tmp/xu-pe64-server-review.json
diff -u "$xu_evidence/verification.json" /tmp/xu-pe64-server-review.json
python3 "$xu_evidence/test-storage-evidence.py" > /tmp/xu-pe64-storage-tests.json
diff -u "$xu_evidence/storage-tests.json" /tmp/xu-pe64-storage-tests.json
python3 "$xu_evidence/replay-full-git.py" \
  --candidate /home/mxhanks/Projects/ChipContest-xu-s3-pe64 > /tmp/xu-pe64-full-git.json
diff -u "$xu_evidence/full-git-replay.json" /tmp/xu-pe64-full-git.json
```

重建部署包必须从上述精确main/child、clean独立功能工作树执行：

```bash
python3 /home/mxhanks/Projects/ChipContest-xu-s3-pe64/tools/scripts/xu_prepare_pe64_deployment.py \
  --root /home/mxhanks/Projects/ChipContest-xu-s3-pe64 --out /absolute/new/xu-pe64-package
```

按新package receipt核验字节与SHA后，上传到服务器新目录，在原SiFive10.2/VCS环境运行完整launcher。`source`、`out`、package目录必须全新，保留旧失败与对照记录：

```bash
python3 /absolute/new/xu-pe64-package/launch.py \
  --previous-source /storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/ChipContest-s3-pe32-01 \
  --source /absolute/new/ChipContest-s3-pe64-repro \
  --out /absolute/new/s3-pe64-accept-repro \
  --cross-prefix /storage2/2026contest/server4/s4_23usr/Desktop/xu-platform-eval-20261101-codex/sifive-rv32-c/bin/riscv64-unknown-elf-
```

launcher包含上述全部direct与十二步验收，包括五种完整12层配置；`--prepare-only`只核checkout，不构成VCS通过。重新构建输出须独立保存SHA、实际工具版本与全新日志，不能回写本目录原件。
