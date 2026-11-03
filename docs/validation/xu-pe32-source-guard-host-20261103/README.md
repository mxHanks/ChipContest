# xu PE32 主仓源码冻结补强

状态：**HOST_MUTATIONS_REJECTED_NOT_EDA**。本补丁仅加强后续 `s3-pe32` PPA 准备的源码身份检查，不修改 Chisel、RTL、固件、工艺库、SDC 或既有服务器 producer，也不产生面积、时序、功耗或资格结论。此前已启动的服务器作业仍使用其原 producer 和原始证据；不能追认其运行时具有本补丁的 guard。

发现的问题是：原 profile 对子仓每个 tracked 文件的实际字节与模式检查完整，但对主仓仅核验 HEAD。主仓 `tests/e203/tb_accel_soc.sv` 被设置 `assume-unchanged` 后，将 `always #2` 改为 `#3` 可以保持普通 `git status --porcelain` 为空，固定 main commit 本身不足以证明实际 TB 未改变。

新增的 `pe32_main_identity` 读取 `--no-replace-objects` 下批准的主仓 `94ce6f0f54fffdd590ff9a3ebad0197ec0fd9114` 对象树，独立于 index flags 校验所有 tracked blob 的实际内容、Git 可执行模式、symlink 类型与链接文本，并拒绝源码父目录被 symlink 重定向。唯一 gitlink 必须为 E203 子仓 `fc3977d0a6d5f85fbfd871fd9439c01c9acab5f5`，实际子仓 HEAD 也必须相同；原子仓的完整对象树、9 文件精确 delta 及逐文件实际字节检查继续执行。

主仓源码冻结还检查普通及被忽略的 untracked 文件：`src/`、`tools/`、`tests/`、`model/` 下的新文件和根目录新增源码后缀都会拒绝。生成物所在 `build/`、`generated/`、`reports/` 等目录不会自动成为源码输入，`__pycache__` 下 `.pyc/.pyo` 缓存不作为新增源码；这些例外不豁免任何 tracked 文件。该规则与原 PPA 代码从已批准路径发现输入的方式对应，不能替代任意外部程序的沙箱。

实际干净候选共核验 **1440 个主仓 tracked entries**（包括唯一 gitlink），主仓对象树为 `a2b41d5e9819a9dddab899eb3a6849723d8850d1`，主仓实际模式与内容 manifest SHA-256 为 `748009146102ecd9391bb9027bb87d9f671c0639d40d9dd0d07812597cb3ad11`。此身份嵌入 `source_profile_identity.main_source_freeze`，随既有 `source_freeze.profile` 被 generate、prepare、verify_prepared 及运行前后检查绑定。

验证证据保存在 `raw/`，逐文件原始 SHA-256 与字节数见 `payload-manifest.json`：

- 10 项新增实际 Git fixture 测试，以及既有 profile / launcher / PPA flow 共 30 项测试，合计 **40 项通过**。覆盖 main pin、gitlink 对象与实际 checkout、额外 gitlink、隐藏内容变化、stage 内容变化、模式、symlink 类型/文本/父目录、replacement objects、普通及 ignored 的 untracked 源码。
- 在实际候选的临时独立 shared clone 中重放 7 类变异：`#2→#3` 加 `assume-unchanged`、`skip-worktree`、可执行模式、同内容 symlink 替换、untracked 工具、ignored TB、main replacement object。全部在 generate 创建输出目录前拒绝；普通 status 为空的情况单独记录。原实际候选只读，前后完整身份一致。
- 原实际候选使用明确标识无效的 HOST dummy DB 重新完成 generate → prepare → verify_prepared，仍为 **352 个宏**、32KiB 逻辑 W、64KiB 物理 W、32KiB padding。没有调用 EDA。
- 与前一工具提交 `ffa34db` 比较，全部 6 个 profile 的 template 和 macro-check Tcl 逐字节相同，clock-contract Tcl 也相同。对实际 PE32 候选，在相同输出路径先后调用旧/新 prepare，`synth.tcl`、`sta.tcl`、`constraints.sdc`、`clock-review.tcl`、`rtl.f` 五个文件逐字节相同，不做路径归一化。

`tests-40.log` 中来自原 host 测试 mock 的 `EXECUTED_NOT_QUALIFIED /tmp/...` 仅是模拟流程输出，不表示执行真实 DC/PT。`positive-implementation.json` 的 DB 路径指向本地 HOST fixture，也不能用于面积或功耗计算。

复现（输出必须为新目录）：

```bash
python3 -m unittest tests.host.test_xu_pe32_main_source_guard \
  tests.host.test_xu_soc_ppa_profiles tests.host.test_xu_soc_pe32_ppa_server \
  tests.host.test_xu_soc_ppa_flow -v
python3 docs/validation/xu-pe32-source-guard-host-20261103/probe.py \
  --candidate /home/mxhanks/Projects/ChipContest-xu-s3-pe32 \
  --out /absolute/new/xu-pe32-source-guard-probe
```
