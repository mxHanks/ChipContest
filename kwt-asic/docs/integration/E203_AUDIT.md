# 队友 E203 仓库审计

审计日期：2026-10-17。范围：`ChipContest/quickstart.md`、团队 E203 Fork 的 README、版本与源代码、ICB 地址译码、默认仿真入口和 SDK 依赖。本文是只读静态审计；完整仿真由主代理另行运行，本文不将 README 的“已验证”转换为本次运行结论。

## 固定版本与真实进展

| 项目 | 本地核查结果 |
|---|---|
| ChipContest HEAD | `30e737ca37bc7d3077db1877ee89072ac4dfc723` |
| 主仓库记录的 E203 gitlink | `35e7c960dc151d8ade9deffcb30cdc13c840d541` |
| E203 实际 HEAD | 与 gitlink 一致 |
| E203 origin | `https://github.com/mxhanks/e203_hbirdv2.git` |
| E203 upstream remote | 本次 checkout 未配置；README 的推荐配置尚未在本地落实 |
| Fork 最新提交相对父提交 `9f3e34f` | 仅 `README.md` 改动，没有 SoC 或加速器 RTL 修改 |
| 工作树 | 审计开始时两个仓库均无 tracked/untracked 修改 |

因此，团队仓库目前提供了一个固定版本的开源 E203 SoC 参考平台；并没有提供已经接入加速器的 E203 硬件。该结论与 Fork README:20–44 中“自定义从设备待完成、MMIO 待验证、端到端待完成”的描述一致。

核查命令：

```bash
git -C ChipContest rev-parse HEAD
git -C ChipContest ls-tree HEAD third-party/e203_hbirdv2
git -C ChipContest/third-party/e203_hbirdv2 rev-parse HEAD
git -C ChipContest/third-party/e203_hbirdv2 remote -v
git -C ChipContest/third-party/e203_hbirdv2 diff 9f3e34f HEAD --name-status
git -C ChipContest/third-party/e203_hbirdv2 status --short
```

## 目录与职责

| 路径（相对 E203 根目录） | 职责/集成相关性 |
|---|---|
| `rtl/e203/core/` | CPU、配置、ITCM/DTCM 控制、SRAM 连接 |
| `rtl/e203/subsys/e203_subsys_perips.v` | PPI ICB 到 16 路外设的译码/连接；拟用 o15 位于这里 |
| `rtl/e203/fab/sirv_icb1to16_bus.v` | 地址匹配、请求/响应分流、未命中默认错误响应 |
| `rtl/e203/general/` | 通用 FIFO、ICB、RAM 控制等 |
| `rtl/e203/mems/` | ROM 等平台存储器实现 |
| `tb/tb_top.v` | 基础 ISA 测试 TB，直接装载 ITCM 并按固定 PC/x3 判定完成 |
| `vsim/Makefile`、`vsim/bin/run.makefile` | 安装源文件副本、编译、执行测试 |
| `riscv-tools/riscv-tests/isa/generated/` | 预生成的 ISA 测试映像；默认 ADD 可不经过交叉编译直接执行 |
| `doc/source/quick_start/` | 上游仿真、SDK 等入门文档 |

ChipContest 的 `.gitmodules:1–3` 只管理 E203，没有管理 Hbird SDK。审计时 `ChipContest/third-party/` 只有 E203 目录，SDK 需另行取得并固定版本。主仓库 Scala/Chisel 加速器源位于 `ChipContest/src/main/scala/`，不会自动被 E203 的 `vsim` 编译文件集包含。

## 必须修正/补齐的事项

### P1：o15 尚未连接，4 KiB 仅为计划

- `rtl/e203/subsys/e203_subsys_perips.v:402–403` 当前是 `O15_BASE_ADDR=0x10042000`、`O15_BASE_REGION_LSB=3`。实际比较高于 bit 2 的地址位，若启用只覆盖 `0x10042000–0x10042007`，不是注释/README 所说的 4 KiB。
- 同文件 `:745–763` 把 o15 禁用，cmd/rsp 端口均悬空或 tie-off。没有 `accel_icb_slave` 实例。
- `rtl/e203/fab/sirv_icb1to16_bus.v:911–913` 的地址命中还要求 `o15_icb_enable`；`:915–930`、`:1018–1025` 对未命中请求产生 `rsp_err=1`、数据零的默认响应。因此当前 CPU 访问该区域会得到总线错误响应，不会访问到加速器；CPU 软件可能进一步进入异常处理。
- 真实接入需将区域改为 `REGION_LSB=12`（如果最终确认 4 KiB）、启用 o15、接上完整 ICB cmd/rsp，并冻结寄存器协议；不能只修改基地址或 README。

### P1：默认测试的完成判据不能用于 SDK/加速器程序

- `tb/tb_top.v:16` 写死 `PC_WRITE_TOHOST=0x80000086`。
- `:39–44` 统计该提交 PC，`:182` 等待出现 8 次；`:198–221` 以寄存器 x3 是否等于 1 打印 `TEST_PASS` 或 `TEST_FAIL`，然后 `$finish`。
- `:224–227` 超时同样只是打印 `Time Out !!!` 并 `$finish`。
- 这是预生成 RISC-V ISA 测试程序的约定。普通 Hello World 的代码布局、退出位置和 x3 用途不同，即使正确输出字符，也不会自然满足该约定。
- 加速器 E2E 需要独立 TB/固件完成邮箱、错误码、结果检查及超时 `$fatal`；DONE 必须在全部输出已经接收/写回确认后才满足，不应直接复用核心最后一个 MAC 或最后一次 valid。

### P1：Make 返回码不能独立证明测试通过

`vsim/bin/run.makefile:131` 使用 `vvp ... | tee ...`，没有 `pipefail`。同时 TB 的失败和超时都用 `$finish`。因此 `make run_test` 退出 0 既不排除仿真错误，也不排除测试失败或超时。外围运行器必须：保存完整日志和退出码、要求唯一/完整的 `TEST_PASS` 结束摘要，并拒绝 `TEST_FAIL`、`Time Out`、`ERROR`、装载失败、未知值导致的错误。后续专用 TB 应以 `$fatal(1, ...)` 让故障传播到进程退出码。

### P2：安装仿真副本存在重入和陈旧代码风险

- `vsim/Makefile:19–22` 把源码复制到 `install/`；`:29–36` 编译/运行副本，而非直接使用原始 `rtl/`。
- `cp ../rtl/e203 install/rtl -rf` 第一次在目的目录不存在时得到期望布局；再次运行且 `install/rtl` 已存在时会复制为其下的 `e203/` 子目录，同时保留旧副本。随后 `run.makefile:17` 的两级/三级通配符可能同时包含旧代码与新嵌套代码，产生重复模块或误用旧代码。
- 每次可复现入口应在独立工作目录清理后执行一次 `make install`，或改为显式同步目标目录的幂等安装脚本。改源文件后单独执行 `make compile` 不会自动刷新 `install/rtl/`。
- `run.makefile:118` 每次重新编译前向已安装 TB 顶部添加宏定义。长期复用副本会累积定义；隔离 clean/install 可避免。

### P2：quickstart 的 Legacy 路径和依赖不完整

- `quickstart.md:77–100` 使用 `~./ChipContest/third_party`，其中 `~.` 不是通常的主目录写法，且 `third_party` 与实际 `third-party` 不同。该段的重新 clone 官方 E203 也会绕开固定的 Fork gitlink。应按文档开头初始化 submodule，再使用 `ChipContest/third-party/e203_hbirdv2/vsim`。
- `quickstart.md:145–186` 指导另行 clone SDK 和编译 Hello World；SDK 未固定提交，不随 E203 submodule 拉取。本次审计的初始 PATH 中 `riscv-nuclei-elf-gcc`、`riscv64-unknown-elf-gcc` 均未找到，因此不能声称新 C 固件已能构建。
- `gcc-riscv64-unknown-elf` 名称本身不能证明具备所需 RV32 multilib、C 运行库和 SDK 兼容性。须检查 `-print-multi-lib`，实际编译链接指定 RV32 ISA/ILP32 固件；如使用 `NEWLIB=normal`，还须确认对应头文件/库可用。
- 图形工具 GTKWave 只用于人工看波形，`DUMPWAVE=0` 的批量验证无需运行它。

## 启动与存储容量

`tb/tb_top.v:268–280` 直接把 `${TESTCASE}.verilog` 的字节重新组装为 ITCM 的 64-bit 字。这里的仿真装载是测试环境行为，并不证明 CPU 完成了输入/权重搬运。

TB 的 bootrom 管脚固定为 0（`:350`）；`rtl/e203/mems/sirv_mrom.v:44–55` 的 ROM 路径跳至 ITCM。配置 `rtl/e203/core/config.v:42–45,75–76,100` 给出：

| 区域 | 地址/容量 |
|---|---|
| ITCM | `0x80000000` 起，地址宽 16，64 KiB |
| DTCM | `0x90000000` 起，地址宽 16，64 KiB |
| PPI | `0x10000000–0x1fffffff`，配置 `:78–80` |
| 拟用加速器 | `0x10042000`，目前禁用；4 KiB 尚待实现 |

`config.v:58–59` 的 DTCM 16 KiB 注释已经落后于 `:100` 的实际 16 位地址配置，应以宏定义/展开后的 RTL 为准。

单层 X int16、W int16、Bias int40 的逻辑总量分别为 12,672 B、32,768 B、1,280 B，共 46,720 B；完整 99×256 的 48-bit Y 为 152,064 B，若每项用两个 CPU 32-bit 字则为 202,752 B。默认 64 KiB DTCM 装不下完整输出。软件/存储架构必须采用分块写回或经过验证的外部存储接口；不能让仿真 TB 隐藏一个无限容量结果数组后声称实际 SoC 已完成全部写回。

PPI 总线 `e203_subsys_perips.v:346–352` 配置 2 深度缓冲、切断 ready 路径，且只允许 1 outstanding；固件逐字 MMIO 搬运的延迟将成为完整窗口的一部分。仅比较 AI 核心周期不能替代包含 CPU 装载、调度、等待和结果写回的比赛计时。

## 可复现执行入口与验收层次

从本项目环境激活后，基础 E203 测试应按以下顺序运行（主代理执行并另存运行证据）：

```bash
source env/activate.sh
cd ChipContest/third-party/e203_hbirdv2/vsim
make clean
make install
make compile SIM=iverilog
make run_test SIM=iverilog DUMPWAVE=0
```

SDK 获得并固定版本、工具链检查通过后，才继续 quickstart 的：

```bash
cd ChipContest/third-party/hbird-sdk/application/baremetal/helloworld
make CORE=e203 DOWNLOAD=ilm \
  COMPILE_PREFIX=riscv64-unknown-elf- NEWLIB=normal dasm
```

该命令的成功仅证明固件构建。将其 `.verilog` 放入 ISA TB 并运行不能直接产生可靠的程序完成证明，需要前述独立退出协议。

| 验收层 | 本文静态核查后的状态 | 仍需运行证明 |
|---|---|---|
| gitlink 与 Fork 版本一致 | PASS（版本一致） | 主代理在最终 manifest 记录提交及源码哈希 |
| 基础 E203 ADD 测试 | NOT_RUN（本子任务未运行） | 完整日志的结束 PASS、退出码、映像与源码哈希 |
| SDK Hello World | BLOCKED（初始 SDK/编译器缺失） | 实际构建、启动、输出与独立结束判据 |
| CPU→加速器 MMIO | NOT_RUN（接口尚未实现） | 命令/响应背压、wmask、非法访问、复位测试 |
| 真实 12 层位一致 + 完整写回 | NOT_RUN | 固定数据集、金模逐位比较、完整窗口计数 |
| 指定工艺 150 MHz/面积/功耗 | NOT_RUN | 正确的指定库和 SRAM、完整约束、映射后 STA/PPA |

## 融合接口建议（Proposed，不能当作现有实现）

1. 保留团队 Chisel 引擎的行缓存/权重银行实现和本项目独立位精确参考；在统一固定点契约下运行同一套真实 checkpoint 向量。E203 首次接入优先使用已经验证过的引擎，禁止同时修改量化格式、计算调度和总线协议。
2. 新增独立 ICB adapter，不将业务 FSM 塞进官方 CPU 核心。沿用 32-bit 数据与 4-bit wmask，起初采用单 outstanding、响应保持到 rsp_ready 的实现；非法地址/方向/写掩码给确定错误响应。
3. 40-bit Bias 的 CPU 写入要用 staging low32/high8 和一次提交保证原子性；48-bit 结果读出要锁存 low32/high16，完成两个读/显式 ACK 后才 pop，避免半个结果丢失。CPU 的 `volatile` 访问不能替代 RTL 原子性和握手设计。
4. 冻结 start/busy/error/done、输入地址边界、输出索引/last、复位中止和重复启动约束；首次集成不假设总线读写永不阻塞。DONE 以完整写回确认定义。
5. 先用 CPU 实际执行短程序验证寄存器，再做小矩阵/单行，之后完整 99×256 与 12 个独立层任务。新 TB 应覆盖随机请求/响应延迟、忙时写入、提前 start、总线异常、复位与最后输出背压。
6. 使用专门的结果缓冲/块传输协议解决 DTCM 容量；若引入 DMA 或新增 SRAM，面积计入新增硬件，并验证 DMA 的真实总线主设备接入与最后写响应。

## 输入哈希

以下绑定审计时读取的关键文件；后续修改需刷新审计结论：

```text
3a13905e67e1b8f6e8075179a7ddfc64001e0519abbfa35fd9bafc97916ec4b0  ChipContest/quickstart.md
5a316adf8981a8d59ead7f7e2178a39c213f7ff167a7ba0da5b96b9ce83457d3  ChipContest/third-party/e203_hbirdv2/README.md
0fe8e353ff1187e78715a26b8ec40b1bec6f21c8fbc2a6b5aebf061e6b344c6b  ChipContest/third-party/e203_hbirdv2/vsim/Makefile
850e0f129a33ebd598b96458e9bacc3a250d7b8791caa2886043bbaecbcb5674  ChipContest/third-party/e203_hbirdv2/vsim/bin/run.makefile
42f5eaddf7e60acc4dc1b80ac13171e254ef1b8296c26980aeac4be44cf19b20  ChipContest/third-party/e203_hbirdv2/tb/tb_top.v
9a7e4dd76b55e327eb2a81fbce44404b617fc045060a251e0898970ef2ddf1cb  ChipContest/third-party/e203_hbirdv2/rtl/e203/subsys/e203_subsys_perips.v
```
