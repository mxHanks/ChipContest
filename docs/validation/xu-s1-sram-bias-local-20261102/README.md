# xu S1 SRAM bias 独立候选：本地实现与验证（2026-11-02）

本目录记录独立 `codex/xu-s1-sram-bias` 候选，执行主仓提交 `223c416bf05285c935c7164512345643c802187b`，E203 子仓提交 `eee41507965d562066af3335192e3ef93ef36d31`。基线主仓为 `da359af`，基线 E203 为 `f49a5fc914971426bd4530db39e270a84b41139f`。这里只建立本地功能与身份，未决定保留，未声称服务器 VCS、面积、150 MHz 时序、功耗或评分通过。

## Chisel 与接口

新增可维护源 `src/main/scala/linear/BiasSramCache.scala`、`LinearSramCachedCore.scala`；`GenerateRTL.scala` 仅注册两个额外生成入口。默认无参数入口仍是 `LinearComputeCore`，原 `LinearCachedCore` 和 `BiasBankCache` 完全保留。PE、X/W/bias/Y 精确格式仍为 8 PE / signed16 / signed16 / signed40 / signed48；原乘加与权重存储链没有改动。

候选活动层级用 8 份 `SyncReadMem(32, Vec(5, UInt(8.W)))` 替换完整 bias 的寄存器缓存，逻辑容量 256×40 bit，仅当前 8×40 bit tile 保持在寄存器。每 bank 是 masked single-RW 同步存储，写地址为 `{group,lane}`，五个 byte mask 分别控制完整40位。预取优先于写，写优先于 MMIO 读；拒绝的请求必须保持或重试。缓存读返回 valid；禁止/写周期 SRAM 输出不构成有效数据。缓存内容和 tile 不复位，wrapper 复位默认关闭缓存并清空总线事务状态。

一次缓存 START 同时读取所选组的八 bank，下一拍捕获 tile，再向原计算核发一个 START。group/cache 模式随 START 锁定，tile 在 INIT 和整个计算期间保持稳定，后续 MMIO 读回或写入不会替换在途 tile。核心 START→done 测试延迟为旧路径66拍、缓存路径68拍；wrapper busy 固定为每组68/70拍。固定 3,168 个组使缓存路径每任务 busy=221,760，比旧路径215,424多6,336拍。该延迟被 `--bias-storage sram` 的独立精确契约检查，未放宽 MAC、START/done、共享读写、MMIO写数或数值要求；`prefetches`/`extra_busy_cycles` 是契约推导值，busy 是实际观测值。

MMIO 地址与 H1+H2 基线完全相同。CACHE_LO/HI 读先发一个实际同步 SRAM 读，等待其 valid，并锁存40位数据，随后才使 ICB `cmd_ready` 有效。旧响应受阻时不发推测读；响应槽退休后可继续接受命令。读请求、返回、命令接受分别有 pending/available 状态，避免重复读取和重复接受。响应数据/valid在反压时保持。写只在真正 `cmd_valid && cmd_ready` 时生效；START预取期间写命令等待ready。连续结果窗口与旧地址语义保留。

## 原始验证

| 检查 | 实际结果 | 原始记录 |
|---|---|---|
| 最终完整 Chisel 回归 | PASS，12 suites / 15 tests，完整99×256旧核矩阵 | `chisel-final.log` |
| 增强 SRAM component | PASS，全部列/32种mask、组边界、预取/保持写/读仲裁、旧tile稳定 | `chisel-component-extended.log` |
| E203 Python 回归 | PASS，50 tests | `e203-final.log` |
| 数值 Python 回归 | PASS，42 tests | `numeric-tests.log` |
| wrapper 四态 Icarus | PASS，4,990接受=4,990退休；597 SRAM请求=597返回=597缓存读接受 | `wrapper/`、`wrapper-direct/result.json` |
| 旧 ABI 五项实际 Icarus | PASS，add/mmio/compute/multigroup/repeat_x | `legacy5/result.json` |
| RV32 编译 doctor | PASS | `doctor/result.json` |
| 固定真实12层整数独立核算 | PASS，304,128 outputs | `vectors12/result.json` |
| 真实 full-SoC real1，行为 SRAM | PASS，25,344 outputs、50,688退休Y写字 | `real1/result.json` |
| 连续 full-SoC synthetic2，行为 SRAM | PASS，50,688 outputs、101,376退休Y写字；两任务bias不同且无层间复位 | `synthetic2/` |

wrapper 包含随机响应保持、每字节mask/零mask、cache控制复位、START/read和START/write冲突、busy START、旧响应阻塞期间禁止SRAM请求、连续LO/HI读、旧响应同拍退休与新请求，以及精确物理读请求/返回/命令接受计数。最终数相等之外，每拍还检查未获接受命令不能产生额外响应，SRAM读在途最多一笔。component 额外覆盖写跨预取保持，写接受与tile捕获同拍时保留旧tile，以及不同bank写优先于读。

real1 使用 `bias-hw-window / -O2 / both-unroll-no-masks`，本地 GCC 与 Verilator 5.032，完整E203 CPU执行原固件，经共享ICB真实退休输出，不以host计算替代。总窗口1,415,556拍，固件mcycle差1,415,659；3,168 START和done、202,752 MAC有效拍、23,232共享读、50,688共享写、55,720 MMIO写、busy221,760。这个本地周期不能与服务器另一工具链数值直接作收益比较。synthetic2 两层窗口分别为1,415,556和1,415,553拍，每层固定busy221,760，完整工作量与事务契约均通过。加载镜像 SHA256 为 `8d2ff853f5444d0188d5bca63020aa8048ce8a1b29675ef65cdf8b3b40203185`；ELF和仿真二进制SHA见原始JSON。

Host套件实际为 **FAILED：29 tests，27通过、1 ERROR、1 FAIL**（`host-tests.log`）。两项为 S0 固定实现生成器的正向生成与 stale-clock-review 测试；未修改的 `xu_soc_implementation.py` 在其第一道 `FROZEN_E203=f49a5fc` 检查拒绝 S1 的 `eee4150`，因此两项未到达各自预期断言。没有跳过或伪称这两项通过，没有放宽 S0 源冻结，也没有生成S1已资格化的实施/PPA manifest。

## 身份与 SRAM 工艺接口范围

先实际运行无参数默认生成和显式S1生成，再运行 `verify_source_identity.py`。`source-identity-final.json` 记录当前主/子仓提交、全部Chisel源哈希、生成/安装SV哈希和adapter哈希，拒绝脏子仓RTL，并把候选安装文件与子仓HEAD blob逐字节比较。默认生成的10份SV与冻结f49a5fc完全相同；S1生成的13份SV与候选子仓完全相同。子仓相对f49a5fc只改变四个加速器文件：新增 `BiasSramCache.sv`、`LinearSramCachedCore.sv`、`mem_32x40.sv`，以及切换候选和同步握手的 `accel_icb_slave.v`。其余149份RTL（含CPU、SoC、共享/TCM与外设平台树）逐字节相同。源身份脚本检查结果是结构与字节身份，不是综合或等价签核。

`tools/ppa/xu_bias_sram_adapter.sv` 为一份逻辑32×40 bank实例化三份实际 `RAMSP128X16`，八bank的映射基数为24份宏。第三份的高8位不写。实际私有vendor四态Icarus契约已另存[原始5377周期证据](../xu-s1-bias-sram-contract-20261102/README.md)。本地SoC使用生成的行为SRAM，不把vendor四态模型送入Verilator；24只是adapter实例映射基数，尚无本分支 DC/PT 物理实例或PPA结论。

## 复现与完整性

`commands.json` 保留本轮实际命令、输出位置与退出码；SoC各JSON进一步保存工具路径/版本、安装RTL/夹具/固件/runner哈希，日志首行保存实际子进程argv。所有输出必须使用新的不存在目录。身份脚本依赖两次生成的结果；它不会自行重跑Chisel。`evidence-sha256.json` 绑定本目录其他全部文件的原始字节；未提交ELF/仿真二进制、厂商模型或大波形。
